#!/usr/bin/env bash
# Run one `opencode run` review call inside a locked-down Docker container.
#
# Why: opencode v2.1.4's `execute` tool runs model-written JavaScript, and no
# permission or tools key stops it (2026-10-27, PR #886). The model reads an
# untrusted PR, so treat every call as running hostile code. The container:
#   - has its own network namespace: host services bound to 127.0.0.1 (the host
#     opencode service, engram, pihole, cups) are unreachable. Outbound internet
#     stays open, because the model API needs it;
#   - sees no host files except the opencode binary (ro), the CA certs (ro) and
#     the locked config (ro). HOME is a throwaway dir with an EMPTY auth.json:
#     the free `opencode/*` models need no credentials, so there is nothing to
#     steal. No global config, plugins or MCP servers are loaded;
#   - has a read-only root, no capabilities, no-new-privileges, runs as the
#     caller's uid, and has pid and memory limits.
#
# Usage: opencode-sandbox.sh <container-name> <locked-config.json> <opencode run args...>
# Prints opencode's output on stdout/stderr; stdin is closed (a non-interactive
# run auto-rejects "ask" permissions instead of waiting on stdin).
set -euo pipefail
NAME="${1:?usage: opencode-sandbox.sh <container-name> <locked-config> <args...>}"
LOCKED_CONFIG="$(readlink -f "${2:?locked config}")"
shift 2
OPENCODE_BIN="$(readlink -f "$(command -v opencode)")"
IMAGE="${OPENCODE_SANDBOX_IMAGE:-ubuntu:24.04}"
DOCKER=(docker --context "${OPENCODE_SANDBOX_DOCKER_CONTEXT:-default}")

SB="$(mktemp -d)"
trap 'rm -rf "$SB"' EXIT
mkdir -p "$SB/.local/share/opencode" "$SB/.local/state" "$SB/.config/opencode" "$SB/.cache"
echo '{}' > "$SB/.local/share/opencode/auth.json"

"${DOCKER[@]}" run --rm --name "$NAME" \
  --network bridge \
  --read-only --cap-drop ALL --security-opt no-new-privileges \
  --pids-limit 256 --memory 2g \
  --user "$(id -u):$(id -g)" \
  --tmpfs /tmp:rw,nosuid,nodev,size=256m \
  --tmpfs /work:rw,nosuid,nodev,size=64m \
  -v "$SB:/sbhome:rw" \
  -v "$OPENCODE_BIN:/opt/opencode/opencode:ro" \
  -v "$LOCKED_CONFIG:/sbhome/locked-config.json:ro" \
  -v /etc/ssl/certs:/etc/ssl/certs:ro \
  -w /work \
  -e HOME=/sbhome \
  -e XDG_CONFIG_HOME=/sbhome/.config \
  -e XDG_DATA_HOME=/sbhome/.local/share \
  -e XDG_CACHE_HOME=/sbhome/.cache \
  -e XDG_STATE_HOME=/sbhome/.local/state \
  -e TERM=dumb \
  -e OPENCODE_CONFIG=/sbhome/locked-config.json \
  "$IMAGE" /opt/opencode/opencode run "$@" </dev/null
