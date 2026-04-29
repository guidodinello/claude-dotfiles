---
name: clickup-task-description
description: Generate a ClickUp subtask description for a completed backend feature. Use this skill whenever a developer asks to write, draft, or create a ClickUp task description, subtask description, or ticket description for backend work they've just implemented. Also trigger when the user says things like "write the description for this subtask", "help me document what I did for QA", or "write a ticket description for this backend change". Reads the relevant source files to understand what was built and produces a concise, QA-oriented description.
disable-model-invocation: true
---

# ClickUp Task Description

Generate a concise, QA-oriented ClickUp subtask description by reading the relevant source files to understand what was implemented.

## Step 1 — Identify what changed

If the user hasn't pointed you at specific files, find them. Try `origin/develop` first; fall back to `origin/main` if that ref doesn't exist:

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

**From action files** *(this is the most important source for behaviors to test)*:
- **Filtering/exclusion rules**: every `whereNot`, `where`, `whereHas` condition tells you what gets excluded and why — each one is a behavior to test
- **Data scoping**: does the action scope results to the authenticated user? (e.g. `where('patient_id', $patient->id)`) — if so, isolation from other users' data is a behavior to test
- **Deduplication**: does it group by something and keep only the latest/first? — if so, "returns only the most recent result per X" is a behavior to test
- **Ordering**: does it sort by a field or a custom priority map? — if so, the sort order is a behavior to test
- **Empty-state cases**: what happens when a pivot/relation has no records? — derive empty-response behaviors from the query structure

**From feature test files** *(if present)*:
- Each `it('...')` description is a behavior the endpoint must satisfy — translate test names into QA-friendly language
- Tests are the ground truth for edge cases; prefer them over guessing

**From migrations and seeders:**
- Column names and SQL types added; what the seeder now populates

## Step 3 — Write the description

Use this exact template (no extra sections, no fluff):

---

**Summary**
One sentence. What behavior was added and what endpoint exposes it.

**What was done**
- **Migration:** Added `column_name` (type) [and `column_name` (type)] columns. *(omit if no migration)*
- **Seeder:** Updated to populate [fields]. *(omit if no seeder change)*
- **Model/Resource:** [Fields] are declared on the model and included in the API response. *(omit if no model change)*
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
Populate the JSON with the actual fields from the resource file. Use realistic placeholder values — not `"string"` or `null`. Do not use `...` or leave placeholder keys.

**Behaviors to test**

Start with the endpoint's primary happy path, then cover every filtering, scoping, deduplication, and ordering rule found in the action, then close with the standard auth/404 cases. Each behavior should be independently verifiable by QA without reading code.

1. [Primary happy path — authenticate and call with valid input, verify key response fields]
2. [One item per filtering/exclusion rule from the action]
3. [Deduplication rule if applicable]
4. [Ordering rule if applicable]
5. [Empty-state cases]
6. Calls with a non-existent ID should return `404`.
7. The endpoint requires authentication. Unauthenticated requests return `401`.

---

## Guidelines

- **QA audience**: no instructions to run migrations, seeders, or artisan commands — they test the live endpoint only.
- **Action logic → behaviors**: every conditional in the action is something QA can break. Surface all of them. An action with `whereNot('type', Comment)`, `where('patient_id', ...)`, `groupBy(...)->first()`, and a sort map should produce at least 4 dedicated behavior items.
- **JSON example**: use realistic placeholder values, not generic `"string"` or `null`. Make it clear they're illustrative.
- **Multiple endpoints**: add one **Endpoint** bullet per endpoint and expand the behaviors section accordingly.
- **Omit sections that don't apply**: if no migration changed, skip that bullet entirely.

## Reference output

This is the gold-standard output — calibrate tone, length, and depth of the behaviors section against this:

---

**Summary**
Added `GET /api/symptoms/{id}/biomarkers` endpoint that returns the patient's latest lab result for each biomarker associated with a given symptom, ordered by severity (Critical → Abnormal → Normal).

**What was done**
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

**Behaviors to test**
1. Authenticate as a patient and call `GET /api/symptoms/{id}/biomarkers` with a valid symptom ID — verify the response includes `name`, `result`, `unit`, `interpretation`, `product.display_name`, and range fields (`min_range_value`, `max_range_value`, `is_above_max_range`, `is_below_min_range`).
2. If the symptom has no associated biomarkers, the response should be `200` with an empty `data` array.
3. If the patient has no lab results for the symptom's biomarkers, the response should be `200` with an empty `data` array.
4. When a biomarker has multiple results, only the most recent one should appear in the response.
5. Lab results belonging to other patients must not appear in the response.
6. Lab results of type `Comment` must not appear in the response.
7. Results must be ordered by severity: Critical first, then Abnormal, then Normal.
8. Calls with a non-existent symptom ID should return `404`.
9. The endpoint requires authentication. Unauthenticated requests return `401`.
