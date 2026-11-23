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
# settings.json is NOT symlinked: it is generated per config dir from
# settings.base.json plus what is local to that dir (LOCAL_KEYS and entries
# installers added), so each dir keeps its own autoMode/enabledPlugins state
# instead of sharing one file. See merge_settings.

set -e

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_SRC="${DOTFILES_DIR}/.claude"
OPENCODE_SRC="${DOTFILES_DIR}/.config/opencode"
OPENCODE_DST="${HOME}/.config/opencode"

# Keys owned by the config dir, not the repo. Claude Code and installers write
# these at runtime (learned auto-mode environment, plugin toggles, the output
# style gentle-ai sets, the /model and effort choices); a sync must not clobber
# them, and they must not leak between the personal and work dirs. The base
# value of a local key is only the default for a dir that has none. Any other
# live key is rebuilt from the base, and merge_settings names each one it
# drops or overrides. Not local on purpose: permissions.defaultMode (policy).
LOCAL_KEYS=("autoMode" "enabledPlugins" "outputStyle" "model" "effortLevel")

# Lists that both the repo and installers write to: Orca and herdr register
# hooks, gentle-ai adds engram permissions and secret-file deny rules. Hooks
# (per event) and these permission lists are unioned with the live file instead
# of replaced, so a sync never drops an installer's entry. Entries the last sync
# took from the base (recorded in the manifest, see MANIFEST_NAME) and the base
# no longer has are removed, and an edited hook replaces its old copy. A dir with
# no manifest yet subtracts nothing on its first sync; what must go from such a
# dir is listed in RETIRED_HOOK_COMMANDS (hooks, by command) or
# RETIRED_PERMISSION_RULES (permission rules) below, which always apply.
UNION_PERMISSIONS='["allow","deny","ask","additionalDirectories"]'

# Permission rules that must leave the live file. Same mechanism as the retired
# hooks: merge_settings strips these from every UNION_PERMISSIONS list before the
# union. Entries are exact rule strings. Keep them listed once retired. Deleting
# a rule from the base is enough on a dir that already has a manifest; list it
# here for a dir with no manifest yet and for rules an installer added that were
# never in the base.
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
# With a manifest, deleting the hook from the base is enough; the list covers a
# dir with no manifest yet and hooks an installer added that were never in the
# base.
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

# Where the last sync records which entries it took from settings.base.json, so
# the next sync can tell "ours, since removed from the base" from "added by an
# installer or the user". A regular file at the root of each config dir: the
# repo never contains it (so link_under/prune_dangling leave it alone) and
# Claude Code does not read it. Deleting it is safe: the merge then subtracts
# nothing, except what RETIRED_* lists.
MANIFEST_NAME=".sync-settings-manifest.json"

# The jq program behind merge_settings. Inputs (--argjson): base (rendered),
# live, manifest (object or null), localKeys, retired (hook commands),
# retiredPerms, unionPerms. It prints one object:
#   merged        the new settings.json
#   manifest      what this sync takes from the base (written after the merge)
#   removedRules  [{list, rule}]  rules the manifest says were ours, no longer in base
#   removedHooks  ["Event: command"]  same, for hooks
#   refuse        lists the manifest recorded but the base now lacks or empties
#                 ("permissions.deny", "hooks"): see merge_settings
#   dropped / overrode  live keys the merge discards / replaces (names only)
#   liveOnly      entries that stay because only the live file has them
read -r -d '' JQ_MERGE <<'JQ' || true
# Every inner hook with a non-empty command, as [event, matcher, command]. That
# triple is a hook's identity: an edit to the same hook keeps it.
def hook_ids:
    if type == "object" then
        [ to_entries[] | .key as $ev
          | (.value | if type == "array" then .[] else empty end)
          | select(type == "object") | (.matcher // "") as $m
          | (.hooks | if type == "array" then .[] else empty end)
          | select(type == "object" and (.command | type) == "string" and (.command | length) > 0)
          | [$ev, $m, .command] ]
    else [] end;
def union($a; $b): reduce ($b // [])[] as $x (($a // []);
    if any(.[]; . == $x) then . else . + [$x] end);
def objs: if type == "object" then . else {} end;
def lst: if type == "array" then . else [] end;

($base.permissions | objs) as $bp
| ($live.permissions | objs) as $lp
| ($manifest.permissions | objs) as $mp
| ($base.hooks | hook_ids) as $baseIds
| (($manifest.hooks // []) | map([.event, .matcher, .command])) as $manIds
# Rules the last sync wrote that the base no longer has.
| def gone($p): (($mp[$p] | lst) - ($bp[$p] | lst));

# Drop from one event entry every hook that is the base's (an edit replaces it),
# the manifest's (removed from the base) or retired. An entry goes only when
# the strip emptied it; one that was empty or is not {hooks: [...]} stays.
def strip_entry($ev; $ids):
    if type == "object" and (.hooks | type) == "array" then
        (.matcher // "") as $m | (.hooks | length) as $n
        | .hooks |= map(select((type == "object" and (.command | type) == "string" and (.command | length) > 0
              and (([$ev, $m, .command] | IN($ids[])) or (.command | IN($retired[])))) | not))
        | if $n > 0 and (.hooks | length) == 0 then empty else . end
    else . end;

($live
 | if (.hooks | type) == "object" then
       .hooks |= (with_entries(.key as $ev | .value |= (if type == "array" then [.[] | strip_entry($ev; $baseIds + $manIds)] else . end))
                  | with_entries(select((.value | type) != "array" or (.value | length) > 0)))
   else . end
 | if (.permissions | type) == "object" then
       .permissions |= with_entries(.key as $k
           | if ($unionPerms | index($k)) != null and (.value | type) == "array"
             then .value |= map(select((IN($retiredPerms[]) or IN(gone($k)[])) | not))
             else . end)
   else . end) as $l
| ($l.permissions | objs) as $lps
| ($l | with_entries(select(.key as $k | $localKeys | index($k))) | with_entries(select(.value != null))) as $own
| ($base * $own
   | .hooks = (reduce ((($base.hooks | objs) + ($l.hooks | objs)) | keys[]) as $ev
         ({}; .[$ev] = union($base.hooks[$ev]; $l.hooks[$ev])))
   | reduce $unionPerms[] as $p (.;
         (union($bp[$p]; $lps[$p])) as $u
         | if ($u | length) > 0 then .permissions[$p] = $u else . end)
   | if .hooks == {} then del(.hooks) else . end) as $merged
| (["hooks", "permissions"] + $localKeys) as $skip
| {
    merged: $merged,
    manifest: {
        version: 1,
        permissions: (reduce $unionPerms[] as $p ({}; .[$p] = ($bp[$p] | lst))),
        hooks: ($baseIds | map({event: .[0], matcher: .[1], command: .[2]}))
    },
    refuse: ([ $unionPerms[] as $p | select(($mp[$p] | lst | length) > 0 and ($bp[$p] | lst | length) == 0) | "permissions.\($p)" ]
             + (if (($manifest.hooks // []) | length) > 0 and ($baseIds | length) == 0 then ["hooks"] else [] end)),
    removedRules: [ $unionPerms[] as $p | ($lp[$p] | lst)[] | select(IN(gone($p)[])) | {list: $p, rule: .} ],
    removedHooks: [ ($live.hooks | hook_ids)[] | select(IN($manIds[]) and (IN($baseIds[]) | not)) | "\(.[0]): \(.[2])" ],
    dropped: ([ ($live | keys[]) as $k | select(($skip | index($k)) == null and ($base | has($k) | not)) | $k ]
              + [ ($lp | keys[]) as $k | select(($unionPerms | index($k)) == null and ($bp | has($k) | not)) | "permissions.\($k)" ]),
    overrode: ([ ($live | keys[]) as $k | select(($skip | index($k)) == null and ($base | has($k)) and $live[$k] != $base[$k]) | $k ]
               + [ ($lp | keys[]) as $k | select(($unionPerms | index($k)) == null and ($bp | has($k)) and $lp[$k] != $bp[$k]) | "permissions.\($k)" ]),
    liveOnly: (
        (reduce $unionPerms[] as $p ({}; .[$p] = [ ($lps[$p] | lst)[] | select(IN(($bp[$p] | lst)[]) | not) ]))
        + {hooks: [ ($l.hooks | objs) | to_entries[] | .key as $ev | (.value | lst)[]
                    | select(IN(($base.hooks[$ev] | lst)[]) | not)
                    | if type == "object" and (.hooks | type) == "array"
                      then .hooks[] | "\($ev): \(if type == "object" then (.command // "(no command)") else "(unrecognised)" end)"
                      else "\($ev): (no command)" end ] })
  }
JQ

# Resolve {{CONFIG_DIR}} in settings.base.json to <dst>. Literal in jq: no regex
# and no sed escaping, so a path with & or | is safe.
render_base() {
    jq --arg dir "$2" 'walk(if type == "string" then split("{{CONFIG_DIR}}") | join($dir) else . end)' "$1"
}

# Print the manifest of the last sync, or "null" when there is none or it is
# unusable (merge_settings warns; the merge then subtracts nothing).
read_manifest() {
    local file="$1/${MANIFEST_NAME}"
    if [ ! -f "${file}" ]; then
        echo null
        return 0
    fi
    if jq -e '.version == 1 and (.permissions | type) == "object"
              and ([.permissions[] | type == "array"] | all) and (.hooks | type) == "array"' \
        "${file}" >/dev/null 2>&1; then
        jq -c . "${file}"
    else
        echo null
    fi
}

# Write the manifest only when its content changed, so a no-op sync touches nothing.
write_manifest() {
    local dst="$1" manifest="$2" file="$1/${MANIFEST_NAME}"
    if [ -f "${file}" ] && [ "$(jq -S . <<<"${manifest}")" = "$(jq -S . "${file}" 2>/dev/null)" ]; then
        return 0
    fi
    printf '%s\n' "${manifest}" > "${file}"
}

# Name every entry the merge dropped on purpose. Removing a deny or ask rule, or
# a hook (a PreToolUse hook is a guard), loosens policy, so those are WARNs; a
# removed allow or additionalDirectories rule tightens it and is an INFO. Takes
# the jq result object.
report_removals() {
    local line list rule
    while IFS=$'\t' read -r list rule; do
        if [ "${list}" = deny ] || [ "${list}" = ask ]; then
            log_warn "Removed ${list} rule no longer in settings.base.json: ${rule}"
        else
            log_info "Removed ${list} rule no longer in settings.base.json: ${rule}"
        fi
    done < <(jq -r '.removedRules[] | "\(.list)\t\(.rule)"' <<<"$1")
    while IFS= read -r line; do
        log_warn "Removed hook no longer in settings.base.json: ${line}"
    done < <(jq -r '.removedHooks[]' <<<"$1")
}

# Live keys the merge discards or replaces, by name. Never the value: env may
# hold tokens.
report_key_changes() {
    local key
    while IFS= read -r key; do
        log_warn "Dropped live key: ${key}"
    done < <(jq -r '.dropped[]' <<<"$1")
    while IFS= read -r key; do
        log_warn "Overrode live key: ${key}"
    done < <(jq -r '.overrode[]' <<<"$1")
}

# One line with the counts of entries that only the live file has (installer or
# hand additions); SYNC_LIST_LIVE_ONLY=1 also lists each one.
report_live_only() {
    log_info "Live-only (not in settings.base.json): $(jq -r --argjson unionPerms "${UNION_PERMISSIONS}" \
        '[ $unionPerms[] as $p | "\($p) \(.liveOnly[$p] | length)" ] + ["hooks \(.liveOnly.hooks | length)"] | join(", ")' <<<"$1")"
    if [ "${SYNC_LIST_LIVE_ONLY:-}" = "1" ]; then
        local entry
        while IFS= read -r entry; do
            log_info "  live-only ${entry}"
        done < <(jq -r '.liveOnly | to_entries[] | .key as $k | .value[] | "\($k): \(.)"' <<<"$1")
    fi
}

# Merge settings.base.json into <dst>/settings.json: the base, plus what is
# genuinely local. LOCAL_KEYS are kept from the live file; permission lists and
# hooks are unioned, minus what the last sync took from the base and the base
# no longer has (see MANIFEST_NAME). Every other live key is dropped or
# overridden, and named in the log. Returns 1 without touching settings.json
# when it cannot decide (invalid live JSON, a failed merge, a base that lost a
# list the manifest recorded); the caller carries on with the other config dirs.
# Every step that decides or writes ends in `|| return 1`, because sync.sh calls
# this under `||`, which turns `set -e` off inside the function. A failure to
# write the manifest also returns 1, after settings.json was written. The
# reports, the carve-out warning and backup pruning are best effort: they never
# fail the merge.
merge_settings() {
    local dst="$1"
    local base="${CLAUDE_SRC}/settings.base.json"
    local current="${dst}/settings.json"

    if [ ! -f "${base}" ]; then
        log_warn "No settings.base.json - skipping settings merge."
        return 0
    fi

    # Read the live file FIRST: in the old layout this path is a symlink into
    # the repo, and Claude Code wrote runtime keys back through it. Reading
    # follows the link; removing it before reading would discard that state.
    local live_json="{}"
    if [ -f "${current}" ]; then
        if ! jq empty "${current}" 2>/dev/null; then
            log_err "${current} is not valid JSON - refusing to overwrite it."
            return 1
        fi
        live_json="$(jq . "${current}")" || return 1
    fi

    local rendered local_keys_json retired_json retired_perms_json manifest_json
    rendered="$(render_base "${base}" "${dst}")" || { log_err "Cannot read ${base}."; return 1; }
    local_keys_json="$(printf '%s\n' "${LOCAL_KEYS[@]}" | jq -R . | jq -s .)" || return 1
    # select(length > 0): an empty array prints one blank line, which must not
    # become [""] and match every hook that has no command.
    retired_json="$(printf '%s\n' "${RETIRED_HOOK_COMMANDS[@]}" | jq -R 'select(length > 0)' | jq -s .)" || return 1
    retired_perms_json="$(printf '%s\n' "${RETIRED_PERMISSION_RULES[@]}" | jq -R 'select(length > 0)' | jq -s .)" || return 1
    manifest_json="$(read_manifest "${dst}")" || return 1
    if [ "${manifest_json}" = null ] && [ -f "${dst}/${MANIFEST_NAME}" ]; then
        log_warn "${MANIFEST_NAME} is not a valid manifest - ignoring it (removals from the base will not propagate this run)."
    fi

    local result merged manifest
    result="$(jq -n \
        --argjson base "${rendered}" \
        --argjson live "${live_json}" \
        --argjson manifest "${manifest_json}" \
        --argjson localKeys "${local_keys_json}" \
        --argjson retired "${retired_json}" \
        --argjson retiredPerms "${retired_perms_json}" \
        --argjson unionPerms "${UNION_PERMISSIONS}" \
        "${JQ_MERGE}")" || { log_err "Settings merge failed for ${dst} - leaving settings.json as it is."; return 1; }
    merged="$(jq '.merged' <<<"${result}")" || return 1
    manifest="$(jq -c '.manifest' <<<"${result}")" || return 1
    # Never write what is not a settings object.
    if ! jq -e 'type == "object"' <<<"${merged}" >/dev/null 2>&1; then
        log_err "Settings merge for ${dst} produced no valid settings - leaving settings.json as it is."
        return 1
    fi

    # Fail closed. A base that is `{}`, half-edited or from a stale branch has no
    # list where the last sync recorded entries, and subtracting would then drop
    # every deny rule and guard hook it used to carry. A deliberate removal of a
    # whole list looks the same, so refuse either way and write nothing.
    local refused
    refused="$(jq -r '.refuse | join(", ")' <<<"${result}")" || return 1
    if [ -n "${refused}" ]; then
        log_err "settings.base.json has no entries for ${refused}, but the last sync recorded some for ${dst}. Refusing to merge: a broken or stale base would remove every guard. If emptying them is deliberate, delete ${dst}/${MANIFEST_NAME} and sync again."
        return 1
    fi

    report_removals "${result}"
    report_key_changes "${result}"
    report_live_only "${result}"
    warn_shadowed_carve_outs "${merged}"

    # Now drop the legacy symlink so the generated file is real and per-dir.
    if [ -L "${current}" ]; then
        log_warn "Replacing legacy settings.json symlink with a generated file"
        cp "${current}" "${current}.bak-$(date +%Y%m%d-%H%M%S)" || return 1
        rm "${current}" || return 1
    fi

    if [ -f "${current}" ] && [ "$(jq -S . <<<"${merged}")" = "$(jq -S . "${current}")" ]; then
        write_manifest "${dst}" "${manifest}" || return 1
        log_info "settings.json already up to date"
        return 0
    fi

    if [ -f "${current}" ]; then
        cp "${current}" "${current}.bak-$(date +%Y%m%d-%H%M%S)" || return 1
        log_warn "Backed up previous settings.json"
    fi

    printf '%s\n' "${merged}" > "${current}" || return 1
    write_manifest "${dst}" "${manifest}" || return 1
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

    warn_untracked_files "${CLAUDE_SRC}"
    if ! expected="$(expected_rels "${CLAUDE_SRC}" skip)"; then
        log_err "Cannot list the files this repo links; check refuses to guess."
        return 1
    fi
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
            if expected="$(expected_rels "${OPENCODE_SRC}")"; then
                verify_links "${OPENCODE_SRC}" "${OPENCODE_DST}" ".config/opencode" "${expected}" info || status=1
            else
                log_err "Cannot list the files this repo links for opencode; check refuses to guess."
                status=1
            fi
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
MERGE_FAILED=()
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
# If what the repo tracks cannot be listed (unreadable git index, nothing staged),
# nothing is linked or pruned: an empty list must never read as "link nothing".
EXPECTED_OK=1
EXPECTED_CLAUDE="$(expected_rels "${CLAUDE_SRC}" skip)" || EXPECTED_OK=0
warn_untracked_files "${CLAUDE_SRC}"

for CLAUDE_DST in "${CLAUDE_DSTS[@]}"; do
    log_info "Target config dir: ${CLAUDE_DST}"
    # Prune first: a path that turned from a file into a directory (or back) needs
    # its old link gone before the new one can be written, in this same run.
    LINKS_OK="${EXPECTED_OK}"
    if [ "${LINKS_OK}" -eq 1 ]; then
        prune_links "${CLAUDE_SRC}" "${CLAUDE_DST}" ".claude" "${EXPECTED_CLAUDE}" || LINKS_OK=0
    fi
    if [ "${LINKS_OK}" -eq 1 ]; then
        link_under "${CLAUDE_SRC}" "${CLAUDE_SRC}" "${CLAUDE_DST}" "skip" || LINKS_OK=0
    fi
    merge_settings "${CLAUDE_DST}" || MERGE_FAILED+=("${CLAUDE_DST}")
    if [ "${LINKS_OK}" -eq 1 ]; then
        verify_links "${CLAUDE_SRC}" "${CLAUDE_DST}" ".claude" "${EXPECTED_CLAUDE}" || LINK_FAILED+=("${CLAUDE_DST}")
    else
        LINK_FAILED+=("${CLAUDE_DST}")
    fi
done

# opencode lives at a fixed path, not per profile; sync it once, on runs
# that include the default ~/.claude.
if [ "${CLAUDE_DSTS[0]}" = "${HOME}/.claude" ] && [ -d "${OPENCODE_SRC}" ]; then
    warn_untracked_files "${OPENCODE_SRC}"
    if EXPECTED_OPENCODE="$(expected_rels "${OPENCODE_SRC}")" &&
        prune_links "${OPENCODE_SRC}" "${OPENCODE_DST}" ".config/opencode" "${EXPECTED_OPENCODE}" &&
        link_under "${OPENCODE_SRC}" "${OPENCODE_SRC}" "${OPENCODE_DST}"; then
        verify_links "${OPENCODE_SRC}" "${OPENCODE_DST}" ".config/opencode" "${EXPECTED_OPENCODE}" || LINK_FAILED+=("${OPENCODE_DST}")
    else
        LINK_FAILED+=("${OPENCODE_DST}")
    fi
fi

if [ "${#LINK_FAILED[@]}" -gt 0 ]; then
    for failed_dst in "${LINK_FAILED[@]}"; do
        log_err "Links do not match the repo in: ${failed_dst}"
    done
    log_err "Install is broken (see the errors above); run ./sync.sh --check for the full picture."
fi

# A dir whose settings could not be merged does not stop the others, but the
# run still fails.
if [ "${#MERGE_FAILED[@]}" -gt 0 ]; then
    for failed_dst in "${MERGE_FAILED[@]}"; do
        log_err "Settings merge failed for: ${failed_dst}"
    done
fi

# Both failures are reported above before the run exits.
if [ "${#LINK_FAILED[@]}" -gt 0 ] || [ "${#MERGE_FAILED[@]}" -gt 0 ]; then
    exit 1
fi

log_info "Done! Claude Code tools are ready in: ${CLAUDE_DSTS[*]}"
