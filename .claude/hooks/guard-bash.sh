#!/usr/bin/env bash
# PreToolUse guard for the Bash tool. Blocks (exit 2) commands that destroy
# data or silently target production:
#   - docker compose/stack (or docker-compose) down with a volume flag, compose
#     rm and docker rm / container rm with a volume flag, docker system prune
#     --volumes, docker volume rm|remove|prune
#   - any wrangler command while CLOUDFLARE_ENV is set
#   - wrangler d1 execute / migrations apply without --local
#   - wrangler <anything> delete, wrangler d1 time-travel restore
#
# It does not look at env or secret file names: a Bash command that reads an
# env file under a name the deny rules do not list, or through an interpreter,
# is not guarded here by owner decision. See docs/hooks.md.
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
# is not what this guard was written for. The -z check is needed because jq 1.6
# `-e` exits 0 on empty input (no output at all), so an empty stdin would pass.
if ! cmd="$(jq -er '.tool_input.command | select(type == "string")' 2>/dev/null)" || [[ -z "${cmd}" ]]; then
  block "guard-bash.sh could not read .tool_input.command from the hook input (is jq installed?). Refusing to run unchecked."
fi

# A word boundary, since ERE has no \b.
nw='[^[:alnum:]_]'
sp='[[:space:]]'

# Quotes and backslashes removed, so "docker" 'volume' rm and w\rangler still
# match. This can only add matches, never hide one. tr, not ${cmd//...}: that
# substitution is quadratic in bash 3.2 (minutes on a 300KB command).
plain="$(printf '%s' "${cmd}" | tr -d "\"'\\\\")"

# Nothing here concerns a command without docker or wrangler in it.
case "${plain}" in
  *docker* | *wrangler*) ;;
  *) exit 0 ;;
esac

# Subcommands and flags are matched as whole words (whitespace on both sides),
# so `down.yml` or `--verbose` is not `down` or `-v`.
compose="(docker${sp}+(compose|stack)|docker-compose)"
# What may follow a word: whitespace, a shell metacharacter, `=` (--volumes=true)
# or the end.
end='([[:space:];&|()<>=`]|$)'
# -v, --volumes, or a short flag cluster containing v (-sfv, -tv).
vflag="(-v|--volumes|-[[:alpha:]]*v[[:alpha:]]*)${end}"
docker_down="${compose}${sp}+(.*${sp})?down${sp}(.*${sp})?${vflag}"
docker_compose_rm="${compose}${sp}+(.*${sp})?rm${sp}(.*${sp})?${vflag}"
docker_rm="docker${sp}+(container${sp}+)?(rm|remove)${sp}(.*${sp})?${vflag}"
docker_prune="docker${sp}+system${sp}+prune${sp}(.*${sp})?--volumes${end}"
docker_volume="docker${sp}+volume${sp}+(rm|remove|prune)${end}"

# Judged on one simple command, or on the whole command when it is too long to
# split (below), so a `-v` that belongs to a neighbour, `docker run -v data:/d`
# after `docker rm c1 &&`, does not count.
check_docker() {
  [[ "$1" == *docker* ]] || return 0
  if [[ "$1" =~ ${docker_down} || "$1" =~ ${docker_compose_rm} || "$1" =~ ${docker_rm} ||
    "$1" =~ ${docker_prune} || "$1" =~ ${docker_volume} ]]; then
    block "destructive Docker volume command. Volumes hold persistent data and removal is irreversible. Ask the user before running this."
  fi
}

# wrangler, optionally with a version (npx wrangler@3 ...).
wrangler_tok="(^|${nw})wrangler(@[^[:space:]]*)?"
if [[ -n "${CLOUDFLARE_ENV:-}" && "${plain}" =~ ${wrangler_tok}(${sp}|\$) ]]; then
  block "CLOUDFLARE_ENV=${CLOUDFLARE_ENV} is set, so wrangler may silently target that environment. Unset it and use explicit --env flags instead."
fi

wrangler_restore="${wrangler_tok}${sp}(.*${sp})?d1${sp}+time-travel${sp}+restore${end}"
block_restore="wrangler d1 time-travel restore overwrites the database with an earlier state. Ask the user before running this."
block_delete="wrangler delete removes a deployed or stored resource (Worker, D1, R2, KV, secret). Ask the user before running this."

# `delete` as a wrangler subcommand word: one of the first four words after
# wrangler (d1 delete, kv namespace delete, pages deployment delete, delete).
# The scan ends at the first option, so `wrangler tail --search delete` and the
# SQL of `d1 execute ... --command "delete from t"` do not count. The options
# that take a value before the subcommand (--config x, --env x) are skipped.
check_wrangler_delete() {
  local words=() i j depth w
  [[ "$1" == *wrangler* ]] || return 0
  read -r -a words <<<"$1"
  for ((i = 0; i < ${#words[@]}; i++)); do
    w="${words[i]##*/}"
    [[ "${w}" == wrangler || "${w}" == wrangler@* ]] || continue
    depth=0
    for ((j = i + 1; j < ${#words[@]} && depth < 4; j++)); do
      case "${words[j]}" in
        delete) block "${block_delete}" ;;
        --config | -c | --cwd | --env | -e) ((j++)) ;;
        --*=*) ;;
        -*) break ;;
        *) ((depth++)) ;;
      esac
    done
  done
}

# wrangler d1 execute / migrations apply, which default to remote.
wrangler_d1="${wrangler_tok}${sp}(.*${sp})?d1${sp}+(execute|migrations${sp}+apply)(${sp}|\$)"
# The same invocation followed by a standalone --local, all of it unquoted.
wrangler_d1_local="${wrangler_d1}(.*${sp})?--local(${sp}|\$)"
# --local must be followed by another option, a redirect or nothing. wrangler's
# option parser (yargs) reads a word after a boolean flag as its value, so
# `--local false`, `--local $X` and the like are not provably local.
not_local="${sp}(--remote|--no-local|--local=|--local${sp}+([^-<>0-9[:space:]]|[0-9]+[^<>0-9]))"

# Each simple command is judged on its own, so `... --remote && echo --local`
# cannot borrow a --local from a neighbour.
#   full: the segment with quotes removed but their content kept (detection)
#   bare: the segment with quoted text dropped, so --local inside a quoted
#         string (an SQL literal, an echo) does not count as the flag
check_segment() {
  local full=" $1 " bare="$2"
  check_docker "${full}"
  check_wrangler_delete "${full}"
  if [[ "${full}" =~ ${wrangler_restore} ]]; then
    block "${block_restore}"
  fi
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

# The walk below is quadratic in bash 3.2 (13s on a 60KB command), so a command
# longer than this is not split into simple commands: it is judged as one piece
# (a Docker volume flag, a delete word or a restore anywhere in it blocks, as
# they did before the split) and a wrangler d1 write in it is blocked.
max_len=4000
if ((${#cmd} > max_len)); then
  check_docker "${plain}"
  wrangler_delete="${wrangler_tok}${sp}(.*${sp})?delete${end}"
  if [[ "${plain}" =~ ${wrangler_delete} ]]; then
    block "${block_delete}"
  fi
  if [[ "${plain}" =~ ${wrangler_restore} ]]; then
    block "${block_restore}"
  fi
  wrangler_d1_loose="wrangler.*d1${sp}+(execute|migrations${sp}+apply)"
  if [[ "${plain}" =~ ${wrangler_d1_loose} ]]; then
    block "wrangler d1 execute/migrations apply inside a command longer than ${max_len} characters; too long to check. Run it on its own (use --file for long SQL)."
  fi
  exit 0
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
