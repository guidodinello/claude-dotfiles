#!/usr/bin/env python3
"""Measure what a model or effort change cost on our own sessions, before and after.

The frontier report predicts a move from the Artificial Analysis (AA) index: "+11 points
for 2.1x the cost per task". This script checks the cost half of that prediction against
our Claude Code transcripts, and records the prediction so a later run can compare.

What it reads: every `<projects dir>/*/<session>.jsonl` plus that session's
`<session>/subagents/*.jsonl` (the code-review reviewer and scorer agents spend most of a
review's tokens there). Each assistant turn carries `message.model`, `message.usage` and the
turn's `effort`. One message is logged once per content block with the same usage, so turns
are deduplicated by message id.

A session's kind (code-review, worker) comes from `session_kinds` in references/roles.json.
Cost is API-equivalent USD at the snapshot's per-token prices: input, output and cache-hit
from AA, cache writes at 1.25x input (5 minute TTL) and 2x input (1 hour TTL), the Anthropic
prompt-caching multipliers. On a subscription this is a relative measure, not a bill.

Transcripts are deleted after `cleanupPeriodDays` (30 by default), so `record` stores the
baseline numbers in the decision itself; `check` never needs the old transcripts.

Usage:
  model_retro.py measure --kind code-review [--since YYYY-MM-DD] [--until YYYY-MM-DD]
  model_retro.py record --id ID --kind code-review --from claude-sonnet-5-5@medium --to claude-sonnet-5-5@high --change "..."
  model_retro.py check --id ID [--save]
  model_retro.py verified --id ID --item N
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import statistics
import sys
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aa_frontier  # noqa: E402

DECISIONS_FILE = aa_frontier.SKILL_DIR / "references" / "decisions.json"
DEFAULT_PROJECTS = [Path.home() / ".claude" / "projects"]
CACHE_WRITE_5M, CACHE_WRITE_1H = 1.25, 2.0
FINDINGS_RE = re.compile(r"Found (\d+) blocking issue\(s\) and (\d+) non-blocking")
CLEAN_REVIEW = "No issues found. Checked for bugs and CLAUDE.md compliance."
MODEL_ALIASES = ("haiku", "sonnet", "opus", "fable")


def first_prompt(record: dict[str, Any]) -> str | None:
    if record.get("type") != "user" or record.get("isMeta"):
        return None
    content = (record.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        return "\n".join(texts) if texts else None
    return None


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(errors="replace") as handle:
        for line in handle:
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def classify(prompt: str | None, kinds: dict[str, Any]) -> str | None:
    for kind, rule in kinds.items():
        if prompt and any(prompt.lstrip().startswith(p) for p in rule.get("first_prompt_prefix", [])):
            return kind
        if prompt and any(marker in prompt for marker in rule.get("first_prompt_contains", [])):
            return kind
    return None


def turns(paths: Iterable[Path]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out = []
    for path in paths:
        for record in read_jsonl(path):
            message = record.get("message")
            if not isinstance(message, dict) or not message.get("usage"):
                continue
            key = message.get("id") or record.get("requestId") or record.get("uuid")
            if key is not None:
                if key in seen:
                    continue
                seen.add(key)
            out.append({"model": message.get("model"), "effort": record.get("effort"), "usage": message["usage"]})
    return out


def turn_cost(turn: dict[str, Any], prices: dict[str, dict[str, float]]) -> float | None:
    price = prices.get(turn["model"] or "")
    if price is None:
        return None
    usage = turn["usage"]
    creation = usage.get("cache_creation") or {}
    write_5m = creation.get("ephemeral_5m_input_tokens", 0)
    write_1h = creation.get("ephemeral_1h_input_tokens", 0)
    if not creation:
        write_5m = usage.get("cache_creation_input_tokens", 0)
    per_token = {
        "input": price["input"] * usage.get("input_tokens", 0),
        "cache_read": price["cache_hit"] * usage.get("cache_read_input_tokens", 0),
        "cache_write": price["input"] * (CACHE_WRITE_5M * write_5m + CACHE_WRITE_1H * write_1h),
        "output": price["output"] * usage.get("output_tokens", 0),
    }
    return sum(per_token.values()) / 1_000_000


def price_table(snapshot: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Prices by model id. Transcripts sometimes log a short alias (`haiku`), priced as the
    first release of that family in the snapshot's watch list."""
    prices = {}
    for m in snapshot["models"]:
        if m["release"] and m["price_1m_input"] is not None and m["price_1m_output"] is not None:
            prices.setdefault(m["release"], {"input": m["price_1m_input"], "output": m["price_1m_output"], "cache_hit": m["price_1m_cache_hit"] if m["price_1m_cache_hit"] is not None else m["price_1m_input"] * 0.1})
    for alias in MODEL_ALIASES:
        release = next((r for r in snapshot.get("releases", []) if r.startswith(f"claude-{alias}-") and r in prices), None)
        if release:
            prices.setdefault(alias, prices[release])
    return prices


def assistant_text(paths: Iterable[Path]) -> str:
    """What the session itself wrote (text and tool inputs), not the skill text it was given."""
    parts = []
    for path in paths:
        for record in read_jsonl(path):
            message = record.get("message")
            if isinstance(message, dict) and message.get("role") == "assistant":
                parts.append(json.dumps(message.get("content"), ensure_ascii=False))
    return "\n".join(parts)


def review_findings(text: str) -> int | None:
    counts = [int(a) + int(b) for a, b in FINDINGS_RE.findall(text)]
    if counts:
        return counts[-1]
    return 0 if CLEAN_REVIEW in text else None


def session_files(projects_dirs: list[Path]) -> Iterable[Path]:
    for root in projects_dirs:
        yield from root.glob("*/*.jsonl")


def session_start(path: Path) -> dt.date | None:
    for record in read_jsonl(path):
        stamp = record.get("timestamp")
        if stamp:
            return dt.datetime.fromisoformat(stamp.replace("Z", "+00:00")).date()
    return None


def collect(kind: str, since: dt.date, until: dt.date, projects_dirs: list[Path], prices: dict[str, dict[str, float]], require: str | None = None) -> dict[str, Any]:
    """Cost profile of one session kind. `require` (model@effort) keeps only units with a turn on it.

    A unit is one session, or with `"unit": "project"` every matching session in one project dir
    (one worktree), so a worker split into planner and coder sessions counts once.
    """
    kinds = aa_frontier.load_roles()["session_kinds"]
    by_project = kinds[kind].get("unit") == "project"
    units: dict[Path, dict[str, Any]] = {}
    unpriced: set[str] = set()
    for path in session_files(projects_dirs):
        start = session_start(path)
        if start is None or not since <= start <= until:
            continue
        prompt = next((p for r in read_jsonl(path) if (p := first_prompt(r))), None)
        if classify(prompt, kinds) != kind:
            continue
        files = [path, *sorted((path.parent / path.stem / "subagents").glob("*.jsonl"))]
        cost, mix = 0.0, {}
        for turn in turns(files):
            value = turn_cost(turn, prices)
            if value is None:
                if turn["model"] != "<synthetic>":
                    unpriced.add(turn["model"] or "?")
                continue
            cost += value
            key = f"{turn['model']}@{turn['effort'] or '?'}"
            mix[key] = mix.get(key, 0.0) + value
        findings = review_findings(assistant_text([path])) if kind == "code-review" else None
        unit = units.setdefault(path.parent if by_project else path, {"cost": 0.0, "mix": {}, "findings": None})
        unit["cost"] += cost
        for key, value in mix.items():
            unit["mix"][key] = unit["mix"].get(key, 0.0) + value
        if findings is not None:
            unit["findings"] = findings
    sessions = [u for u in units.values() if not require or require in u["mix"]]
    return summarize(kind, since, until, sessions, unpriced)


def summarize(kind: str, since: dt.date, until: dt.date, sessions: list[dict[str, Any]], unpriced: set[str]) -> dict[str, Any]:
    costs = sorted(s["cost"] for s in sessions)
    total = sum(costs)
    mix: dict[str, float] = {}
    for s in sessions:
        for key, value in s["mix"].items():
            mix[key] = mix.get(key, 0.0) + value
    findings = [s["findings"] for s in sessions if s["findings"] is not None]
    quartiles = statistics.quantiles(costs, n=4) if len(costs) >= 2 else [costs[0]] * 3 if costs else [None] * 3
    return {
        "kind": kind,
        "window": [since.isoformat(), until.isoformat()],
        "sessions": len(sessions),
        "cost_per_session": {"median": round(statistics.median(costs), 3) if costs else None, "p25": _r(quartiles[0]), "p75": _r(quartiles[2])},
        "cost_share": {k: round(v / total, 3) for k, v in sorted(mix.items(), key=lambda kv: -kv[1])} if total else {},
        "findings_per_review_median": statistics.median(findings) if findings else None,
        "unpriced_models": sorted(unpriced),
    }


def _r(value: float | None) -> float | None:
    return round(value, 3) if value is not None else None


def load_prices(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, dict[str, float]]]:
    data_dir = Path(args.data_dir).expanduser()
    path = Path(args.snapshot).expanduser() if args.snapshot else aa_frontier.latest_snapshot(data_dir)
    snapshot = json.loads(path.read_text())
    return snapshot, price_table(snapshot)


def projects(args: argparse.Namespace) -> list[Path]:
    return [Path(p).expanduser() for p in args.projects_dir] if args.projects_dir else DEFAULT_PROJECTS


def parse_date(value: str | None, default: dt.date) -> dt.date:
    return dt.date.fromisoformat(value) if value else default


def cmd_measure(args: argparse.Namespace) -> int:
    _, prices = load_prices(args)
    today = dt.date.today()
    result = collect(args.kind, parse_date(args.since, today - dt.timedelta(days=30)), parse_date(args.until, today), projects(args), prices)
    print(json.dumps(result, indent=2))
    return 0


def split_variant(text: str) -> tuple[str, str]:
    release, _, effort = text.partition("@")
    if not effort:
        raise SystemExit(f"expected <release>@<effort>, got {text!r}")
    return release, effort


def load_decisions() -> list[dict[str, Any]]:
    return json.loads(DECISIONS_FILE.read_text()) if DECISIONS_FILE.exists() else []


def cmd_record(args: argparse.Namespace) -> int:
    snapshot, prices = load_prices(args)
    decisions = load_decisions()
    if any(d["id"] == args.id for d in decisions):
        raise SystemExit(f"decision {args.id} already exists")
    old, new = (aa_frontier.variant(snapshot["models"], *split_variant(v)) for v in (args.from_variant, args.to_variant))
    if old is None or new is None:
        raise SystemExit("both variants must be in the snapshot")
    today = dt.date.today()
    baseline = collect(args.kind, parse_date(args.since, today - dt.timedelta(days=30)), today, projects(args), prices, require=args.from_variant)
    decision = {
        "id": args.id,
        "date": today.isoformat(),
        "change": args.change,
        "kind": args.kind,
        "from": args.from_variant,
        "to": args.to_variant,
        "expected": {
            "index_version": snapshot["index_version"],
            "index_from": old["index"],
            "index_to": new["index"],
            "aa_cost_ratio": round(new["cost_per_task"] / old["cost_per_task"], 2),
            "input_price_ratio": round(new["price_1m_input"] / old["price_1m_input"], 2),
        },
        "baseline": baseline,
        "verify": [{"what": what, "done": None} for what in args.verify or []],
        "checks": [],
    }
    decisions.append(decision)
    DECISIONS_FILE.write_text(json.dumps(decisions, indent=2) + "\n")
    print(json.dumps(decision, indent=2))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    _, prices = load_prices(args)
    decisions = load_decisions()
    decision = next((d for d in decisions if d["id"] == args.id), None)
    if decision is None:
        raise SystemExit(f"no decision {args.id} in {DECISIONS_FILE}")
    # The change goes live at merge and sync, not at the decision date, so "after" counts only
    # sessions that actually ran the new variant.
    after = collect(decision["kind"], dt.date.fromisoformat(decision["date"]), dt.date.today(), projects(args), prices, require=decision["to"])
    before, expected = decision["baseline"], decision["expected"]
    b, a = before["cost_per_session"]["median"], after["cost_per_session"]["median"]
    observed = round(a / b, 2) if a is not None and b else None
    print(f"# {decision['id']}: {decision['change']}\n")
    predicted = expected.get("blended_cost_ratio", expected["aa_cost_ratio"])
    print(f"Expected (AA v{expected['index_version']}): {expected['index_from']:.0f} -> {expected['index_to']:.0f} pts, cost x{predicted} per session\n")
    print("| | Before | After |")
    print("|---|---|---|")
    print(f"| Sessions | {before['sessions']} | {after['sessions']} |")
    print(f"| Median API-equivalent $ per session | {b} | {a} |")
    print(f"| Median findings per review | {before['findings_per_review_median']} | {after['findings_per_review_median']} |")
    print(f"\nObserved cost ratio: {observed} (predicted {predicted})")
    print(f"Cost mix after: {after['cost_share']}")
    if after["unpriced_models"]:
        print(f"Not priced, left out of the cost: {after['unpriced_models']}")
    if after["sessions"] < 10:
        print(f"\nOnly {after['sessions']} sessions since the change: too few to judge, check again later.")
    print_open_verifications(decision)
    if args.save:
        decision["checks"].append({"date": dt.date.today().isoformat(), "after": after, "observed_cost_ratio": observed})
        DECISIONS_FILE.write_text(json.dumps(decisions, indent=2) + "\n")
    return 0


def print_open_verifications(decision: dict[str, Any]) -> None:
    open_items = [(i, v["what"]) for i, v in enumerate(decision.get("verify", [])) if not v["done"]]
    if open_items:
        print("\nStill to verify (mark with `verified --id <id> --item <n>`):")
        for i, what in open_items:
            print(f"  {i}. {what}")


def cmd_verified(args: argparse.Namespace) -> int:
    decisions = load_decisions()
    decision = next((d for d in decisions if d["id"] == args.id), None)
    if decision is None:
        raise SystemExit(f"no decision {args.id} in {DECISIONS_FILE}")
    items = decision.get("verify", [])
    if not 0 <= args.item < len(items):
        raise SystemExit(f"{args.id} has no verify item {args.item}")
    items[args.item]["done"] = dt.date.today().isoformat()
    DECISIONS_FILE.write_text(json.dumps(decisions, indent=2) + "\n")
    print_open_verifications(decision)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", default=str(aa_frontier.DEFAULT_DATA_DIR))
    parser.add_argument("--snapshot", help="AA snapshot for prices (default: newest)")
    parser.add_argument("--projects-dir", action="append", help="Claude Code projects dir, repeatable (default: ~/.claude/projects)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    measure = sub.add_parser("measure", help="cost profile of one session kind in a window")
    measure.add_argument("--kind", required=True)
    measure.add_argument("--since")
    measure.add_argument("--until")
    measure.set_defaults(func=cmd_measure)
    record = sub.add_parser("record", help="store a decision with its prediction and baseline")
    record.add_argument("--id", required=True)
    record.add_argument("--kind", required=True)
    record.add_argument("--from", dest="from_variant", required=True, help="<release>@<effort>")
    record.add_argument("--to", dest="to_variant", required=True, help="<release>@<effort>")
    record.add_argument("--change", required=True, help="one line: what changed and where")
    record.add_argument("--since", help="baseline window start (default: 30 days ago)")
    record.add_argument("--verify", action="append", help="a runtime check the change still needs, repeatable; `check` lists it until marked done")
    record.set_defaults(func=cmd_record)
    check = sub.add_parser("check", help="compare sessions since a decision with its baseline")
    check.add_argument("--id", required=True)
    check.add_argument("--save", action="store_true", help="append the result to the decision")
    verified = sub.add_parser("verified", help="mark one verify item of a decision as done")
    verified.add_argument("--id", required=True)
    verified.add_argument("--item", type=int, required=True)
    verified.set_defaults(func=cmd_verified)
    check.set_defaults(func=cmd_check)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
