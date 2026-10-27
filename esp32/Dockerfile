# dev-esp32: ESP-IDF for esp32, esp32s3, esp32c3 (from the toolchain image
# picodev-lab-toolchain-esp), plus what development needs and the toolchain
# image leaves out: OpenOCD, GDB and Espressif's QEMU, at the versions ESP-IDF pins.
ARG BASE=dev-base-esp32
FROM ${BASE}

RUN apt-get update \
 && apt-get install -y --no-install-recommends libgcrypt20 libglib2.0-0t64 libpixman-1-0 libsdl2-2.0-0 libslirp0 \
 && rm -rf /var/lib/apt/lists/* \
 && python3 $IDF_PATH/tools/idf_tools.py install \
      openocd-esp32 xtensa-esp-elf-gdb riscv32-esp-elf-gdb qemu-xtensa qemu-riscv32 \
 && rm -rf $IDF_TOOLS_PATH/dist \
 # The toolchain image points this at /tmp for its read-only builds. World-writable, not
 # owned by picodev: Dev Containers changes picodev's UID to the host user's.
 && rm $IDF_TOOLS_PATH/root_managed_components \
 && install -d -m 1777 $IDF_TOOLS_PATH/root_managed_components \
 # The ESP-IDF environment (export.sh) for every shell: login shells, Dev Containers, SSH.
 && bash -c ". $IDF_PATH/export.sh >/dev/null && env" \
      | grep -E '^(PATH|IDF_PYTHON_ENV_PATH|ESP_IDF_VERSION|ESP_ROM_ELF_DIR|OPENOCD_SCRIPTS)=' \
      | sed 's/^/export /; s/=\(.*\)$/="\1"/' > /etc/profile.d/esp-idf.sh \
 && bash -c ". /etc/profile.d/esp-idf.sh && python3 - " <<'EOF'
import json, subprocess
v = json.load(open("/opt/picodev/versions.json")) | json.load(open("/opt/tc/versions.json"))
def first(cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout.splitlines()[0]
v["openocd-esp32"] = subprocess.run(["openocd", "--version"], capture_output=True, text=True).stderr.splitlines()[0]
v["qemu-xtensa"] = first(["qemu-system-xtensa", "--version"])
v["qemu-riscv32"] = first(["qemu-system-riscv32", "--version"])
v["esp-gdb"] = first(["xtensa-esp32-elf-gdb", "--version"])
json.dump(v, open("/opt/picodev/versions.json", "w"), indent=1)
EOF

# picodev build | send (dev-base): how this family builds.
ENV PICODEV_FAMILY=esp32

ARG VERSION=dev
LABEL org.opencontainers.image.title="dev-esp32" \
      org.opencontainers.image.description="Picodev CTF development container: ESP32, ESP32-S3, ESP32-C3 (ESP-IDF)" \
      org.opencontainers.image.version="${VERSION}"
