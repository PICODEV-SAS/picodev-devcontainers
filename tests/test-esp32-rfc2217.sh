#!/bin/sh
# tests/test-esp32-rfc2217.sh <image>: the documented Linux procedure, with
# Espressif's QEMU (download mode) standing in for the board on USB:
#   host:      esp_rfc2217_server.py -p 4000 <serial port>
#   container: idf.py -p 'rfc2217://host.docker.internal:4000?ign_set_control' flash
# then QEMU boots the flash it was given and must print the starter's hello.
set -eu
image=$1
root=$(cd "$(dirname "$0")/.." && pwd)
tmp=$(mktemp -d)
name=picodev-rfc2217-$$
port=$((20000 + $$ % 10000)) serial=$((30000 + $$ % 10000))
cleanup() {
  [ -z "${server:-}" ] || kill $server 2>/dev/null || true
  docker rm -f $name-qemu $name-qemu2 >/dev/null 2>&1 || true
  rm -rf "$tmp"
}
trap cleanup EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }

# esptool on the host, the version ESP-IDF pins (what the player installs with pipx).
esptool=$(docker run --rm "$image" bash -lc 'esptool.py version | tail -1')
python3 -m venv "$tmp/venv" && "$tmp/venv/bin/pip" install -q "esptool==$esptool"

# The "board": a blank 4 MB flash, QEMU in download mode, its UART on a TCP port.
chmod 777 "$tmp" && truncate -s 4M "$tmp/flash.bin" && chmod 666 "$tmp/flash.bin"
qemu() {
  docker run -d --name "$1" -v "$tmp:/flash" -p 127.0.0.1:$serial:5555 --entrypoint bash "$image" -lc \
    "qemu-system-xtensa -nographic -machine esp32 -drive file=/flash/flash.bin,if=mtd,format=raw \
     -serial tcp::5555,server $2" >/dev/null
  sleep 3
}
qemu $name-qemu "-global driver=esp32.gpio,property=strap_mode,value=0x0f"

# Host side of the procedure.
"$tmp/venv/bin/esp_rfc2217_server.py" -p $port "socket://127.0.0.1:$serial" > "$tmp/server.log" 2>&1 &
server=$!
sleep 2

# Container side: build and flash through RFC2217, as the starter's task does. A host
# firewall may drop container -> host traffic (some do): then the host network.
net="--add-host=host.docker.internal:host-gateway" host=host.docker.internal
docker run --rm $net --entrypoint bash "$image" -c "timeout 3 bash -c '</dev/tcp/$host/$port'" 2>/dev/null \
  || { net="--network host" host=127.0.0.1; echo "note: host.docker.internal:$port unreachable (host firewall), using --network host"; }
docker run --rm $net -v "$root/starters/esp32:/src:ro" "$image" bash -lc \
  "cp -r /src ~/p && cd ~/p && idf.py set-target esp32 build >/dev/null \
   && idf.py -p 'rfc2217://$host:$port?ign_set_control' -b 115200 flash" > "$tmp/flash.log" 2>&1 \
  || { tail -30 "$tmp/flash.log"; tail -20 "$tmp/server.log"; fail "flash through RFC2217"; }
grep -q 'Hash of data verified' "$tmp/flash.log" || { tail -30 "$tmp/flash.log"; fail "esptool did not verify the flash"; }
echo "ok: flashed through esp_rfc2217_server ($(grep -c 'Hash of data verified' "$tmp/flash.log") images verified)"

# The flashed firmware boots.
kill $server; server=
docker rm -f $name-qemu >/dev/null
qemu $name-qemu2 ""
out=$(timeout 15 python3 -c "
import socket, time
s = socket.create_connection(('127.0.0.1', $serial)); s.settimeout(1); buf = b''; end = time.time() + 12
while time.time() < end and b'tick 1' not in buf:
    try: buf += s.recv(4096)
    except socket.timeout: pass
print(buf.decode(errors='replace'))") || true
echo "$out" | grep -q 'Hello from Picodev on esp32' || { echo "$out" | tail -20; fail "flashed firmware does not boot"; }
echo "ok: QEMU boots the flashed firmware: $(echo "$out" | tr -d '\r' | grep -o 'Hello from Picodev.*' | head -1)"
