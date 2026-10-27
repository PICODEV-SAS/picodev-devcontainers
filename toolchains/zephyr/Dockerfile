# Zephyr toolchain image: Zephyr with the modules of the nRF52840 DK and of
# the M2 STM32 boards only, and the Zephyr SDK reduced to arm-zephyr-eabi.
# Build from toolchains/:
#   docker buildx build -f zephyr/Dockerfile --platform linux/amd64,linux/arm64 .
ARG BASE=debian:trixie-slim@sha256:62bd423aeee912639ca8ee681c2b762cb3e25137e0a92b20be455898a9f034ad
FROM ${BASE}

ARG VERSION=0.1.0
ARG ZEPHYR_VERSION=v4.4.2
ARG ZEPHYR_SDK_VERSION=1.0.1
ARG SDK_SHA256_AMD64="ca9bc0ff66fafca1dac9d592a36d953cf16d096a9d09b1c0357f021cf9f6a7eb 21b85981cb5a1818d9bc53d82af80f208946ec038b982ff1907287572ed3a634"
ARG SDK_SHA256_ARM64="d79c5bfc68e679488659bea289a4026e52a64f03338875c8c9c850fff13cee30 b9805b691f2f0a8926c92694cae378d05ba07b76abca745e216fcc52753cc4d6"
ARG WEST_VERSION=1.5.0
# Modules from Zephyr's west.yml (revisions pinned by the Zephyr tag)
# mbedtls and tf-psa-crypto: PSA Crypto, which BLE pairing (CONFIG_BT_SMP) needs
ARG ZEPHYR_MODULES_LIST="cmsis cmsis_6 hal_nordic hal_stm32 mbedtls tf-psa-crypto"
ARG TARGETARCH

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl git xz-utils python3 python3-venv \
      cmake ninja-build device-tree-compiler make gperf file \
 && rm -rf /var/lib/apt/lists/*

ENV ZEPHYR_SDK_INSTALL_DIR=/opt/zephyr-sdk-${ZEPHYR_SDK_VERSION}
RUN case "$TARGETARCH" in amd64) h=x86_64 sums=$SDK_SHA256_AMD64 ;; arm64) h=aarch64 sums=$SDK_SHA256_ARM64 ;; *) exit 1 ;; esac \
 && base=https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v${ZEPHYR_SDK_VERSION} \
 && sdk=zephyr-sdk-${ZEPHYR_SDK_VERSION}_linux-${h}_minimal.tar.xz tool=toolchain_gnu_linux-${h}_arm-zephyr-eabi.tar.xz \
 && curl -fsSL -o /tmp/$sdk $base/$sdk && curl -fsSL -o /tmp/$tool $base/$tool \
 && set -- $sums && printf '%s  /tmp/%s\n%s  /tmp/%s\n' "$1" "$sdk" "$2" "$tool" | sha256sum -c - \
 && tar -xJf /tmp/$sdk -C /opt && mkdir -p $ZEPHYR_SDK_INSTALL_DIR/gnu \
 && tar -xJf /tmp/$tool -C $ZEPHYR_SDK_INSTALL_DIR/gnu \
 && cd $ZEPHYR_SDK_INSTALL_DIR && ln -s gnu/* . \
 && rm -rf /tmp/*.tar.xz $ZEPHYR_SDK_INSTALL_DIR/hosttools \
      $ZEPHYR_SDK_INSTALL_DIR/gnu/arm-zephyr-eabi/share/doc $ZEPHYR_SDK_INSTALL_DIR/gnu/arm-zephyr-eabi/share/man

ENV PATH=/opt/venv/bin:$PATH
RUN python3 -m venv /opt/venv \
 && pip install --no-cache-dir -q "west==${WEST_VERSION}" \
 && west init -m https://github.com/zephyrproject-rtos/zephyr --mr "$ZEPHYR_VERSION" /opt/zephyrproject \
 && cd /opt/zephyrproject \
 && west config manifest.project-filter -- "-.*,$(echo $ZEPHYR_MODULES_LIST | sed 's/\([^ ]*\)/+\1/g; s/ /,/g')" \
 && west update --narrow -o=--depth=1 \
 && pip install --no-cache-dir -q -r zephyr/scripts/requirements-base.txt \
 && west list -f '{name} {revision}' > /opt/zephyr-modules.txt \
 && pip freeze > /opt/zephyr-pip-freeze.txt \
 && find /opt/zephyrproject -name .git -prune -exec rm -rf {} + \
 && rm -rf /opt/zephyrproject/.west
ENV ZEPHYR_BASE=/opt/zephyrproject/zephyr \
    ZEPHYR_TOOLCHAIN_VARIANT=zephyr \
    ZEPHYR_MODULES="/opt/zephyrproject/modules/hal/cmsis;/opt/zephyrproject/modules/hal/cmsis_6;/opt/zephyrproject/modules/hal/nordic;/opt/zephyrproject/modules/hal/stm32;/opt/zephyrproject/modules/crypto/mbedtls;/opt/zephyrproject/modules/crypto/tf-psa-crypto"

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
ENV TC_FAMILY=zephyr TC_IMAGE=picodev-lab-toolchain-zephyr@${VERSION}
RUN ln -s /opt/tc/tc.py /usr/local/bin/tc \
 && printf '{"zephyr": "%s", "zephyr-sdk": "%s", "arm-zephyr-eabi-gcc": "%s", "modules": "%s", "cmake": "%s"}\n' \
      "$ZEPHYR_VERSION" "$ZEPHYR_SDK_VERSION" "$($ZEPHYR_SDK_INSTALL_DIR/arm-zephyr-eabi/bin/arm-zephyr-eabi-gcc -dumpversion)" \
      "$(tr '\n' ' ' < /opt/zephyr-modules.txt | sed 's/ $//')" "$(cmake --version | head -1 | cut -d' ' -f3)" > /opt/tc/versions.json \
 && mkdir -p /opt/tc/seed/ccache /cache && chown 10001:10001 /cache \
 && CCACHE_REMOTE_STORAGE=file:/opt/tc/seed/ccache tc prewarm /opt/tc/examples \
 && chmod -R a+rX /opt/tc && rm -rf /tmp/* \
 && useradd -u 10001 -M -d /tmp/work/home builder

# Measured (docs/toolchains.adoc): CPUs a build uses well, peak memory in MiB.
ARG CPU=4
ARG MEMORY=1024
LABEL org.opencontainers.image.title="picodev-lab-toolchain-zephyr" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.licenses="Apache-2.0" \
      fr.picodev.lab.kind="toolchain" \
      fr.picodev.lab.family="zephyr" \
      fr.picodev.lab.cpu="${CPU}" \
      fr.picodev.lab.memory="${MEMORY}"
USER 10001
WORKDIR /tmp
ENTRYPOINT ["tc"]
CMD ["info"]
