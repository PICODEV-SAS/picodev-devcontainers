#!/bin/sh
# tests/test-image.sh <family> <image>: nothing secret in the image, the starter
# of the family builds in it, Remote-SSH mode lets keys in and nothing else.
set -eu
family=$1 image=$2
root=$(cd "$(dirname "$0")/.." && pwd)
tmp=$(mktemp -d)
name=picodev-test-$family-$$
cleanup() {
  docker rm -f $name $(docker ps -aq --filter label=picodev-test=$name) >/dev/null 2>&1 || true
  # the image the Dev Containers CLI makes to match the host UID
  docker images --format '{{.Repository}}' | grep "^vsc-$name-" | xargs -r docker rmi -f >/dev/null 2>&1 || true
  rm -rf "$tmp"
}
trap cleanup EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }
ok() { echo "ok: $*"; }

# Command that builds the starter (from its top directory) and the file it must produce.
case $family in
  base)  build='cmake -S . -B build -G Ninja && cmake --build build && ./build/hello'; out=build/hello; tool=clangd ;;
  avr)   build='picodev build blink'; out=build/blink.ino.hex; tool=avr-gcc ;;
  esp32) build='picodev build && for t in esp32s3 esp32c3; do idf.py -B build-$t set-target $t build || exit 1; done && test -s build/merged.hex'; out=build-esp32c3/starter-esp32.bin; tool=idf.py ;;
  stm32) build='cmake --preset nucleo-f446re && cmake --build --preset nucleo-f446re && picodev build && test -s build/nucleo-g071rb/starter.hex'; out=build/nucleo-g071rb/starter.elf; tool=arm-none-eabi-gcc ;;
  nrf52) build='picodev build app && (. /opt/ncs/activate && west build -b nrf52840dk/nrf52840 -d build-ncs app) && test -s build-ncs/app/zephyr/zephyr.hex'; out=build/zephyr/zephyr.hex; tool=west ;;
  *) fail "unknown family $family" ;;
esac
starter=$root/starters/$family
[ "$family" != base ] || starter=$root/tests/base-hello

# 1. Labels and nothing secret.
for l in title version source licenses; do
  v=$(docker image inspect -f "{{index .Config.Labels \"org.opencontainers.image.$l\"}}" "$image")
  [ -n "$v" ] || fail "label org.opencontainers.image.$l missing"
done
ok "OCI labels"
docker run --rm --entrypoint sh "$image" -c '
  set -e
  ! ls /etc/ssh/ssh_host_* 2>/dev/null
  ! find / -xdev \( -name authorized_keys -o -name .git-credentials -o -name "id_rsa" -o -name "id_ed25519" -o -name ".netrc" \) 2>/dev/null | grep .
  ! env | grep -iE "^[^=]*(token|secret|password)[^=]*="
  [ "$(id -u picodev)" = 1000 ]
' || fail "secret or user check"
ok "no host key, no private key, no token; user picodev"

# 2. The starter builds, as picodev, from a copy (the image stays clean).
docker run --rm -v "$starter:/src:ro" "$image" bash -lc "cp -r /src ~/p && cd ~/p && ($build) && test -s $out" \
  > "$tmp/build.log" 2>&1 || { tail -40 "$tmp/build.log"; fail "starter build"; }
ok "starter builds ($out)"
if [ "$family" = stm32 ]; then  # a challenge's own Makefile in src/ (kind make, as project.zip lays it out)
  docker run --rm -v "$root/tests/fixtures/stm32-make:/src:ro" "$image" bash -lc "cp -r /src ~/p && cd ~/p && picodev build && test -s src/build/firmware.hex" \
    > "$tmp/make.log" 2>&1 || { tail -40 "$tmp/make.log"; fail "Makefile project build"; }
  ok "a Makefile project in src/ builds (src/build/firmware.hex)"
fi

# 3. Remote-SSH: no key -> refuses to start; a key -> login with the image tools on PATH.
code=0; docker run --rm "$image" >/dev/null 2>&1 || code=$?
[ $code = 64 ] || fail "sshd without a key: exit $code, expected 64"
ssh-keygen -q -t ed25519 -N '' -f "$tmp/key"
docker run -d --name $name -p 127.0.0.1::22 -e SSH_AUTHORIZED_KEYS="$(cat "$tmp/key.pub")" "$image" >/dev/null
port=$(docker port $name 22/tcp | head -1 | sed 's/.*://')
s="ssh -p $port -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes -o LogLevel=ERROR -o ConnectTimeout=5"
i=0; until $s -i "$tmp/key" picodev@127.0.0.1 true 2>/dev/null; do
  i=$((i+1)); [ $i -lt 30 ] || { docker logs $name; fail "ssh login with the key"; }; sleep 1
done
$s -i "$tmp/key" picodev@127.0.0.1 "command -v $tool" >/dev/null || fail "$tool not on PATH over SSH (non-interactive)"
$s -i "$tmp/key" picodev@127.0.0.1 "bash -lc 'command -v $tool'" >/dev/null || fail "$tool not on PATH over SSH (login shell)"
ok "ssh with the key, $tool on PATH"
! $s -i "$tmp/key" root@127.0.0.1 true 2>/dev/null || fail "root login allowed"
ssh-keygen -q -t ed25519 -N '' -f "$tmp/other"
! $s -i "$tmp/other" picodev@127.0.0.1 true 2>/dev/null || fail "unknown key accepted"
methods=$($s -v -o PubkeyAuthentication=no picodev@127.0.0.1 true 2>&1 | sed -n 's/.*Authentications that can continue: //p' | tr -d '\r' | sort -u)
[ "$methods" = publickey ] || fail "server offers '$methods', expected publickey only"
ok "root, unknown key and password refused"

# 4. Dev Containers mode: the starter's devcontainer.json, pointed at this image.
if [ "$family" != base ] && command -v npx >/dev/null; then
  dc="npx -y @devcontainers/cli@0.89.0"
  cp -r "$starter" "$tmp/$name"
  sed -i "s#\"image\": \"[^\"]*\"#\"image\": \"$image\"#" "$tmp/$name/.devcontainer/devcontainer.json"
  $dc up --workspace-folder "$tmp/$name" --id-label picodev-test=$name > "$tmp/up.log" 2>&1 || { tail -20 "$tmp/up.log"; fail "devcontainer up"; }
  $dc exec --workspace-folder "$tmp/$name" --id-label picodev-test=$name bash -c "id -un && $build && test -s $out" > "$tmp/dc.log" 2>&1 \
    || { tail -40 "$tmp/dc.log"; fail "build in the dev container"; }
  head -1 "$tmp/dc.log" | grep -qx picodev || fail "dev container user is $(head -1 "$tmp/dc.log"), expected picodev"
  docker rm -f $(docker ps -aq --filter label=picodev-test=$name) >/dev/null
  ok "devcontainer up, starter builds as picodev"
else
  echo "skip: Dev Containers mode (needs npx)"
fi

size=$(docker image inspect -f '{{.Size}}' "$image")
disk=$(docker image ls --format '{{.Size}}' "$image")
echo "size: $image $(awk "BEGIN {printf \"%.2f\", $size/1e9}") GB compressed (download), $disk in the local store"
