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

# Quotes and backslashes removed, so "docker" 'volume' rm and w\rangler still
# match. This can only add matches, never hide one. tr, not ${cmd//...}: that
# substitution is quadratic in bash 3.2 (minutes on a 300KB command).
plain="$(printf '%s' "${cmd}" | tr -d "\"'\\\\")"

docker_down="docker${sp}+(compose|stack)${sp}+(.*${nw})?down(${nw}.*)?(-v|--volumes)(${nw}|\$)"
docker_volume="docker${sp}+volume${sp}+(rm|remove|prune)(${nw}|\$)"
if [[ "${plain}" =~ ${docker_down} || "${plain}" =~ ${docker_volume} ]]; then
  block "destructive Docker volume command. Volumes hold persistent data and removal is irreversible. Ask the user before running this."
fi

# No wrangler anywhere: nothing left to check, and the per-character walk
# below is skipped for long unrelated commands.
[[ "${plain}" == *wrangler* ]] || exit 0

# wrangler, optionally with a version (npx wrangler@3 ...).
wrangler_tok="(^|${nw})wrangler(@[^[:space:]]*)?"
if [[ -n "${CLOUDFLARE_ENV:-}" && "${plain}" =~ ${wrangler_tok}(${sp}|\$) ]]; then
  block "CLOUDFLARE_ENV=${CLOUDFLARE_ENV} is set, so wrangler may silently target that environment. Unset it and use explicit --env flags instead."
fi

# Each simple command is judged on its own, so `... --remote && echo --local`
# cannot borrow a --local from a neighbour.
#   full: the segment with quotes removed but their content kept (detection)
#   bare: the segment with quoted text dropped, so --local inside a quoted
#         string (an SQL literal, an echo) does not count as the flag
wrangler_d1="${wrangler_tok}${sp}(.*${sp})?d1${sp}+(execute|migrations${sp}+apply)(${sp}|\$)"
# The same invocation followed by a standalone --local, all of it unquoted.
wrangler_d1_local="${wrangler_d1}(.*${sp})?--local(${sp}|\$)"
# --local must be followed by another option, a redirect or nothing. wrangler's
# option parser (yargs) reads a word after a boolean flag as its value, so
# `--local false`, `--local $X` and the like are not provably local.
not_local="${sp}(--remote|--no-local|--local=|--local${sp}+([^-<>0-9[:space:]]|[0-9]+[^<>0-9]))"
check_segment() {
  local full=" $1 " bare="$2"
  [[ "${full}" =~ ${wrangler_d1} ]] || return 0
  # Looked for in full, so quoting the flag does not hide it.
  if [[ "${full}" =~ ${not_local} ]]; then
    block "wrangler d1 execute/migrations apply with --remote, --no-local, --local=... or a value after --local may target production. Run the command manually after reviewing."
  fi
  # Matched against bare: a wrangler call that only exists inside quoted text
  # (sh -c '...', eval) or a --local that is quoted or sits before wrangler
  # does not count.
  if ! [[ "${bare}" =~ ${wrangler_d1_local} ]]; then
    block "wrangler d1 execute/migrations apply without an unquoted, standalone --local after it targets production. Write it as: wrangler d1 execute <db> --local ... (flag before any quoted argument), or run it manually with --remote after reviewing."
  fi
}

# Nothing that looks like a wrangler d1 write anywhere in the command: done.
# This loose match over the whole command is a superset of the per-segment
# match in check_segment.
wrangler_d1_loose="wrangler.*d1${sp}+(execute|migrations${sp}+apply)"
[[ "${plain}" =~ ${wrangler_d1_loose} ]] || exit 0

# The walk below is quadratic in bash 3.2 (13s on a 60KB command), so a long
# command that contains a wrangler d1 write is blocked instead of analysed.
max_len=4000
if ((${#cmd} > max_len)); then
  block "wrangler d1 execute/migrations apply inside a command longer than ${max_len} characters; too long to check. Run it on its own (use --file for long SQL)."
fi

# Byte-wise from here on: the delimiters are all ASCII, and in a UTF-8 locale
# bash 3.2 makes each ${cmd:i:1} cost O(i).
LC_ALL=C
full="" bare="" quote="" ch=""
for ((i = 0; i < ${#cmd}; i++)); do
  ch="${cmd:i:1}"
  if [[ -n "${quote}" ]]; then
    if [[ "${ch}" == "${quote}" ]]; then
      quote=""
    elif [[ "${quote}" == '"' && "${ch}" == "\\" ]]; then
      ((i++))
      full+="${cmd:i:1}"
    else
      full+="${ch}"
    fi
    continue
  fi
  case "${ch}" in
    "\\")
      ((i++))
      full+="${cmd:i:1}"
      bare+="${cmd:i:1}"
      ;;
    '"' | "'") quote="${ch}" ;;
    $'\n' | ';' | '&' | '|' | '(' | ')' | '`')
      check_segment "${full}" "${bare}"
      full="" bare=""
      ;;
    *)
      full+="${ch}"
      bare+="${ch}"
      ;;
  esac
done
if [[ -n "${quote}" && "${full}" =~ ${wrangler_d1} ]]; then
  block "wrangler d1 command with an unterminated quote; cannot tell what it targets."
fi
check_segment "${full}" "${bare}"

exit 0
