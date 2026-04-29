---
name: slite-sync-to-clickup-doc
description: Syncs the content of a Slite document to a ClickUp Doc page, overwriting the ClickUp page with the Slite content. The Slite doc is always the source of truth. Use this skill whenever the user wants to push, sync, mirror, or copy a Slite doc to ClickUp, says things like "sync Slite to ClickUp", "move this Slite doc to ClickUp", "update the ClickUp doc from Slite", or provides both a Slite URL/ID and a ClickUp doc URL.
---

# slite-to-clickup-doc

Fetches a Slite document's markdown content and overwrites a ClickUp Doc page with it. Slite is the source of truth — the ClickUp page is always overwritten.

## Usage

```
/slite-to-clickup-doc <slite-doc-id-or-url> <clickup-page-url>
```

**Examples:**
```
/slite-to-clickup-doc Zaw50HTALbpo69 https://app.clickup.com/3015277/v/dc/2w0kd-311357/2w0kd-147937
/slite-to-clickup-doc https://lightit.slite.com/api/s/Zaw50HTALbpo69/DB-Migration-Plan https://app.clickup.com/3015277/v/dc/2w0kd-311357/2w0kd-147937
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

Build the payload and PUT it to the ClickUp Docs API:

```bash
python3 -c "
import json
with open('/tmp/slite-doc.json') as f:
    data = json.load(f)
payload = {'name': data.get('title', ''), 'content': data.get('content', '')}
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
- A one-liner confirming the Slite doc that was the source
