#!/usr/bin/env bash
# Runs a PR's diff through two free opencode models with independent fallback chains.
#
# The prompt mirrors code-review's 5 review dimensions (CLAUDE.md compliance, bugs,
# git blame/history, previous-PR comments, false-positive filter) as far as a toolless
# model allows: the model can't call `git blame`, `gh api`, or read a CLAUDE.md file
# itself, so this script gathers all of that and inlines it. The false-positive list
# is read from code-review's own SKILL.md at runtime instead of a hand-copied
# paraphrase, so the two skills can't drift apart silently.
#
# Usage: dual-review.sh <repo-dir> <pr-number> [diff-base-ref]
#
# diff-base-ref: review only HEAD's changes since this ref instead of the PR's full
# diff against its base. Use it for a PR stacked on an unmerged sibling branch, whose
# GitHub diff still includes the sibling's commits (e.g. origin/feature/sibling).
# Findings still post to the PR; their lines are a subset of the PR diff.
set -euo pipefail

# Resolved before the `cd "$REPO_DIR"` below: BASH_SOURCE is relative when the
# script is invoked by a relative path, and stops resolving once the cwd moves.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

REPO_DIR="$(cd "${1:?usage: dual-review.sh <repo-dir> <pr-number>}" && pwd)"
PR_NUMBER="${2:?usage: dual-review.sh <repo-dir> <pr-number>}"
DIFF_BASE="${3:-}"

CODE_REVIEW_SKILL="${CODE_REVIEW_SKILL:-$HOME/.claude/skills/code-review/SKILL.md}"
MAX_CONTEXT_FILES=15
MAX_PR_HISTORY=5
MAX_BLAME_LINES_PER_HUNK=5

cd "$REPO_DIR"

OUT_DIR="$(mktemp -d)"
echo "Output dir: $OUT_DIR" >&2

ORIGINAL_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
cleanup() {
  git checkout "$ORIGINAL_BRANCH" >/dev/null 2>&1 || true
  if [[ -n "${REVIEW_SANDBOX:-}" ]]; then rm -rf "$REVIEW_SANDBOX"; fi
}
trap cleanup EXIT

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Working tree is dirty — commit or stash before running a review." >&2
  exit 1
fi

if [[ ! -f "$CODE_REVIEW_SKILL" ]]; then
  echo "Warning: canonical code-review skill not found at $CODE_REVIEW_SKILL — falling back to a minimal false-positive list." >&2
fi

gh pr checkout "$PR_NUMBER" ${PR_CHECKOUT_DETACH:+--detach} >/dev/null
if [[ -n "$DIFF_BASE" ]]; then
  git fetch origin --quiet 2>/dev/null || true
  git rev-parse --verify --quiet "$DIFF_BASE" >/dev/null || { echo "Unknown diff base: $DIFF_BASE" >&2; exit 1; }
  git diff "$DIFF_BASE"...HEAD > "$OUT_DIR/pr.diff"
else
  gh pr diff "$PR_NUMBER" > "$OUT_DIR/pr.diff"
fi
PR_TITLE="$(gh pr view "$PR_NUMBER" --json title -q '.title')"
BASE_REF="$(gh pr view "$PR_NUMBER" --json baseRefName -q '.baseRefName')"
OWNER_REPO="$(gh repo view --json nameWithOwner -q '.nameWithOwner')"

if [[ -n "$DIFF_BASE" ]]; then
  mapfile -t CHANGED_FILES < <(git diff --name-only "$DIFF_BASE"...HEAD)
else
  mapfile -t CHANGED_FILES < <(gh pr view "$PR_NUMBER" --json files --jq '.files[].path')
fi

git fetch origin "$BASE_REF" --quiet 2>/dev/null || true
MERGE_BASE="$(git merge-base HEAD "${DIFF_BASE:-origin/$BASE_REF}" 2>/dev/null || true)"

DIFF_LINES=$(wc -l < "$OUT_DIR/pr.diff")
# 4000 fits the free opencode models; sonnet-review.sh raises it to send the whole diff.
MAX_DIFF_LINES="${MAX_DIFF_LINES:-4000}"
if [[ "$DIFF_LINES" -gt "$MAX_DIFF_LINES" ]]; then
  echo "Diff is ${DIFF_LINES} lines — truncating to first ${MAX_DIFF_LINES} for the prompt (full diff saved at $OUT_DIR/pr.diff)." >&2
  head -n "$MAX_DIFF_LINES" "$OUT_DIR/pr.diff" > "$OUT_DIR/pr.diff.truncated"
  DIFF_FILE="$OUT_DIR/pr.diff.truncated"
else
  DIFF_FILE="$OUT_DIR/pr.diff"
fi

# --- Shared false-positive list, read straight from code-review's own SKILL.md.
FALSE_POSITIVES_FILE="$OUT_DIR/false_positives.txt"
: > "$FALSE_POSITIVES_FILE"
if [[ -f "$CODE_REVIEW_SKILL" ]]; then
  awk '/^Examples of false positives/,/^Notes:/' "$CODE_REVIEW_SKILL" | sed '$d' > "$FALSE_POSITIVES_FILE" || true
fi
if [[ ! -s "$FALSE_POSITIVES_FILE" ]]; then
  cat > "$FALSE_POSITIVES_FILE" <<'EOF'
Examples of false positives:
- Pre-existing issues
- Something that looks like a bug but is not actually a bug
- Pedantic nitpicks that a senior engineer wouldn't call out
- Issues a linter/typechecker/compiler/CI would catch
- General code quality wishlist items with no concrete bug
- Issues explicitly silenced in the code (e.g. a lint-ignore comment)
- Changes in functionality that are likely intentional
- Real issues, but on lines the diff didn't touch
EOF
fi

# --- CLAUDE.md context: the model has no tools, so any relevant CLAUDE.md
# content (root + every ancestor dir of each changed file) is inlined here,
# capped to the first MAX_CONTEXT_FILES changed files and 8000 chars total.
CLAUDE_MD_FILE="$OUT_DIR/claude_md_context.txt"
: > "$CLAUDE_MD_FILE"
declare -A SEEN_CLAUDE_MD=()
collect_claude_md() {
  local dir="$1"
  while true; do
    local candidate="$dir/CLAUDE.md"
    local rel="${candidate#"$REPO_DIR"/}"
    # Read from the PR's committed tree, never the working tree: a CLAUDE.md the PR
    # commits as a symlink (mode 120000) could point at any file on this machine.
    local mode
    mode="$(git -C "$REPO_DIR" ls-files -s -- "$rel" | cut -d' ' -f1)"
    if [[ ( "$mode" == 100644 || "$mode" == 100755 ) && -z "${SEEN_CLAUDE_MD[$candidate]:-}" ]]; then
      SEEN_CLAUDE_MD["$candidate"]=1
      {
        echo "--- $rel ---"
        git -C "$REPO_DIR" show "HEAD:$rel"
        echo ""
      } >> "$CLAUDE_MD_FILE"
    fi
    [[ "$dir" == "$REPO_DIR" ]] && break
    dir="$(dirname "$dir")"
  done
}
file_count=0
for f in "${CHANGED_FILES[@]}"; do
  (( file_count >= MAX_CONTEXT_FILES )) && break
  collect_claude_md "$(dirname "$REPO_DIR/$f")"
  file_count=$((file_count + 1))
done
# A repo cloned into a multi-repo workspace often carries no CLAUDE.md of its own;
# its rules live in the workspace's CLAUDE.md, an ancestor of the repo. Without this
# fallback the prompt promised guidance "below" that wasn't there, and models burned
# their turn trying to read CLAUDE.md with tools they don't have.
#
# The walk starts at the parent of the repo's MAIN checkout, never at REPO_DIR:
# review-pr.sh and sonnet-review.sh hand this script a detached worktree under
# mktemp, which has no meaningful ancestors, and starting above every checkout of
# the PR means no PR-controlled file can be read here.
#   REVIEW_CLAUDE_MD           explicit fallback file; skips the ancestor walk.
#   REVIEW_CLAUDE_MD_SECTIONS  "|"-separated "## " heading prefixes to inline. An
#                              entry "<file>=## Heading" applies only when the repo
#                              root has <file>. Unset: inline the whole file.
find_fallback_claude_md() {
  if [[ -n "${REVIEW_CLAUDE_MD:-}" ]]; then
    [[ -f "$REVIEW_CLAUDE_MD" ]] && echo "$REVIEW_CLAUDE_MD"
    return 0
  fi
  local common_dir main_root dir
  common_dir="$(git -C "$REPO_DIR" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" || return 0
  main_root="$(dirname "$common_dir")"
  dir="$(dirname "$main_root")"
  while true; do
    if [[ -f "$dir/CLAUDE.md" ]]; then
      echo "$dir/CLAUDE.md"
      return 0
    fi
    [[ "$dir" == "/" ]] && return 0
    dir="$(dirname "$dir")"
  done
}
FALLBACK_CLAUDE_MD="$(find_fallback_claude_md)"
if [[ ! -s "$CLAUDE_MD_FILE" && -n "$FALLBACK_CLAUDE_MD" ]]; then
  python3 -I - "$FALLBACK_CLAUDE_MD" "$REPO_DIR" "${REVIEW_CLAUDE_MD_SECTIONS:-}" >> "$CLAUDE_MD_FILE" <<'PY'
import os, re, sys
path, repo_dir, spec = sys.argv[1:4]
text = open(path).read()
if not spec.strip():
    print("--- ancestor CLAUDE.md ---")
    print(re.sub(r"<!--.*?-->", "", text, flags=re.S).strip() + "\n")
    sys.exit(0)
wanted = []
for entry in filter(None, (e.strip() for e in spec.split("|"))):
    marker, sep, heading = entry.partition("=")
    if not sep:
        wanted.append(entry)
    elif os.path.isfile(os.path.join(repo_dir, marker.strip())):
        wanted.append(heading.strip())
sections = re.split(r"(?m)^(?=## )", text)
print("--- workspace CLAUDE.md (relevant sections) ---")
for s in sections:
    if any(s.startswith(w) for w in wanted):
        print(re.sub(r"<!--.*?-->", "", s, flags=re.S).strip() + "\n")
PY
fi
CLAUDE_MD_CHARS=$(wc -c < "$CLAUDE_MD_FILE")
if [[ "$CLAUDE_MD_CHARS" -gt 8000 ]]; then
  head -c 8000 "$CLAUDE_MD_FILE" > "$CLAUDE_MD_FILE.truncated"
  {
    echo ""
    echo "[...truncated, ${CLAUDE_MD_CHARS} chars total...]"
  } >> "$CLAUDE_MD_FILE.truncated"
  mv "$CLAUDE_MD_FILE.truncated" "$CLAUDE_MD_FILE"
fi

# --- Git blame/history context: for each changed file (same cap), blame the
# old-side line ranges at the merge-base so findings can cite *why* the
# original code looks the way it does, plus the file's last 2 pre-PR commits.
HISTORY_FILE="$OUT_DIR/history_context.txt"
: > "$HISTORY_FILE"
if [[ -n "$MERGE_BASE" ]]; then
  file_count=0
  for f in "${CHANGED_FILES[@]}"; do
    (( file_count >= MAX_CONTEXT_FILES )) && break
    file_count=$((file_count + 1))
    [[ -f "$f" ]] || continue

    {
      echo "--- history: $f ---"
      git log --format='%h %s' -n 2 "$MERGE_BASE" -- "$f" 2>/dev/null || true
    } >> "$HISTORY_FILE"

    while read -r hunk_line; do
      old_range="$(echo "$hunk_line" | sed -n 's/^@@ -\([0-9,]*\) .*/\1/p')"
      [[ -z "$old_range" ]] && continue
      old_start="${old_range%%,*}"
      old_count="${old_range#*,}"
      [[ "$old_range" == "$old_count" ]] && old_count=1
      [[ -z "$old_start" || "$old_count" -eq 0 ]] && continue
      old_end=$((old_start + old_count - 1))
      {
        echo "blame @ $MERGE_BASE, lines $old_start-$old_end:"
        git blame "$MERGE_BASE" -L "$old_start,$old_end" -- "$f" 2>/dev/null | head -n "$MAX_BLAME_LINES_PER_HUNK" || true
      } >> "$HISTORY_FILE"
    done < <(git diff "$MERGE_BASE" HEAD -- "$f" 2>/dev/null | grep '^@@' || true)
    echo "" >> "$HISTORY_FILE"
  done
fi

# --- Previous PR comments on these same files: walk each file's recent
# pre-PR commits, resolve their associated PRs, and pull review comments
# anchored to one of the changed files. Capped to MAX_PR_HISTORY distinct PRs.
PR_HISTORY_FILE="$OUT_DIR/pr_history_context.txt"
: > "$PR_HISTORY_FILE"
if [[ -n "$MERGE_BASE" ]]; then
  declare -A SEEN_PR=()
  pr_count=0
  file_count=0
  for f in "${CHANGED_FILES[@]}"; do
    (( file_count >= MAX_CONTEXT_FILES || pr_count >= MAX_PR_HISTORY )) && break
    file_count=$((file_count + 1))
    [[ -f "$f" ]] || continue

    while read -r sha; do
      (( pr_count >= MAX_PR_HISTORY )) && break
      [[ -z "$sha" ]] && continue
      mapfile -t prs < <(gh api "repos/$OWNER_REPO/commits/$sha/pulls" --jq '.[].number' 2>/dev/null || true)
      for pr in "${prs[@]}"; do
        (( pr_count >= MAX_PR_HISTORY )) && break
        [[ "$pr" == "$PR_NUMBER" ]] && continue
        [[ -n "${SEEN_PR[$pr]:-}" ]] && continue
        SEEN_PR["$pr"]=1
        pr_count=$((pr_count + 1))

        mapfile -t comments < <(gh api "repos/$OWNER_REPO/pulls/$pr/comments" --paginate \
          --jq '.[] | "\(.path)|\(.line // .original_line // "?")|\((.body | gsub("\n";" "))[0:200])"' 2>/dev/null || true)
        for line in "${comments[@]}"; do
          [[ -z "$line" ]] && continue
          c_path="${line%%|*}"
          for cf in "${CHANGED_FILES[@]}"; do
            if [[ "$c_path" == "$cf" ]]; then
              echo "PR #$pr on $line" >> "$PR_HISTORY_FILE"
              break
            fi
          done
        done
      done
    done < <(git log --format='%H' -n 2 "$MERGE_BASE" -- "$f" 2>/dev/null || true)
  done
fi

PROMPT_FILE="$OUT_DIR/prompt.txt"
{
  echo "Review this pull request diff. Title: ${PR_TITLE}"
  echo ""
  echo "You have no tools. Do not try to read, glob or search files: everything you need"
  echo "(the diff, the CLAUDE.md guidance, history and past review comments) is inline below."
  echo "Answer only with FINDING blocks or NO_FINDINGS, as specified at the end."
  echo ""
  echo "Check for issues across these areas, same as a senior engineer's review:"
  echo "1. Compliance with the CLAUDE.md guidance below (it's guidance for how code in this repo"
  echo "   should be written — not every line applies to every change)."
  echo "2. Obvious bugs in the diff itself — focus on the changes, avoid nitpicks."
  echo "3. The git history/blame context below — does this change contradict or ignore why the"
  echo "   original code was written that way?"
  echo "4. The previous-PR-comment context below — does any of it apply again here?"
  echo "5. Reasonable engineering practice for this stack."
  echo ""
  if [[ -s "$CLAUDE_MD_FILE" ]]; then
    echo "--- CLAUDE.md CONTEXT ---"
    cat "$CLAUDE_MD_FILE"
    echo "--- END CLAUDE.md CONTEXT ---"
    echo ""
  fi
  if [[ -s "$HISTORY_FILE" ]]; then
    echo "--- GIT HISTORY/BLAME CONTEXT ---"
    cat "$HISTORY_FILE"
    echo "--- END GIT HISTORY/BLAME CONTEXT ---"
    echo ""
  fi
  if [[ -s "$PR_HISTORY_FILE" ]]; then
    echo "--- PREVIOUS PR COMMENTS ON THESE FILES ---"
    cat "$PR_HISTORY_FILE"
    echo "--- END PREVIOUS PR COMMENTS ---"
    echo ""
  fi
  cat "$FALSE_POSITIVES_FILE"
  echo ""
  echo "Output every real finding as its own block, in exactly this format, nothing else around each block:"
  echo ""
  echo "---FINDING-START---"
  echo "TIER: blocking|non-blocking"
  echo "FILE: <repo-relative path>"
  echo "LINE: <line number on the new/right side of the diff>"
  echo "BODY: <one paragraph: what's wrong and why, cite the specific rule or reasoning>"
  echo "---FINDING-END---"
  echo ""
  echo "blocking = you verified it's real and it matters (will break something, contradicts an explicit rule,"
  echo "likely to be hit in practice). non-blocking = real but minor, low-frequency, or low-impact — still say so,"
  echo "don't drop it just because it's small. If you found nothing that clears that bar, output exactly: NO_FINDINGS"
  echo "and nothing else."
  echo ""
  echo "--- DIFF START ---"
  cat "$DIFF_FILE"
  echo "--- DIFF END ---"
} > "$PROMPT_FILE"

# PROMPT_ONLY=1: stop after building the prompt and print its path (used by sonnet-review.sh).
if [[ -n "${PROMPT_ONLY:-}" ]]; then
  trap - EXIT
  echo "$PROMPT_FILE"
  exit 0
fi

FALLBACKS=(nemotron-3-ultra-free mimo-v2.5-free hy3-free nemotron-3.5-lightning-free)
USED_MODELS_FILE="$OUT_DIR/used_models.txt"
: > "$USED_MODELS_FILE"

# Bumped from 90s: the prompt now carries CLAUDE.md/history/PR-comment context
# on top of the diff, so free models need more headroom to finish.
MODEL_TIMEOUT_SECS="${MODEL_TIMEOUT_SECS:-150}"
# One attempt per model and an overall wall-clock budget per slot: past it, the slot
# gives up so review-pr.sh can hand the PR to the Sonnet fallback.
ATTEMPTS_PER_MODEL="${ATTEMPTS_PER_MODEL:-1}"
REVIEW_BUDGET_SECS="${REVIEW_BUDGET_SECS:-480}"
REVIEW_START=$SECONDS

# The model reviews an untrusted PR, so it runs from an empty directory outside any
# repo: a project opencode.json outranks OPENCODE_CONFIG, and the PR checkout could
# ship one that re-enables every tool. bash/read/glob/grep/list are "ask", which
# `opencode run` auto-rejects; "deny" on bash or read makes OpenCode's free tier
# refuse the request ("can only be used from within OpenCode", opencode 1.18.29).
REVIEW_SANDBOX="$(mktemp -d)"
LOCKED_CONFIG="$OUT_DIR/opencode-locked.json"
cat > "$LOCKED_CONFIG" <<'EOF'
{"permission":{
  "bash":"ask","read":"ask","glob":"ask","grep":"ask","list":"ask",
  "edit":"deny","webfetch":"deny","websearch":"deny","task":"deny",
  "external_directory":"deny","skill":"deny"}}
EOF

# A tool that actually ran prints "$ cmd" (bash), "→ Read …", "✱ Glob/Grep …" or
# "⚙ <tool> {…}" (execute, MCP and other tools); a rejected one prints "✗ … failed".
# Any executed call means the lockdown above stopped holding, so that review is
# discarded rather than posted.
tool_ran() {
  perl -pe 's/\e\[[0-9;]*m//g' "$1" | grep -qE '^(\$|→|✱|←|⚙) '
}

run_with_model() {
  local model="$1"
  local out_file="$2"

  (cd "$REVIEW_SANDBOX" && OPENCODE_CONFIG="$LOCKED_CONFIG" \
    opencode run -m "opencode/${model}" "$(cat "$PROMPT_FILE")") > "$out_file" 2>&1 &
  local run_pid=$!

  ( sleep "${3:-$MODEL_TIMEOUT_SECS}" && kill -9 "$run_pid" 2>/dev/null ) &
  local watchdog_pid=$!

  local status=0
  wait "$run_pid" || status=$?

  pkill -P "$watchdog_pid" 2>/dev/null || true
  kill "$watchdog_pid" 2>/dev/null || true
  wait "$watchdog_pid" 2>/dev/null || true

  if [[ "$status" -ne 0 ]]; then
    echo "Error: opencode call timed out after ${3:-$MODEL_TIMEOUT_SECS}s or exited non-zero (status $status)" >> "$out_file"
    return 1
  fi
  return 0
}

post_review_comment() {
  local model="$1"
  local out_file="$2"
  python3 -I "$SCRIPT_DIR/post_structured_review.py" "$REPO_DIR" "$PR_NUMBER" "$model" "$out_file" >&2
}

review_slot() {
  local slot_name="$1"
  local primary_model="$2"
  local out_file="$OUT_DIR/review_${slot_name}.txt"
  local model_used_file="$OUT_DIR/model_${slot_name}.txt"

  local candidates=("$primary_model" "${FALLBACKS[@]}")
  local attempted=0

  for model in "${candidates[@]}"; do
    if grep -qx "$model" "$USED_MODELS_FILE" 2>/dev/null; then
      continue
    fi

    for attempt in $(seq 1 "$ATTEMPTS_PER_MODEL"); do
      attempted=1
      local remaining=$(( REVIEW_BUDGET_SECS - (SECONDS - REVIEW_START) ))
      if (( remaining < 30 )); then
        echo "[$slot_name] review budget (${REVIEW_BUDGET_SECS}s) spent, stopping" >&2
        break 2
      fi
      local attempt_timeout=$(( remaining < MODEL_TIMEOUT_SECS ? remaining : MODEL_TIMEOUT_SECS ))
      echo "[$slot_name] attempt $attempt with $model" >&2
      if run_with_model "$model" "$out_file" "$attempt_timeout"; then
        # Only an output without a verdict counts as an error body: a finding may
        # legitimately start a line with "Error".
        if grep -qi "^Error" "$out_file" && ! grep -q -e 'NO_FINDINGS' -e '---FINDING-START---' "$out_file"; then
          echo "[$slot_name] $model returned an error body, retrying/falling back" >&2
          continue
        fi
        if tool_ran "$out_file"; then
          echo "[$slot_name] SECURITY: $model executed a tool despite the locked config; review discarded, nothing posted ($out_file)" >&2
          continue
        fi
        # A model that spends its turn on rejected tool calls (or returns noise)
        # exits 0 with no verdict, and posting that would publish a false
        # "No issues found". Require an explicit verdict marker.
        if ! grep -q -e 'NO_FINDINGS' -e '---FINDING-START---' "$out_file"; then
          echo "[$slot_name] $model returned no verdict (no NO_FINDINGS / FINDING block), retrying/falling back" >&2
          continue
        fi
        echo "$model" >> "$USED_MODELS_FILE"
        echo "$model" > "$model_used_file"
        echo "[$slot_name] succeeded with $model" >&2
        if post_review_comment "$model" "$out_file"; then
          echo "[$slot_name] posted comment to PR #$PR_NUMBER" >&2
        else
          echo "[$slot_name] ERROR: posting the review to PR #$PR_NUMBER failed; findings are in $out_file" >&2
        fi
        return 0
      fi
      echo "[$slot_name] $model attempt $attempt failed" >&2
    done
  done

  echo "FAILED: all models exhausted for slot $slot_name" > "$out_file"
  echo "none" > "$model_used_file"
  echo "[$slot_name] exhausted all models — nothing posted" >&2
  return 1
}

review_slot "A" "big-pickle" &
PID_A=$!
review_slot "B" "muse-spark-1.2-contributor-free" &
PID_B=$!

wait "$PID_A" || true
wait "$PID_B" || true

echo ""
echo "=== RESULTS ==="
echo "Output dir: $OUT_DIR"
for slot in A B; do
  model_file="$OUT_DIR/model_${slot}.txt"
  model="$(cat "$model_file" 2>/dev/null || echo unknown)"
  echo "Slot $slot -> model: $model -> $OUT_DIR/review_${slot}.txt"
done
