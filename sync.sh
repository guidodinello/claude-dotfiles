#!/bin/bash
# Dotfiles sync
# Symlinks config files from this repo into a Claude config directory, and
# merges the shared settings base into that directory's settings.json.
# Safe to re-run any time to pick up new/updated files after a `git pull`.
#
# Usage:
#   ./sync.sh                     # sync ~/.claude plus every marked ~/.claude-* profile
#   ./sync.sh ~/.claude-work      # sync only that CLAUDE_CONFIG_DIR, and mark it as a target
#   ./sync.sh --check             # read-only: report prerequisites and link problems, exit 1 if any
#   ./sync.sh --relink            # also move links that point into another checkout that still exists
#
# A run exits non-zero when any config dir's links do not match this repo's
# tracked files afterwards.
#
# settings.json is NOT symlinked: it is generated per config dir by merging
# settings.base.json with the keys Claude Code writes at runtime, so each dir
# keeps its own autoMode/enabledPlugins state instead of sharing one file.

set -e

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_SRC="${DOTFILES_DIR}/.claude"
OPENCODE_SRC="${DOTFILES_DIR}/.config/opencode"
OPENCODE_DST="${HOME}/.config/opencode"

# Keys owned by the config dir, not the repo. Claude Code and installers write
# these at runtime (learned auto-mode environment, plugin toggles, the output
# style gentle-ai sets); a sync must not clobber them, and they must not leak
# between the personal and work dirs.
LOCAL_KEYS=("autoMode" "enabledPlugins" "outputStyle")

# Lists that both the repo and installers write to: Orca and herdr register
# hooks, gentle-ai adds engram permissions and secret-file deny rules. Hooks
# (per event) and these permission lists are unioned with the live file instead
# of replaced, so a sync never drops an installer's entry. The cost: removing an
# entry from the base does not remove it from an existing config dir, unless
# its command is listed in RETIRED_HOOK_COMMANDS (hooks) or
# RETIRED_PERMISSION_RULES (permission rules) below.
UNION_PERMISSIONS='["allow","deny","ask","additionalDirectories"]'

# Permission rules that must leave the live file. Same mechanism as the retired
# hooks: merge_settings strips these from every UNION_PERMISSIONS list before the
# union. Entries are exact rule strings. Keep them listed once retired.
# All of these re-deny .env.example (or cannot be carved out of) next to base's
# `Read(.env*)` / `Edit(.env*)` plus its `!` carve-outs: a `!` rule only carves
# out of rules listed BEFORE it, and the union puts live extras after base.
#   - Edit(**/.env), Bash(echo * > *.env*), Bash(echo * >> *.env*): replaced by
#     Edit(.env*) and the base's Bash redirect rules. A broad `*.env.*` redirect
#     rule would also block `> .env.example` and a Bash rule cannot be carved
#     out, so base lists the real-file names (.env.local, .env.production, ...).
#   - Read(.env), Read(.env.*), Edit(.env), Edit(.env.*): added by gentle-ai,
#     redundant with .env*.
RETIRED_PERMISSION_RULES=(
    'Edit(**/.env)'
    'Bash(echo * > *.env*)'
    'Bash(echo * >> *.env*)'
    'Read(.env)'
    'Read(.env.*)'
    'Edit(.env)'
    'Edit(.env.*)'
)

# Hook commands that were removed from settings.base.json on purpose. To retire
# a hook, delete it from the base AND add its exact command here: merge_settings
# strips these from the live file before the union, so the old entry is not
# kept next to the new one. Keep entries listed (they are harmless once gone).
#   "rtk hook claude" - its rewrite voids auto-mode verdicts (Issue 389).
RETIRED_HOOK_COMMANDS=("rtk hook claude")
# The two inline Bash guards (Docker volumes, wrangler), replaced by
# hooks/guard-bash.sh: they read .command instead of .tool_input.command and
# used `grep -P`, so they never fired. And the inline JSON lint, replaced by
# hooks/json-lint.sh: it read $CLAUDE_FILE_PATH, which Claude Code does not
# set. One command per line, read literally.
while IFS= read -r retired_cmd; do
    RETIRED_HOOK_COMMANDS+=("${retired_cmd}")
done <<'RETIRED'
cmd=$(cat | jq -r '.command // ""'); if echo "$cmd" | grep -qP 'docker\s+(compose|stack)\s+.*\bdown\b.*(-v|--volumes)\b|docker\s+volume\s+(rm|remove|prune)\b'; then echo "BLOCKED: destructive Docker volume command. Volumes hold persistent data and removal is irreversible. Ask the user before running this."; exit 2; fi
cmd=$(cat | jq -r '.command // ""'); if [ -n "$CLOUDFLARE_ENV" ] && echo "$cmd" | grep -qP 'wrangler(\s+|$)'; then echo "BLOCKED: CLOUDFLARE_ENV=$CLOUDFLARE_ENV is set — wrangler may silently target that environment. Unset it and use explicit --env flags instead."; exit 2; fi; if echo "$cmd" | grep -qP 'wrangler(\s+|$)(?=.*d1\s+(?:execute|migrations\s+apply))(?!.*--local)'; then echo "BLOCKED: wrangler d1 execute/migrations apply without --local targets production. Run the command manually with --remote after reviewing."; exit 2; fi
if [[ $CLAUDE_FILE_PATH == *.json ]]; then jq . "$CLAUDE_FILE_PATH" > /dev/null || echo "Warning: $CLAUDE_FILE_PATH is not valid JSON"; fi
RETIRED

# shellcheck source=lib/link.sh
source "${DOTFILES_DIR}/lib/link.sh"

CHECK_ONLY=0
TARGET_ARG=""
for arg in "$@"; do
    case "${arg}" in
        --check) CHECK_ONLY=1 ;;
        --relink) RELINK=1 ;;
        -*) log_err "Unknown option: ${arg} (usage: ./sync.sh [--check] [--relink] [dir])"; exit 2 ;;
        *)
            if [ -n "${TARGET_ARG}" ]; then
                log_err "Only one config dir can be given (usage: ./sync.sh [--check] [--relink] [dir])"
                exit 2
            fi
            TARGET_ARG="${arg}"
            ;;
    esac
done

# --check reports a missing jq instead of dying on it.
if [ "${CHECK_ONLY}" -eq 0 ]; then
    command -v jq >/dev/null 2>&1 || { log_err "jq is required but not installed."; exit 1; }
fi

# How many timestamped settings.json backups to keep per config dir.
KEEP_SETTINGS_BACKUPS=3

# Each changed merge leaves a settings.json.bak-YYYYMMDD-HHMMSS behind. Keep
# the newest KEEP_SETTINGS_BACKUPS and delete older ones. Only that exact name
# shape is touched: backups made by hand or by other tools (.bak,
# .bak-engram, ...) are not ours to delete.
prune_settings_backups() {
    local dst="$1" d='[0-9]' backups=() f
    while IFS= read -r f; do
        backups+=("${f}")
    done < <(find "${dst}" -maxdepth 1 -type f \
        -name "settings.json.bak-${d}${d}${d}${d}${d}${d}${d}${d}-${d}${d}${d}${d}${d}${d}" | sort)

    local excess=$(( ${#backups[@]} - KEEP_SETTINGS_BACKUPS )) i
    for (( i = 0; i < excess; i++ )); do
        rm "${backups[i]}"
        log_info "Removed old backup: $(display_path "${backups[i]}")"
    done
}

# A `Read(!.env.example)` carve-out only carves out of relative deny rules listed
# BEFORE it. Two ways an env deny can re-block .env.example for good:
#   - A relative rule (`.env*`, `**/.env.local`) listed after the carve-outs: the
#     union puts live-only entries after base's, so an installer's env deny can
#     land there.
#   - An anchored rule (`//` or `~/`) that globs after `.env` (`.env*`, `.env.*`),
#     at ANY position: Claude Code reads a `!` pattern relative to the current
#     directory even when `~/` or `//` follows it, so no carve-out reaches it.
#     Anchored rules that list real-file names (`//**/.env.local`) match no
#     example file and are fine.
# Fail closed but loud: keep the rule and warn, naming it, so it can be added to
# RETIRED_PERMISSION_RULES. Takes the merged settings JSON; runs on every sync.
warn_shadowed_carve_outs() {
    local rule
    while IFS= read -r rule; do
        [ -n "${rule}" ] || continue
        log_warn "Deny rule ${rule} is listed after the .env.example carve-outs, so .env.example stays blocked until it is added to RETIRED_PERMISSION_RULES in sync.sh."
    done < <(jq -r '
        (.permissions.deny // []) as $deny
        | ([$deny | to_entries[] | select(.value | test("^(Read|Edit)\\(!")) | .key] | min) as $first
        | if $first == null then empty
          else $deny | to_entries[]
               | select(.key > $first and (.value | test("^(Read|Edit)\\((\\*\\*/)?\\.env")))
               | .value
          end' <<<"$1")
    while IFS= read -r rule; do
        [ -n "${rule}" ] || continue
        log_warn "Deny rule ${rule} is anchored (// or ~/) and globs after .env, so no carve-out can reach it and .env.example stays blocked everywhere. Narrow it to real-file names or add it to RETIRED_PERMISSION_RULES in sync.sh."
    done < <(jq -r '
        (.permissions.deny // [])[]
        | select(test("^(Read|Edit)\\((~/|//)[^)]*\\.env(\\*|\\.\\*)\\)$"))' <<<"$1")
}

# Merge settings.base.json into <dst>/settings.json, preserving LOCAL_KEYS from
# whatever is already there. {{CONFIG_DIR}} resolves to the destination dir so
# each config dir points at its own symlinked scripts.
merge_settings() {
    local dst="$1"
    local base="${CLAUDE_SRC}/settings.base.json"
    local current="${dst}/settings.json"

    if [ ! -f "${base}" ]; then
        log_warn "No settings.base.json - skipping settings merge."
        return
    fi

    # Read the local keys FIRST: in the old layout this path is a symlink into
    # the repo, and Claude Code wrote runtime keys back through it. Reading
    # follows the link; removing it before reading would discard that state.
    local live_json="{}"
    if [ -f "${current}" ]; then
        if ! jq empty "${current}" 2>/dev/null; then
            log_err "${current} is not valid JSON - refusing to overwrite it."
            return 1
        fi
        live_json="$(jq . "${current}")"
    fi
    local local_keys_json
    local_keys_json="$(printf '%s\n' "${LOCAL_KEYS[@]}" | jq -R . | jq -s .)"

    # Now drop the legacy symlink so the generated file is real and per-dir.
    if [ -L "${current}" ]; then
        log_warn "Replacing legacy settings.json symlink with a generated file"
        cp "${current}" "${current}.bak-$(date +%Y%m%d-%H%M%S)"
        rm "${current}"
    fi

    local retired_json
    # select(length > 0): an empty array prints one blank line, which must not
    # become [""] and match every hook that has no command.
    retired_json="$(printf '%s\n' "${RETIRED_HOOK_COMMANDS[@]}" | jq -R 'select(length > 0)' | jq -s .)"
    local retired_perms_json
    retired_perms_json="$(printf '%s\n' "${RETIRED_PERMISSION_RULES[@]}" | jq -R 'select(length > 0)' | jq -s .)"

    local merged
    merged="$(jq -n \
        --argjson base "$(sed "s|{{CONFIG_DIR}}|${dst}|g" "${base}")" \
        --argjson live "${live_json}" \
        --argjson localKeys "${local_keys_json}" \
        --argjson retired "${retired_json}" \
        --argjson retiredPerms "${retired_perms_json}" \
        --argjson unionPerms "${UNION_PERMISSIONS}" '
        def union($a; $b): reduce ($b // [])[] as $x (($a // []);
            if any(.[]; . == $x) then . else . + [$x] end);
        # Strip retired permission rules from the live lists before the union.
        def unretire_perms:
            if (.permissions | type) == "object" then
                .permissions |= with_entries(
                    if ((.key as $k | $unionPerms | index($k)) != null) and (.value | type) == "array"
                    then .value |= map(select(IN($retiredPerms[]) | not))
                    else . end)
            else . end;
        # Strip retired commands from one event entry. Drop the entry only when
        # the strip emptied it; entries that were already empty, or are not
        # shaped like {hooks: [...]}, pass through untouched.
        def unretire_entry:
            if type == "object" and (.hooks | type) == "array" then
                (.hooks | length) as $n
                | .hooks |= map(select((type == "object" and ((.command // "") | IN($retired[]))) | not))
                | if $n > 0 and (.hooks | length) == 0 then empty else . end
            else . end;
        def unretire:
            if (.hooks | type) == "object" then
                .hooks |= with_entries(.value |= (if type == "array" then map(unretire_entry) else . end))
            else . end;
        ($live | unretire | unretire_perms) as $live
        | ($live | with_entries(select(.key as $k | $localKeys | index($k)))
               | with_entries(select(.value != null))) as $own
        | ($base * $own)
        | .hooks = (reduce ((($base.hooks // {}) + ($live.hooks // {})) | keys[]) as $ev
            ({}; .[$ev] = union($base.hooks[$ev]; $live.hooks[$ev])))
        | reduce $unionPerms[] as $p (.;
            (union($base.permissions[$p]; $live.permissions[$p])) as $u
            | if ($u | length) > 0 then .permissions[$p] = $u else . end)
        | if .hooks == {} then del(.hooks) else . end')"

    warn_shadowed_carve_outs "${merged}"

    if [ -f "${current}" ] && [ "$(jq -S . <<<"${merged}")" = "$(jq -S . "${current}")" ]; then
        log_info "settings.json already up to date"
        return
    fi

    if [ -f "${current}" ]; then
        cp "${current}" "${current}.bak-$(date +%Y%m%d-%H%M%S)"
        log_warn "Backed up previous settings.json"
    fi

    printf '%s\n' "${merged}" > "${current}"
    log_info "Merged settings.json (preserved: ${LOCAL_KEYS[*]})"
    prune_settings_backups "${dst}"
}

# Read-only report for `./sync.sh --check`: required tools, soft prerequisites,
# and every link problem per target. Writes nothing (no mkdir, no marker, no
# settings merge, no prune). Exit 1 when a required tool is missing or any
# link problem exists.
run_check() {
    local status=0 tool dst expected targets=()

    for tool in jq python3 git; do
        if ! command -v "${tool}" >/dev/null 2>&1; then
            log_err "Required tool missing: ${tool}"
            status=1
        fi
    done

    if [ -n "${TARGET_ARG}" ]; then
        targets+=("${TARGET_ARG}")
    else
        while IFS= read -r dst; do
            targets+=("${dst}")
        done < <(config_dirs)
    fi

    expected="$(expected_rels "${CLAUDE_SRC}" skip)"
    for dst in "${targets[@]}"; do
        log_info "Checking config dir: ${dst}"
        if [ ! -d "${dst}" ]; then
            log_err "${dst} does not exist; run ./sync.sh to create it"
            status=1
            continue
        fi
        dst="$(cd "${dst}" && pwd)"
        grep -qs 'engram@' "${dst}/plugins/installed_plugins.json" ||
            log_warn "engram plugin not installed in ${dst} (the memory instructions assume it)"
        [ -f "${dst}/output-styles/gentleman.md" ] ||
            log_warn "gentleman output style not installed in ${dst} (update-gentle-ai.sh installs it)"
        verify_links "${CLAUDE_SRC}" "${dst}" ".claude" "${expected}" info || status=1
    done

    [ -d "${HOME}/.agents/skills" ] ||
        log_warn "$(display_path "${HOME}/.agents/skills") is missing (install ecosystem skills with npx skills)"

    if [ -z "${TARGET_ARG}" ]; then
        warn_unmarked_config_dirs
        if [ "${targets[0]}" = "${HOME}/.claude" ] && [ -d "${OPENCODE_SRC}" ]; then
            log_info "Checking config dir: ${OPENCODE_DST}"
            verify_links "${OPENCODE_SRC}" "${OPENCODE_DST}" ".config/opencode" \
                "$(expected_rels "${OPENCODE_SRC}")" info || status=1
        fi
    fi

    if [ "${status}" -eq 0 ]; then
        log_info "Check passed."
    else
        log_err "Check found problems; ./sync.sh fixes links (add --relink to move links held by another checkout)."
    fi
    return "${status}"
}

if [ "${CHECK_ONLY}" -eq 1 ]; then
    run_check
    exit $?
fi

# With an explicit target, sync only that dir and mark it as a target for later
# bare runs. Otherwise sync every config dir on this machine (see config_dirs in
# lib/link.sh).
CLAUDE_DSTS=()
if [ -n "${TARGET_ARG}" ]; then
    mkdir -p "${TARGET_ARG}"
    CLAUDE_DSTS+=("$(cd "${TARGET_ARG}" && pwd)")
    if [ "${CLAUDE_DSTS[0]}" != "${HOME}/.claude" ]; then
        write_config_marker "${CLAUDE_DSTS[0]}"
    fi
else
    mkdir -p "${HOME}/.claude"
    while IFS= read -r dir; do
        CLAUDE_DSTS+=("${dir}")
    done < <(config_dirs)
    warn_unmarked_config_dirs
fi

# Every dir is processed before the run fails, so one broken dir does not hide
# the state of the others.
LINK_FAILED=()
EXPECTED_CLAUDE="$(expected_rels "${CLAUDE_SRC}" skip)"

for CLAUDE_DST in "${CLAUDE_DSTS[@]}"; do
    log_info "Target config dir: ${CLAUDE_DST}"
    link_under "${CLAUDE_SRC}" "${CLAUDE_SRC}" "${CLAUDE_DST}" "skip"
    merge_settings "${CLAUDE_DST}"
    # After the merge: it converts a legacy settings.json symlink first.
    prune_links "${CLAUDE_SRC}" "${CLAUDE_DST}" ".claude" "${EXPECTED_CLAUDE}"
    verify_links "${CLAUDE_SRC}" "${CLAUDE_DST}" ".claude" "${EXPECTED_CLAUDE}" || LINK_FAILED+=("${CLAUDE_DST}")
done

# opencode lives at a fixed path, not per profile; sync it once, on runs
# that include the default ~/.claude.
if [ "${CLAUDE_DSTS[0]}" = "${HOME}/.claude" ] && [ -d "${OPENCODE_SRC}" ]; then
    EXPECTED_OPENCODE="$(expected_rels "${OPENCODE_SRC}")"
    link_under "${OPENCODE_SRC}" "${OPENCODE_SRC}" "${OPENCODE_DST}"
    prune_links "${OPENCODE_SRC}" "${OPENCODE_DST}" ".config/opencode" "${EXPECTED_OPENCODE}"
    verify_links "${OPENCODE_SRC}" "${OPENCODE_DST}" ".config/opencode" "${EXPECTED_OPENCODE}" || LINK_FAILED+=("${OPENCODE_DST}")
fi

if [ "${#LINK_FAILED[@]}" -gt 0 ]; then
    for failed_dst in "${LINK_FAILED[@]}"; do
        log_err "Links do not match the repo in: ${failed_dst}"
    done
    log_err "Install is broken (see the errors above); run ./sync.sh --check for the full picture."
    exit 1
fi

log_info "Done! Claude Code tools are ready in: ${CLAUDE_DSTS[*]}"
