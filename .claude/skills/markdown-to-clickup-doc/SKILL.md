---
name: markdown-to-clickup-doc
description: Syncs a local Markdown file to a ClickUp Doc page, overwriting it with the file's content. The local file is always the source of truth. Use this skill whenever the user wants to push, sync, or upload a local markdown file to ClickUp, says things like "sync this markdown to ClickUp", "upload this file to ClickUp", "update the ClickUp doc from this file", or provides a local file path and a ClickUp doc URL.
---

# markdown-to-clickup-doc

Reads a local Markdown file and overwrites a ClickUp Doc page with its content. The local file is the source of truth — the ClickUp page is always overwritten.

## Usage

```
/markdown-to-clickup-doc <file-path> <clickup-page-url>
```

**Examples:**
```
/markdown-to-clickup-doc ./docs/audit.md https://app.clickup.com/3015277/v/dc/2w0kd-311357/2w0kd-147937
/markdown-to-clickup-doc /Users/me/reports/summary.md https://app.clickup.com/3015277/v/dc/2w0kd-311357/2w0kd-147937
```

## Prerequisites

Requires the ClickUp token set in the environment. Load it from 1Password, falling back to the macOS keychain:

```bash
export CLICKUP_API_TOKEN=$(op read "op://Private/CLICKUP_API_TOKEN/password" 2>/dev/null || security find-generic-password -s CLICKUP_API_TOKEN -a "$USER" -w)
```

Check that `CLICKUP_API_TOKEN` is set. If it is missing, stop and tell the user to add it (`op item create --category=password --title=CLICKUP_API_TOKEN --vault=Private password='<token>'` or `security add-generic-password -U -s CLICKUP_API_TOKEN -a "$USER" -w '<token>'`).

## Markdown format support & limitations

The v3 Docs API ingests **standard Markdown** via `content_format: text/md`. Standard block types
work: headings (`#`/`##`/`###`), bold/italic, bullet and numbered lists, links, code blocks, blockquotes,
tables. Use these freely.

What does **not** work (verified empirically, 2026-06-17):

- **Collapsible / toggle sections are not creatable via the API.** Toggles are an editor-only block
  type. There is no Markdown or HTML syntax you can send that produces a real fold/expand toggle:
  - `+++ Heading ... +++` (the syntax some ClickUp surfaces accept) renders as **literal `+++` text**.
  - On *read*, an existing toggle round-trips as a plain indented bullet (`*   Heading` with the body
    indented 4 spaces beneath it) — so even copying that representation back in just yields a nested
    bullet list, not a toggle.
  - `content_format: text/html` returns an **empty body** on GET, so the HTML route is not usable for
    round-tripping either.
  - **If the user asks for collapsible sections, do not attempt `+++`.** Use `##` headings instead
    (clean and skimmable), and tell the user that true toggles can only be added by hand in the editor
    (`/toggle`), and that any future re-sync from the file will flatten them back to bullets.

When unsure whether a given block type survives, the reliable test is: have the user create it manually
in the editor, then GET the page with `?content_format=text/md` and inspect how it comes back. If it
round-trips as something you can't reproduce with standard Markdown, fall back to headings.

## Step 1 — Parse arguments

From the file path argument, resolve the absolute path of the markdown file. Verify it exists and is readable; if not, stop and report the error.

From the ClickUp URL (`https://app.clickup.com/{workspace_id}/v/dc/{doc_id}/{page_id}`), extract:
- `workspace_id` — first path segment after the domain
- `doc_id` — third segment after `v/dc/`
- `page_id` — fourth segment after `v/dc/`

## Step 2 — Read local file

```python
from pathlib import Path
p = Path('FILE_PATH')
content = p.read_text(encoding='utf-8')
title = p.stem.replace('-', ' ').replace('_', ' ').title()
print(f"Title: {title}, Content length: {len(content)}")
```

Use the filename stem (without extension) as the page title, converted to title case with hyphens and underscores replaced by spaces.

If the file is empty, stop and tell the user.

## Step 3 — Push content to ClickUp

Build the payload and PUT it to the ClickUp Docs API:

```bash
python3 -c "
import json
from pathlib import Path
content = Path('FILE_PATH').read_text(encoding='utf-8')
title = Path('FILE_PATH').stem.replace('-', ' ').replace('_', ' ').title()
payload = {'name': title, 'content': content}
with open('/tmp/clickup-payload.json', 'w') as f:
    json.dump(payload, f)
"

curl -s -X PUT \
  -H "Authorization: $CLICKUP_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d @/tmp/clickup-payload.json \
  -o /tmp/clickup-response.json \
  -w "%{http_code}" \
  "https://api.clickup.com/api/v3/workspaces/WORKSPACE_ID/docs/DOC_ID/pages/PAGE_ID"
```

ClickUp returns an **empty body** (HTTP 200) on success — an empty `/tmp/clickup-response.json` is expected and correct. Only treat it as a failure if the HTTP status code is 4xx or 5xx.

Note: ClickUp auth uses no Bearer prefix — the header is `Authorization: $CLICKUP_API_TOKEN` directly.

## Step 4 — Verify

Re-fetch the page to confirm content was saved:

```bash
curl -s -H "Authorization: $CLICKUP_API_TOKEN" \
  "https://api.clickup.com/api/v3/workspaces/WORKSPACE_ID/docs/DOC_ID/pages/PAGE_ID" \
  -o /tmp/clickup-verify.json
```

Parse with Python, stripping control characters before JSON parsing (the API sometimes includes them in content):

```python
import json, re
with open('/tmp/clickup-verify.json', 'rb') as f:
    raw = f.read()
cleaned = re.sub(rb'[\x00-\x08\x0b\x0c\x0e-\x1f]', b' ', raw)
d = json.loads(cleaned)
content = d.get('content', '')
print(f"Page name: {d.get('name')}, Content length: {len(content)}")
```

If content length is 0, report failure. Otherwise report success with the page name and character count.

## Step 5 — Report

Tell the user:
- The ClickUp page name and URL that was updated
- How many characters were written
- The local file path that was the source
