#!/usr/bin/env bash
# PreToolUse guard for the Bash tool. Blocks (exit 2) commands that destroy
# data, silently target production or name a secret file:
#   - docker compose/stack (or docker-compose) down with a volume flag, compose
#     rm and docker rm / container rm with a volume flag, docker system prune
#     --volumes, docker volume rm|remove|prune
#   - any wrangler command while CLOUDFLARE_ENV is set
#   - wrangler d1 execute / migrations apply without --local
#   - wrangler <anything> delete, wrangler d1 time-travel restore
#   - a command with a word that names an env file or another secret file (see
#     env-names.sh for the name rules, shared with guard-env-files.sh)
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

# env-names.sh (is_env_file, is_secret_path) sits next to this script's REAL
# path. ~/.claude/hooks/ holds per-file symlinks into the checkout, and after a
# `git pull` but before `./sync.sh` there is no env-names.sh link next to them,
# so the library is looked up from where the links point. readlink without -f:
# BSD readlink lacks it. If the library is missing or fails to load, block.
self="${BASH_SOURCE[0]}"
hops=0
while [[ -L "${self}" ]]; do
  ((hops++ >= 40)) && block "symlink chain from ${BASH_SOURCE[0]} is longer than 40 hops or loops. Refusing to run unchecked."
  link="$(readlink "${self}")" || block "could not follow the symlink ${self}. Refusing to run unchecked."
  if [[ "${link}" == /* ]]; then
    self="${link}"
  elif [[ "${self}" == */* ]]; then
    self="${self%/*}/${link}"
  else
    self="${link}"
  fi
done
libdir="."
[[ "${self}" == */* ]] && libdir="${self%/*}"
[[ -r "${libdir}/env-names.sh" ]] || block "env-names.sh not found next to ${self}. Refusing to run unchecked."
# shellcheck source=env-names.sh
source "${libdir}/env-names.sh" || block "could not load ${libdir}/env-names.sh. Refusing to run unchecked."

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

# Subcommands and flags are matched as whole words (whitespace on both sides),
# so `down.yml` or `--verbose` is not `down` or `-v`.
compose="(docker${sp}+(compose|stack)|docker-compose)"
# What may follow a word: whitespace, a shell metacharacter, `=` (--volumes=true)
# or the end. Not only whitespace: a prune followed by `;true` is still a prune.
end='([[:space:];&|()<>=`]|$)'
# -v, --volumes, or a short flag cluster containing v (-sfv, -tv).
vflag="(-v|--volumes|-[[:alpha:]]*v[[:alpha:]]*)${end}"
docker_down="${compose}${sp}+(.*${sp})?down${sp}(.*${sp})?${vflag}"
docker_compose_rm="${compose}${sp}+(.*${sp})?rm${sp}(.*${sp})?${vflag}"
docker_rm="docker${sp}+(container${sp}+)?rm${sp}(.*${sp})?${vflag}"
docker_prune="docker${sp}+system${sp}+prune${sp}(.*${sp})?--volumes${end}"
docker_volume="docker${sp}+volume${sp}+(rm|remove|prune)${end}"
if [[ "${plain}" =~ ${docker_down} || "${plain}" =~ ${docker_compose_rm} || "${plain}" =~ ${docker_rm} ||
  "${plain}" =~ ${docker_prune} || "${plain}" =~ ${docker_volume} ]]; then
  block "destructive Docker volume command. Volumes hold persistent data and removal is irreversible. Ask the user before running this."
fi

# A word that names an env file or another secret file. The words are the
# command with quotes removed, split on whitespace and on ; | & ( ) < > = , :
# and backticks, so `--env-file=.env`, open('x/.env') and `cat .env.backup` all
# yield the name. Not caught: a name built at runtime (.e$X, $F), a glob (.e*,
# .[e]nv), a file a script opens itself, a recursive grep over a directory, and
# SSH keys with custom names. A command line that holds none of the markers
# below skips the loop, which keeps long unrelated commands cheap.
lower="$(printf '%s' "${plain}" | tr '[:upper:]' '[:lower:]')"
case "${lower}" in
  *.env* | *.dev.vars* | *.aws* | *.ssh* | *.npmrc*)
    while IFS= read -r word; do
      case "${word}" in
        # Runtime objects, not files: `rg process.env src`, `import.meta.env`.
        # Only these exact words, and only when no file of that name exists in
        # the working directory; `x/process.env` is still a path.
        process.env | import.meta.env | deno.env | bun.env)
          [[ -e "${word}" ]] || continue
          ;;
        *.env* | *.dev.vars* | *.aws* | *.ssh* | *.npmrc*) ;;
        *) continue ;;
      esac
      if is_env_file "${word}" || is_secret_path "${word}"; then
        block "this command names an env or secret file (${word}). Real env and secret files hold secrets. Run it yourself with ! or ask the user."
      fi
    done < <(printf '%s\n' "${lower}" | tr ' \t;|&()<>=,:`' '\n')
    ;;
esac

# No wrangler anywhere: nothing left to check, and the per-character walk
# below is skipped for long unrelated commands.
[[ "${plain}" == *wrangler* ]] || exit 0

# wrangler, optionally with a version (npx wrangler@3 ...).
wrangler_tok="(^|${nw})wrangler(@[^[:space:]]*)?"
if [[ -n "${CLOUDFLARE_ENV:-}" && "${plain}" =~ ${wrangler_tok}(${sp}|\$) ]]; then
  block "CLOUDFLARE_ENV=${CLOUDFLARE_ENV} is set, so wrangler may silently target that environment. Unset it and use explicit --env flags instead."
fi

# Deletes and restores: any wrangler subcommand path with `delete` as a word
# (d1 delete, r2 bucket delete, kv namespace delete, secret delete, delete), and
# d1 time-travel restore, which overwrites a database with an earlier state.
wrangler_delete="${wrangler_tok}${sp}(.*${sp})?delete${end}"
wrangler_restore="${wrangler_tok}${sp}(.*${sp})?d1${sp}+time-travel${sp}+restore${end}"
if [[ "${plain}" =~ ${wrangler_delete} ]]; then
  block "wrangler delete removes a deployed or stored resource (Worker, D1, R2, KV, secret). Ask the user before running this."
fi
if [[ "${plain}" =~ ${wrangler_restore} ]]; then
  block "wrangler d1 time-travel restore overwrites the database with an earlier state. Ask the user before running this."
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
