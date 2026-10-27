#!/bin/sh
# tests/test-vscode-server.sh <family> <image>: what VS Code Remote-SSH does on
# connection, by hand: over SSH, fetch the VS Code server and install the
# extensions of the starter's devcontainer.json. Checks that each one installs
# on this image (marketplace, platform build, glibc); not that it activates,
# which needs a VS Code window.
set -eu
family=$1 image=$2
root=$(cd "$(dirname "$0")/.." && pwd)
tmp=$(mktemp -d)
name=picodev-vscode-$family-$$
trap 'docker rm -f $name >/dev/null 2>&1 || true; rm -rf "$tmp"' EXIT

exts=$(python3 -c '
import json, re, sys
text = re.sub(r"^\s*//.*$", "", open(sys.argv[1]).read(), flags=re.M)
print(" ".join(json.loads(text)["customizations"]["vscode"]["extensions"]))' "$root/starters/$family/.devcontainer/devcontainer.json")

ssh-keygen -q -t ed25519 -N '' -f "$tmp/key"
docker run -d --name $name -p 127.0.0.1::22 -e SSH_AUTHORIZED_KEYS="$(cat "$tmp/key.pub")" "$image" >/dev/null
port=$(docker port $name 22/tcp | head -1 | sed 's/.*://')
s="ssh -p $port -i $tmp/key -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes -o LogLevel=ERROR"
i=0; until $s picodev@127.0.0.1 true 2>/dev/null; do i=$((i+1)); [ $i -lt 30 ] || exit 1; sleep 1; done

arch=$(docker image inspect -f '{{.Architecture}}' "$image"); [ "$arch" = amd64 ] && arch=x64
$s picodev@127.0.0.1 "set -e; mkdir -p ~/.vscode-server/test && cd ~/.vscode-server/test
  curl -fsSL https://update.code.visualstudio.com/latest/server-linux-$arch/stable | tar -xz --strip-components=1
  ./bin/code-server --version | head -1
  for e in $exts; do ./bin/code-server --install-extension \$e >/dev/null 2>&1 && echo \"ok: \$e\" || echo \"FAIL: \$e\"; done
  ./bin/code-server --list-extensions --show-versions" | tee "$tmp/out"
! grep -q '^FAIL' "$tmp/out"
