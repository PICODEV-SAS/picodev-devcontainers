# Bare-metal ARM toolchain image: Arm GNU Toolchain (arm-none-eabi-gcc),
# CMSIS 6 Core, and a minimal STM32Cube for the lab's STM32 boards (CMSIS device
# headers, startup files, HAL drivers of the F4, G0 and L5 series).
# Build from toolchains/:
#   docker buildx build -f arm/Dockerfile --platform linux/amd64,linux/arm64 .
ARG BASE=debian:trixie-slim@sha256:62bd423aeee912639ca8ee681c2b762cb3e25137e0a92b20be455898a9f034ad
FROM ${BASE}

ARG VERSION=0.1.0
ARG ARM_GNU_VERSION=14.3.rel1
ARG ARM_GNU_SHA256_AMD64=8f6903f8ceb084d9227b9ef991490413014d991874a1e34074443c2a72b14dbd
ARG ARM_GNU_SHA256_ARM64=2d465847eb1d05f876270494f51034de9ace9abe87a4222d079f3360240184d3
ARG CMSIS_VERSION=v6.3.0
# series:cmsis-device tag:hal driver tag
ARG STM32CUBE="f4:v2.6.11:v1.8.5 g0:v1.4.5:v1.4.7 l5:v1.0.7:v1.0.7"
ARG TARGETARCH

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl git xz-utils python3 make \
 && rm -rf /var/lib/apt/lists/*

RUN case "$TARGETARCH" in \
      amd64) a=x86_64 sum=$ARM_GNU_SHA256_AMD64 ;; arm64) a=aarch64 sum=$ARM_GNU_SHA256_ARM64 ;; *) exit 1 ;; esac \
 && f=arm-gnu-toolchain-${ARM_GNU_VERSION}-${a}-arm-none-eabi.tar.xz \
 && curl -fsSL -o /tmp/$f "https://developer.arm.com/-/media/Files/downloads/gnu/${ARM_GNU_VERSION}/binrel/$f" \
 && echo "$sum  /tmp/$f" | sha256sum -c - \
 && mkdir /opt/arm-gnu && tar -xJf /tmp/$f -C /opt/arm-gnu --strip-components=1 \
 && rm -rf /tmp/$f /opt/arm-gnu/share/doc /opt/arm-gnu/share/info /opt/arm-gnu/share/man
ENV PATH=/opt/arm-gnu/bin:$PATH

RUN git clone -q --depth 1 -b "$CMSIS_VERSION" https://github.com/ARM-software/CMSIS_6.git /tmp/cmsis \
 && mkdir -p /opt/cmsis/CMSIS && mv /tmp/cmsis/CMSIS/Core /opt/cmsis/CMSIS/ && cp /tmp/cmsis/LICENSE /opt/cmsis/ \
 && for s in $STM32CUBE; do \
      series=${s%%:*}; rest=${s#*:}; dev=${rest%%:*}; hal=${rest#*:}; \
      git clone -q --depth 1 -b "$dev" "https://github.com/STMicroelectronics/cmsis-device-$series.git" /opt/stm32cube/$series/cmsis-device \
   && git clone -q --depth 1 -b "$hal" "https://github.com/STMicroelectronics/stm32${series}xx-hal-driver.git" /opt/stm32cube/$series/hal \
   && rm -rf /opt/stm32cube/$series/*/.git; \
    done \
 && rm -rf /tmp/cmsis
COPY arm/cortex-m.ld /opt/tc/arm/
ENV CMSIS_PATH=/opt/cmsis STM32CUBE_PATH=/opt/stm32cube TC_ARM_LD=/opt/tc/arm

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
ENV TC_FAMILY=arm TC_IMAGE=picodev-lab-toolchain-arm@${VERSION}
RUN ln -s /opt/tc/tc.py /usr/local/bin/tc \
 && printf '{"arm-none-eabi-gcc": "%s (Arm GNU Toolchain %s)", "cmsis": "%s", "stm32cube": "%s"}\n' \
      "$(arm-none-eabi-gcc -dumpversion)" "$ARM_GNU_VERSION" "$CMSIS_VERSION" "$STM32CUBE" > /opt/tc/versions.json \
 && mkdir -p /opt/tc/seed/ccache /cache && chown 10001:10001 /cache \
 && CCACHE_REMOTE_STORAGE=file:/opt/tc/seed/ccache tc prewarm /opt/tc/examples \
 && chmod -R a+rX /opt/tc && rm -rf /tmp/* \
 && useradd -u 10001 -M -d /tmp/work/home builder

# Measured with `make measure`: CPUs a build uses well, peak memory in MiB.
ARG CPU=1
ARG MEMORY=64
LABEL org.opencontainers.image.title="picodev-lab-toolchain-arm" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.licenses="Apache-2.0" \
      fr.picodev.lab.kind="toolchain" \
      fr.picodev.lab.family="arm" \
      fr.picodev.lab.cpu="${CPU}" \
      fr.picodev.lab.memory="${MEMORY}"
USER 10001
WORKDIR /tmp
ENTRYPOINT ["tc"]
CMD ["info"]
