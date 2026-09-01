---
name: scripts-audit
allowed-tools: Bash Read Grep Glob
description: >
  Verify the scripts directory is consistent — every file under scripts/
  is documented in scripts/CLAUDE.md and every documented script still exists.
  Does NOT modify code — reports only.
---

## Goal

Catch documentation drift in `scripts/`. New scripts are sometimes added
without updating the CLAUDE.md table, and old scripts get renamed or removed
without updating the docs.

---

## Step 1 — Check for undocumented scripts

From the repo root, run:

```bash
# List all .py files in scripts/ (not in __pycache__ or subdirectories with their own purpose)
find scripts/ -maxdepth 2 -name '*.py' ! -path '*/__pycache__/*' ! -path '*/onboarding/artifacts/*' | sort

# Extract documented script names from the table in scripts/CLAUDE.md
grep -E '^\| \`' scripts/CLAUDE.md | sed -E 's/^\| `([^`]+)`.*/\1/' | sort
```

Diff the two lists. Any `.py` file not in the CLAUDE.md table is a **documentation gap**.

Also check for scripts with their own purpose (e.g. anything under `scripts/onboarding/` that isn't listed).

---

## Step 2 — Check for obsolete documentation

For each script name in the CLAUDE.md table, check it still exists on disk:

```bash
for script in $(grep -E '^\| \`' scripts/CLAUDE.md | sed -E 's/^\| `([^`]+)`.*/\1/'); do
  if [ ! -f "scripts/$script" ]; then
    echo "MISSING: $script"
  fi
done
```

---

## Step 3 — Report

| Script | In docs? | On disk? | Action |
|--------|----------|----------|--------|
| `catalog_gap.py` | ✅ | ✅ | — |
| `backfill_llm_enrichment.py` | ❌ | ✅ | Add to CLAUDE.md |
| `compute_clusters.py` | ✅ | ❌ | Remove from CLAUDE.md |

If any gaps exist, update `scripts/CLAUDE.md` (add missing entries, remove deleted references). Suggest this as a pre-PR check for anyone adding a new script.
