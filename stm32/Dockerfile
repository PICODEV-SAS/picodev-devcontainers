# dev-stm32: Arm GNU Toolchain, CMSIS 6 and the CMSIS device headers and HAL of the
# F4, G0 and L5 series (from the toolchain image picodev-lab-toolchain-arm), plus
# OpenOCD, pyOCD and the first-start installer of STM32CubeCLT (not redistributed).
ARG BASE=dev-base-stm32
FROM ${BASE}

ARG PYOCD_VERSION=0.45.1
RUN apt-get update \
 && apt-get install -y --no-install-recommends openocd libncursesw6 \
 && rm -rf /var/lib/apt/lists/* \
 && python3 -m venv /opt/pyocd \
 && /opt/pyocd/bin/pip install --no-cache-dir -q "pyocd==${PYOCD_VERSION}" \
 && ln -s /opt/pyocd/bin/pyocd /usr/local/bin/pyocd \
 && python3 - <<'PY'
import json, subprocess
v = json.load(open("/opt/picodev/versions.json")) | json.load(open("/opt/tc/versions.json"))
def out(*cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    return (p.stdout or p.stderr).splitlines()[0]
v["openocd"] = out("openocd", "--version")
v["pyocd"] = out("pyocd", "--version")
v["arm-none-eabi-gdb"] = out("arm-none-eabi-gdb", "--version")
json.dump(v, open("/opt/picodev/versions.json", "w"), indent=1)
PY

# CMSIS packs of the three series (Apache-2.0, BSD-3-Clause): pyOCD targets, SVD files
# for the register views of Cortex-Debug.
ARG PACKS="F4xx:3.1.1:cd6983099df1aaa7c482d24dd061827ccb44d6303f84a09bfebcdda9f98d4999 \
G0xx:2.1.0:391e486cf4a69981bf1c10273e5b118b752b072af7557c9f4f9bd4e4302e91ed \
L5xx:2.1.0:190ebdd8615107f9be69cd7a8bd9710e4c4240ed69c5886a5d7694a6d8c74c31"
RUN mkdir -p /opt/cmsis-packs/svd && cd /opt/cmsis-packs \
 && for p in $PACKS; do \
      s=${p%%:*} r=${p#*:}; v=${r%%:*} sum=${r#*:}; f=Keil.STM32${s}_DFP.$v.pack; \
      curl -fsSL -o $f "https://github.com/Open-CMSIS-Pack/STM32${s}_DFP/releases/download/v$v/$f" \
   && echo "$sum  $f" | sha256sum -c - \
   && unzip -q -j -o $f 'CMSIS/SVD/*.svd' -d svd || exit 1; \
    done \
 && python3 -c 'import json; p="/opt/picodev/versions.json"; v=json.load(open(p)); v["cmsis-packs"]="'"$(echo $PACKS | sed 's/:[0-9a-f]\{64\}//g')"'"; json.dump(v, open(p, "w"), indent=1)'
COPY picodev-install-stm32cubeclt /usr/local/bin/
# picodev build | send (dev-base): how this family builds.
ENV PICODEV_FAMILY=stm32

ARG VERSION=dev
LABEL org.opencontainers.image.title="dev-stm32" \
      org.opencontainers.image.description="Picodev CTF development container: STM32 F4, G0, L5 (Arm GNU Toolchain, CMSIS, HAL)" \
      org.opencontainers.image.version="${VERSION}"
