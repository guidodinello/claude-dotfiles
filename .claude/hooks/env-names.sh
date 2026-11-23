# shellcheck shell=bash
# Name rules shared by guard-bash.sh and guard-env-files.sh. A sourced library,
# not a hook: it is never registered and has no exit codes of its own. Both
# guards source it from the directory of their own REAL path (symlinks
# followed), and block when it cannot be loaded, so the two guards judge a name
# with one definition, not two.
#
#   is_env_file <path>     0 when the basename is an env file that is not an
#                          example: starts with `.env` (.env, .env.local,
#                          .env.backup, .envrc) or ends in `.env` (prod.env).
#                          .env.example, .env.*.example, .env.sample and
#                          .env.template are allowed.
#   is_secret_path <path>  0 when the path is a secret file other than an env
#                          file: .dev.vars (and .dev.vars.*), anything under a
#                          .aws directory, a private SSH key (a *_rsa, *_dsa,
#                          *_ecdsa, *_ed25519, *_ecdsa_sk, *_ed25519_sk or
#                          *.pem file under a .ssh directory; the .pub files,
#                          config and known_hosts stay readable), and the
#                          .npmrc in the home directory.
#
# Both compare lowercased: macOS volumes are case-insensitive, so `.ENV` is the
# same file as `.env`.

_lowercase() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

# Lexical clean-up of a path, no file system access: `//` and `/./` collapse and
# `x/..` cancels, so `~//.`, `$HOME/./x/..` and `/home/me/../me` compare equal to
# the plain directory.
_normalize_path() {
  local p="$1" part abs="" out=() parts=() IFS=/
  [[ "${p}" == /* ]] && abs="/"
  read -r -a parts <<<"${p}"
  for part in "${parts[@]}"; do
    case "${part}" in
      "" | ".") ;;
      "..")
        if ((${#out[@]} > 0)) && [[ "${out[${#out[@]} - 1]}" != ".." ]]; then
          out=("${out[@]:0:${#out[@]}-1}")
        elif [[ -z "${abs}" ]]; then
          out+=("..")
        fi
        ;;
      *) out+=("${part}") ;;
    esac
  done
  printf '%s' "${abs}${out[*]}"
}

is_env_file() {
  local p="$1" name
  while [[ "${p}" == */ && "${p}" != "/" ]]; do p="${p%/}"; done
  name="$(printf '%s' "${p##*/}" | tr '[:upper:]' '[:lower:]')"
  case "${name}" in
    .env.example | .env.*.example | .env.sample | .env.template) return 1 ;;
    .env* | *.env) return 0 ;;
  esac
  return 1
}

is_secret_path() {
  local p dir name home
  p="$(_lowercase "$1")"
  while [[ "${p}" == */ && "${p}" != "/" ]]; do p="${p%/}"; done
  name="${p##*/}"

  case "${name}" in
    .dev.vars | .dev.vars.*) return 0 ;;
  esac

  # The leading and trailing slash let `.aws/credentials` (no parent) and the
  # directory itself match like `/home/me/.aws/credentials`.
  case "/${p}/" in
    */.aws/*) return 0 ;;
  esac

  case "${name}" in
    *_rsa | *_dsa | *_ecdsa | *_ed25519 | *_ecdsa_sk | *_ed25519_sk | *.pem)
      case "/${p}" in
        */.ssh/*) return 0 ;;
      esac
      ;;
  esac

  # Only the home directory's .npmrc: a project .npmrc holds registry settings.
  if [[ "${name}" == .npmrc && "${p}" == */* ]]; then
    dir="$(_normalize_path "${p%/*}")"
    home="$(_normalize_path "$(_lowercase "${HOME:-}")")"
    case "${dir}" in
      '~' | '$home' | '${home}') return 0 ;;
    esac
    [[ -n "${home}" && "${dir}" == "${home}" ]] && return 0
  fi
  return 1
}
