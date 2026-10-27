# ESP toolchain image: ESP-IDF for esp32, esp32s3 and esp32c3, and the Arduino
# core for ESP32 (arduino-cli). Build from toolchains/:
#   docker buildx build -f esp/Dockerfile --platform linux/amd64,linux/arm64 .
ARG BASE=debian:trixie-slim@sha256:62bd423aeee912639ca8ee681c2b762cb3e25137e0a92b20be455898a9f034ad
FROM ${BASE}

ARG VERSION=0.1.0
ARG IDF_VERSION=v5.5.6
ARG IDF_TARGETS=esp32,esp32s3,esp32c3
ARG ARDUINO_CLI_VERSION=1.5.1
ARG ARDUINO_ESP32_CORE=esp32:esp32@3.3.12
ARG ARDUINO_ESP32_INDEX=https://espressif.github.io/arduino-esp32/package_esp32_index.json
ARG TARGETARCH

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl git wget xz-utils python3 python3-venv \
      cmake ninja-build flex bison gperf make libffi8 libssl3t64 libusb-1.0-0 \
 && rm -rf /var/lib/apt/lists/* \
 && git config --system --add safe.directory '*'

# ESP-IDF: the build of a project only reads it; the cross compilers, the
# Python environment and the ROM ELFs are installed under IDF_TOOLS_PATH.
ENV IDF_PATH=/opt/esp-idf IDF_TOOLS_PATH=/opt/espressif
RUN git clone -q --depth 1 -b "$IDF_VERSION" --recurse-submodules --shallow-submodules \
      https://github.com/espressif/esp-idf.git $IDF_PATH \
 && $IDF_PATH/install.sh "$IDF_TARGETS" \
 && mkdir -p /opt/tc \
 && bash -c ". $IDF_PATH/export.sh >/dev/null && env" \
      | grep -E '^(PATH|IDF_PYTHON_ENV_PATH|ESP_IDF_VERSION|ESP_ROM_ELF_DIR)=' > /opt/tc/env \
 && rm -rf $IDF_TOOLS_PATH/dist $IDF_TOOLS_PATH/tools/openocd-esp32 $IDF_TOOLS_PATH/tools/*-gdb

# Arduino core for ESP32: its own prebuilt ESP-IDF libraries and compilers.
# Its compilers are the same builds as ESP-IDF's: linked to them when the
# trees are identical (saves 3 GB); libraries of the chips we do not build go.
ENV ARDUINO_DIRECTORIES_DATA=/opt/arduino \
    ARDUINO_DIRECTORIES_USER=/opt/arduino/user \
    ARDUINO_DIRECTORIES_DOWNLOADS=/tmp/arduino-downloads \
    ARDUINO_BOARD_MANAGER_ADDITIONAL_URLS=${ARDUINO_ESP32_INDEX} \
    ARDUINO_UPDATER_ENABLE_NOTIFICATION=false
RUN case "$TARGETARCH" in amd64) a=64bit ;; arm64) a=ARM64 ;; *) exit 1 ;; esac \
 && curl -fsSL "https://github.com/arduino/arduino-cli/releases/download/v${ARDUINO_CLI_VERSION}/arduino-cli_${ARDUINO_CLI_VERSION}_Linux_${a}.tar.gz" \
      | tar -xz -C /usr/local/bin arduino-cli \
 && arduino-cli core update-index \
 && arduino-cli core install "$ARDUINO_ESP32_CORE" \
 && t=/opt/arduino/packages/esp32/tools \
 && for pair in esp-x32:xtensa-esp-elf esp-rv32:riscv32-esp-elf; do \
      a=${pair%%:*} i=${pair#*:}; idf=$(ls -d $IDF_TOOLS_PATH/tools/$i/*/$i | head -1); \
      for v in $t/$a/*/; do diff -rq "$v" "$idf" >/dev/null && rm -rf "$v" && ln -s "$idf" "${v%/}"; done; \
    done \
 && rm -rf $t/esp32c5-libs $t/esp32c6-libs $t/esp32h2-libs $t/esp32p4-libs $t/esp32p4_es-libs $t/esp32s2-libs \
      $t/*-gdb $t/openocd-esp32 /tmp/arduino-downloads

# ccache from upstream: 4.14 finds a "-specs=" file through the compiler
# (Zephyr's picolibc.specs), Debian's 4.11 refuses to cache those builds.
ARG CCACHE_VERSION=4.14.2
ARG CCACHE_SHA256_AMD64=bd1313f5316f594443dcb4113a4191c666ac6450e0cf016ff8cb8b080f46c160
ARG CCACHE_SHA256_ARM64=1f3c155db005d3d1b99ce5c8ce40a1afd45507fef0168c36a6b0fd6e628d0168
RUN case "$TARGETARCH" in \
      amd64) a=x86_64 sum=$CCACHE_SHA256_AMD64 ;; arm64) a=aarch64 sum=$CCACHE_SHA256_ARM64 ;; *) exit 1 ;; esac \
 && f=ccache-${CCACHE_VERSION}-linux-$a-glibc.tar.xz \
 && curl -fsSL -o /tmp/$f "https://github.com/ccache/ccache/releases/download/v${CCACHE_VERSION}/$f" \
 && echo "$sum  /tmp/$f" | sha256sum -c - \
 && tar -xJf /tmp/$f -C /usr/local/bin --strip-components=1 --wildcards '*/ccache' && rm /tmp/$f

COPY common/tc.py common/boards.json /opt/tc/
COPY examples/ /opt/tc/examples/
ENV TC_FAMILY=esp TC_IMAGE=picodev-lab-toolchain-esp@${VERSION}
# Prewarm builds under arm64 emulation (CI) can pass the 900 s limit of a visitor build.
RUN ln -s /opt/tc/tc.py /usr/local/bin/tc \
 && printf '{"esp-idf": "%s", "idf-targets": "%s", "arduino-cli": "%s", "core": "%s"}\n' \
      "$IDF_VERSION" "$IDF_TARGETS" "$ARDUINO_CLI_VERSION" "$ARDUINO_ESP32_CORE" > /opt/tc/versions.json \
 && mkdir -p /opt/tc/seed/ccache /cache && chown 10001:10001 /cache \
 && rm -rf $IDF_TOOLS_PATH/root_managed_components \
 && ln -s /tmp/idf-root-managed $IDF_TOOLS_PATH/root_managed_components \
 && CCACHE_REMOTE_STORAGE=file:/opt/tc/seed/ccache TC_TIMEOUT=3600 tc prewarm /opt/tc/examples \
 && chmod -R a+rX /opt/tc && rm -rf /tmp/* \
 && useradd -u 10001 -M -d /tmp/work/home builder

# Measured with `make measure`: CPUs a build uses well, peak memory in MiB.
ARG CPU=4
ARG MEMORY=2048
LABEL org.opencontainers.image.title="picodev-lab-toolchain-esp" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.licenses="Apache-2.0" \
      fr.picodev.lab.kind="toolchain" \
      fr.picodev.lab.family="esp" \
      fr.picodev.lab.cpu="${CPU}" \
      fr.picodev.lab.memory="${MEMORY}"
USER 10001
WORKDIR /tmp
ENTRYPOINT ["tc"]
CMD ["info"]
