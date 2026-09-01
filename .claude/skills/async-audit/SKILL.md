---
name: async-audit
description: >
  Detect and fix bad sync/async usage patterns in the Python backend.
  Use when you suspect blocking calls in async handlers, fire-and-forget tasks,
  or missing ruff ASYNC rules. Does NOT auto-commit — reports findings and
  applies fixes to the working tree only.
---

## Goal

Find real async bugs and misconfigurations. This codebase uses the correct
`asyncio.run()` bridge pattern in Celery tasks — the skill must NOT flag those.
A well-calibrated run against a healthy codebase should produce few or no findings.

---

## Step 1 — Check ruff ASYNC config

Read `backend/pyproject.toml`. Check whether `"ASYNC"` appears in `[tool.ruff.lint] select`.

- If absent: propose adding it. Run `uv run ruff check --select ASYNC --preview backend/`
  from the repo root to confirm the current codebase is clean before adding it. If clean,
  add `"ASYNC"` to the select list now. If there are violations, list them first and ask
  the user whether to fix or add the rule anyway.
- If already present: note that it's covered and move on.

---

## Step 2 — Semantic scan (what ruff can't catch)

Run these greps from `backend/src/`:

```bash
# fire-and-forget create_task — result not stored
grep -rn "asyncio\.create_task(" . --include="*.py"

# asyncio.run() — note all call sites; we'll classify below
grep -rn "asyncio\.run(" . --include="*.py"

# async def with no await — may be pointless async
grep -rn "^async def\|^    async def" . --include="*.py" -l
```

Spawn a **single classify agent** (general-purpose, needs Read and Bash) with:
- The grep output above
- The instruction below

### Classify agent instructions

```
You are classifying async/sync usage findings in a Python FastAPI + Celery codebase.

For EVERY hit in the grep output, read ~20 lines of context around that line in the
actual file before classifying. Do not classify from the grep string alone — the
surrounding code is what determines whether a pattern is a bug or correct usage.

Rules for this codebase:
1. asyncio.run() at a SYNC entry point is CORRECT — Celery tasks (@celery_app.task)
   and CLI commands (if __name__ == "__main__" or Click commands) use asyncio.run()
   to bridge from the sync Celery/CLI world into async code. These are NEVER bugs.
   To verify: read upward from the call site to confirm it is inside a sync def, not
   inside an async def.
2. asyncio.run() inside an async def is a BUG — it will raise RuntimeError at runtime
   because a loop is already running. Confirm by reading the enclosing function signature.
3. asyncio.create_task() whose return value is not assigned to a variable is a
   POTENTIAL BUG — the task may be garbage-collected before it completes. Read the
   surrounding 10 lines: if it's inside a TaskGroup or the result is immediately
   added to a set/list, it's fine. Only flag bare fire-and-forget calls.
4. For "async def with no await": read each flagged file fully and list functions that are
   async but contain no await expression. These may be unnecessarily async. Exclude
   abstract methods, Protocol stubs, and test fixtures (conftest.py).

For each finding, return:
- file:line
- pattern matched
- verdict: BUG / CORRECT / INVESTIGATE
- one-line reason citing what you read in the file

Return a structured list. Be conservative — when in doubt, mark INVESTIGATE, not BUG.
```

---

## Step 3 — Report and fix

After the classify agent returns:

**If no BUG verdicts:** report "async audit clean — N findings reviewed, all correct or
intentional." List INVESTIGATE items with context so the user can decide.

**If BUG verdicts exist:** for each one:

1. Read the file at the flagged location.
2. Determine the fix:
   - `asyncio.run()` inside async def → remove the asyncio.run() wrapper and await
     the inner coroutine directly.
   - Fire-and-forget `create_task` → add `task = asyncio.create_task(...)` and keep
     a reference. If the caller is a method, store on `self._tasks` or a local set.
     Do NOT rewrite the caller's architecture — just capture the reference.
   - Unnecessary `async def` with no await → only fix if the function is not part of
     a protocol or overrides an async base. Remove the `async` keyword and any
     `await asyncio.sleep(0)` workarounds.
3. Apply the fix with Edit. Do not fix riskier rewrites (e.g., changing the
   `requests` library to `httpx`) silently — list those as TODOs instead.
4. Run `uv run ruff check backend/` to verify no new lint errors were introduced.

---

## Step 4 — Summary

Print a table:

| File | Line | Pattern | Verdict | Action |
|------|------|---------|---------|--------|
| ... | ... | ... | ... | Fixed / TODO / Correct |

Close by reminding the user: no commits were made, and they should run the `qa` agent before pushing.

---

## Appendix — Async Mental Model

### 1. The Event Loop

Python's `asyncio` runs a single-threaded event loop that multiplexes coroutines via cooperative multitasking. A coroutine yields control at `await` — the scheduler picks another ready coroutine. If any code path blocks the thread (e.g. `time.sleep`, `requests.get`, a CPU-bound loop), the entire loop stalls. No other request, heartbeat, or timeout can advance until control returns.

```python
# BAD — blocks the whole event loop for 10 seconds
@app.get("/slow")
async def slow_endpoint():
    time.sleep(10)  # ← thread blocked, all other requests queued
    return {"done": True}

# GOOD — yields control, other requests interleave
@app.get("/fast")
async def fast_endpoint():
    await asyncio.sleep(10)  # ← loop runs other coroutines
    return {"done": True}
```

### 2. Why Blocking Calls Crash Your App

FastAPI processes many concurrent requests on *one* event loop (one thread, absent uvicorn `--workers`). A single sync-blocking handler freezes every in-flight request. This manifests as mysterious timeouts, dropped connections, or "server not responding" for *all* users, not just the caller of the slow endpoint. The fix is always `asyncio.sleep` / `httpx.AsyncClient` / `aiosqlite` / etc.

```python
# BAD — requests.get blocks the loop
import requests
@app.post("/search")
async def search(query: str):
    resp = requests.get(f"https://api.example.com/search?q={query}")
    return resp.json()

# GOOD — httpx.AsyncClient awaits (yields control)
import httpx
@app.post("/search")
async def search(query: str):
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"https://api.example.com/search?q={query}")
    return resp.json()
```

### 3. The `asyncio.run()` Bridge

`asyncio.run(coro)` creates a *new* event loop, runs `coro` to completion, then closes the loop. This is the correct pattern at a **sync entry point** — a Celery task, a CLI command, `if __name__ == "__main__"`:

```python
# CORRECT — sync Celery task bridges into async
@celery_app.task
def compute_recommendations(user_id: int):
    result = asyncio.run(_compute_recos(user_id))  # sync → async bridge
    return result
```

Calling `asyncio.run()` **inside an async def** is a bug — it raises `RuntimeError: asyncio.run() cannot be called from a running event loop` because you can't nest event loops:

```python
# BUG — asyncio.run() inside an already-running loop
async def handler(data: dict):
    result = asyncio.run(process(data))  # RuntimeError at runtime!
    return result

# FIX — just await directly
async def handler(data: dict):
    result = await process(data)
    return result
```

### 4. Fire-and-Forget Dangers

`asyncio.create_task(coro)` schedules a coroutine on the loop and returns a `Task` handle. If nothing holds a reference to that handle, the garbage collector may reap the task *while it is still running*, cancelling it silently. The fix is to store the task somewhere that lives as long as the work matters.

```python
# BUG — task reference discarded immediately
@app.post("/notify")
async def notify(user_id: int):
    asyncio.create_task(send_email(user_id))  # ← may be GC'd mid-send
    return {"ok": True}

# FIX — keep reference during scope
_pending_tasks: set[asyncio.Task] = set()

@app.post("/notify")
async def notify(user_id: int):
    task = asyncio.create_task(send_email(user_id))
    _pending_tasks.add(task)    # keep alive
    task.add_done_callback(_pending_tasks.discard)  # clean up
    return {"ok": True}

# Alternative: TaskGroup (3.11+) manages the reference for you, but it is not
# fire-and-forget — __aexit__ blocks until all child tasks finish, so this
# adds latency to the caller rather than removing it.
async def notify(user_id: int):
    async with asyncio.TaskGroup() as tg:
        tg.create_task(send_email(user_id))
    return {"ok": True}
```

### 5. Unnecessary `async def`

A function declared `async def` with no `await` inside is just a slower sync function. It returns a *coroutine object* instead of the value directly — callers must `await` it, adding scheduling overhead vs a plain sync call. Worse, it forces all transitive callers to also be async (async infection).

```python
# BAD — async def with no await (pointless overhead)
async def format_name(first: str, last: str) -> str:
    return f"{first} {last}"

result = await format_name("Jane", "Doe")  # unnecessary await

# FIX — plain sync function
def format_name(first: str, last: str) -> str:
    return f"{first} {last}"

result = format_name("Jane", "Doe")  # simpler, faster, no await
```

### 6. Why Ruff ASYNC Rules Matter

| Rule | What it catches | Why it matters |
|------|----------------|----------------|
| `ASYNC251` (blocking-sleep-in-async-function) | `time.sleep()` inside `async def` | The blocking-sleep bug from §1 |
| `ASYNC210` (blocking-http-call-in-async-function) | Blocking HTTP calls (`requests`, `urllib3`) inside `async def` | The blocking-HTTP bug from §2 |
| `ASYNC230` (blocking-open-call-in-async-function) | Blocking `open()` inside `async def` | File I/O blocks the loop too |
| `ASYNC220` / `ASYNC221` / `ASYNC222` | Creating, running, or waiting on subprocesses with blocking methods inside `async def` | Another blocking-the-loop variant |
| `ASYNC110` (async-busy-wait) | `while ...: await asyncio.sleep(...)` polling loops | Prefer `asyncio.Event` over busy-waiting |
| `RUF006` (asyncio-dangling-task) | `asyncio.create_task` / `ensure_future` result not stored | The fire-and-forget bug from §4 — note this is a `RUF` rule, not `ASYNC` |
| `RUF029` (unused-async, preview) | `async def` that contains no `await` expression | The pointless-async pattern from §5 — also `RUF`, requires `--preview` |

Enable `ASYNC` in ruff and the blocking-the-loop bugs surface automatically. The fire-and-forget (§4) and pointless-async (§5) patterns need `RUF006` / `RUF029`, which live in the `RUF` category — check whether `RUF` is in the select list too. No lint rule catches `asyncio.run()` inside an `async def`; that is exactly what the semantic scan (§2) exists for.
