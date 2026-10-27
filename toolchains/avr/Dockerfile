# AVR toolchain image: arduino-cli, the arduino:avr core (and its avr-gcc),
# the libraries the lab allows. Build from toolchains/:
#   docker buildx build -f avr/Dockerfile --platform linux/amd64,linux/arm64 .
ARG BASE=debian:trixie-slim@sha256:62bd423aeee912639ca8ee681c2b762cb3e25137e0a92b20be455898a9f034ad
FROM ${BASE}

ARG VERSION=0.1.0
ARG ARDUINO_CLI_VERSION=1.5.1
ARG AVR_CORE=arduino:avr@1.8.6
ARG ARDUINO_LIBS="Servo@1.2.2"
ARG TARGETARCH

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl xz-utils python3 make \
 && rm -rf /var/lib/apt/lists/*

ENV ARDUINO_DIRECTORIES_DATA=/opt/arduino \
    ARDUINO_DIRECTORIES_USER=/opt/arduino/user \
    ARDUINO_DIRECTORIES_DOWNLOADS=/tmp/arduino-downloads \
    ARDUINO_UPDATER_ENABLE_NOTIFICATION=false
RUN case "$TARGETARCH" in amd64) a=64bit ;; arm64) a=ARM64 ;; *) exit 1 ;; esac \
 && curl -fsSL "https://github.com/arduino/arduino-cli/releases/download/v${ARDUINO_CLI_VERSION}/arduino-cli_${ARDUINO_CLI_VERSION}_Linux_${a}.tar.gz" \
      | tar -xz -C /usr/local/bin arduino-cli \
 && arduino-cli core update-index \
 && arduino-cli core install "$AVR_CORE" \
 && for lib in $ARDUINO_LIBS; do arduino-cli lib install "$lib"; done \
 && ln -s /opt/arduino/packages/arduino/tools/avr-gcc/*/bin /opt/avr-gcc-bin \
 && rm -rf /tmp/arduino-downloads
ENV PATH=/opt/avr-gcc-bin:$PATH

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
ENV TC_FAMILY=avr TC_IMAGE=picodev-lab-toolchain-avr@${VERSION}
RUN ln -s /opt/tc/tc.py /usr/local/bin/tc \
 && printf '{"arduino-cli": "%s", "core": "%s", "libraries": "%s", "avr-gcc": "%s"}\n' \
      "$ARDUINO_CLI_VERSION" "$AVR_CORE" "$ARDUINO_LIBS" "$(avr-gcc -dumpversion)" > /opt/tc/versions.json \
 && mkdir -p /opt/tc/seed/ccache /cache && chown 10001:10001 /cache \
 && CCACHE_REMOTE_STORAGE=file:/opt/tc/seed/ccache tc prewarm /opt/tc/examples \
 && chmod -R a+rX /opt/tc && rm -rf /tmp/* \
 && useradd -u 10001 -M -d /tmp/work/home builder

# Measured with `make measure`: CPUs a build uses well, peak memory in MiB.
ARG CPU=1
ARG MEMORY=256
LABEL org.opencontainers.image.title="picodev-lab-toolchain-avr" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.licenses="Apache-2.0" \
      fr.picodev.lab.kind="toolchain" \
      fr.picodev.lab.family="avr" \
      fr.picodev.lab.cpu="${CPU}" \
      fr.picodev.lab.memory="${MEMORY}"
USER 10001
WORKDIR /tmp
ENTRYPOINT ["tc"]
CMD ["info"]
