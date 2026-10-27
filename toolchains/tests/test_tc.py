"""Unit tests of tc.py, without Docker: the archive guard, the options, the
kinds, the runner's limits, the ELF sizes."""
import argparse
import contextlib
import io
import os
import struct
import sys
import tarfile
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
import tc  # noqa: E402


def tar_bytes(entries, mode="w"):
    """entries: list of (name, data | None for a dir | TarInfo factory)."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode=mode) as tf:
        for name, data in entries:
            if callable(data):
                tf.addfile(data(name))
                continue
            info = tarfile.TarInfo(name)
            if data is None:
                info.type = tarfile.DIRTYPE
                tf.addfile(info)
            else:
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def zip_bytes(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries:
            if isinstance(data, zipfile.ZipInfo):
                zf.writestr(data, b"target")
            else:
                zf.writestr(name, data)
    return buf.getvalue()


def link(kind):
    def make(name):
        info = tarfile.TarInfo(name)
        info.type = kind
        info.linkname = "/etc/passwd"
        return info
    return make


class Extract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dest = Path(self.tmp.name) / "in"

    def tearDown(self):
        self.tmp.cleanup()

    def refused(self, data, code):
        dest = Path(tempfile.mkdtemp(dir=self.tmp.name)) / "in"
        with self.assertRaises(tc.BuildError) as cm:
            tc.extract(data, dest)
        self.assertEqual(cm.exception.code, code, cm.exception.message)
        self.assertFalse((Path(self.tmp.name) / "evil").exists())

    def test_plain_tar_and_top_dir_stripped(self):
        root = tc.extract(tar_bytes([("proj/", None), ("proj/main.c", b"int main(){}"),
                                     ("proj/inc/a.h", b"")]), self.dest)
        self.assertEqual(root, self.dest / "proj")
        self.assertEqual((root / "main.c").read_bytes(), b"int main(){}")

    def test_flat_tar_gz_and_zip(self):
        for data in (tar_bytes([("a.c", b"x"), ("b.c", b"y")], "w:gz"),
                     zip_bytes([("a.c", b"x"), ("sub/b.c", b"y")])):
            dest = self.dest.with_name(f"in{len(data)}")
            self.assertEqual(tc.extract(data, dest), dest)
            self.assertEqual((dest / "a.c").read_bytes(), b"x")

    def test_parent_path(self):
        self.refused(tar_bytes([("../evil", b"x")]), "unsafe_path")
        self.refused(tar_bytes([("a/../../evil", b"x")]), "unsafe_path")
        self.refused(zip_bytes([("../evil", b"x")]), "unsafe_path")

    def test_absolute_and_windows_paths(self):
        self.refused(tar_bytes([("/tmp/evil", b"x")]), "unsafe_path")
        self.refused(zip_bytes([("C:/evil", b"x")]), "unsafe_path")
        self.refused(zip_bytes([("..\\evil", b"x")]), "unsafe_path")

    def test_links_and_devices(self):
        self.refused(tar_bytes([("l", link(tarfile.SYMTYPE))]), "unsafe_path")
        self.refused(tar_bytes([("l", link(tarfile.LNKTYPE))]), "unsafe_path")
        self.refused(tar_bytes([("d", link(tarfile.CHRTYPE))]), "unsafe_path")
        self.refused(tar_bytes([("f", link(tarfile.FIFOTYPE))]), "unsafe_path")
        info = zipfile.ZipInfo("l")
        info.external_attr = (0o120777 << 16)
        self.refused(zip_bytes([("l", info)]), "unsafe_path")

    def test_symlink_then_write_through_it(self):
        self.refused(tar_bytes([("d", link(tarfile.SYMTYPE)), ("d/evil", b"x")]), "unsafe_path")

    def test_sizes(self):
        old = tc.MAX_FILES, tc.MAX_EXTRACT_BYTES, tc.MAX_ARCHIVE_BYTES
        try:
            tc.MAX_FILES = 3
            self.refused(tar_bytes([(f"{i}.c", b"") for i in range(4)]), "too_large")
            tc.MAX_EXTRACT_BYTES = 1 << 20  # a small zip that unpacks to 8 MiB
            self.refused(zip_bytes([("zeros.c", bytes(8 << 20))]), "too_large")
            tc.MAX_ARCHIVE_BYTES = 100
            self.refused(b"x" * 101, "too_large")
        finally:
            tc.MAX_FILES, tc.MAX_EXTRACT_BYTES, tc.MAX_ARCHIVE_BYTES = old

    def test_long_path(self):
        self.refused(tar_bytes([("a/" * 20 + "x.c", b"")]), "unsafe_path")
        self.refused(tar_bytes([("x" * 250, b"")]), "unsafe_path")

    def test_garbage_empty_duplicate(self):
        self.refused(b"not an archive at all" * 50, "bad_archive")
        self.refused(tar_bytes([("dir/", None)]), "bad_project")
        self.refused(tar_bytes([("a.c", b"x"), ("a.c", b"y")]), "bad_archive")
        self.refused(tar_bytes([("a", b"x"), ("a/b.c", b"y")]), "bad_archive")


class Kinds(unittest.TestCase):
    def kind(self, files):
        with tempfile.TemporaryDirectory() as d:
            for name in files:
                p = Path(d) / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("")
            return tc.detect_kind(Path(d))

    def test_detect(self):
        self.assertEqual(self.kind(["blink.ino"]), "arduino")
        self.assertEqual(self.kind(["CMakeLists.txt", "prj.conf", "src/main.c"]), "zephyr")
        self.assertEqual(self.kind(["CMakeLists.txt", "main/main.c"]), "idf")
        self.assertEqual(self.kind(["Makefile", "main.c"]), "make")
        self.assertEqual(self.kind(["src/main.c"]), "c")
        with self.assertRaises(tc.BuildError):
            self.kind(["README.md"])

    def test_family_for(self):
        self.assertEqual(tc.family_for("nucleo-g071rb", "zephyr"), "zephyr")
        self.assertEqual(tc.family_for("nucleo-g071rb", "c"), "arm")
        self.assertEqual(tc.family_for("arduino-nano", "arduino"), "avr")
        self.assertEqual(tc.family_for("esp32-c3-devkitm-1", "arduino"), "esp")
        self.assertIsNone(tc.family_for("arduino-nano", "zephyr"))


class Options(unittest.TestCase):
    def test_accepted(self):
        o = tc.parse_options(["define=LED=13", "define=DEBUG", "kind=c", "board_options=cpu=atmega328old"])
        self.assertEqual(o["define"], ["LED=13", "DEBUG"])

    def test_dir(self):
        self.assertEqual(tc.parse_options(["dir=./a//b/"])["dir"], "a/b")
        for bad in ("dir=../x", "dir=/etc"):
            with self.assertRaises(tc.BuildError) as cm:
                tc.parse_options([bad])
            self.assertEqual(cm.exception.code, "unsafe_path")

    def test_refused(self):
        for bad in ("define=X -o/etc/passwd", "define=X=$(id)", "define=-fplugin=x", "board_options=a=b;c",
                    "unknown=1", "kind"):
            with self.assertRaises(tc.BuildError, msg=bad) as cm:
                tc.parse_options([bad])
            self.assertEqual(cm.exception.code, "usage")


class Runner(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = Path(self.tmp.name) / "log"
        self.log.touch()

    def tearDown(self):
        self.tmp.cleanup()

    def code(self, cmd, timeout=30):
        try:
            tc.Runner(self.log, timeout).run(cmd, Path(self.tmp.name), dict(os.environ))
        except tc.BuildError as exc:
            return exc.code
        return "ok"

    def test_ok_and_failure(self):
        self.assertEqual(self.code(["true"]), "ok")
        self.assertEqual(self.code(["false"]), "build_failed")

    def test_timeout_kills_the_whole_group(self):
        marker = Path(self.tmp.name) / "alive"
        started = time.monotonic()
        code = self.code(["sh", "-c", f"(sleep 3; touch {marker}) & sleep 30"], timeout=1)
        self.assertEqual(code, "timeout")
        self.assertLess(time.monotonic() - started, 5)
        time.sleep(3)
        self.assertFalse(marker.exists(), "a background process survived the timeout")

    def test_memory_per_process(self):
        old = tc.MEMORY_MB
        tc.MEMORY_MB = 256
        try:
            self.assertEqual(self.code([sys.executable, "-c", "b = b'x' * (1 << 30)"]), "out_of_memory")
        finally:
            tc.MEMORY_MB = old


class Build(unittest.TestCase):
    def test_family_and_board(self):
        with tempfile.TemporaryDirectory() as d:
            old_work = tc.WORK
            tc.WORK = Path(d) / "work"
            env = os.environ.pop("TC_FAMILY", None)
            try:
                r, _ = tc.build(tar_bytes([("a.c", b"")]), "arduino-nano", [])
                self.assertEqual(r["code"], "internal")
                os.environ["TC_FAMILY"] = "avr"
                r, _ = tc.build(tar_bytes([("a.c", b"")]), "nucleo-g071rb", [])
                self.assertEqual(r["code"], "bad_board")
                self.assertEqual(r["log"], "")
                r, _ = tc.build(tar_bytes([("CMakeLists.txt", b""), ("prj.conf", b"")]), "arduino-nano", [])
                self.assertEqual(r["code"], "bad_project")
            finally:
                tc.WORK = old_work
                os.environ.pop("TC_FAMILY", None)
                if env:
                    os.environ["TC_FAMILY"] = env

    def test_sources_do_not_outlive_the_build(self):
        # tc serve runs one build per process: nothing of the visitor may wait for the next build
        with tempfile.TemporaryDirectory() as d:
            old_work, tc.WORK = tc.WORK, Path(d) / "work"
            env = os.environ.get("TC_FAMILY")
            os.environ["TC_FAMILY"] = "avr"
            src = Path(d) / "src.tar"
            src.write_bytes(tar_bytes([("sketch/sketch.ino", b"void setup(){}\nvoid loop(){}\n")]))
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    tc.cmd_build(argparse.Namespace(src=str(src), board="arduino-nano", option=[], out=None))
                self.assertFalse(tc.WORK.exists())
                # the same when writing the result fails (here --out is a file): the sources were already extracted
                blocker = Path(d) / "out"
                blocker.write_text("")
                with self.assertRaises(OSError), contextlib.redirect_stdout(io.StringIO()):
                    tc.cmd_build(argparse.Namespace(src=str(src), board="arduino-nano", option=[], out=str(blocker)))
                self.assertFalse(tc.WORK.exists())
            finally:
                tc.WORK = old_work
                os.environ.pop("TC_FAMILY", None)
                if env:
                    os.environ["TC_FAMILY"] = env

    def test_exit_codes_are_stable(self):
        self.assertEqual(tc.CODES, {
            "ok": 0, "usage": 2, "bad_archive": 3, "unsafe_path": 4, "too_large": 5,
            "bad_board": 6, "bad_project": 7, "build_failed": 8, "timeout": 9,
            "out_of_memory": 10, "output_too_large": 11, "internal": 12, "busy": 13,
            "unauthorized": 14})


class ElfSize(unittest.TestCase):
    def test_berkeley_sizes(self):
        # ELF32 LE header + 4 section headers: null, .text (AX), .data (WA), .bss (WA, NOBITS)
        sections = [(0, 0, 0), (1, 0x6, 100), (1, 0x3, 20), (8, 0x3, 300)]
        shoff = 52
        header = bytearray(52)
        header[:6] = b"\x7fELF\x01\x01"
        struct.pack_into("<I", header, 0x20, shoff)
        struct.pack_into("<HH", header, 0x2E, 40, len(sections))
        table = b"".join(struct.pack("<IIIIIIIIII", 0, t, f, 0, 0, s, 0, 0, 0, 0) for t, f, s in sections)
        with tempfile.NamedTemporaryFile() as fh:
            fh.write(bytes(header) + table)
            fh.flush()
            self.assertEqual(tc.elf_size(Path(fh.name)), {"text": 100, "data": 20, "bss": 300})


if __name__ == "__main__":
    unittest.main()
