---
name: markdown-to-slite
description: 'Sync a local Markdown file to a Slite document, overwriting it (the local file is the source of truth).'
---

# markdown-to-slite

Syncs a local Markdown file to a Slite document by overwriting the doc's content. The local file is the source of truth — never read the existing Slite doc first.

## Usage

```
/markdown-to-slite <path/to/file.md> <slite-doc-id>
```

## Prerequisites

Requires `SLITE_API_TOKEN` to be set in the environment. Before any curl call, load it from 1Password, falling back to the macOS keychain:

```bash
export SLITE_API_TOKEN=$(op read "op://Private/SLITE_API_TOKEN/password" 2>/dev/null || security find-generic-password -s SLITE_API_TOKEN -a "$USER" -w)
```

If `SLITE_API_TOKEN` is still unset after this, stop and tell the user to add it (`op item create --category=password --title=SLITE_API_TOKEN --vault=Private password='<token>'` or `security add-generic-password -U -s SLITE_API_TOKEN -a "$USER" -w '<token>'`).

## Style rules

Before syncing, enforce these rules on the file content:

- **No em dashes (—)**: replace with a colon, comma, or parentheses depending on context. Never use a plain hyphen as a substitute unless it's already a hyphenated word.

## Steps

1. Parse the two arguments: the local file path and the Slite doc ID.

2. Read the local file. Apply the style rules above to the content. Overwrite the local file with the cleaned content.

3. Spawn the `slite-sync` agent using the Agent tool, passing only the file path and doc ID:

   ```
   File path: <path>
   Slite doc ID: <doc-id>
   ```

4. Report the agent's one-line result to the user. Nothing more.
