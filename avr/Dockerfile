# dev-avr: arduino-cli, the arduino:avr core and its avr-gcc (from the toolchain
# image picodev-lab-toolchain-avr), avrdude, on top of the development layer.
ARG BASE=dev-base-avr
FROM ${BASE}

# The core and the libraries stay where the toolchain image put them; the user may
# add libraries (user directory) and refresh the indexes (top of the data directory).
# World-writable, not owned by picodev: Dev Containers changes picodev's UID to the host user's.
RUN find /opt/arduino -maxdepth 1 -exec chmod a+w {} + \
 && chmod -R a+w /opt/arduino/user \
 && ln -s /opt/arduino/packages/arduino/tools/avrdude/*/bin/avrdude /usr/local/bin/avrdude \
 && python3 - <<'EOF'
import json, subprocess
v = json.load(open("/opt/picodev/versions.json")) | json.load(open("/opt/tc/versions.json"))
v["avrdude"] = subprocess.run(["avrdude", "-?"], capture_output=True, text=True).stderr.split("version ")[1].split()[0].rstrip(",")
json.dump(v, open("/opt/picodev/versions.json", "w"), indent=1)
EOF
# picodev build | send (dev-base): how this family builds.
ENV PICODEV_FAMILY=avr

ARG VERSION=dev
LABEL org.opencontainers.image.title="dev-avr" \
      org.opencontainers.image.description="Picodev CTF development container: Arduino Nano and Uno (AVR)" \
      org.opencontainers.image.version="${VERSION}"
