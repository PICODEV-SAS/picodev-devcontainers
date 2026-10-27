"""Tests of the toolchain images, through tc-docker (the guard): every
example builds, the engines' examples build, the guard holds, the cache hits,
the HTTP service works. Needs the images: `make test` builds them first."""
import base64
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "common"))
import tc  # noqa: E402

TC_DOCKER = ROOT / "tc-docker"
TAG = os.environ.get("TC_TAG", "dev")
# The engines' examples; TC_ENGINES_DIR can point at another checkout.
ENGINES = Path(os.environ.get("TC_ENGINES_DIR", ROOT.parent / "engines"))
# What each family must hand to its engine.
FORMATS = {"avr": {"elf", "hex"}, "arm": {"elf", "bin", "hex"},
           "zephyr": {"elf", "bin", "hex", "map"}, "esp": {"elf", "bin", "hex", "map"}}


ESP32_FLASH = 4 * 2**20


def flash_from_hex(text):
    """The 4 MiB flash image the emulation bench makes of an ESP32 Intel HEX (records 00, 01, 04)."""
    flash, upper = bytearray(b"\xff" * ESP32_FLASH), 0
    for line in text.split():
        rec = bytes.fromhex(line[1:])
        assert line[0] == ":" and sum(rec) & 0xFF == 0, line
        n, addr, kind, data = rec[0], int.from_bytes(rec[1:3], "big"), rec[3], rec[4:-1]
        if kind == 0:
            at = upper + addr
            flash[at:at + n] = data
        elif kind == 4:
            upper = int.from_bytes(data, "big") << 16
        elif kind == 1:
            break
    return bytes(flash)


def image(family):
    return f"picodev-lab-toolchain-{family}:{TAG}"


def build(family, board, src, env=None, args=()):
    proc = subprocess.run([TC_DOCKER, family, board, str(src), *args], capture_output=True,
                          env=dict(os.environ, **(env or {})), timeout=3600)
    try:
        result = json.loads(proc.stdout)
    except ValueError:
        raise AssertionError(f"no JSON result (rc {proc.returncode}): {proc.stderr.decode()[-2000:]}")
    return proc.returncode, result


def examples(base):
    """(example dir, board) for every board.txt under base/*/ (one board per
    line or separated by blanks)."""
    for board_txt in sorted(base.glob("*/board.txt")):
        for board in board_txt.read_text().split():
            yield board_txt.parent, board


def project(files):
    d = Path(tempfile.mkdtemp())
    for name, text in files.items():
        (d / name).write_text(text)
    return d


def make_project(recipe, **files):
    """A make-kind project whose Makefile runs recipe (one shell line per item)."""
    return project({"Makefile": "all:\n" + "".join(f"\t{line}\n" for line in recipe), "main.c": "", **files})


# Build outputs shipped next to the engines' sources: left out, so that the
# test proves a build from source (and make cannot find its target up to date).
PREBUILT = (".elf", ".hex", ".bin", ".map", ".o")


def engine_archive(example):
    """The whole examples/ directory (an example may use ../common), sources only."""
    def keep(info):
        name = Path(info.name)
        if name.suffix in PREBUILT or {"bin", "build"} & set(name.parts):
            return None
        return info
    fh = tempfile.NamedTemporaryFile(suffix=".tar", delete=False)
    with tarfile.open(fileobj=fh, mode="w") as tf:
        tf.add(example.parent, arcname=".", filter=keep)
    fh.close()
    return Path(fh.name)


class ExampleBuilds:
    def check(self, example, board, engine=False):
        kind = tc.detect_kind(example)
        family = tc.family_for(board, kind)
        self.assertIsNotNone(family, f"no image builds {kind} for {board}")
        if engine:
            archive = engine_archive(example)
            try:
                rc, r = build(family, board, archive, args=("--option", f"dir={example.name}"))
            finally:
                archive.unlink()
        else:
            rc, r = build(family, board, example)
        self.assertEqual((rc, r["code"]), (0, "ok"), r["message"] + "\n" + r["log"][-3000:])
        self.assertLessEqual(FORMATS[family], set(r["artifacts"]), r["artifacts"].keys())
        self.assertGreater(r["size"]["text"], 0)
        if family == "esp":
            # The HEX the hub sends gives the emulation bench the same flash image as the merged bin.
            art = {f: base64.b64decode(a["b64"]) for f, a in r["artifacts"].items() if f in ("hex", "bin")}
            self.assertLess(len(art["hex"]), 4 * 2**20)
            self.assertEqual(flash_from_hex(art["hex"].decode()), art["bin"].ljust(ESP32_FLASH, b"\xff"))
        return r


class OurExamples(unittest.TestCase, ExampleBuilds):
    def test_every_example_builds(self):
        found = list(examples(ROOT / "examples"))
        self.assertGreaterEqual(len(found), 16)
        for example, board in found:
            with self.subTest(example=example.name, board=board):
                self.check(example, board)

    def test_out_directory(self):
        with tempfile.TemporaryDirectory() as out:
            rc, _ = build("avr", "arduino-nano", ROOT / "examples/avr-blink", args=("--out", out))
            self.assertEqual(rc, 0)
            names = sorted(p.name for p in Path(out).iterdir())
            self.assertEqual(names, ["build.log", "firmware.elf", "firmware.hex", "firmware.map", "result.json"])
            self.assertTrue(Path(out, "firmware.hex").read_text().startswith(":"))


class EngineExamples(unittest.TestCase, ExampleBuilds):
    def test_engine_examples_build(self):
        found = list(examples_of_engines())
        print(f"\n  engine examples under {ENGINES}: {len(found)}", file=sys.stderr)
        for example, board in found:
            with self.subTest(engine=example.parts[-3], example=example.name, board=board):
                self.check(example, board, engine=True)


def examples_of_engines():
    for examples_dir in sorted(ENGINES.glob("*/examples")):
        yield from examples(examples_dir)


class Guard(unittest.TestCase):
    """The lab's rules, on hostile projects (arm image: make, python3)."""

    def run_make(self, recipe, env=None):
        src = make_project(recipe)
        try:
            return build("arm", "stm32f4-discovery", src, env)
        finally:
            shutil.rmtree(src)

    def test_no_network(self):
        rc, r = self.run_make([
            "python3 -c \"import socket; socket.create_connection(('1.1.1.1', 53), 3)\" "
            "&& echo NET-OPEN || echo NET-BLOCKED",
            "python3 -c \"import socket; socket.getaddrinfo('github.com', 443)\" "
            "&& echo DNS-OPEN || echo DNS-BLOCKED",
            "false"])
        self.assertEqual((rc, r["code"]), (8, "build_failed"))
        self.assertIn("NET-BLOCKED", r["log"])
        self.assertIn("DNS-BLOCKED", r["log"])

    def test_read_only_unprivileged(self):
        rc, r = self.run_make([
            "for d in /opt/tc /etc /usr/bin /cache /; do touch $$d/x 2>/dev/null && echo WROTE $$d; done; true",
            "touch $$HOME/ok && echo HOME-OK",
            "echo UID=$$(id -u)",
            "grep -E '^(CapEff|NoNewPrivs)' /proc/self/status",
            "false"])
        self.assertNotRegex(r["log"], r"(?m)^WROTE")
        self.assertIn("HOME-OK", r["log"])
        self.assertIn("UID=10001", r["log"])
        self.assertRegex(r["log"], r"CapEff:\s+0+\n")
        self.assertRegex(r["log"], r"NoNewPrivs:\s+1")

    def test_timeout(self):
        started = time.monotonic()
        rc, r = self.run_make(["sleep 120"], {"TC_TIMEOUT": "3"})
        self.assertEqual((rc, r["code"]), (9, "timeout"))
        self.assertLess(time.monotonic() - started, 60)

    def test_memory(self):
        rc, r = self.run_make(["python3 -c \"b = b'x' * (1 << 30)\""], {"TC_MEMORY": "256m"})
        self.assertEqual((rc, r["code"]), (10, "out_of_memory"), r["log"])

    def test_processes(self):
        spawn = ("import subprocess\nn = 0\ntry:\n    while n < 1000:\n"
                 "        subprocess.Popen(['sleep', '30'])\n        n += 1\n"
                 "except OSError:\n    pass\nprint('SPAWNED', n)\n")
        src = make_project(["python3 spawn.py", "false"], **{"spawn.py": spawn})
        try:
            rc, r = build("arm", "stm32f4-discovery", src, {"TC_PIDS": "64"})
        finally:
            shutil.rmtree(src)
        spawned = int(r["log"].split("SPAWNED ")[1].split()[0])
        self.assertLess(spawned, 64)

    def test_unsafe_archive(self):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tf:
            info = tarfile.TarInfo("../../etc/evil")
            info.size = 1
            tf.addfile(info, io.BytesIO(b"x"))
        with tempfile.NamedTemporaryFile(suffix=".tar") as fh:
            fh.write(buf.getvalue())
            fh.flush()
            rc, r = build("arm", "stm32f4-discovery", fh.name)
        self.assertEqual((rc, r["code"]), (4, "unsafe_path"))

    def test_archive_too_large(self):
        with tempfile.NamedTemporaryFile(suffix=".tar") as fh:
            fh.write(os.urandom(5 << 20))
            fh.flush()
            rc, r = build("arm", "stm32f4-discovery", fh.name)
        self.assertEqual((rc, r["code"]), (5, "too_large"))

    def test_bad_board(self):
        rc, r = build("arm", "arduino-nano", ROOT / "examples/arm-blink-c")
        self.assertEqual((rc, r["code"]), (6, "bad_board"))


class Cache(unittest.TestCase):
    def test_seed_serves_a_new_project(self):
        """Not one of our examples, yet most objects come from the seed."""
        src = Path(tempfile.mkdtemp()) / "app"
        shutil.copytree(ROOT / "examples/zephyr-hello", src)
        main = src / "src/main.c"
        main.write_text(main.read_text().replace("hello from", "another app on"))
        try:
            rc, r = build("zephyr", "nucleo-g071rb", src)
        finally:
            shutil.rmtree(src.parent)
        self.assertEqual(rc, 0, r["log"][-2000:])
        print(f"\n  zephyr cache: {r['cache']}, {r['duration_ms']} ms", file=sys.stderr)
        self.assertGreater(r["cache"]["remote_storage_hit"], 50)
        self.assertLess(r["cache"]["cache_miss"], r["cache"]["remote_storage_hit"] // 5)


class Service(unittest.TestCase):
    """tc serve on an internal Docker network (no route out), with a token."""

    @classmethod
    def setUpClass(cls):
        cls.name = f"tc-test-{os.getpid()}"
        subprocess.run(["docker", "network", "create", "--internal", cls.name], check=True, capture_output=True)
        subprocess.run(["docker", "run", "-d", "--name", cls.name, "--network", cls.name,
                        "--read-only", "--tmpfs", "/tmp:rw,exec,size=1g", "--cap-drop", "ALL",
                        "--security-opt", "no-new-privileges", "--memory", "2g", "--pids-limit", "256",
                        "-e", "TC_TOKEN=s3cret", image("avr"), "serve"], check=True, capture_output=True)
        time.sleep(1)

    @classmethod
    def tearDownClass(cls):
        subprocess.run(["docker", "rm", "-f", cls.name], capture_output=True)
        subprocess.run(["docker", "network", "rm", cls.name], capture_output=True)

    def request(self, path, src=None, token="s3cret"):
        data = b""
        if src is not None:
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w") as tf:
                tf.add(src, arcname=".")
            data = buf.getvalue()
        client = (
            "import sys, urllib.request, urllib.error\n"
            "body = sys.stdin.buffer.read()\n"
            f"req = urllib.request.Request('http://{self.name}:8080{path}', data=body or None,\n"
            f"    headers={{'Authorization': 'Bearer {token}'}})\n"
            "try:\n    r = urllib.request.urlopen(req, timeout=300); print(r.status); print(r.read().decode())\n"
            "except urllib.error.HTTPError as e:\n    print(e.code); print(e.read().decode())\n")
        proc = subprocess.run(["docker", "run", "--rm", "-i", "--network", self.name, "--entrypoint", "python3",
                               image("avr"), "-c", client], input=data, capture_output=True, timeout=600)
        status, _, body = proc.stdout.decode().partition("\n")
        return int(status), json.loads(body)

    def test_health(self):
        status, body = self.request("/health")
        self.assertEqual(status, 200)
        self.assertEqual(body["family"], "avr")
        self.assertIn("arduino-nano", body["boards"])

    def test_build(self):
        status, body = self.request("/build?board=arduino-nano", ROOT / "examples/avr-blink")
        self.assertEqual((status, body["code"]), (200, "ok"))
        self.assertIn("b64", body["artifacts"]["hex"])

    def test_token(self):
        status, body = self.request("/build?board=arduino-nano", ROOT / "examples/avr-blink", token="wrong")
        self.assertEqual((status, body["code"]), (401, "unauthorized"))

    def test_build_has_no_network(self):
        src = make_project(["python3 -c \"import socket; socket.create_connection(('1.1.1.1', 53), 3)\" "
                            "&& echo NET-OPEN || echo NET-BLOCKED", "false"])
        try:
            status, body = self.request("/build?board=arduino-nano&kind=make", src)
        finally:
            shutil.rmtree(src)
        self.assertEqual((status, body["code"]), (422, "build_failed"))
        self.assertIn("NET-BLOCKED", body["log"])


if __name__ == "__main__":
    unittest.main()
