"""Sizes and build times of the toolchain images, as AsciiDoc tables for
docs/toolchains.adoc. Each example and board is built three ways:
cold (no cache at all), seed (the read-only seed of the image, what a first
build gets) and warm (the same sources again with a cache volume)."""
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_images import ROOT, build, examples, image  # noqa: E402
import tc  # noqa: E402

CPUS = os.environ.get("TC_CPUS", "4")


def image_size(family):
    """(compressed, as pulled; unpacked, on disk) for this machine's platform."""
    pulled = subprocess.run(["docker", "image", "inspect", "--format", "{{.Size}}", image(family)],
                            capture_output=True, text=True).stdout.strip()
    disk = subprocess.run(["docker", "image", "ls", "--format", "{{.Size}}", image(family)],
                          capture_output=True, text=True).stdout.strip()
    return f"{int(pulled) / 1e9:.2f} Go" if pulled else "?", disk.replace("GB", " Go").replace("MB", " Mo")


def main():
    print(f"Machine : {platform.machine()}, {os.cpu_count()} cœurs ; conteneur : {CPUS} CPU, "
          f"mémoire {os.environ.get('TC_MEMORY', '4g')}.\n")
    print("[cols=\"2,1,1\", options=\"header\"]\n|===\n|Image (" + platform.machine() + ") |Téléchargée |Sur disque")
    for family in ("avr", "arm", "zephyr", "esp"):
        pulled, disk = image_size(family)
        print(f"|`{image(family)}` |{pulled} |{disk}")
    print("|===\n")
    print("[cols=\"3,2,1,1,1,1,2\", options=\"header\"]\n|===\n"
          "|Exemple |Carte |À froid |Graine |Chaud |Mémoire max. |ccache (graine)")
    for example, board in examples(ROOT / "examples"):
        family = tc.family_for(board, tc.detect_kind(example))
        volume = f"tc-measure-{family}-{example.name}-{board}"
        subprocess.run(["docker", "volume", "rm", "-f", volume], capture_output=True)
        _, cold = build(family, board, example, {"TC_SEED": "/nonexistent"})
        _, seed = build(family, board, example)
        build(family, board, example, {"TC_CACHE_VOLUME": volume})
        _, warm = build(family, board, example, {"TC_CACHE_VOLUME": volume})
        subprocess.run(["docker", "volume", "rm", "-f", volume], capture_output=True)
        c = seed["cache"]
        hits = f"{c.get('remote_storage_hit', 0)} / {c.get('remote_storage_hit', 0) + c.get('cache_miss', 0)}" \
            if c.get("remote_storage_hit") or c.get("cache_miss") else "–"
        peak = max(r["peak_memory_mb"] or 0 for r in (cold, seed, warm))
        print(f"|{example.name} |{board} |{cold['duration_ms'] / 1000:.1f} s |{seed['duration_ms'] / 1000:.1f} s "
              f"|{warm['duration_ms'] / 1000:.1f} s |{peak} Mio |{hits}")
        print(json.dumps({"example": example.name, "board": board, "codes": [cold["code"], seed["code"], warm["code"]]}),
              file=sys.stderr)
    print("|===")


if __name__ == "__main__":
    main()
