---
name: slite-compare-docs
description: >
  Compare two Slite documents to check whether one supersedes the other — i.e., that no content
  was lost when creating a newer version. Use this skill whenever the user wants to diff Slite docs,
  check if a "Copy of" document can be safely archived or deleted, verify that a newer document
  contains everything the old one had, or asks "did we lose anything?", "is this a superseding
  version?", "can I delete the old one?", or "compare these Slite documents". Trigger even if the
  user just pastes two Slite URLs and asks a vague comparison question.
---

## What this skill does

Fetch two Slite documents, diff their content, and tell the user:
- Whether the newer doc is a strict superset (nothing lost)
- What was added, changed, or removed
- Whether it is safe to archive or delete the older doc

---

## Step 1: Parse document IDs from the input

Slite URLs follow this pattern:

```
https://lightit.slite.com/api/s/<NOTE_ID>/Some-Title-Slug
https://lightit.slite.com/app/docs/<NOTE_ID>
```

Extract the `<NOTE_ID>` from each URL. If the user provided bare IDs instead of URLs, use them directly.

If only one URL/ID was given, ask for the second one before proceeding.

---

## Step 2: Fetch both documents in parallel

Call `mcp__claude_ai_Slite__get-note` for both IDs at the same time (same turn, two tool calls). Use `format: "md"` — markdown is the most diff-friendly format.

The response will be a JSON object. The document content is in the `content` field.

---

## Step 3: Write content to temp files and diff

Use Python to extract the content from both responses and write them to `/tmp/slite_doc_a.md` and `/tmp/slite_doc_b.md`. Then run a unified diff.

```python
import json, subprocess

# doc_a_json and doc_b_json are the parsed JSON from the Slite responses
content_a = doc_a_json["content"]
content_b = doc_b_json["content"]

with open("/tmp/slite_doc_a.md", "w") as f:
    f.write(content_a)
with open("/tmp/slite_doc_b.md", "w") as f:
    f.write(content_b)

result = subprocess.run(
    ["diff", "/tmp/slite_doc_a.md", "/tmp/slite_doc_b.md"],
    capture_output=True, text=True
)
print(result.stdout or "(no differences)")
```

If the documents are large (>20KB), write the content to disk first and diff the files rather than diffing in-memory strings — `diff` handles large files much more efficiently.

The diff output uses this convention:
- Lines starting with `<` are only in doc A (the first/older one)
- Lines starting with `>` are only in doc B (the second/newer one)
- Lines starting with `---` are context markers

---

## Step 4: Analyze and report

Read the diff output and produce a clear verdict. Structure your report like this:

---

**Doc A:** `<title>` ([link](<url>))
**Doc B:** `<title>` ([link](<url>))

### Verdict: [Safe to archive Doc A / Content was lost — do not archive / Identical]

**Summary:** One sentence explaining the overall relationship.

### What Doc B adds (not in Doc A)
List the meaningful additions — new sections, new findings, updated dates, extra items. Skip trivial differences like title-only changes ("Copy of …" → original name).

### What Doc A has that Doc B doesn't
List anything present in Doc A but absent in Doc B. If there is nothing, say "Nothing — Doc B is a complete superset."

### Recommendation
One clear action: archive Doc A / keep both / investigate further.

---

Keep the report tight. The user wants a decision, not a line-by-line transcript of the diff. Group related changes together and call out only meaningful differences.

---

## Edge cases

- **Identical content:** Say so directly and confirm both are safe to consolidate.
- **Doc A has unique content:** Flag it clearly — do not recommend archiving until the user resolves the gap.
- **Very large diffs:** Summarize by section rather than listing every changed line. Focus on structural differences (new headings, removed sections) rather than wording tweaks.
- **Slite MCP not connected:** Tell the user the Slite MCP is required and is not currently available.
