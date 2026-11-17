#!/usr/bin/env bash
# PreToolUse guard for the Bash tool. Blocks (exit 2) commands that destroy
# data or silently target production:
#   - docker compose/stack down -v|--volumes, docker volume rm|remove|prune
#   - any wrangler command while CLOUDFLARE_ENV is set
#   - wrangler d1 execute / migrations apply without --local
#
# Unlike the other hooks here, this one is a policy control, so it fails
# closed: if the hook input cannot be read, the command is blocked.
#
# Matching uses bash's own [[ =~ ]] (POSIX ERE) on purpose. The previous inline
# version used `grep -P`, which stock macOS grep rejects, so the guard never
# fired there.

block() {
  echo "BLOCKED: $*" >&2
  exit 2
}

# The command is at .tool_input.command. Anything else means the input shape
# is not what this guard was written for.
if ! cmd="$(jq -er '.tool_input.command | select(type == "string")' 2>/dev/null)"; then
  block "guard-bash.sh could not read .tool_input.command from the hook input (is jq installed?). Refusing to run unchecked."
fi

# A word boundary, since ERE has no \b.
nw='[^[:alnum:]_]'
sp='[[:space:]]'

docker_down="docker${sp}+(compose|stack)${sp}+(.*${nw})?down(${nw}.*)?(-v|--volumes)(${nw}|\$)"
docker_volume="docker${sp}+volume${sp}+(rm|remove|prune)(${nw}|\$)"
if [[ "${cmd}" =~ ${docker_down} || "${cmd}" =~ ${docker_volume} ]]; then
  block "destructive Docker volume command. Volumes hold persistent data and removal is irreversible. Ask the user before running this."
fi

wrangler="(^|${nw})wrangler(${sp}|\$)"
if [[ -n "${CLOUDFLARE_ENV:-}" && "${cmd}" =~ ${wrangler} ]]; then
  block "CLOUDFLARE_ENV=${CLOUDFLARE_ENV} is set, so wrangler may silently target that environment. Unset it and use explicit --env flags instead."
fi

# The greedy (.*) picks the LAST wrangler that is still followed by a d1
# execute/migrations apply, so BASH_REMATCH[2] is the shortest such tail. If
# even that tail has no --local, some wrangler d1 call here is not local.
wrangler_d1="(.*)wrangler${sp}(.*d1${sp}+(execute|migrations${sp}+apply).*)"
if [[ "${cmd}" =~ ${wrangler_d1} && "${BASH_REMATCH[2]}" != *--local* ]]; then
  block "wrangler d1 execute/migrations apply without --local targets production. Run the command manually with --remote after reviewing."
fi

exit 0
