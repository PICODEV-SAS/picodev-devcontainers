# dev-nrf52: Zephyr with the Zephyr SDK reduced to arm-zephyr-eabi (from the
# toolchain image picodev-lab-toolchain-zephyr), its west workspace made usable
# again, the nRF Connect SDK on the same Zephyr and SDK, OpenOCD and pyOCD.
# nrfutil and SEGGER J-Link may not be redistributed: first-start installers.
ARG BASE=dev-base-nrf52
FROM ${BASE}

ARG NCS_VERSION=v3.4.1
ARG PYOCD_VERSION=0.45.1
RUN apt-get update \
 && apt-get install -y --no-install-recommends openocd \
 && rm -rf /var/lib/apt/lists/* \
 # nRF Connect SDK: its own west workspace, on Zephyr and SDK versions identical to the image's.
 && west init -m https://github.com/nrfconnect/sdk-nrf --mr "$NCS_VERSION" /opt/ncs \
 && cd /opt/ncs && west update --narrow -o=--depth=1 \
 # Its own Python environment: Zephyr's (/opt/venv) stays as the toolchain image built it.
 && python3 -m venv /opt/ncs/venv \
 && /opt/ncs/venv/bin/pip install --no-cache-dir -q "west==$(west --version | sed 's/.*v//')" \
      -r zephyr/scripts/requirements-base.txt -r nrf/scripts/requirements-build.txt \
 && /opt/ncs/venv/bin/pip freeze > /opt/ncs-pip-freeze.txt \
 && west list -f '{name} {revision}' > /opt/ncs-projects.txt \
 # Without .git, west cannot read the imports of NCS's manifest: a resolved one, imports done.
 && west manifest --resolve > nrf/west-resolved.yml && west config manifest.file west-resolved.yml \
 && west config zephyr.base zephyr \
 # NCS's build reads the commits of nrf and zephyr from their .git (shallow): those stay.
 && find /opt/ncs -name .git -prune ! -path /opt/ncs/nrf/.git ! -path /opt/ncs/zephyr/.git -exec rm -rf {} + \
 && git config --system --add safe.directory /opt/ncs/nrf \
 && git config --system --add safe.directory /opt/ncs/zephyr \
 # LC3 codec of T2 Software (library and its header): its licence grants no redistribution;
 # nRF52840 does not use it. Nordic's Kconfig and glue stay, NCS needs them to configure.
 && rm -rf /opt/ncs/nrfxlib/lc3/lib /opt/ncs/nrfxlib/lc3/codec \
 && grep -q '^PATCHLEVEL = 2' /opt/ncs/zephyr/VERSION \
 # The toolchain image drops .west (its builds run without west): back, for west build.
 # After NCS: west init would find this workspace through ZEPHYR_BASE and refuse.
 && mkdir /opt/zephyrproject/.west \
 && printf '[manifest]\npath = zephyr\nfile = west.yml\nproject-filter = -.*,+cmsis,+cmsis_6,+hal_nordic,+hal_stm32,+mbedtls,+tf-psa-crypto\n\n[zephyr]\nbase = zephyr\n' \
      > /opt/zephyrproject/.west/config \
 && python3 -m venv /opt/pyocd && /opt/pyocd/bin/pip install --no-cache-dir -q "pyocd==${PYOCD_VERSION}" \
 && ln -s /opt/pyocd/bin/pyocd /usr/local/bin/pyocd
COPY ncs-activate /opt/ncs/activate
# picodev build | send (dev-base): how this family builds.
ENV PICODEV_FAMILY=nrf52
COPY picodev-install-nrfutil picodev-install-jlink /usr/local/bin/
RUN python3 - <<'PY'
import json, os, subprocess
v = json.load(open("/opt/picodev/versions.json")) | json.load(open("/opt/tc/versions.json"))
def out(*cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    return (p.stdout or p.stderr).splitlines()[0]
v["west"] = out("west", "--version")
v["ncs"] = os.environ["NCS_VERSION"]
v["openocd"] = out("openocd", "--version")
v["pyocd"] = out("pyocd", "--version")
json.dump(v, open("/opt/picodev/versions.json", "w"), indent=1)
PY

ARG VERSION=dev
LABEL org.opencontainers.image.title="dev-nrf52" \
      org.opencontainers.image.description="Picodev CTF development container: nRF52840 (Zephyr, nRF Connect SDK)" \
      org.opencontainers.image.version="${VERSION}"
