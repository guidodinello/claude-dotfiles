#!/usr/bin/env python3
import collections
import json
from datetime import datetime
from pathlib import Path

stats_path = Path.home() / ".claude/stats-cache.json"
history_path = Path.home() / ".claude/history.jsonl"

# ── stats-cache.json ──────────────────────────────────────────────────────────
stats = json.loads(stats_path.read_text()) if stats_path.exists() else {}
model_usage = stats.get("modelUsage", {})

pricing = {
    "claude-haiku": {"in": 0.80, "out": 4.00, "cr": 0.08, "cw": 1.00},
    "claude-sonnet": {"in": 3.00, "out": 15.00, "cr": 0.30, "cw": 3.75},
    "claude-opus": {"in": 15.00, "out": 75.00, "cr": 1.50, "cw": 18.75},
}


def get_price(model_id):
    for k, p in pricing.items():
        if k in model_id:
            return p
    return pricing["claude-sonnet"]


def short(model_id):
    return model_id.replace("claude-", "").rsplit("-202", 1)[0]


print("=== MODEL TOKEN USAGE ===")
total_cost = 0
for model, s in model_usage.items():
    total = s["inputTokens"] + s["cacheReadInputTokens"] + s["cacheCreationInputTokens"]
    cache_hit = s["cacheReadInputTokens"] / max(1, total) * 100
    out_ratio = s["outputTokens"] / max(1, s["inputTokens"])
    p = get_price(model)
    cost = (
        s["inputTokens"] * p["in"]
        + s["outputTokens"] * p["out"]
        + s["cacheReadInputTokens"] * p["cr"]
        + s["cacheCreationInputTokens"] * p["cw"]
    ) / 1e6
    total_cost += cost
    flag = " ⚠ low output ratio" if out_ratio < 0.1 else ""
    print(f"  {short(model)}")
    print(
        f"    input={s['inputTokens']:,}  cache_read={s['cacheReadInputTokens']:,}  cache_write={s['cacheCreationInputTokens']:,}  output={s['outputTokens']:,}"
    )
    print(
        f"    cache_hit={cache_hit:.0f}%  out/in={out_ratio:.2f}x  est_cost=${cost:.2f}{flag}"
    )

print(f"  TOTAL estimated: ${total_cost:.2f}")
print(f"  Stats last computed: {stats.get('lastComputedDate', 'unknown')}")
print()

# ── history.jsonl ─────────────────────────────────────────────────────────────
records = []
if history_path.exists():
    for line in history_path.read_text().splitlines():
        try:
            records.append(json.loads(line))
        except:
            pass

projects = collections.Counter(r.get("project", "").split("/")[-1] for r in records)
print("=== TOP PROJECTS (message count) ===")
for p, c in projects.most_common(5):
    print(f"  {c:4d}  {p}")
print()

sessions = collections.defaultdict(list)
for r in records:
    sessions[r.get("sessionId", "")].append(r.get("timestamp", 0))

session_list = [(sid, ts) for sid, ts in sessions.items() if ts]
avg_msgs = sum(len(sessions[s]) for s in sessions) / max(1, len(sessions))
durations = [(max(ts) - min(ts)) / 60000 for _, ts in session_list if len(ts) > 1]
avg_dur = sum(durations) / max(1, len(durations))

print("=== SESSION STATS ===")
print(f"  Total sessions: {len(sessions)}")
print(f"  Total messages: {len(records)}")
print(f"  Avg msgs/session: {avg_msgs:.1f}")
print(f"  Avg session duration: {avg_dur:.0f} min")
print()

hours = collections.Counter(
    datetime.fromtimestamp(r["timestamp"] / 1000).hour
    for r in records
    if r.get("timestamp")
)
peak = max(hours, key=hours.get) if hours else "n/a"
print("=== ACTIVITY PEAK ===")
print(f"  Peak hour: {peak:02d}:00 ({hours.get(peak, 0)} messages)")
recent_days = sorted(
    set(
        datetime.fromtimestamp(r["timestamp"] / 1000).strftime("%Y-%m-%d")
        for r in records
        if r.get("timestamp")
    )
)[-5:]
print(f"  Recent active days: {' '.join(recent_days)}")
