---
name: post-implementation-handoff-comment
description: >
  Generate a post-implementation QA handoff comment for a completed backend
  feature. Use this skill whenever a developer has finished implementing backend
  work and needs to write a comment to post on the ClickUp card to inform QA
  of what was built and what to verify. Trigger when the user says things like
  "write a QA comment", "write the comment for this card", "post-implementation
  comment", "handoff to QA", "write a ClickUp comment", "help me document what
  I did for QA", or "write a ticket description for this backend change". Also
  trigger when the user says "write the description for this subtask" or "write
  a card comment" after finishing implementation. Reads the relevant source
  files to understand what was built and produces a concise developer-to-QA
  handoff note.
disable-model-invocation: true
---

# ClickUp QA Handoff Comment

You're writing a post-implementation comment to be posted on the ClickUp card
after the code is done. The audience is QA — they need to know what was shipped
and what to verify, without reading the code. This is a developer-to-QA
handoff note, not a ticket spec.

## Step 1 — Identify what changed

If the user hasn't pointed you at specific files, find them. Try `origin/develop`
first; fall back to `origin/main` if that ref doesn't exist:

```bash
git diff --name-only origin/develop...HEAD 2>/dev/null || git diff --name-only origin/main...HEAD
```

Look for changes in:

- Controllers: `src/Fifty410/{Entity}/App/Controllers/`
- Actions: `src/Fifty410/{Entity}/Domain/Actions/`
- Resources: `src/Fifty410/{Entity}/App/Resources/`
- Models: `src/Fifty410/{Entity}/Domain/Models/`
- Migrations: `database/migrations/`
- Routes: `routes/api.php`
- Seeders: `database/seeders/` (only if changed)
- Feature tests: `tests/Feature/` (if present — test names map directly to behaviors)

## Step 2 — Read the relevant files

Read them in parallel. Extract:

**From controllers and routes:**

- HTTP method, path, auth requirements, route constraints (e.g. numeric IDs only)

**From resources:**

- The full JSON response shape — every field name and type

**From action files** _(this is the most important source for understanding what the code actually does)_:

- **Filtering/exclusion rules**: every `whereNot`, `where`, `whereHas` condition tells you what gets excluded and why — each one is something QA should verify
- **Data scoping**: does the action scope results to the authenticated user? (e.g. `where('patient_id', $patient->id)`) — isolation from other users' data is something QA should verify
- **Deduplication**: does it group by something and keep only the latest/first?
- **Ordering**: does it sort by a field or a custom priority map?
- **Empty-state cases**: what happens when a pivot/relation has no records?

**From feature test files** _(if present)_:

- Each `it('...')` description is a behavior the endpoint must satisfy — translate test names into plain English for QA
- Tests are ground truth for edge cases; prefer them over guessing

**From migrations and seeders:**

- Column names and SQL types added; what the seeder now populates

## Step 3 — Write the comment

Use this exact template. Output it as a markdown code block (` ```markdown `) so
the user can copy-paste it directly into ClickUp.

---

```markdown
## Summary
One sentence. What was implemented and what endpoint exposes it.

## What was done

- **Migration:** Added `column_name` (type) [and `column_name` (type)] columns. _(omit if no migration)_
- **Seeder:** Updated to populate [fields]. _(omit if no seeder change)_
- **Model/Resource:** [Fields] are declared on the model and included in the API response. _(omit if no model/resource change)_
- **Endpoint:** Added `METHOD /api/path/{param}` (authenticated), which returns:

```json
{
  "data": [
    {
      "id": 1,
      "field_from_resource": "realistic example value"
    }
  ]
}
```
```

---

## Guidelines

- **QA audience**: no instructions to run migrations, seeders, or artisan commands — they test the live endpoint only.
- **JSON example**: use realistic placeholder values, not generic `"string"` or `null`. Make it clear they're illustrative.
- **Multiple endpoints**: add one **Endpoint** bullet per endpoint.
- **Omit sections that don't apply**: if no migration changed, skip that bullet entirely.
- **This is a handoff note, not a spec**: write as if you're briefing your QA colleague on what just shipped. Confident, specific, no fluff.

## Reference output

This is the gold-standard output — calibrate tone, length, and depth of the
acceptance criteria section against this:

---

````markdown
## Summary
Added `GET /api/symptoms/{id}/biomarkers` endpoint that returns the patient's latest lab result for each biomarker associated with a given symptom, ordered by severity (Critical → Abnormal → Normal).

## What was done

- **Endpoint:** Added `GET /api/symptoms/{symptom}/biomarkers` (authenticated), which returns:

```json
{
  "data": [
    {
      "id": 12,
      "lab_id": 5,
      "name": "Progesterone",
      "result": "5.0",
      "type": "Numeric",
      "unit": "mg/dL",
      "interpretation": "Normal",
      "loinc_slug": "2839-9",
      "min_range_value": 4.0,
      "max_range_value": 5.6,
      "is_above_max_range": false,
      "is_below_min_range": false,
      "product": {
        "id": 3,
        "slug": "hormone-longevity",
        "display_name": "Hormone & Longevity",
        "description": "Panel covering hormonal and longevity markers",
        "price_in_cents": 0,
        "image_url": null,
        "tag": null,
        "characteristics": []
      },
      "biomarker": {
        "id": 1,
        "name": "Progesterone",
        "description": "A steroid hormone involved in the menstrual cycle",
        "loinc_slug": "2839-9",
        "weight": 1
      },
      "created_at": "2026-01-20T00:00:00+00:00",
      "updated_at": "2026-01-20T00:00:00+00:00"
    }
  ]
}
```
````
