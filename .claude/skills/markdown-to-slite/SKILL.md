---
name: markdown-to-slite
description: Syncs a local Markdown file to a Slite document, overwriting the Slite doc with the local file's content. The local file is always the source of truth — no Slite read needed. Use this skill whenever the user wants to publish, update, or sync a local .md file to Slite, or says things like "sync to Slite", "update Slite doc", "push to Slite", "write this to Slite", "upload to Slite". Also use it when the user has just edited a local doc and wants to reflect those changes in Slite.
---

# markdown-to-slite

Syncs a local Markdown file to a Slite document by overwriting the doc's content. The local file is the source of truth — never read the existing Slite doc first.

## Usage

```
/markdown-to-slite <path/to/file.md> <slite-doc-id>
```

## Prerequisites

Requires `SLITE_API_TOKEN` to be set in the environment. Before any curl call, load it from the macOS keychain:

```bash
export SLITE_API_TOKEN=$(security find-generic-password -s SLITE_API_TOKEN -w)
```

If `SLITE_API_TOKEN` is still unset after this, stop and tell the user to add it to the keychain (`security add-generic-password -U -s SLITE_API_TOKEN -a "$USER" -w '<token>'`).

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
