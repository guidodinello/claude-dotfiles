---
name: clickup-create-ticket
description: Creates Bug, Improvement, or Task tickets in the current sprint on ClickUp using the correct template for the active project. Use whenever the user wants to log a bug, report an issue, propose an improvement, or create a task ticket. Also triggers when the user shares a screenshot or video of a problem and wants it tracked. Never attach files — photos or videos shared by the user are for context only.
---

# ClickUp Ticket Creator

Creates structured ClickUp tickets in the **current sprint** using the correct template, with a **preview step** before submission.

---

## Prerequisites

Requires `CLICKUP_API_TOKEN` set in the environment. Before any curl call, load it from the macOS keychain:

```bash
export CLICKUP_API_TOKEN=$(security find-generic-password -s CLICKUP_API_TOKEN -w)
```

If `CLICKUP_API_TOKEN` is still unset after this, stop and tell the user to add it to the keychain (`security add-generic-password -U -s CLICKUP_API_TOKEN -a "$USER" -w '<token>'`).

All API calls use:
```
Authorization: $CLICKUP_API_TOKEN
Content-Type: application/json
Base URL: https://api.clickup.com/api/v2
```

Note: ClickUp auth uses no `Bearer` prefix — the token is sent as a raw header value.

---

## Key Rules

- **Always create tickets in the current sprint list** inside the project folder defined in the Project Instructions.
- **Never attach files** — if the user sends a photo or video, use it only to understand the issue. Do not attach it to the ticket.
- **Always infer the ticket type** from context: Bug, Improvement, or Task.
- **Always preview the ticket as .md** before creating it in ClickUp. Wait for explicit user confirmation.
- Ask clarifying questions if you don't have enough information to fill out the template properly.
- **Before creating a new ticket**, search ClickUp filtered by epic (`[EllaDx] Epic`) to check if a similar ticket already exists. If one does, complete or update that ticket instead of creating a duplicate. Tickets must reflect the issue at the product/business level — not as isolated technical items.
- **Title and first paragraph must describe the business or user flow impact.** The technical explanation comes after. Never put `[FE]`, `[MB]`, `[High]`, or similar tags in the title — those go in the board's custom field columns.

### Bug vs Improvement

- **Bug** = something broken or behaving unexpectedly.
- **Improvement** = something that works but could be improved, implying a change in the flow or business logic. **Requires a product decision before implementing.**

**Special case — Bug needing a definition**: If the issue is clearly a bug but the correct behavior is ambiguous or undefined, mark the Expected Result field with a note that a product definition is required, then ask the user how they want it to work before proceeding.

---

## ClickUp Destination

Read the project's **Project Instructions** to get:

| Field | Source |
|-------|--------|
| **Folder ID** | From `ClickUp > Folder` in Project Instructions |
| **Space ID** | From `ClickUp > Space` in Project Instructions |

**Status for new tickets**: `to do`

---

## How to Find the Current Sprint List

The current sprint is the one whose date range includes **today's date**.

```bash
curl -s -o /tmp/clickup-lists.json \
  -H "Authorization: $CLICKUP_API_TOKEN" \
  "https://api.clickup.com/api/v2/folder/FOLDER_ID/list?archived=false"
```

Parse `/tmp/clickup-lists.json`: each list has a `name`, `id`, `start_date`, and `due_date` (Unix ms timestamps). Find the list whose date range includes today.

If sprint names don't contain dates, use the most recently created active list.

---

## Templates

### Bug Template

```markdown
📋 Description
[Clear description of the bug]

🖥️ Environment
[Complete with environment provided]

1️⃣ Preconditions
[Preconditions necessary to reproduce the bug]

2️⃣ Steps to reproduce
1. Log in as a [specific role/user type]
2. [Next step]
3. [Next step]

📹 Evidence
[Leave blank — user will add manually]

❌ Actual Result
[What actually happens]

✅ Expected Result
[What should happen]

🖌️ Figma Link (Optional)
[Link if applicable]
```

### Improvement Template

```markdown
📋 Description
[Description of the improvement]

📹 Evidence
[Leave blank — user will add manually]

❌ Current Behavior
[What currently happens]

✅ Proposed Improvement
[What should happen instead]
```

### Task Template

```markdown
📋 Description
[Description of the task]

✅ Technical Requirements
[List of technical requirements]

🧪 Acceptance Criteria
[List of acceptance criteria]

🖌️ Figma Link (Optional)
[Link if applicable]
```

---

## Custom Fields (Bug tickets only)

When the ticket type is **Bug**, fill in the following custom fields. **Group all questions together** (including `[FE]`/`[BE]` confirmation) and ask the user in a **single message** before generating the preview.

| Field | ID | Behavior |
|-------|----|----------|
| **Environment** | `b7560a94-f5ef-4237-a4f3-f9e03379dc14` | Ask the user. Options: `prod`, `uat`, `stg`, `dev`, `local`, `demo`, `staging`, `Pre-prod` |
| **⚡ Issue Severity** | `ba89aeae-8d84-40db-a721-4c1720a4f8fd` | Suggest based on context and ask to confirm. Options: `Blocker`, `Critical`, `Major`, `Minor`, `Trivial` |
| **⚡ Issue type** | `3ac33494-432d-47ae-8915-a50ef18be944` | Infer from context. Ask to confirm. Options: `Functional gap`, `UX/UI`, `Crash`, `Compatibility`, `Performance`, `Security`, `HIPAA Violation`, `Accessibility`, `SEO`, `Content`, `Tech Debt`, `Bug`, `Improvement` |
| **⚡ Role** | `a1a7b4f8-5f01-4d34-8222-7959d96a1c81` | Set based on `[FE]`/`[BE]` confirmed by user. |
| **⚡ Detected By** | `29179f4a-c79b-408a-8061-c0ec2bea62fc` | Always ask the user. Options: `QA Team`, `Dev Team`, `Automation`, `Client/User` |
| **Needs Design?** | `60235493-6f97-40d8-b65c-aa16f4ff39ec` | Ask the user. Options: `Yes`, `No` |

### Custom Field Option UUIDs

Use these exact UUIDs as the `value` for dropdown fields in the API payload.

**Environment** (`b7560a94-f5ef-4237-a4f3-f9e03379dc14`):
- `prod` → `034891b0-f803-4970-97aa-ea384b0bd247`
- `stg` → `9378c010-ab7d-4a6b-92c1-4ce6fd3418b4`
- `uat` → `65c32794-fcc8-4bdd-8791-ad361d462188`
- `dev` → `4961754f-6a2a-42e6-97c9-09866f649d9d`
- `local` → `65079609-50bb-458a-8699-77396d279c69`
- `demo` → `0d34f6e5-f886-4455-8570-69ac8c019e2e`
- `staging` → `eef56619-b932-457c-ace1-bc42911ca1c9`
- `Pre-prod` → `a6fbab1d-7b70-488a-a0f5-acaef9f03995`

**⚡ Issue Severity** (`ba89aeae-8d84-40db-a721-4c1720a4f8fd`):
- `Blocker` → `448e182c-9f3e-4d85-bc6a-7253eb9ec8b2`
- `Critical` → `013512d4-c0d2-4f61-9da3-3069d64b1ec2`
- `Major` → `b43c542c-89ae-4816-aecd-96ba33de0c78`
- `Minor` → `73a15884-ce4f-4abf-9bc2-6a4d2ca60f9a`
- `Trivial` → `57bf6c62-837b-4376-bec0-df470ada7c10`

**⚡ Issue type** (`3ac33494-432d-47ae-8915-a50ef18be944`):
- `Functional gap` → `5ccc103d-6b05-4fb3-968e-5f5c3752014a`
- `UX/UI` → `b5e69714-f178-43ad-97a4-0bab2758ddb5`
- `Crash` → `b5647b52-5711-4c0f-b61e-4894c9149e7c`
- `Compatibility` → `45f037a2-31f2-49a7-9de9-0fa723ca06a0`
- `Performance` → `a191c0a8-ca54-4637-bde6-b3035ffdaa0c`
- `Security` → `630b59cf-0ba6-4220-a97c-13055dc4b3c3`
- `HIPAA Violation` → `4951932d-7409-41b9-a7c7-9c9caaffef94`
- `Accessibility` → `e45ec4f7-1708-4a5c-915f-c76024d1d8e3`
- `Bug` → `196286bb-41ec-425c-b04e-22d5a8940201`

**⚡ Role** (`a1a7b4f8-5f01-4d34-8222-7959d96a1c81`):
- `Frontend` → `a8dc6ec4-e5a9-404d-ad25-0d05cd55e68f`
- `Backend` → `a4425fc1-6c29-4db6-b7f5-e36297a29b4b`
- `Frontend & Backend` → `29a70ef9-3cff-4018-a795-4b8b7601d4af`

**⚡ Detected By** (`29179f4a-c79b-408a-8061-c0ec2bea62fc`):
- `QA Team` → `e8a4a518-cab6-4dd7-953a-527514eb2fa2`
- `Project Team` → `9b03df39-3bb6-447b-abe2-e57e9bb78bf6`
- `Automation` → `9c5d1104-d68e-4ebd-a70f-432b58788875`
- `Client/User` → `8d2ed167-c7f9-42c7-bb78-f68be81a0099`
- `Dev team` → `05e91a4b-4b54-406c-9c98-8fc915df4853`

**Needs Design?** (`60235493-6f97-40d8-b65c-aa16f4ff39ec`):
- `Yes` → `01f83fbf-9e74-4316-b261-40e7e71c1f2e`
- `No` → `9bbcc129-3350-4fff-ac80-ff72f6884c4e`

---

## Workflow

### Step 0 — Check for duplicate tickets
Before doing anything else, search ClickUp for existing tickets in the same epic (`[EllaDx] Epic` field) that may already cover the same issue. If a match is found, surface it to the user and ask whether to update the existing ticket instead.

### Step 1 — Identify ticket type
Determine if it's a **Bug**, **Improvement**, or **Task** from the user's message and any context (including screenshots or videos). If the issue is a bug but the expected behavior is unclear or undefined, flag this immediately and ask the user to define the expected behavior before proceeding.

### Step 2 — Gather required info
- If anything is missing, ask the user.
- **For Bugs**: gather all custom field values. Group **all** questions (environment, severity, issue type, `[FE]`/`[BE]`, detected by, needs design) into a **single message**.

### Step 3 — Ask for related task (Bugs only)
Ask if this bug is related to an existing ClickUp task:
1. **Provide the URL** of the related task.
2. **Not related** — skip.

If a URL is provided, extract the task ID (e.g., `https://app.clickup.com/t/86abcdef` → `86abcdef`).

### Step 4 — Find the current sprint

```bash
curl -s -o /tmp/clickup-lists.json \
  -H "Authorization: $CLICKUP_API_TOKEN" \
  "https://api.clickup.com/api/v2/folder/FOLDER_ID/list?archived=false"
```

Parse `/tmp/clickup-lists.json` to find the list whose `start_date`/`due_date` range includes today.

### Step 5 — Generate preview as .md
Fill the appropriate template and present the full ticket to the user, including:
- **Title** (must describe the business/user flow impact — no `[FE]`/`[BE]`/severity tags in the title)
- **Type** (Bug / Improvement / Task)
- **Description** (filled template)
- **Custom fields summary** (for Bugs)
- **Related task** (URL if provided, or "None")
- **Target sprint list**

Ask: **"¿Confirmás la creación de este ticket en ClickUp?"**

### Step 6 — Wait for confirmation
Do NOT create the ticket until the user explicitly confirms. If changes are requested, update the preview and ask again.

### Step 7 — Create the ticket

Write a params file and spawn the `clickup-create-task` agent:

```python
import json
params = {
    "list_id": "LIST_ID",
    "name": "TICKET_TITLE",
    "description": "FILLED_TEMPLATE_BODY",
    "custom_type": "Bug",  # or "Improvement" / "Task"
    "status": "to do",
    "custom_fields": [
        {"id": "FIELD_UUID", "value": "OPTION_UUID"},
    ],
    # Include only for Bug tickets with a related task:
    "related_task_id": "RELATED_TASK_ID",
}
# Omit custom_fields for non-Bug tickets.
# Omit related_task_id if none.
with open('/tmp/clickup-new-ticket.json', 'w') as f:
    json.dump(params, f)
```

Spawn the `clickup-create-task` agent using the Agent tool, passing:

```
Params file: /tmp/clickup-new-ticket.json
```

### Step 8 — Confirm

Reply with the agent's one-line result. If cross-comments were added, append: "Se agregaron comentarios cruzados en ambas tareas."

---

## Example Interaction

**User**: "Hay un bug en la app mobile — cuando un paciente intenta subir una foto de su comida, la app se queda en un spinner infinito."

**Claude should**:
1. Identify this as a **Bug**.
2. Ask (in a single grouped message):
   - ¿En qué ambiente ocurre? (prod, uat, stg, dev...)
   - Sugiero severity **Major** — ¿confirmás?
   - Parece un issue tipo **Functional gap** — ¿confirmás?
   - ¿Es Frontend, Backend, o ambos? (para el campo Role — no va en el título)
   - ¿Quién lo detectó? (QA Team, Dev Team, Automation, Client/User)
   - ¿Necesita pasar por diseño primero?
3. Ask: ¿Este bug está relacionado a alguna task existente en ClickUp?
4. Fill the Bug template with all info.
5. Present a `.md` preview.
6. Wait for confirmation.
7. Create the task via REST API.
8. Add cross-comments if related task was provided.
9. Share the link and confirm.
