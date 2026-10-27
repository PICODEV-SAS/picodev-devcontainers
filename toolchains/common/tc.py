#!/usr/bin/env python3
"""tc: the build interface shared by every Picodev toolchain image.

    tc build --board <board> [--option key=value ...] [--src FILE] [--out DIR]
    tc serve [--port 8080]
    tc info

Input: an archive of the sources (tar, tar.gz/xz/bz2 or zip) on stdin or in
--src, a board from boards.json and a few options. Output: one JSON object on
stdout (firmware as base64, memory map, log tail, sizes) or, with --out, the
same files written in DIR. The exit code is stable and matches "code" in the
JSON (see CODES).

The guard that this program enforces itself: archive size, number of files,
extracted size, no path outside the archive (absolute, "..", links, devices),
build time, memory per process, output size. The rest (no network, read-only
root, total memory, CPU, processes) is the container's job: see tc-docker.

Standard library only, so the same file runs in every image and on the host
(the tests import it).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import io
import json
import os
import re
import resource
import shutil
import signal
import stat
import struct
import subprocess
import sys
import tarfile
import threading
import time
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

HERE = Path(__file__).resolve().parent
BOARDS_FILE = Path(os.environ.get("TC_BOARDS", HERE / "boards.json"))
WORK = Path(os.environ.get("TC_WORK", "/tmp/work"))
SEED = Path(os.environ.get("TC_SEED", "/opt/tc/seed"))
VERSIONS_FILE = Path(os.environ.get("TC_VERSIONS", "/opt/tc/versions.json"))

# Stable: callers (the hub, the author MCP, scripts) switch on these.
CODES = {
    "ok": 0,
    "usage": 2,
    "bad_archive": 3,
    "unsafe_path": 4,
    "too_large": 5,
    "bad_board": 6,
    "bad_project": 7,
    "build_failed": 8,
    "timeout": 9,
    "out_of_memory": 10,
    "output_too_large": 11,
    "internal": 12,
    "busy": 13,          # HTTP only
    "unauthorized": 14,  # HTTP only
}
HTTP_STATUS = {"ok": 200, "usage": 400, "too_large": 413, "unauthorized": 401,
               "busy": 503, "internal": 500}

FAMILY_KINDS = {
    "avr": ("arduino", "make", "c"),
    "esp": ("arduino", "idf"),
    "zephyr": ("zephyr",),
    "arm": ("make", "c"),
}
DEFAULT_TIMEOUT = {"avr": 120, "arm": 120, "esp": 900, "zephyr": 600}
SOURCE_SUFFIXES = (".c", ".cpp", ".cc", ".S", ".s")


def limit(name: str, default: int) -> int:
    return int(os.environ.get("TC_" + name, default))


MAX_ARCHIVE_BYTES = limit("MAX_ARCHIVE_BYTES", 4 << 20)
MAX_EXTRACT_BYTES = limit("MAX_EXTRACT_BYTES", 16 << 20)
MAX_FILES = limit("MAX_FILES", 512)
MAX_PATH = limit("MAX_PATH", 200)
MAX_DEPTH = 16
MAX_OUTPUT_BYTES = limit("MAX_OUTPUT_BYTES", 32 << 20)
MAX_LOG_BYTES = limit("MAX_LOG_BYTES", 64 << 10)
MEMORY_MB = limit("MEMORY_MB", 4096)  # address space of each build process

DEFINE_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(=[A-Za-z0-9_.+-]*)?")
BOARD_OPTIONS_RE = re.compile(r"[A-Za-z0-9_]+=[A-Za-z0-9_.]+(,[A-Za-z0-9_]+=[A-Za-z0-9_.]+)*")
SKETCH_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*")


class BuildError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def boards() -> dict:
    return json.loads(BOARDS_FILE.read_text())


def family_for(board: str, kind: str) -> str | None:
    """Which image builds this board and kind (host side: the tests use it)."""
    for family, catalog in boards().items():
        if board in catalog and kind in FAMILY_KINDS[family]:
            return family
    return None


# ---------------------------------------------------------------- archive

def _parts(name: str) -> list[str]:
    if "\x00" in name or "\\" in name or name.startswith("/") or re.match(r"[A-Za-z]:", name):
        raise BuildError("unsafe_path", f"path not allowed: {name!r}")
    parts = [p for p in name.split("/") if p not in ("", ".")]
    if ".." in parts:
        raise BuildError("unsafe_path", f"path outside the archive: {name!r}")
    if len(name) > MAX_PATH or len(parts) > MAX_DEPTH:
        raise BuildError("unsafe_path", f"path too long: {name[:80]!r}")
    return parts


def _members(data: bytes):
    """Yield (name, is_dir, executable, file object or None) for each entry."""
    if data[:4] in (b"PK\x03\x04", b"PK\x05\x06"):
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as exc:
            raise BuildError("bad_archive", f"bad zip: {exc}") from None
        for info in zf.infolist():
            mode = info.external_attr >> 16
            if info.flag_bits & 0x1:
                raise BuildError("bad_archive", "encrypted zip entries are not accepted")
            if stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):  # 0: no type, as many zip tools write
                raise BuildError("unsafe_path", f"links and special files are not accepted: {info.filename!r}")
            if info.is_dir():
                yield info.filename, True, False, None
            else:
                yield info.filename, False, bool(mode & 0o111), zf.open(info)
        return
    try:
        tf = tarfile.open(fileobj=io.BytesIO(data), mode="r:*")
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise BuildError("bad_archive", f"not a tar or zip archive: {exc}") from None
    try:
        for m in tf:
            if m.isdir():
                yield m.name, True, False, None
            elif m.isreg() and not m.issparse():
                yield m.name, False, bool(m.mode & 0o111), tf.extractfile(m)
            else:
                raise BuildError("unsafe_path", f"links and special files are not accepted: {m.name!r}")
    except (tarfile.TarError, EOFError, OSError, zipfile.BadZipFile) as exc:
        raise BuildError("bad_archive", f"broken archive: {exc}") from None


def extract(data: bytes, dest: Path) -> Path:
    """Unpack a source archive under dest, refusing anything that could land
    outside it. Returns the source root (the single top directory, if any)."""
    if len(data) > MAX_ARCHIVE_BYTES:
        raise BuildError("too_large", f"archive over {MAX_ARCHIVE_BYTES} bytes")
    dest.mkdir(parents=True)
    files = total = 0
    for name, is_dir, executable, fh in _members(data):
        parts = _parts(name)
        if not parts:
            continue
        target = dest.joinpath(*parts)
        try:
            if is_dir:
                target.mkdir(parents=True, exist_ok=True)
                continue
            files += 1
            if files > MAX_FILES:
                raise BuildError("too_large", f"more than {MAX_FILES} files")
            target.parent.mkdir(parents=True, exist_ok=True)
            # No link is ever created, so every path stays under dest.
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o755 if executable else 0o644)
            with os.fdopen(fd, "wb") as out:
                while chunk := fh.read(1 << 16):
                    total += len(chunk)
                    if total > MAX_EXTRACT_BYTES:
                        raise BuildError("too_large", f"sources over {MAX_EXTRACT_BYTES} bytes once unpacked")
                    out.write(chunk)
        except (FileExistsError, NotADirectoryError, IsADirectoryError):
            raise BuildError("bad_archive", f"duplicate or conflicting entry: {name!r}") from None
        except (zipfile.BadZipFile, tarfile.TarError, EOFError, OSError) as exc:
            raise BuildError("bad_archive", f"broken archive: {exc}") from None
    if files == 0:
        raise BuildError("bad_project", "the archive holds no file")
    entries = list(dest.iterdir())
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return dest


def detect_kind(src: Path) -> str:
    names = {p.name for p in src.iterdir() if p.is_file()}
    if any(n.endswith(".ino") for n in names):
        return "arduino"
    if {"CMakeLists.txt", "prj.conf"} <= names:
        return "zephyr"
    if "CMakeLists.txt" in names and (src / "main").is_dir():
        return "idf"
    if names & {"Makefile", "makefile", "GNUmakefile"}:
        return "make"
    if any(p.suffix in SOURCE_SUFFIXES for p in src.rglob("*")):
        return "c"
    raise BuildError("bad_project", "no sketch, project or C source found")


# ---------------------------------------------------------------- ELF size

def elf_size(path: Path) -> dict:
    """Berkeley-style text/data/bss of a 32-bit little-endian ELF (AVR, ARM,
    Xtensa, RISC-V), like `size`, without needing each family's binutils."""
    data = path.read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 1 or data[5] != 1:
        return {}
    shoff, = struct.unpack_from("<I", data, 0x20)
    shentsize, shnum = struct.unpack_from("<HH", data, 0x2E)
    text = dat = bss = 0
    for i in range(shnum):
        _, sh_type, flags, _, _, size = struct.unpack_from("<IIIIII", data, shoff + i * shentsize)
        if not flags & 0x2:  # SHF_ALLOC
            continue
        if sh_type == 8:  # SHT_NOBITS
            bss += size
        elif flags & 0x1:  # SHF_WRITE
            dat += size
        else:
            text += size
    return {"text": text, "data": dat, "bss": bss}


# ---------------------------------------------------------------- running

def cpu_jobs() -> int:
    """CPUs this container may use: the cgroup quota when there is one."""
    n = len(os.sched_getaffinity(0))
    try:
        quota, period = Path("/sys/fs/cgroup/cpu.max").read_text().split()
        if quota != "max":
            n = min(n, max(1, -(-int(quota) // int(period))))
    except (OSError, ValueError):
        pass
    return limit("JOBS", n)


def _limits() -> None:
    mem = MEMORY_MB << 20
    resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    fsize = MAX_EXTRACT_BYTES * 64
    resource.setrlimit(resource.RLIMIT_FSIZE, (fsize, fsize))


OOM_MARKS = ("virtual memory exhausted", "out of memory", "cannot allocate memory",
             "std::bad_alloc", "memoryerror", "signal terminated program", "killed signal",
             "] killed", "error 137", "\nkilled\n")


class Runner:
    def __init__(self, log: Path, timeout: int) -> None:
        self.log = log
        self.deadline = time.monotonic() + timeout
        self.timeout = timeout

    def note(self, text: str) -> None:
        with self.log.open("a") as fh:
            fh.write(text + "\n")

    def run(self, cmd: list, cwd: Path, env: dict) -> None:
        self.note("$ " + " ".join(str(c) for c in cmd))
        left = self.deadline - time.monotonic()
        if left <= 0:
            raise BuildError("timeout", f"build over {self.timeout} s")
        with self.log.open("ab") as out:
            try:
                proc = subprocess.Popen([str(c) for c in cmd], cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                        stdout=out, stderr=subprocess.STDOUT,
                                        start_new_session=True, preexec_fn=_limits)
            except OSError as exc:
                raise BuildError("internal", f"cannot run {cmd[0]}: {exc}") from None
            try:
                rc = proc.wait(timeout=left)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
                raise BuildError("timeout", f"build over {self.timeout} s") from None
            finally:
                try:  # leftovers of the build (daemons, background jobs)
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        if rc == 0:
            return
        tail = self.log.read_bytes()[-(16 << 10):].decode(errors="replace").lower()
        if rc in (-signal.SIGKILL, 128 + signal.SIGKILL) or any(m in tail for m in OOM_MARKS):
            raise BuildError("out_of_memory", "a build process ran out of memory")
        raise BuildError("build_failed", f"{Path(str(cmd[0])).name} exited with {rc}")


def load_env_file(path: Path) -> dict:
    env = {}
    if path.is_file():
        for line in path.read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep:
                env[key] = value
    return env


def cache_env() -> dict:
    """Cache between builds. A writable /cache (one volume per tenant, never
    shared: a build could poison it) is used when mounted; otherwise a cache
    in /tmp that lives as long as the container. The seed built into the image
    from our own examples is read-only either way."""
    root = Path(os.environ.get("TC_CACHE", "/cache"))
    if not (root.is_dir() and os.access(root, os.W_OK)):
        root = Path("/tmp/cache")
    (WORK / "tmp" / "ccache").mkdir(parents=True, exist_ok=True)
    env = {
        "CCACHE_DIR": str(root / "ccache"),
        "CCACHE_BASEDIR": str(WORK),
        "CCACHE_NOHASHDIR": "1",
        "CCACHE_TEMPDIR": str(WORK / "tmp" / "ccache"),
        "CCACHE_MAXSIZE": os.environ.get("CCACHE_MAXSIZE", "2G"),
        "ARDUINO_BUILD_CACHE_PATH": str(root / "arduino"),
    }
    if (SEED / "ccache").is_dir() and not os.environ.get("CCACHE_REMOTE_STORAGE"):
        env["CCACHE_REMOTE_STORAGE"] = f"file:{SEED / 'ccache'}|read-only"
    arduino = root / "arduino"
    if not arduino.exists() and (SEED / "arduino").is_dir():
        shutil.copytree(SEED / "arduino", arduino, symlinks=True)
    return env


def ccache_stats(env: dict) -> dict:
    try:
        out = subprocess.run(["ccache", "--print-stats"], env=env, capture_output=True,
                             text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return {}
    keys = ("direct_cache_hit", "preprocessed_cache_hit", "cache_miss",
            "local_storage_hit", "remote_storage_hit")
    stats = {}
    for line in out.splitlines():
        key, _, value = line.partition("\t")
        if key in keys:
            stats[key] = int(value)
    return stats


# ---------------------------------------------------------------- builders

class Ctx:
    def __init__(self, family, board, spec, kind, src, build, options, runner, env):
        self.family, self.board, self.spec, self.kind = family, board, spec, kind
        self.src, self.build, self.options, self.runner, self.env = src, build, options, runner, env
        self.jobs = cpu_jobs()

    @property
    def defines(self) -> list[str]:
        return ["-D" + d for d in self.options.get("define", [])]


def build_arduino(ctx: Ctx) -> dict:
    inos = sorted(ctx.src.glob("*.ino"))
    main = inos[0] if len(inos) == 1 else next((p for p in inos if p.stem == "sketch"), None)
    if main is None:
        raise BuildError("bad_project", "several .ino files: name the main one sketch.ino")
    if not SKETCH_RE.fullmatch(main.stem):
        raise BuildError("bad_project", f"sketch name not accepted: {main.name!r}")
    # arduino-cli wants the sketch in a directory of the same name.
    sketch = WORK / "sketch" / main.stem
    sketch.parent.mkdir()
    ctx.src.rename(sketch)
    fqbn = ctx.spec["fqbn"]
    if ctx.options.get("board_options"):  # after the board's own menu options, if any
        fqbn += ("," if fqbn.count(":") == 3 else ":") + ctx.options["board_options"]
    props = []
    if ctx.defines:
        flags = " ".join(ctx.defines)
        props += ["--build-property", f"compiler.c.extra_flags={flags}",
                  "--build-property", f"compiler.cpp.extra_flags={flags}"]
    if ctx.family == "avr":
        props += ["--build-property", f"compiler.c.elf.extra_flags=-Wl,-Map,{ctx.build}/{main.name}.map"]
    ctx.runner.run(["arduino-cli", "compile", "--fqbn", fqbn, "--build-path", ctx.build,
                    "--jobs", ctx.jobs, "--warnings", "default", *props, sketch], WORK, ctx.env)
    out = {"elf": ctx.build / f"{main.name}.elf", "map": ctx.build / f"{main.name}.map"}
    if ctx.family == "avr":
        out["hex"] = ctx.build / f"{main.name}.hex"
    else:  # the full flash image (bootloader, partitions, app): what QEMU boots
        out["bin"] = ctx.build / f"{main.name}.merged.bin"
    return out


def _gcc_flags(ctx: Ctx) -> tuple[str, list, list]:
    """Compiler prefix, flags and extra sources of the default recipe."""
    spec = ctx.spec
    if ctx.family == "avr":
        return "avr-", [f"-mmcu={spec['mcu']}", f"-DF_CPU={spec['f_cpu']}UL", "-Os"], []
    cmsis = Path(os.environ.get("CMSIS_PATH", "/opt/cmsis"))
    device = Path(os.environ.get("STM32CUBE_PATH", "/opt/stm32cube")) / spec["series"] / "cmsis-device"
    names = {p.name for p in ctx.src.rglob("*")}
    extra = []
    if not any(n.startswith("startup_") for n in names):
        extra.append(device / "Source/Templates/gcc" / spec["startup"])
    system = f"system_stm32{spec['series']}xx.c"
    if system not in names:
        extra.append(device / "Source/Templates" / system)
    lds = sorted(ctx.src.rglob("*.ld"))
    if len(lds) == 1:
        script = lds[0]
    else:
        script = WORK / "board.ld"
        script.write_text(
            "MEMORY {\n"
            f"  FLASH (rx) : ORIGIN = {spec['flash'][0]}, LENGTH = {spec['flash'][1]}\n"
            f"  RAM (rwx) : ORIGIN = {spec['ram'][0]}, LENGTH = {spec['ram'][1]}\n"
            "}\nINCLUDE cortex-m.ld\n")
    flags = [*spec["cpu"], "-mthumb", "-Os", "-g", f"-D{spec['device']}",
             "-I", cmsis / "CMSIS/Core/Include", "-I", device / "Include",
             "-T", script, "-L", Path(os.environ.get("TC_ARM_LD", "/opt/tc/arm")),
             "--specs=nano.specs", "--specs=nosys.specs"]
    return "arm-none-eabi-", flags, extra


def _objcopy(ctx: Ctx, prefix: str, elf: Path, out: dict) -> None:
    hex_ = out.get("hex") or elf.with_suffix(".hex")
    if not hex_.exists():
        ctx.runner.run([prefix + "objcopy", "-O", "ihex", "-R", ".eeprom", elf, hex_], WORK, ctx.env)
    out["hex"] = hex_
    if ctx.family == "arm":
        bin_ = out.get("bin") or elf.with_suffix(".bin")
        if not bin_.exists():
            ctx.runner.run([prefix + "objcopy", "-O", "binary", elf, bin_], WORK, ctx.env)
        out["bin"] = bin_


def build_c(ctx: Ctx) -> dict:
    prefix, flags, extra = _gcc_flags(ctx)
    sources = sorted(p for p in ctx.src.rglob("*") if p.is_file() and p.suffix in SOURCE_SUFFIXES)
    elf, map_ = ctx.build / "firmware.elf", ctx.build / "firmware.map"
    ctx.runner.run([prefix + "gcc", *flags, "-Wall", "-ffunction-sections", "-fdata-sections",
                    *ctx.defines, "-I", ctx.src, *sources, *extra, "-o", elf,
                    f"-Wl,-Map={map_}", "-Wl,--gc-sections"], ctx.src, ctx.env)
    out = {"elf": elf, "map": map_}
    _objcopy(ctx, prefix, elf, out)
    return out


def build_make(ctx: Ctx) -> dict:
    prefix, _, _ = _gcc_flags(ctx)
    env = dict(ctx.env, TC_BOARD=ctx.board, TC_DEFINES=" ".join(ctx.defines),
               CROSS_COMPILE=prefix, **{k.upper(): str(v) for k, v in ctx.spec.items()
                                         if isinstance(v, (str, int))})
    started = time.time()
    ctx.runner.run(["make", f"-j{ctx.jobs}"], ctx.src, env)
    # The .elf that make wrote (not one shipped in the archive): firmware.elf, or the only one.
    elves = sorted(p for p in ctx.src.rglob("*.elf") if p.stat().st_mtime >= started - 1)
    named = [p for p in elves if p.name == "firmware.elf"]
    if len(named) == 1:
        elves = named
    if len(elves) != 1:
        raise BuildError("bad_project", "make must write firmware.elf or exactly one .elf, "
                         f"wrote {', '.join(p.name for p in elves) or 'none'}")
    elf = elves[0]
    out = {"elf": elf}
    for fmt in ("map", "hex", "bin"):
        if elf.with_suffix("." + fmt).exists():
            out[fmt] = elf.with_suffix("." + fmt)
    _objcopy(ctx, prefix, elf, out)
    return out


def build_idf(ctx: Ctx) -> dict:
    env = dict(ctx.env, IDF_CCACHE_ENABLE="1")
    # The component manager writes a lock under IDF_TOOLS_PATH; the image links it here.
    Path("/tmp/idf-root-managed").mkdir(exist_ok=True)
    target = ctx.spec["idf_target"]
    ctx.runner.run(["idf.py", "-C", ctx.src, "-B", ctx.build, f"-DIDF_TARGET={target}",
                    f"-DSDKCONFIG={ctx.build / 'sdkconfig'}", "build"], WORK, env)
    desc = json.loads((ctx.build / "project_description.json").read_text())
    elf = ctx.build / desc["app_elf"]
    merged = ctx.build / "merged.bin"
    ctx.runner.run(["esptool.py", "--chip", target, "merge_bin", "-o", merged, "@flash_args"],
                   ctx.build, env)
    return {"elf": elf, "bin": merged, "map": elf.with_suffix(".map")}


def build_zephyr(ctx: Ctx) -> dict:
    ctx.runner.run(["cmake", "-GNinja", "-S", ctx.src, "-B", ctx.build,
                    f"-DBOARD={ctx.spec['zephyr_board']}"], WORK, ctx.env)
    ctx.runner.run(["ninja", "-C", ctx.build, f"-j{ctx.jobs}"], WORK, ctx.env)
    z = ctx.build / "zephyr"
    return {fmt: z / f"zephyr.{fmt}" for fmt in ("elf", "bin", "hex", "map")}


BUILDERS = {"arduino": build_arduino, "c": build_c, "make": build_make,
            "idf": build_idf, "zephyr": build_zephyr}


# ---------------------------------------------------------------- build

def parse_options(pairs: list[str]) -> dict:
    options: dict = {"define": []}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep:
            raise BuildError("usage", f"option must be key=value: {pair!r}")
        if key == "define":
            if not DEFINE_RE.fullmatch(value):
                raise BuildError("usage", f"define not accepted: {value!r}")
            options["define"].append(value)
        elif key == "board_options":
            if not BOARD_OPTIONS_RE.fullmatch(value):
                raise BuildError("usage", f"board_options not accepted: {value!r}")
            options[key] = value
        elif key == "kind":
            options[key] = value
        elif key == "dir":  # the project is a subdirectory of the archive (it may use ../common)
            options[key] = "/".join(_parts(value))
        else:
            raise BuildError("usage", f"unknown option: {key!r}")
    return options


def versions() -> dict:
    try:
        return json.loads(VERSIONS_FILE.read_text())
    except (OSError, ValueError):
        return {}


def build(data: bytes, board: str, option_pairs: list[str]) -> tuple[dict, dict]:
    """Run one build. Returns (result, artifacts as {format: path})."""
    family = os.environ.get("TC_FAMILY", "")
    result = {"v": 0, "ok": False, "code": "internal", "message": "", "family": family,
              "board": board, "kind": None, "image": os.environ.get("TC_IMAGE", ""),
              "toolchain": versions(), "duration_ms": 0, "jobs": None,
              "size": {}, "cache": {}, "peak_memory_mb": None, "artifacts": {}, "log": ""}
    started = time.monotonic()
    log = WORK / "build.log"
    artifacts: dict = {}
    try:
        if WORK.exists():
            shutil.rmtree(WORK)
        WORK.mkdir(parents=True)
        log.touch()
        if family not in FAMILY_KINDS:
            raise BuildError("internal", "TC_FAMILY is not set: run tc inside a toolchain image")
        spec = boards()[family].get(board)
        if spec is None:
            raise BuildError("bad_board", f"board {board!r} is not built by the {family} image "
                             f"(boards: {', '.join(boards()[family])})")
        options = parse_options(option_pairs)
        src = extract(data, WORK / "in")
        if src != WORK / "src":  # a stable path, so that the cache hits
            src.rename(WORK / "src")
            src = WORK / "src"
        if options.get("dir"):
            src = src / options["dir"]
            if not src.is_dir():
                raise BuildError("bad_project", f"no directory {options['dir']!r} in the archive")
        kind = options.get("kind") or detect_kind(src)
        result["kind"] = kind
        if kind not in FAMILY_KINDS[family]:
            raise BuildError("bad_project", f"the {family} image builds {', '.join(FAMILY_KINDS[family])}, "
                             f"not {kind!r}")
        if options["define"] and kind in ("idf", "zephyr"):
            raise BuildError("usage", f"define is not supported for {kind} (use the project's config)")
        # /opt/tc/env: what the image computed at build time (export.sh of ESP-IDF, Zephyr modules)
        env = dict(os.environ, **load_env_file(Path("/opt/tc/env")),
                   HOME=str(WORK / "home"), TMPDIR=str(WORK / "tmp"),
                   PYTHONDONTWRITEBYTECODE="1", **cache_env())
        (WORK / "home").mkdir()
        runner = Runner(log, limit("TIMEOUT", DEFAULT_TIMEOUT[family]))
        ctx = Ctx(family, board, spec, kind, src, WORK / "build", options, runner, env)
        result["jobs"] = ctx.jobs
        ctx.build.mkdir()
        if shutil.which("ccache"):
            subprocess.run(["ccache", "-z"], env=env, capture_output=True)
        artifacts = {k: v for k, v in BUILDERS[kind](ctx).items() if v.exists()}
        if shutil.which("ccache"):
            result["cache"] = ccache_stats(env)
        if "elf" not in artifacts:
            raise BuildError("build_failed", "the build left no ELF file")
        if sum(p.stat().st_size for p in artifacts.values()) > MAX_OUTPUT_BYTES:
            raise BuildError("output_too_large", f"output over {MAX_OUTPUT_BYTES} bytes")
        result["size"] = elf_size(artifacts["elf"])
        result.update(ok=True, code="ok", message="built")
    except BuildError as exc:
        result.update(code=exc.code, message=exc.message)
        artifacts = {}
    except Exception as exc:  # report, never a traceback on stdout
        result.update(code="internal", message=f"{type(exc).__name__}: {exc}")
        artifacts = {}
    result["duration_ms"] = int((time.monotonic() - started) * 1000)
    try:  # the container's cgroup: the peak of the whole build, for the image labels
        result["peak_memory_mb"] = int(Path("/sys/fs/cgroup/memory.peak").read_text()) >> 20
    except (OSError, ValueError):
        pass
    if log.exists():
        result["log"] = log.read_bytes()[-MAX_LOG_BYTES:].decode(errors="replace")
    for fmt, path in artifacts.items():
        result["artifacts"][fmt] = {"name": path.name, "size": path.stat().st_size,
                                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return result, artifacts


def cmd_build(args) -> int:
    try:  # the visitor's sources go with the build, not at the next one, whatever fails on the way
        data = Path(args.src).read_bytes() if args.src not in (None, "-") else \
            sys.stdin.buffer.read(MAX_ARCHIVE_BYTES + 1)
        result, artifacts = build(data, args.board, args.option)
        if args.out:
            out = Path(args.out)
            out.mkdir(parents=True, exist_ok=True)
            for fmt, path in artifacts.items():
                shutil.copyfile(path, out / f"firmware.{fmt}")
            (out / "build.log").write_text(result["log"])
            (out / "result.json").write_text(json.dumps(result, indent=1))
        else:
            for fmt, path in artifacts.items():
                result["artifacts"][fmt]["b64"] = base64.b64encode(path.read_bytes()).decode()
        json.dump(result, sys.stdout)
        sys.stdout.write("\n")
        return CODES[result["code"]]
    finally:
        shutil.rmtree(WORK, ignore_errors=True)


def cmd_prewarm(args) -> int:
    """Build our own examples at image build time; with CCACHE_REMOTE_STORAGE
    pointed at the seed, their objects become the read-only cache seed."""
    family = os.environ.get("TC_FAMILY", "")
    built = 0
    for board_txt in sorted(Path(args.examples).glob("*/board.txt")):
        example = board_txt.parent
        kind = detect_kind(example)
        for board in board_txt.read_text().split():
            if family_for(board, kind) != family:
                continue
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w") as tf:
                tf.add(example, arcname=".")
            result, _ = build(buf.getvalue(), board, [])
            print(f"prewarm {example.name} {board}: {result['code']} {result['duration_ms']} ms",
                  file=sys.stderr)
            if not result["ok"]:
                print(result["log"], file=sys.stderr)
                return CODES[result["code"]]
            built += 1
    arduino = Path("/tmp/cache/arduino")
    if arduino.is_dir():
        shutil.copytree(arduino, SEED / "arduino", symlinks=True, dirs_exist_ok=True)
    print(f"prewarm: {built} builds", file=sys.stderr)
    return 0 if built else CODES["bad_project"]


# ---------------------------------------------------------------- serve

def info() -> dict:
    family = os.environ.get("TC_FAMILY", "")
    return {"family": family, "image": os.environ.get("TC_IMAGE", ""), "toolchain": versions(),
            "boards": sorted(boards().get(family, {})), "kinds": list(FAMILY_KINDS.get(family, ())),
            "codes": CODES}


class Service:
    """One build at a time (each in its own process), a few waiting."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.slot = threading.Semaphore(1)
        self.waiting = 0
        self.queue = limit("QUEUE", 4)
        self.token = os.environ.get("TC_TOKEN", "")


def make_handler(service: Service):
    class Handler(BaseHTTPRequestHandler):
        server_version = "tc"
        sys_version = ""

        def log_message(self, *args) -> None:  # no access log
            pass

        def reply(self, status: int, body: dict | bytes) -> None:
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def refuse(self, code: str, message: str) -> None:
            self.reply(HTTP_STATUS.get(code, 422), {"v": 0, "ok": False, "code": code, "message": message})

        def authorized(self) -> bool:
            if not service.token:
                return True
            given = self.headers.get("Authorization", "")
            return hmac.compare_digest(given.encode(), f"Bearer {service.token}".encode())

        def do_GET(self) -> None:
            if urlsplit(self.path).path == "/health":
                return self.reply(200, dict(info(), ok=True))
            self.refuse("usage", "GET /health or POST /build")

        def do_POST(self) -> None:
            url = urlsplit(self.path)
            if url.path != "/build":
                return self.refuse("usage", "POST /build?board=<board>[&kind=..][&define=..]")
            if not self.authorized():
                return self.refuse("unauthorized", "missing or wrong token")
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                return self.refuse("usage", "Content-Length is required")
            if length > MAX_ARCHIVE_BYTES:
                return self.refuse("too_large", f"archive over {MAX_ARCHIVE_BYTES} bytes")
            body = self.rfile.read(length)
            query = parse_qsl(url.query)
            board = next((v for k, v in query if k == "board"), "")
            options = [f"{k}={v}" for k, v in query if k != "board"]
            with service.lock:
                if service.waiting >= service.queue:
                    return self.refuse("busy", "too many builds waiting, retry later")
                service.waiting += 1
            try:
                with service.slot:
                    proc = subprocess.run(
                        [sys.executable, __file__, "build", "--board", board,
                         *[a for o in options for a in ("--option", o)]],
                        input=body, capture_output=True)
            finally:
                with service.lock:
                    service.waiting -= 1
            try:
                code = json.loads(proc.stdout)["code"]
            except (ValueError, KeyError):
                return self.refuse("internal", "the build gave no result")
            self.reply(HTTP_STATUS.get(code, 422), proc.stdout)

    return Handler


def cmd_serve(args) -> int:
    server = ThreadingHTTPServer((args.host, args.port), make_handler(Service()))
    print(f"tc: serving {os.environ.get('TC_FAMILY', '?')} on {args.host}:{args.port}", file=sys.stderr)
    server.serve_forever()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tc", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="build an archive of sources")
    b.add_argument("--board", required=True)
    b.add_argument("--option", action="append", default=[], metavar="KEY=VALUE",
                   help="kind=arduino|idf|zephyr|make|c, define=NAME[=VALUE], board_options=a=b,c=d")
    b.add_argument("--src", help="archive file (default: stdin)")
    b.add_argument("--out", help="write firmware.*, build.log, result.json here instead of base64")
    s = sub.add_parser("serve", help="HTTP service: POST /build, GET /health")
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int, default=8080)
    sub.add_parser("info", help="family, versions, boards, codes")
    p = sub.add_parser("prewarm", help="image build only: build the examples into the cache seed")
    p.add_argument("examples")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return CODES["usage"] if exc.code else 0
    if args.cmd == "build":
        return cmd_build(args)
    if args.cmd == "serve":
        return cmd_serve(args)
    if args.cmd == "prewarm":
        return cmd_prewarm(args)
    json.dump(info(), sys.stdout, indent=1)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
