---
name: slite-bugs-to-clickup
description: Imports bug reports from a Slite parent document into ClickUp as Bug tickets in the current sprint. Use this skill whenever the user wants to sync, migrate, import, or push Slite bug docs to ClickUp, or says things like "create ClickUp tickets from Slite", "push these Slite bugs to ClickUp", "import our Slite bug reports", "sync bugs from Slite to ClickUp", or shares a Slite doc ID and wants it turned into tasks. Also triggers when the user has a collection of bug write-ups in Slite and wants them tracked in ClickUp without creating each one manually.
---

# slite-to-clickup

Reads all child documents under a Slite parent doc, extracts bug fields from each one using Haiku (cheap extraction), and creates ClickUp Bug tickets in the current sprint using the same template that `clickup-item-generator` enforces.

The key UX design: instead of confirming each ticket individually (very chatty for 10+ bugs), this skill gathers shared fields **once**, infers per-bug fields via Haiku, and shows a **single batch preview** for the user to confirm before creating anything.

---

## Usage

```
/slite-to-clickup <slite-parent-doc-id>
```

---

## Prerequisites

Requires both tokens set in the environment:
- `SLITE_API_TOKEN` — for reading Slite docs
- `CLICKUP_API_TOKEN` — for creating ClickUp tasks

If either is missing, stop and tell the user to add it to `~/.secrets`.

API bases:
- Slite: `https://api.slite.com/v1` — auth header: `Authorization: Bearer $SLITE_API_TOKEN`
- ClickUp: `https://api.clickup.com/api/v2` — auth header: `Authorization: $CLICKUP_API_TOKEN` (no Bearer prefix)

---

## Step 1 — Fetch child documents

```bash
curl -s -o /tmp/slite-children.json \
  -H "Authorization: Bearer $SLITE_API_TOKEN" \
  "https://api.slite.com/v1/notes/PARENT_DOC_ID/children"
```

Parse `/tmp/slite-children.json`. If there are no children, tell the user and stop.

---

## Step 2 — Extract bug fields from each child (use Haiku)

For each child doc, fetch its content:

```bash
curl -s -o /tmp/slite-note.json \
  -H "Authorization: Bearer $SLITE_API_TOKEN" \
  "https://api.slite.com/v1/notes/NOTE_ID"
```

Read the content from `/tmp/slite-note.json`.

Then use the `claude-haiku-4-5-20251001` model (via the Agent tool with `model: "haiku"`) to extract structured fields. Pass it a prompt like:

```
You are extracting bug report fields from a document. The document may be a structured QA report
(with explicit "Steps to Reproduce" / "Expected" / "Actual" sections) or a developer investigation
report (with sections like "Observed", "Root cause", "Impact", "Fix"). Handle both formats.

Document title: <title>
Document content:
<content>

Extract the following fields as JSON. If a field is not present or cannot be inferred, use null.

{
  "is_bug_report": true/false,
  // false only if this doc is clearly NOT a bug — e.g. a meeting note, changelog, or design spec.
  // Developer investigation reports, QA reports, and any doc describing broken behavior = true.

  "title": "...",
  // Use the document title as-is if it is already a good bug title (max 80 chars).

  "description": "...",
  // 1-3 sentences describing what the bug is.

  "preconditions": "...",
  // Any setup needed before the bug can be reproduced. Use null if truly not inferable.

  "steps_to_reproduce": ["step 1", "step 2"],
  // Ordered steps. Reconstruct from context if no explicit section. A rough sequence is better than null.

  "actual_result": "...",
  "expected_result": "...",

  "environment": "prod|uat|stg|dev|local|demo|staging|Pre-prod|null",
  // Only set if explicitly mentioned. Do not guess.

  "severity": "Blocker|Critical|Major|Minor|Trivial|null",
  // Map labels: [Critical]/[Blocker] → Blocker/Critical, [High] → Major, [Medium] → Major, [Low] → Minor.
  // Infer from impact if no label: data loss/crash/always-failing → Critical, degraded → Major, cosmetic → Minor.

  "issue_type": "Functional gap|UX/UI|Crash|Compatibility|Performance|Security|HIPAA Violation|Accessibility|SEO|Content|Tech Debt|Bug|Improvement|null",

  "role": "Frontend|Backend|Frontend & Backend|null"
  // Infer from file paths or context.
}

Return ONLY the JSON object, no explanation.
```

Collect all results. Mark any doc where `is_bug_report: false` as **skipped**.

---

## Step 3 — Gather shared fields from the user (ask once)

Ask in a **single message**:

1. **Environment** — which environment do these bugs come from? (prod, uat, stg, dev, local, demo, staging, Pre-prod). Skip if Haiku inferred it consistently across all bugs.
2. **Detected By** — who found these bugs? (QA Team, Dev Team, Automation, Client/User)
3. **Needs Design?** — default `No` for all; user can update individually in ClickUp if needed.

These answers become defaults. If a specific bug's extracted data has more precise info, use that instead.

---

## Step 4 — Show batch preview

Present a Markdown table summarizing all bugs to be created, plus skipped docs:

```markdown
## Bugs to create (N tickets)

| # | Title | Severity | Issue Type | Role | Environment |
|---|-------|----------|------------|------|-------------|
| 1 | [FE] Login spinner never resolves | Major | Functional gap | Frontend | prod |
| 2 | [BE] Patient search returns 500 | Critical | Crash | Backend | prod |

## Skipped (M docs)
- "Meeting notes 2024-01" — not a bug report

---
Detected By: QA Team | Needs Design: No

¿Confirmás la creación de estos N tickets en ClickUp?
```

Wait for explicit user confirmation. If the user wants to adjust any ticket, update the preview and ask again.

---

## Step 5 — Find the current sprint

```bash
curl -s -o /tmp/clickup-lists.json \
  -H "Authorization: $CLICKUP_API_TOKEN" \
  "https://api.clickup.com/api/v2/folder/FOLDER_ID/list?archived=false"
```

Parse `/tmp/clickup-lists.json` to find the list whose `start_date`/`due_date` range includes today. Folder ID comes from the Project Instructions. This is the same destination `clickup-item-generator` uses.

---

## Step 6 — Create tickets

Once the user confirms, create each ticket:

```bash
curl -s -o /tmp/clickup-task.json -w "%{http_code}" -X POST \
  -H "Authorization: $CLICKUP_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "[FE/BE] TITLE",
    "description": "FILLED_BUG_TEMPLATE",
    "custom_type": "Bug",
    "status": "to do",
    "custom_fields": [
      { "id": "FIELD_UUID", "value": "OPTION_UUID" },
      ...
    ]
  }' \
  "https://api.clickup.com/api/v2/list/LIST_ID/task"
```

If a ticket creation fails, skip it, note the failure, and continue. Report all failures at the end.

### Bug description template

```markdown
📋 Description
{description}

🖥️ Environment
{environment}

1️⃣ Preconditions
{preconditions}

2️⃣ Steps to reproduce
{steps_to_reproduce as numbered list}

📹 Evidence
[Leave blank — user will add manually]

❌ Actual Result
{actual_result}

✅ Expected Result
{expected_result}

🖌️ Figma Link (Optional)
```

### Custom field UUIDs

Use the exact field IDs and option UUIDs from `clickup-item-generator`:

| Field | ID |
|-------|----|
| Environment | `b7560a94-f5ef-4237-a4f3-f9e03379dc14` |
| Issue Severity | `ba89aeae-8d84-40db-a721-4c1720a4f8fd` |
| Issue type | `3ac33494-432d-47ae-8915-a50ef18be944` |
| Role | `a1a7b4f8-5f01-4d34-8222-7959d96a1c81` |
| Detected By | `29179f4a-c79b-408a-8061-c0ec2bea62fc` |
| Needs Design? | `60235493-6f97-40d8-b65c-aa16f4ff39ec` |

**Environment:** `prod` → `034891b0`, `stg` → `9378c010`, `uat` → `65c32794`, `dev` → `4961754f`, `local` → `65079609`, `demo` → `0d34f6e5`, `staging` → `eef56619`, `Pre-prod` → `a6fbab1d`

**Severity:** `Blocker` → `448e182c`, `Critical` → `013512d4`, `Major` → `b43c542c`, `Minor` → `73a15884`, `Trivial` → `57bf6c62`

**Issue type:** `Functional gap` → `5ccc103d`, `UX/UI` → `b5e69714`, `Crash` → `b5647b52`, `Compatibility` → `45f037a2`, `Performance` → `a191c0a8`, `Security` → `630b59cf`, `HIPAA Violation` → `4951932d`, `Accessibility` → `e45ec4f7`, `Bug` → `196286bb`

**Role:** `Frontend` → `a8dc6ec4`, `Backend` → `a4425fc1`, `Frontend & Backend` → `29a70ef9`

**Detected By:** `QA Team` → `e8a4a518`, `Project Team` → `9b03df39`, `Automation` → `9c5d1104`, `Client/User` → `8d2ed167`, `Dev team` → `05e91a4b`

**Needs Design?:** `Yes` → `01f83fbf`, `No` → `9bbcc129`

For any field where the value is null, omit it from `custom_fields` entirely.

---

## Step 7 — Report summary

```
✅ Created N ClickUp tickets in [Sprint Name]:
- [FE] Login spinner never resolves → https://app.clickup.com/t/...
- [BE] Patient search returns 500 → https://app.clickup.com/t/...

⏭️ Skipped M docs (not bug reports):
- "Meeting notes 2024-01"
```

---

## Notes

- The `Evidence` and `Figma Link` sections are always left blank — the team fills them in manually.
- Never attach files. Slite doc content is for extraction context only.
- If the parent doc itself looks like a single bug report with no children worth importing, tell the user and suggest using `clickup-item-generator` directly instead.
