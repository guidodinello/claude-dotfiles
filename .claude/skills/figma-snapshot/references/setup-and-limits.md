# figma-snapshot: setup, layout and limits

## Token

The script needs a Figma personal access token (Figma → Help and account → Account settings → Security → Personal access tokens). Read-only scopes are enough: `file_content:read`, `file_metadata:read`, `file_versions:read`.

Store the token in 1Password without it touching the clipboard history, shell history or `argv`:

```sh
read -rs "tok?Figma token: " && op item create --category "API Credential" --title "Figma PAT" --vault <vault> "credential=$tok" >/dev/null && unset tok && echo && echo stored
```

`$(pbpaste)` doesn't work for this: it reads the clipboard when the command runs. If the user copied the command itself, the item stores the command text. Check an item without revealing it by printing only its length and the `figd_` prefix.

## targets.json

```json
{
  "op_ref": "op://<vault>/<item>/credential",
  "targets": [
    {"name": "my-file", "file_key": "<key from the URL>", "nodes": ["12:345"]}
  ]
}
```

`nodes` takes any node id: a page, a section or a single frame. `add <url>` fills `file_key` and `nodes` from a design URL (`node-id=12-345` becomes `12:345`; a branch URL uses the branch key).

Optional `"tier1_monthly_budget": 15` (the default) caps the Tier 1 calls this snapshot dir makes per UTC month.

Optional `"token_expires": "YYYY-MM-DD"`: the date the token expires, as shown when it was created. The Figma API never reports it, so without this field an expired token only shows up as an HTTP 403 mid-task. With it, `check` and `pull` warn on stderr from 14 days before.

## Budget ledger

- Every successful Tier 1 call is appended to `<dir>/tier1-ledger.json`, grouped by UTC month. Before each Tier 1 call, `pull` refuses once the budget is used up, unless `--over-budget` is passed. `check` and `pull` print the count.
- The default of 15 leaves headroom under the documented 20, because the same docs also say 6.
- The ledger only sees calls this snapshot dir made. Calls made with the same token elsewhere (another project on the same plan, curl by hand) aren't counted, so log them in the ledger yourself if they matter.
- Figma doesn't document whether its monthly window is a calendar month or rolling. The ledger uses calendar months, so treat the first days of a new month with care.

## Output, per target

| Path | What |
|---|---|
| `<node>/<section>/…/` | `NN-<screen>.png` (2x) and `README.md` (flow, designer notes, copy, styles, node ids) |
| `CHANGES.md` | One entry per pull that found changes, newest first, with copy diffs |
| `state.json` | Last pulled version, plus a hash per screen |
| `nodes.json` | Raw `/nodes` response from the last pull (styles, geometry) |

Each screen's Styles section lists every text style (family, weight, size/line height, color) with the copy that uses it, plus fills, strokes, icon colors, radii and non-zero auto-layout padding and gap, with the layer names. Values are raw hex: the REST endpoint for variable names needs an Enterprise plan, so token names are not available. Mixed styles inside one text layer show only the base style; look in `nodes.json` for those.

Regenerating the READMEs after a skill update costs no Tier 1 call: `pull --force --nodes-json <dir>/<target>/nodes.json --no-render`. Run it only when `check` says unchanged: otherwise `state.json` records the new file version against the old `nodes.json`, and the next `pull` misses the changes.

## Rate limits

Source: [Figma REST API rate limits](https://developers.figma.com/docs/rest-api/rate-limits), read 18 Nov 2026.

- Tier 1 (`/files`, `/nodes`, `/images`): up to 20 a month for View and Collab seats. The intro of the same page says 6. Full and Dev seats get 10 to 20 a minute, by plan.
- The plan that owns the file sets the limit, not the plan of the token's owner. Personal access tokens are counted per user and per plan, so teammates don't share your quota, but everything that runs with your token (scripts, workers) does.
- The [MCP limits](https://developers.figma.com/docs/figma-mcp-server/rate-limits-access/) are documented in a separate table (20 tool calls a month for View and Collab seats). Whether they share a counter with the REST tiers is not documented.
- A 429 can carry a `Retry-After` of days: one [forum report](https://forum.figma.com/report-a-problem-6/rest-api-rate-limits-pro-plan-with-full-seat-still-getting-x-figma-rate-limit-type-low-and-multi-day-retry-after-51333) describes multi-day waits. Running out means no design access until it expires.
- Why `pull` should never be scheduled: designers edit some page of the file most working days, so the file version changes almost daily. A daily `pull` would spend 1 or 2 Tier 1 calls a day, more than the monthly quota.
- `check` uses `/meta` (Tier 3) and, only when something changed, `/versions` (Tier 2). Neither touches the Tier 1 quota.
- `pull` spends nothing in Tier 1 when the version is unchanged. Otherwise it makes one `/nodes` call for all of a target's nodes, plus one `/images` call when a screen changed.
- `version` is per file, so an edit to any page bumps it, and `check` may say CHANGED while the tracked nodes are the same.
- Avoid `GET /files/:key` for the whole file: one real file was 448 MB.

## Layout conventions (best effort)

- Screens: `FRAME`, `INSTANCE` or `COMPONENT` children of a page or section. Each child `SECTION` gets a subfolder.
- Designer note: a `TEXT` sibling left-aligned with a screen, within 120 px above it.
- Flow: a `VECTOR` or `LINE` named `arrow` links the nearest screen edges; the nearest `TEXT` named `label` describes the link.
- When a file uses none of these conventions, you still get the PNGs and copy, just no notes and no flow.

## Change detection

- A screen's hash covers its node JSON, with bounding boxes made relative to the screen, so moving a screen on the canvas is not a change.
- `/files` and `/nodes` serialize `fills` and `background` differently. Never compare hashes built from different endpoints: one test produced 63 false changes that way.
