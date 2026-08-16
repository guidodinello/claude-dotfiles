#!/usr/bin/env bash
# push-guidelines — push this repo's guidelines out into project repos that
# carry committed copies.
#
# Why: most projects import guidelines from the home deploy
# (`@~/.claude/guidelines/<file>.md`), which is symlinked back here and so can
# never drift. But repos that must be readable from a remote Claude web session
# or another machine can't resolve an absolute home path, and symlinks don't
# survive `git clone` — those repos commit their own copy, and copies drift.
# This is the third sync direction:
#
#   sync.sh             this repo → ~/.claude/     (symlinks)
#   promote.sh          a project → this repo      (adopt a file globally)
#   push-guidelines.sh  this repo → projects       (refresh committed copies)
#
# Edited a guideline inside a project? Run promote.sh first, then this.
#
# Usage:
#   ./push-guidelines.sh                 # dry run over every opted-in project
#   ./push-guidelines.sh --apply         # actually write
#   ./push-guidelines.sh ~/projects/foo  # one project only
#
# A project opts in simply by having a .claude/guidelines/ directory. Only files
# the project ALREADY has are refreshed — adopting a new guideline stays a
# deliberate `cp`, so a Node repo never wakes up owning php.md. Nothing is ever
# deleted, so project-specific files (e.g. ci-fitted.md) are safe.

set -euo pipefail
shopt -s nullglob

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECTS_DIR="${PROJECTS_DIR:-$HOME/projects}"

# Both shared-content directories, each synced independently:
#   rules/       path-scoped (`paths:` frontmatter) — load only when Claude touches a
#                matching file. Where guidelines live unless they can't be glob-scoped.
#   guidelines/  always-on, imported explicitly by a CLAUDE.md.
SUBDIRS=(rules guidelines)

GREEN='\033[1;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }

usage() {
  cat <<EOF
Usage: ./push-guidelines.sh [project-dir] [--apply]

Pushes this repo's .claude/rules/ and .claude/guidelines/ into every project that
already keeps a committed copy of either. Refreshes only files the project already
has; never creates new ones, never deletes.

Arguments:
  project-dir  Push to just this project. Defaults to every opted-in project
               under \$PROJECTS_DIR ($PROJECTS_DIR).

Options:
  --apply    Actually write. Without it this is a dry run that only reports.
  -h,--help  Show this help.

Dry-run output is rsync's itemized format; the leading '>f' marks a file that
would be (or was) overwritten from this repo.
EOF
}

APPLY=0
TARGET_INPUT=""
for arg in "$@"; do
  case "$arg" in
    --apply)   APPLY=1 ;;
    -h|--help) usage; exit 0 ;;
    *)
      if [ -d "$arg" ]; then
        TARGET_INPUT="$arg"
      else
        echo "Unknown argument (not a flag or directory): $arg" >&2
        usage; exit 1
      fi
      ;;
  esac
done

command -v rsync >/dev/null 2>&1 || { echo "rsync is required but not installed." >&2; exit 1; }

# ── Collect targets ──────────────────────────────────────────────────────────
# Each target is a "<project-dir>|<subdir>" pair, so one project carrying both
# rules/ and guidelines/ contributes two independent syncs.
#
# The literal */.claude/<subdir> glob is deliberate: it matches only immediate
# children of $PROJECTS_DIR, so git worktrees nested deeper inside a project
# (e.g. fitted/.claude/worktrees/*) are excluded by construction — they pick the
# content up when their branch merges.
targets=()
if [ -n "$TARGET_INPUT" ]; then
  root="$(cd "$TARGET_INPUT" && (git rev-parse --show-toplevel 2>/dev/null || pwd))"
  for sub in "${SUBDIRS[@]}"; do
    [ -d "$root/.claude/$sub" ] && targets+=("$root|$sub")
  done
  if [ ${#targets[@]} -eq 0 ]; then
    log_warn "$root has no .claude/rules/ or .claude/guidelines/ — nothing to push."
    log_warn "To opt it in: mkdir -p $root/.claude/rules && cp <file>.md there, then re-run."
    exit 0
  fi
else
  for sub in "${SUBDIRS[@]}"; do
    for dir in "$PROJECTS_DIR"/*/.claude/"$sub"; do
      # Never push the source onto itself.
      [ "$dir" = "${DOTFILES_DIR}/.claude/$sub" ] && continue
      targets+=("${dir%/.claude/$sub}|$sub")
    done
  done
fi

if [ ${#targets[@]} -eq 0 ]; then
  log_warn "No projects under $PROJECTS_DIR keep committed copies — nothing to do."
  exit 0
fi

# ── Push ─────────────────────────────────────────────────────────────────────
# -c and "no -t" are a matched pair — changing either alone makes every run
# report spurious drift. Both verified against fitted's (identical) copies:
#   with -t:     byte-identical files report `.f..t......` attribute-only
#                updates, so every dry run cries wolf.
#   without -c:  dropping -t leaves destination mtimes newer than source, and
#                rsync's default quick-check compares size+mtime — so all five
#                files report `>f..T......` and get re-copied on every run.
#   -rlpc:       compare by checksum, ignoring mtime entirely. Only real content
#                drift is reported, and mtimes of "now" don't matter in a git repo.
# --existing  never create files or directories the project didn't already have.
# No --delete: project-specific files in that directory must survive.
RSYNC_OPTS=(-rlpc --existing --itemize-changes)
[ "$APPLY" -eq 1 ] || RSYNC_OPTS+=(--dry-run)

if [ "$APPLY" -eq 1 ]; then
  log_info "Pushing into ${#targets[@]} project/directory pair(s)."
else
  log_info "Dry run over ${#targets[@]} project/directory pair(s) — nothing will be written. Re-run with --apply."
fi

changed=0
for target in "${targets[@]}"; do
  root="${target%|*}"
  sub="${target##*|}"
  label="$(basename "$root")/.claude/$sub"
  out="$(rsync "${RSYNC_OPTS[@]}" "${DOTFILES_DIR}/.claude/${sub}/" "${root}/.claude/${sub}/")"
  if [ -n "$out" ]; then
    changed=1
    log_warn "$label"
    echo "$out" | sed 's/^/    /'
  else
    log_info "$label — up to date"
  fi
done

if [ "$changed" -eq 0 ]; then
  log_info "Everything already in sync."
elif [ "$APPLY" -eq 1 ]; then
  log_info "Done. Remember to commit the updated copies in each project repo."
else
  log_info "Re-run with --apply to write these changes."
  log_warn "Local edits shown above will be overwritten — promote.sh them first if any are worth keeping."
fi
