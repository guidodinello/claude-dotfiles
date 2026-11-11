#!/usr/bin/env bash
# Self-check for the worktree-bootstrap skill. Run it after any change to
# lib.sh or the examples:
#
#   bash <skill-dir>/scripts/self-check.sh
#
# It tests the lib.sh next to this script (WORKTREE_BOOTSTRAP_LIB points the
# example there), never the installed copy and never a real repo: it builds a
# throwaway workspace and repo under a temp dir and deletes them at the end.
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIB="$SKILL_DIR/lib.sh"
EXAMPLE="$SKILL_DIR/examples/bootstrap-links-only.sh"
failures=0

pass() { echo "PASS $*"; }
fail() {
  echo "FAIL $*" >&2
  failures=$((failures + 1))
}
check() {
  local what="$1"
  shift
  if "$@"; then pass "$what"; else fail "$what"; fi
}

echo "--- syntax"
for shell in /bin/bash bash; do
  for file in "$LIB" "$SKILL_DIR"/examples/*.sh "$SKILL_DIR"/scripts/*.sh; do
    check "$shell -n $(basename "$file")" "$shell" -n "$file"
  done
done

SCRATCH="$(cd "$(mktemp -d)" && pwd -P)"
WS="$SCRATCH/ws"
REPO="$WS/infra"
WT="$SCRATCH/worktrees/feature-x"
cleanup() {
  git -C "$REPO" worktree remove --force "$WT" >/dev/null 2>&1 || true
  rm -rf "$SCRATCH"
}
trap cleanup EXIT

echo "--- env helpers"
(
  # shellcheck source-path=SCRIPTDIR source=../lib.sh
  . "$LIB"
  env_file="$SCRATCH/test.env"
  example="$SCRATCH/test.env.example"
  printf 'A=1\nTRICKY=old\nGONE=x' >"$env_file"
  printf 'A=9\nNEW_KEY=default\n' >"$example"
  # shellcheck disable=SC2016
  value='a/b&c\d$e'
  set_env_key "$env_file" TRICKY "$value"
  set_env_key "$env_file" APPENDED "z"
  delete_env_key "$env_file" GONE
  fill_missing_env_keys "$env_file" "$example" >/dev/null
  check "set_env_key keeps special characters literal" test "$(get_env_key "$env_file" TRICKY)" = "$value"
  check "set_env_key appends a missing key on its own line" test "$(get_env_key "$env_file" APPENDED)" = "z"
  check "delete_env_key removes the key" test -z "$(get_env_key "$env_file" GONE)"
  check "fill_missing_env_keys adds only missing keys" test "$(get_env_key "$env_file" NEW_KEY)/$(get_env_key "$env_file" A)" = "default/1"
  check "compose_project_name slugifies" test "$(compose_project_name "proj-" "Feat/X_1")" = "proj-feat-x_1"
  check "port_offset is stable and in range" test "$(port_offset feature-x)" = "$(port_offset feature-x)" -a "$(port_offset feature-x)" -ge 1 -a "$(port_offset feature-x)" -le 899
  exit "$failures"
) || failures=$((failures + $?))

echo "--- links-only run on a throwaway worktree"
mkdir -p "$WS/my-dev-things" "$REPO" "$(dirname "$WT")"
echo "# workspace" >"$WS/CLAUDE.md"
echo "export const note = 1;" >"$WS/my-dev-things/note.ts"
git -C "$REPO" init -q
echo "repo" >"$REPO/README.md"
git -C "$REPO" add README.md
git -C "$REPO" -c user.name=self-check -c user.email=self-check@example.invalid -c commit.gpgsign=false commit -qm init
git -C "$REPO" worktree add -q --detach "$WT" HEAD

run_example() {
  ORCA_WORKTREE_PATH="$1" WORKTREE_BOOTSTRAP_LIB="$LIB" bash "$EXAMPLE"
}
exclude_count() {
  grep -cxF "$1" "$REPO/.git/info/exclude" || true
}

for round in 1 2; do
  check "run $round exits 0" run_example "$WT"
  check "run $round: CLAUDE.local.md -> workspace CLAUDE.md" test "$(readlink "$WT/CLAUDE.local.md")" = "$WS/CLAUDE.md"
  check "run $round: .my-dev-things -> workspace notes" test "$(readlink "$WT/.my-dev-things")" = "$WS/my-dev-things"
  check "run $round: git status --porcelain is empty" test -z "$(git -C "$WT" status --porcelain)"
  check "run $round: each exclude pattern appears once" test "$(exclude_count /CLAUDE.local.md)/$(exclude_count /.my-dev-things)" = "1/1"
done

if run_example "$REPO" >/dev/null 2>&1; then
  fail "refuses to run on the main checkout"
else
  pass "refuses to run on the main checkout"
fi
check "main checkout got no links" test ! -e "$REPO/CLAUDE.local.md" -a ! -e "$REPO/.my-dev-things"

echo "--- lib resolution from HOME"
INSTALLED_HOME="$SCRATCH/home"
mkdir -p "$INSTALLED_HOME/.claude/skills/worktree-bootstrap" "$SCRATCH/empty-home"
ln -s "$LIB" "$INSTALLED_HOME/.claude/skills/worktree-bootstrap/lib.sh"
rm -f "$WT/CLAUDE.local.md" "$WT/.my-dev-things"
check "installed-style path (symlinked like sync.sh) runs without the override" \
  env -u WORKTREE_BOOTSTRAP_LIB HOME="$INSTALLED_HOME" ORCA_WORKTREE_PATH="$WT" bash "$EXAMPLE"
check "installed-style run linked CLAUDE.local.md" test "$(readlink "$WT/CLAUDE.local.md")" = "$WS/CLAUDE.md"
if missing_out="$(env -u WORKTREE_BOOTSTRAP_LIB HOME="$SCRATCH/empty-home" ORCA_WORKTREE_PATH="$WT" bash "$EXAMPLE" 2>&1)"; then
  fail "missing lib exits non-zero"
else
  pass "missing lib exits non-zero"
fi
check "missing lib says 'not found'" grep -q "not found" <<<"$missing_out"

echo "--- missing workspace CLAUDE.md"
mv "$WS/CLAUDE.md" "$WS/CLAUDE.md.off"
if ORCA_WORKTREE_PATH="$WT" WORKTREE_BOOTSTRAP_LIB="$LIB" bash "$EXAMPLE" >/dev/null 2>&1; then
  fail "dies when the workspace CLAUDE.md is missing"
else
  pass "dies when the workspace CLAUDE.md is missing"
fi
mv "$WS/CLAUDE.md.off" "$WS/CLAUDE.md"

echo "---"
if [ "$failures" -eq 0 ]; then
  echo "self-check passed"
else
  echo "self-check: $failures failure(s)" >&2
  exit 1
fi
