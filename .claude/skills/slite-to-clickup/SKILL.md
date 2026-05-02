---
name: slite-to-clickup
description: Syncs the content of a Slite document to a ClickUp Doc page, overwriting the ClickUp page with the Slite content. The Slite doc is always the source of truth. Use this skill whenever the user wants to push, sync, mirror, or copy a Slite doc to ClickUp, says things like "sync Slite to ClickUp", "move this Slite doc to ClickUp", "update the ClickUp doc from Slite", or provides both a Slite URL/ID and a ClickUp doc URL.
---

# slite-to-clickup

Fetches a Slite document's markdown content and overwrites a ClickUp Doc page with it. Slite is the source of truth — the ClickUp page is always overwritten.

## Usage

```
/slite-to-clickup <slite-doc-id-or-url> <clickup-page-url>
```

**Examples:**
```
/slite-to-clickup Zaw50HTALbpo69 https://app.clickup.com/3015277/v/dc/2w0kd-311357/2w0kd-147937
/slite-to-clickup https://lightit.slite.com/api/s/Zaw50HTALbpo69/DB-Migration-Plan https://app.clickup.com/3015277/v/dc/2w0kd-311357/2w0kd-147937
```

## Prerequisites

Requires both tokens set in the environment. Run:

```bash
source ~/.secrets
```

Check that `SLITE_API_TOKEN` and `CLICKUP_API_TOKEN` are both set. If either is missing, stop and tell the user to add it to `~/.secrets`.

## Step 1 — Parse arguments

From the Slite argument, extract the doc ID:
- If it's a URL like `https://lightit.slite.com/api/s/DOCID/Title`, extract `DOCID`
- If it's already a bare ID (no slashes), use it as-is

From the ClickUp URL (`https://app.clickup.com/{workspace_id}/v/dc/{doc_id}/{page_id}`), extract:
- `workspace_id` — first path segment after the domain
- `doc_id` — third segment after `v/dc/`
- `page_id` — fourth segment after `v/dc/`

## Step 2 — Fetch Slite content

```bash
curl -s -o /tmp/slite-doc.json \
  -H "Authorization: Bearer $SLITE_API_TOKEN" \
  "https://api.slite.com/v1/notes/SLITE_DOC_ID"
```

Parse `/tmp/slite-doc.json` with Python. Extract:
- `title` from the `title` field
- `content` from the `content` field (this is markdown)

If the response contains an error key or the content is empty, stop and report the error to the user.

```python
import json
with open('/tmp/slite-doc.json') as f:
    data = json.load(f)
title = data.get('title', '')
content = data.get('content', '')
print(f"Title: {title}, Content length: {len(content)}")
```

## Step 3 — Push content to ClickUp

Write the Slite content to a temp file, then spawn the `clickup-sync` agent:

```bash
python3 -c "
import json
with open('/tmp/slite-doc.json') as f:
    data = json.load(f)
with open('/tmp/slite-content.md', 'w') as f:
    f.write(data.get('content', ''))
"
```

Spawn the `clickup-sync` agent using the Agent tool, passing:

```
File path: /tmp/slite-content.md
Workspace ID: <workspace-id>
Doc ID: <doc-id>
Page ID: <page-id>
```

## Step 4 — Report

Tell the user the agent's one-line result plus a note confirming which Slite doc was the source.
