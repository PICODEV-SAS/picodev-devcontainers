# Development layer shared by every dev-<family> image: editor tools, debugger,
# host gcc (host tests), SSH server (keys only), the non-root user `picodev`.
# BASE: a toolchain image of picodev-lab-workers (dev-<family>) or Debian (dev-base).
ARG BASE=debian:trixie-slim@sha256:62bd423aeee912639ca8ee681c2b762cb3e25137e0a92b20be455898a9f034ad
FROM ${BASE}

USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl wget git openssh-client openssh-server sudo less nano vim-tiny \
      bash-completion procps file unzip xz-utils make gcc libc6-dev cmake ninja-build \
      python3 python3-venv python3-pip clangd gdb-multiarch picocom usbutils \
 && rm -rf /var/lib/apt/lists/* \
 # Host keys made by the package would be the same in every container: each container makes its own.
 && rm -f /etc/ssh/ssh_host_* \
 # Login shells keep the image PATH (toolchains) instead of Debian's default one.
 && sed -i -E 's/((^|\s)PATH=)([^$]*)$/\1${PATH:-\3}/g' /etc/profile \
 && useradd -m -u 1000 -s /bin/bash -G dialout,plugdev picodev \
 # Zephyr writes its compiler checks in ~/.cache only if it exists already.
 && install -d -o picodev -g picodev /home/picodev/.cache \
 && echo 'picodev ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/picodev && chmod 440 /etc/sudoers.d/picodev \
 && mkdir -p /opt/picodev /run/sshd \
 && { printf '{"debian": "%s"' "$(cat /etc/debian_version)"; \
      for p in git python3 cmake ninja-build clangd gdb-multiarch openssh-server; do dpkg-query -W -f ', "${Package}": "${Version}"' $p; done; \
      echo '}'; } > /opt/picodev/versions.json

COPY sshd_config /etc/ssh/sshd_config.d/picodev.conf
COPY picodev-entrypoint /usr/local/bin/
# picodev build | send: compile here, send to the bench of an open CTF game (its agent, MCP).
COPY picodev /usr/local/bin/
# The written offer for the source of the GPL binaries (SOURCES.md).
COPY SOURCES-OFFER /opt/picodev/

ARG VERSION=dev
LABEL org.opencontainers.image.title="dev-base" \
      org.opencontainers.image.description="Picodev CTF development container: base layer" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.vendor="Picodev SAS" \
      org.opencontainers.image.url="https://ctf.picodev.fr" \
      org.opencontainers.image.source="https://github.com/PICODEV-SAS/picodev-devcontainers" \
      org.opencontainers.image.licenses="Apache-2.0" \
      fr.picodev.lab.kind="devcontainer"

WORKDIR /home/picodev
EXPOSE 22
ENTRYPOINT ["picodev-entrypoint"]
CMD ["sshd"]
