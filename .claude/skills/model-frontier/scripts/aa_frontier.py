#!/usr/bin/env python3
"""Fetch Artificial Analysis Intelligence Index data and report the cost/intelligence frontier.

Artificial Analysis (AA) renders its model pages with Next.js. Each page ships its data
inline as React Server Component (RSC) chunks, `self.__next_f.push([1, "<json string>"])`,
and those chunks hold one object per model variant (one per effort level). Plain curl gets
them, so no browser is needed. The variant URLs (`/models/<release>-medium`) redirect to the
max variant, so only the release page (`/models/<release>`) is fetched.

Subcommands:
  fetch    Download the watched releases, write a dated snapshot JSON.
  report   Markdown table, move candidates per role, and an SVG plot from one snapshot.

Snapshots are only comparable within one index version: v4 and v5 use different
evaluations, and mixing them is what produced contradictory numbers on aggregator blogs.
`report --previous` refuses to diff snapshots of different versions.

Usage:
  aa_frontier.py fetch [--release claude-opus-5-5 ...] [--data-dir DIR]
  aa_frontier.py report [--snapshot PATH] [--previous PATH] [--svg PATH] [--all-creators] [--show-dominated]
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import math
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parent.parent
ROLES_FILE = SKILL_DIR / "references" / "roles.json"
DEFAULT_DATA_DIR = Path.home() / ".claude" / "model-frontier"
PAGE_URL = "https://artificialanalysis.ai/models/{release}"
USER_AGENT = "Mozilla/5.0 (model-frontier)"

RSC_CHUNK_RE = re.compile(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', re.S)
INDEX_VERSION_RE = re.compile(r"Intelligence Index v(\d+\.\d+\.\d+)")
REQUIRED_FIELDS = ("slug", "intelligenceIndex", "intelligenceIndexCostPerTask", "release", "effort")


class ScrapeError(RuntimeError):
    pass


def decode_rsc(page_html: str) -> str:
    chunks = RSC_CHUNK_RE.findall(page_html)
    if not chunks:
        raise ScrapeError("no RSC chunks found: the page layout changed")
    return "".join(json.loads(f'"{chunk}"') for chunk in chunks)


def index_version(rsc: str) -> str:
    versions = set(INDEX_VERSION_RE.findall(rsc))
    if len(versions) != 1:
        raise ScrapeError(f"expected one Intelligence Index version on the page, found {sorted(versions)}")
    return versions.pop()


def model_objects(rsc: str) -> list[dict[str, Any]]:
    """Every JSON object in the payload that looks like a scored model variant."""
    decoder = json.JSONDecoder()
    found: dict[str, dict[str, Any]] = {}
    for match in re.finditer(r'\{"id":\s*"', rsc):
        try:
            obj, _ = decoder.raw_decode(rsc, match.start())
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and all(k in obj for k in REQUIRED_FIELDS):
            found.setdefault(obj["slug"], obj)
    return list(found.values())


def _num(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def normalize(obj: dict[str, Any]) -> dict[str, Any] | None:
    cost = (obj.get("intelligenceIndexCostPerTask") or {}).get("cost") or {}
    index, total = _num(obj.get("intelligenceIndex")), _num(cost.get("total"))
    if index is None or total is None or total <= 0:
        return None
    effort = obj.get("effort") or {}
    release = obj.get("release") or {}
    tokens = obj.get("intelligenceIndexOutputTokensPerTask") or {}
    return {
        "slug": obj["slug"],
        "name": obj.get("shortName") or obj.get("name"),
        "release": release.get("slug"),
        "creator": (obj.get("creator") or {}).get("slug"),
        "effort": effort.get("slug"),
        "effort_level": effort.get("level"),
        "index": round(index, 2),
        "cost_per_task": round(total, 4),
        "cost_breakdown": {k: round(v, 4) for k in ("nonCacheInput", "cacheRead", "cacheWrite", "output") if (v := _num(cost.get(k))) is not None},
        "output_tokens_per_task": _num(tokens.get("output")),
        "price_1m_input": _num(obj.get("price1mInputTokens")),
        "price_1m_output": _num(obj.get("price1mOutputTokens")),
        "price_1m_cache_hit": _num(obj.get("cacheHitPrice")),
    }


def parse_page(page_html: str) -> tuple[str, list[dict[str, Any]]]:
    rsc = decode_rsc(page_html)
    version = index_version(rsc)
    models = [m for obj in model_objects(rsc) if (m := normalize(obj))]
    if not models:
        raise ScrapeError("no scored model objects found: the field names changed")
    return version, models


def fetch_page(release: str) -> str:
    request = urllib.request.Request(PAGE_URL.format(release=release), headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ScrapeError(f"{release}: could not fetch the page ({exc})") from exc


def load_roles() -> dict[str, Any]:
    return json.loads(ROLES_FILE.read_text())


def cmd_fetch(args: argparse.Namespace) -> int:
    releases = args.release or load_roles()["watch"]
    versions: set[str] = set()
    models: dict[str, dict[str, Any]] = {}
    for release in releases:
        version, found = parse_page(fetch_page(release))
        versions.add(version)
        if not any(m["release"] == release for m in found):
            raise ScrapeError(f"{release}: the page has no variant of its own release")
        for model in found:
            models.setdefault(model["slug"], model)
    if len(versions) != 1:
        raise ScrapeError(f"pages disagree on the index version: {sorted(versions)}")
    version = versions.pop()
    today = dt.date.today().isoformat()
    snapshot = {"fetched_at": today, "index_version": version, "releases": releases, "models": sorted(models.values(), key=lambda m: m["slug"])}
    out_dir = Path(args.data_dir).expanduser() / "snapshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{today}-v{version}.json"
    path.write_text(json.dumps(snapshot, indent=2) + "\n")
    print(path)
    return 0


def pareto(models: list[dict[str, Any]]) -> set[str]:
    """Slugs no other model beats on both cost (lower) and index (higher)."""
    front = set()
    for m in models:
        beaten = any(o["cost_per_task"] <= m["cost_per_task"] and o["index"] >= m["index"] and (o["cost_per_task"], o["index"]) != (m["cost_per_task"], m["index"]) for o in models)
        if not beaten:
            front.add(m["slug"])
    return front


def variant(models: list[dict[str, Any]], release: str, effort: str) -> dict[str, Any] | None:
    return next((m for m in models if m["release"] == release and m["effort"] == effort), None)


def snapshot_order(path: Path) -> tuple:
    """Date, then index version as numbers: v5.0.10 is newer than v5.0.9."""
    match = re.match(r"(\d{4}-\d{2}-\d{2})-v(\d+(?:\.\d+)*)$", path.stem)
    if not match:
        return (path.stem, ())
    return (match.group(1), tuple(int(n) for n in match.group(2).split(".")))


def latest_snapshot(data_dir: Path) -> Path:
    snaps = sorted((data_dir / "snapshots").glob("*.json"), key=snapshot_order)
    if not snaps:
        raise SystemExit(f"no snapshot under {data_dir}/snapshots: run `fetch` first")
    return snaps[-1]


def role_rows(models: list[dict[str, Any]], roles: dict[str, Any], show_dominated: bool = False) -> list[str]:
    """One move table per distinct (release, effort) in use, listing the roles it serves."""
    groups: dict[tuple[str, str], list[str]] = {}
    for name, role in roles.items():
        groups.setdefault((role["release"], role["effort"]), []).append(name)
    lines = []
    for (release, effort), names in groups.items():
        current = variant(models, release, effort)
        if current is None:
            lines.append(f"\n### {', '.join(names)}: {release} {effort} is not in the snapshot\n")
            continue
        same_creator = [m for m in models if m["creator"] == current["creator"]]
        front = pareto(same_creator)
        candidates = sorted((m for m in same_creator if m["index"] > current["index"]), key=lambda m: m["cost_per_task"])
        shown = [m for m in candidates if show_dominated or m["slug"] in front]
        lines.append(f"\n### {', '.join(names)}: now {current['name']} ({current['index']:.0f} pts, ${current['cost_per_task']:.2f}/task)\n")
        lines.append("| Move to | Index | +pts | AA cost x | Input price/token x | Pts per extra $ |")
        lines.append("|---|---|---|---|---|---|")
        for m in shown:
            extra = m["cost_per_task"] - current["cost_per_task"]
            ppd = f"{(m['index'] - current['index']) / extra:.1f}" if extra > 0 else "cheaper"
            price_x = f"{m['price_1m_input'] / current['price_1m_input']:.1f}x" if m["price_1m_input"] and current["price_1m_input"] else "?"
            mark = "" if m["slug"] in front else " (dominated)"
            lines.append(f"| {m['name']}{mark} | {m['index']:.0f} | +{m['index'] - current['index']:.0f} | {m['cost_per_task'] / current['cost_per_task']:.1f}x | {price_x} | {ppd} |")
        if hidden := len(candidates) - len(shown):
            lines.append(f"\n{hidden} dominated move(s) hidden: a cheaper option scores at least as high (`--show-dominated`).")
    return lines


def diff_rows(models: list[dict[str, Any]], previous: dict[str, Any]) -> list[str]:
    before = {m["slug"]: m for m in previous["models"]}
    lines = [f"\n## Changes since {previous['fetched_at']}\n"]
    for m in models:
        old = before.get(m["slug"])
        if old is None:
            lines.append(f"- new: {m['name']} ({m['index']:.0f} pts, ${m['cost_per_task']:.2f}/task)")
        elif abs(old["index"] - m["index"]) >= 0.5 or abs(old["cost_per_task"] - m["cost_per_task"]) >= 0.01:
            lines.append(f"- changed: {m['name']} {old['index']:.0f} -> {m['index']:.0f} pts, ${old['cost_per_task']:.2f} -> ${m['cost_per_task']:.2f}")
    if len(lines) == 1:
        lines.append("- no changes")
    return lines


def render_svg(models: list[dict[str, Any]], roles: dict[str, Any], version: str, fetched_at: str) -> str:
    width, height, left, right, top, bottom = 960, 600, 70, 190, 50, 60
    costs = [m["cost_per_task"] for m in models]
    lo, hi = math.log10(min(costs) * 0.8), math.log10(max(costs) * 1.25)
    y_lo, y_hi = max(0, math.floor(min(m["index"] for m in models) / 10) * 10 - 5), math.ceil(max(m["index"] for m in models) / 10) * 10 + 5

    def x(cost: float) -> float:
        return left + (math.log10(cost) - lo) / (hi - lo) * (width - left - right)

    def y(index: float) -> float:
        return height - bottom - (index - y_lo) / (y_hi - y_lo) * (height - top - bottom)

    palette = ["#c2410c", "#2563eb", "#059669", "#7c3aed", "#db2777", "#0891b2", "#65a30d", "#9333ea"]
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" font-family="system-ui, sans-serif" font-size="12">',
        f'<rect width="{width}" height="{height}" fill="#fff"/>',
        f'<text x="{left}" y="24" font-size="16" font-weight="600">Intelligence Index v{html.escape(version)} vs cost per task (log scale), {html.escape(fetched_at)}</text>',
    ]
    for tick in [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100]:
        if lo <= math.log10(tick) <= hi:
            out.append(f'<line x1="{x(tick):.1f}" x2="{x(tick):.1f}" y1="{top}" y2="{height - bottom}" stroke="#eee"/>')
            out.append(f'<text x="{x(tick):.1f}" y="{height - bottom + 18}" text-anchor="middle" fill="#555">${tick:g}</text>')
    for tick in range(int(y_lo), int(y_hi) + 1, 10):
        out.append(f'<line x1="{left}" x2="{width - right}" y1="{y(tick):.1f}" y2="{y(tick):.1f}" stroke="#eee"/>')
        out.append(f'<text x="{left - 8}" y="{y(tick) + 4:.1f}" text-anchor="end" fill="#555">{tick}</text>')
    out.append(f'<text x="{(left + width - right) / 2}" y="{height - 15}" text-anchor="middle" fill="#333">USD per Intelligence Index task</text>')
    out.append(f'<text x="18" y="{(top + height - bottom) / 2}" transform="rotate(-90 18 {(top + height - bottom) / 2})" text-anchor="middle" fill="#333">Intelligence Index</text>')

    front = sorted((m for m in models if m["slug"] in pareto(models)), key=lambda m: m["cost_per_task"])
    out.append('<polyline fill="none" stroke="#999" stroke-dasharray="4 4" points="' + " ".join(f"{x(m['cost_per_task']):.1f},{y(m['index']):.1f}" for m in front) + '"/>')

    releases = sorted({m["release"] for m in models})
    for i, release in enumerate(releases):
        color = palette[i % len(palette)]
        points = sorted((m for m in models if m["release"] == release), key=lambda m: m["effort_level"] or 0)
        if len(points) > 1:
            out.append(f'<polyline fill="none" stroke="{color}" stroke-width="2" points="' + " ".join(f"{x(m['cost_per_task']):.1f},{y(m['index']):.1f}" for m in points) + '"/>')
        for m in points:
            out.append(f'<circle cx="{x(m["cost_per_task"]):.1f}" cy="{y(m["index"]):.1f}" r="4" fill="{color}"><title>{html.escape(m["name"])}: {m["index"]:.1f} pts, ${m["cost_per_task"]:.2f}/task</title></circle>')
            out.append(f'<text x="{x(m["cost_per_task"]) + 12:.1f}" y="{y(m["index"]) + 4:.1f}" fill="{color}" font-size="10">{html.escape(m["effort"] or "")}</text>')
        ly = top + 10 + i * 18
        out.append(f'<rect x="{width - right + 20}" y="{ly - 9}" width="10" height="10" fill="{color}"/><text x="{width - right + 36}" y="{ly}">{html.escape(release)}</text>')

    roles_at: dict[str, list[str]] = {}
    for name, role in roles.items():
        if m := variant(models, role["release"], role["effort"]):
            roles_at.setdefault(m["slug"], []).append(name)
    for slug, names in roles_at.items():
        m = next(m for m in models if m["slug"] == slug)
        cx, cy = x(m["cost_per_task"]), y(m["index"])
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="9" fill="none" stroke="#111" stroke-width="1.5"/>')
        out.append(f'<text x="{cx - 12:.1f}" y="{cy - 12:.1f}" text-anchor="end" fill="#111" font-weight="600">{html.escape(", ".join(names))}</text>')
    ly = top + 10 + len(releases) * 18 + 10
    out.append(f'<line x1="{width - right + 20}" x2="{width - right + 32}" y1="{ly - 4}" y2="{ly - 4}" stroke="#999" stroke-dasharray="4 4"/><text x="{width - right + 36}" y="{ly}">Pareto frontier</text>')
    out.append(f'<circle cx="{width - right + 26}" cy="{ly + 14}" r="6" fill="none" stroke="#111"/><text x="{width - right + 36}" y="{ly + 18}">our current role</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def cmd_report(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir).expanduser()
    path = Path(args.snapshot).expanduser() if args.snapshot else latest_snapshot(data_dir)
    snapshot = json.loads(path.read_text())
    roles = load_roles()["roles"]
    models = snapshot["models"]
    if not args.all_creators:
        creators = {m["creator"] for m in models if m["release"] in snapshot["releases"]}
        models = [m for m in models if m["creator"] in creators]
    front = pareto(models)
    lines = [f"# Model frontier, Intelligence Index v{snapshot['index_version']} ({snapshot['fetched_at']})\n", "| Model | Effort | Index | $/task | Input $/1M | Frontier | Role |", "|---|---|---|---|---|---|---|"]
    role_of = {(r["release"], r["effort"]): n for n, r in roles.items()}
    for m in sorted(models, key=lambda m: m["cost_per_task"]):
        tags = ", ".join(n for (rel, eff), n in role_of.items() if (rel, eff) == (m["release"], m["effort"]))
        lines.append(f"| {m['name']} | {m['effort'] or '-'} | {m['index']:.0f} | {m['cost_per_task']:.2f} | {m['price_1m_input'] or '-'} | {'yes' if m['slug'] in front else ''} | {tags} |")
    lines.append("\n## Moves per role\n")
    lines.extend(role_rows(models, roles, args.show_dominated))
    if args.previous:
        previous = json.loads(Path(args.previous).expanduser().read_text())
        if previous["index_version"] != snapshot["index_version"]:
            print(f"refusing to diff: v{previous['index_version']} vs v{snapshot['index_version']} use different evaluations", file=sys.stderr)
            return 2
        lines.extend(diff_rows(models, previous))
    print("\n".join(lines))
    svg_path = Path(args.svg).expanduser() if args.svg else path.with_suffix(".svg")
    svg_path.write_text(render_svg(models, roles, snapshot["index_version"], snapshot["fetched_at"]))
    print(f"\nplot: {svg_path}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    sub = parser.add_subparsers(dest="cmd", required=True)
    fetch = sub.add_parser("fetch", help="download watched releases into a snapshot")
    fetch.add_argument("--release", action="append", help="AA release slug, repeatable (default: watch list in roles.json)")
    fetch.set_defaults(func=cmd_fetch)
    report = sub.add_parser("report", help="table, role moves and SVG plot from a snapshot")
    report.add_argument("--snapshot", help="snapshot JSON (default: newest)")
    report.add_argument("--previous", help="older snapshot of the same index version to diff against")
    report.add_argument("--svg", help="plot path (default: next to the snapshot)")
    report.add_argument("--all-creators", action="store_true", help="keep other vendors' models from the pages")
    report.add_argument("--show-dominated", action="store_true", help="also list moves a cheaper option beats")
    report.set_defaults(func=cmd_report)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ScrapeError as exc:
        print(f"scrape failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
