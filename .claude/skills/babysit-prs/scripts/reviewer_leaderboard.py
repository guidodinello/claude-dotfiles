#!/usr/bin/env python3
"""Rank `/code-review` reviewer models by how often their findings get accepted.

Issue 288. `babysit-prs` Step 3 picks a free model for each review; this
script turns the PR history into the signal for that choice. It is read-only
and stdlib-only, and it fetches everything itself with `gh`:

- Review bodies (GraphQL `pullRequests{reviews{databaseId body}}`). A review is
  a code review when its body starts with the `### Code review` header the
  `code-review` skill writes; its model comes from the
  `🤖 Generated with <harness>, model <id>` footer.
- Inline comments (REST `repos/{owner}/{repo}/pulls/comments`). A thread root
  whose `pull_request_review_id` is a code review is one finding, `[blocking]`
  or `[non-blocking]` by its marker. The first reply in the thread (written by
  `address-pr-comments`) decides the outcome: accepted ("Fixed in ..."),
  rejected ("Declining ...", "doesn't hold ..."), other, or no reply.

Output: a per-model table (reviews, findings per review, outcome counts,
accepted % = accepted / (accepted + rejected)), and a paired-recall table. On
PRs reviewed by two or more models, it counts for each ordered pair (A, B) the
accepted findings of A that B missed, meaning B left no finding on the same
path within +/-5 lines. Only reviews of the same commit are paired: a later
review of a PR, made after the first one's findings were fixed, cannot
re-report them, so cross-commit pairs would count fixes as misses. That table
catches a model whose accepted % is high only because it reports very little.

Usage:
    python3 ~/.claude/skills/babysit-prs/scripts/reviewer_leaderboard.py
    python3 ~/.claude/skills/babysit-prs/scripts/reviewer_leaderboard.py --days 365
    python3 ~/.claude/skills/babysit-prs/scripts/reviewer_leaderboard.py --min-samples 20

Caveats:
- "Accepted" is judged by the Claude-driven `address-pr-comments`. It measures
  whether a finding is *valid*, not how important it is. That agent may also
  be lenient on nits, which inflates acceptance for nit-heavy reviewers.
- Footer formats vary and some reviews lack a model, so the numbers are only
  as good as `normalize_model_id` and `MODEL_ALIASES`. Reviews with no model id
  are bucketed as `unknown:<harness>`, never dropped. Extend the alias map when
  a new variant shows up as `unknown` or as a near-duplicate row.
- Reply classification is a regex over free text. A decline phrased without
  any of the rejection keywords lands in `other`, which is excluded from
  accepted %.
- Paired matching is approximate: two reviews made at different commits can
  put the same finding on drifted line numbers, and a file-level comment (no
  line) matches any finding on the same path.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from itertools import permutations
from typing import Any

ACCEPTED = "accepted"
REJECTED = "rejected"
OTHER = "other"
NO_REPLY = "no-reply"

DEFAULT_DAYS = 180
DEFAULT_MIN_SAMPLES = 10
PAIR_LINE_WINDOW = 5

_CODE_REVIEW_HEADER_RE = re.compile(r"^\s*#{2,3}\s*Code review\b", re.IGNORECASE)
_FOOTER_RE = re.compile(r"Generated with\s+(?P<rest>[^\n]*)", re.IGNORECASE)
_MODEL_RE = re.compile(r"\bmodel\b:?\s*`?\s*(?P<id>[^`\s]+)", re.IGNORECASE)
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_BLOCKING_RE = re.compile(r"\[blocking\]", re.IGNORECASE)

# First words of a reply that mean the finding was acted on, and phrases that
# mean it was declined. Taken verbatim from the 2026-10-25 analysis (Issue 288
# appendix) so the numbers stay comparable with the Issue's table.
_ACCEPT_RE = re.compile(
    r"^\W*(fixed|added|amended|updated|removed|changed|done|addressed|applied"
    r"|renamed|reverted|good catch|agreed|valid)",
    re.IGNORECASE,
)
_REJECT_RE = re.compile(
    r"(declin|not fixing|won't fix|wont fix|doesn't hold|does not hold|not a bug"
    r"|false positive|not valid|invalid|disagree|incorrect|no change"
    r"|not applicable|intentional|by design|moot|not an issue|out of scope"
    r"|skipp)",
    re.IGNORECASE,
)

# Normalized id -> canonical id, for variants the generic rules in
# normalize_model_id cannot merge. Extend when a near-duplicate row appears.
MODEL_ALIASES: dict[str, str] = {}


def normalize_model_id(raw: str) -> str:
    """Canonical model name for a raw footer model id.

    Drops the provider path (`opencode/`, `kilo/nvidia/`, ...), the free-tier
    suffix (`-free`, `:free`), the `-contributor` tag, a parameter-size
    suffix (`-550b-a55b`) and a dated snapshot (`-20251001`), and spells
    `v2-5` as `v2.5`. Distinct versions such as `claude-sonnet-5` and
    `claude-sonnet-5-5` stay distinct.
    """
    name = raw.strip().strip("`").strip().rstrip(".`").lower()
    name = name.rsplit("/", 1)[-1]
    name = re.sub(r"[:-]free$", "", name)
    name = re.sub(r"-contributor$", "", name)
    name = re.sub(r"-\d{8}$", "", name)
    name = re.sub(r"-\d+b(?:-a\d+b)?$", "", name)
    name = re.sub(r"\bv(\d+)-(\d+)\b", r"v\1.\2", name)
    return MODEL_ALIASES.get(name, name)


def _harness_slug(footer_rest: str) -> str:
    text = _MD_LINK_RE.sub(r"\1", footer_rest)
    text = re.split(r"[,(]", text, maxsplit=1)[0]
    slug = re.sub(r"[^a-z0-9]+", "", text.lower())
    return slug or "unspecified"


def review_model(body: str | None) -> str | None:
    """Model bucket for a review body, or None if it is not a code review.

    A code review without a usable model id is `unknown:<harness>` (or plain
    `unknown` with no footer at all), so it still shows up in the table.
    """
    if not body or not _CODE_REVIEW_HEADER_RE.match(body):
        return None
    footer = _FOOTER_RE.search(body)
    if footer is None:
        return "unknown"
    rest = footer.group("rest")
    match = _MODEL_RE.search(rest)
    model_id = match.group("id").strip().rstrip(".`") if match else ""
    if not model_id:
        return f"unknown:{_harness_slug(rest)}"
    return normalize_model_id(model_id)


def classify_reply(body: str | None) -> str:
    """Outcome of a finding from the first reply in its thread."""
    if body is None:
        return NO_REPLY
    if _ACCEPT_RE.search(body[:80]) and not _REJECT_RE.search(body[:60]):
        return ACCEPTED
    if _REJECT_RE.search(body[:300]):
        return REJECTED
    return OTHER


@dataclass(frozen=True)
class Review:
    id: int
    pr: int
    model: str
    commit: str | None = None


@dataclass(frozen=True)
class Finding:
    review_id: int
    pr: int
    model: str
    path: str
    line: int | None
    blocking: bool
    outcome: str


@dataclass
class ModelStats:
    model: str
    reviews: int = 0
    prs: set[int] = field(default_factory=set[int])
    zero_finding_reviews: int = 0
    blocking: int = 0
    non_blocking: int = 0
    outcomes: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    @property
    def decided(self) -> int:
        return self.outcomes[ACCEPTED] + self.outcomes[REJECTED]

    @property
    def accepted_pct(self) -> float | None:
        if not self.decided:
            return None
        return 100 * self.outcomes[ACCEPTED] / self.decided


# A (PR number, reviewed commit oid) pair: what two reviews must share to pair.
Snapshot = tuple[int, str]


@dataclass(frozen=True)
class PairStat:
    model_a: str
    model_b: str
    shared_snapshots: int
    a_accepted: int
    missed_by_b: int


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def code_reviews(pr_nodes: Iterable[dict[str, Any]], cutoff: datetime) -> list[Review]:
    """Code reviews submitted at or after *cutoff*, from GraphQL PR nodes."""
    reviews: list[Review] = []
    for pr in pr_nodes:
        for node in pr["reviews"]["nodes"]:
            submitted = node.get("submittedAt")
            if not submitted or _parse_ts(submitted) < cutoff:
                continue
            model = review_model(node.get("body"))
            if model is not None:
                commit_node: dict[str, Any] = node.get("commit") or {}
                commit: str | None = commit_node.get("oid")
                reviews.append(Review(node["databaseId"], pr["number"], model, commit))
    return reviews


def build_findings(
    reviews: Iterable[Review], comments: Iterable[dict[str, Any]]
) -> list[Finding]:
    """One Finding per inline thread root that belongs to a code review."""
    by_id = {r.id: r for r in reviews}
    comments = sorted(comments, key=lambda c: c["created_at"])
    first_reply: dict[int, str] = {}
    for c in comments:
        parent = c.get("in_reply_to_id")
        if parent and parent not in first_reply:
            first_reply[parent] = c.get("body") or ""
    findings: list[Finding] = []
    for c in comments:
        if c.get("in_reply_to_id"):
            continue
        review_id = c.get("pull_request_review_id")
        review = by_id.get(review_id) if review_id is not None else None
        if review is None:
            continue
        line = c.get("original_line") or c.get("line")
        findings.append(
            Finding(
                review_id=review.id,
                pr=review.pr,
                model=review.model,
                path=c.get("path") or "",
                line=line,
                blocking=bool(_BLOCKING_RE.search(c.get("body") or "")),
                outcome=classify_reply(first_reply.get(c["id"])),
            )
        )
    return findings


def model_stats(
    reviews: Iterable[Review], findings: Iterable[Finding]
) -> dict[str, ModelStats]:
    stats: dict[str, ModelStats] = {}
    findings = list(findings)
    for f in findings:
        s = stats.setdefault(f.model, ModelStats(f.model))
        s.outcomes[f.outcome] += 1
        if f.blocking:
            s.blocking += 1
        else:
            s.non_blocking += 1
    with_findings = {f.review_id for f in findings}
    for r in reviews:
        s = stats.setdefault(r.model, ModelStats(r.model))
        s.reviews += 1
        s.prs.add(r.pr)
        if r.id not in with_findings:
            s.zero_finding_reviews += 1
    return stats


def same_spot(a: Finding, b: Finding, window: int = PAIR_LINE_WINDOW) -> bool:
    """True if *b* plausibly reports the same finding as *a*."""
    if a.path != b.path:
        return False
    if a.line is None or b.line is None:
        return True
    return abs(a.line - b.line) <= window


def paired_recall(
    findings: Iterable[Finding],
    reviews: Iterable[Review],
    window: int = PAIR_LINE_WINDOW,
) -> list[PairStat]:
    """For each ordered model pair, accepted findings of A that B missed.

    Only (PR, commit) snapshots that both models reviewed count; reviews with
    no known commit are never paired. A finding of A is missed by B when B
    left no finding of any outcome on the same spot (`same_spot`).
    """
    snapshot_of: dict[int, Snapshot] = {}
    reviewed: dict[Snapshot, set[str]] = defaultdict(set)
    for r in reviews:
        if r.commit is None:
            continue
        snapshot_of[r.id] = (r.pr, r.commit)
        reviewed[(r.pr, r.commit)].add(r.model)
    by_snapshot: dict[Snapshot, dict[str, list[Finding]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for f in findings:
        snap = snapshot_of.get(f.review_id)
        if snap is not None:
            by_snapshot[snap][f.model].append(f)
    shared: dict[tuple[str, str], int] = defaultdict(int)
    accepted: dict[tuple[str, str], int] = defaultdict(int)
    missed: dict[tuple[str, str], int] = defaultdict(int)
    for snap, models in reviewed.items():
        for a, b in permutations(sorted(models), 2):
            shared[(a, b)] += 1
            theirs = by_snapshot[snap][b]
            for f in by_snapshot[snap][a]:
                if f.outcome != ACCEPTED:
                    continue
                accepted[(a, b)] += 1
                if not any(same_spot(f, g, window) for g in theirs):
                    missed[(a, b)] += 1
    return [
        PairStat(a, b, shared[(a, b)], accepted[(a, b)], missed[(a, b)])
        for (a, b) in sorted(shared)
    ]


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value:.0f}%"


def format_model_table(stats: dict[str, ModelStats], min_samples: int) -> str:
    """Ranked models (by accepted %) first, then low-sample ones by reviews."""

    def key(s: ModelStats) -> tuple[bool, float, int]:
        if s.decided < min_samples:
            return (True, 0.0, -s.reviews)
        return (False, -(s.accepted_pct or 0.0), -s.reviews)

    header = (
        f"{'model':<28}{'revs':>5}{'PRs':>5}{'blk/rev':>8}{'nb/rev':>7}"
        f"{'0-find':>7}{'acc':>5}{'rej':>5}{'oth':>5}{'norep':>6}{'acc%':>6}  note"
    )
    lines = [header, "-" * len(header)]
    for s in sorted(stats.values(), key=key):
        n = s.reviews or 1
        note = f"low-sample (<{min_samples} decided)" if s.decided < min_samples else ""
        lines.append(
            f"{s.model[:27]:<28}{s.reviews:>5}{len(s.prs):>5}"
            f"{s.blocking / n:>8.2f}{s.non_blocking / n:>7.2f}"
            f"{s.zero_finding_reviews:>7}{s.outcomes[ACCEPTED]:>5}"
            f"{s.outcomes[REJECTED]:>5}{s.outcomes[OTHER]:>5}"
            f"{s.outcomes[NO_REPLY]:>6}{_pct(s.accepted_pct):>6}  {note}".rstrip()
        )
    return "\n".join(lines)


def format_pair_table(pairs: Iterable[PairStat]) -> str:
    rows = [p for p in pairs if p.a_accepted]
    rows.sort(key=lambda p: (p.model_a, -p.missed_by_b, p.model_b))
    header = (
        f"{'model A':<28}{'model B':<28}{'snaps':>6}{'A acc':>7}{'B missed':>10}"
        f"{'missed%':>9}"
    )
    lines = [header, "-" * len(header)]
    for p in rows:
        lines.append(
            f"{p.model_a[:27]:<28}{p.model_b[:27]:<28}{p.shared_snapshots:>6}"
            f"{p.a_accepted:>7}{p.missed_by_b:>10}"
            f"{_pct(100 * p.missed_by_b / p.a_accepted):>9}"
        )
    if not rows:
        lines.append("(no commit in the window was reviewed by two models)")
    return "\n".join(lines)


def _gh(args: list[str]) -> str:
    return subprocess.run(
        ["gh", *args], check=True, capture_output=True, text=True
    ).stdout


def _current_repo() -> str:
    return _gh(
        ["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]
    ).strip()


_PRS_QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(first: 25, after: $cursor,
                 orderBy: {field: UPDATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number updatedAt
        reviews(first: 100) {
          pageInfo { hasNextPage }
          nodes { databaseId body submittedAt commit { oid } }
        }
      }
    }
  }
}
"""


def fetch_pr_reviews(repo: str, cutoff: datetime) -> list[dict[str, Any]]:
    """PR nodes with their reviews, newest-updated first, back to *cutoff*."""
    owner, name = repo.split("/", 1)
    nodes: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        args = ["api", "graphql", "-f", f"query={_PRS_QUERY}"]
        args += ["-F", f"owner={owner}", "-F", f"name={name}"]
        if cursor:
            args += ["-F", f"cursor={cursor}"]
        page = json.loads(_gh(args))["data"]["repository"]["pullRequests"]
        for pr in page["nodes"]:
            if pr["reviews"]["pageInfo"]["hasNextPage"]:
                print(
                    f"warning: PR #{pr['number']} has more than 100 reviews; "
                    "only the first 100 are counted",
                    file=sys.stderr,
                )
        nodes.extend(page["nodes"])
        last = page["nodes"][-1] if page["nodes"] else None
        if not page["pageInfo"]["hasNextPage"] or (
            last and _parse_ts(last["updatedAt"]) < cutoff
        ):
            return nodes
        cursor = page["pageInfo"]["endCursor"]


def fetch_inline_comments(repo: str, cutoff: datetime) -> list[dict[str, Any]]:
    """Inline review comments updated since *cutoff* (a superset of the window)."""
    since = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
    out = _gh(
        [
            "api",
            "--paginate",
            "--slurp",
            f"repos/{repo}/pulls/comments?per_page=100&since={since}",
        ]
    )
    return [c for page in json.loads(out) for c in page]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Rank /code-review reviewer models by accepted-finding rate."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS,
        help=f"rolling window on review submit time (default {DEFAULT_DAYS})",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=DEFAULT_MIN_SAMPLES,
        help="decided findings (accepted + rejected) a model needs to be ranked "
        f"rather than marked low-sample (default {DEFAULT_MIN_SAMPLES})",
    )
    parser.add_argument(
        "--repo", help="OWNER/NAME (default: the repo of the current directory)"
    )
    args = parser.parse_args(argv)

    repo = args.repo or _current_repo()
    cutoff = datetime.now(UTC) - timedelta(days=args.days)
    reviews = code_reviews(fetch_pr_reviews(repo, cutoff), cutoff)
    findings = build_findings(reviews, fetch_inline_comments(repo, cutoff))

    print(
        f"{repo}: {len(reviews)} code reviews, {len(findings)} inline findings "
        f"since {cutoff:%Y-%m-%d} (--days {args.days})\n"
    )
    print("Per model (accepted % = accepted / (accepted + rejected)):")
    print(format_model_table(model_stats(reviews, findings), args.min_samples))
    print(
        f"\nPaired recall (same path, +/-{PAIR_LINE_WINDOW} lines; accepted "
        "findings of A that B missed, on PR commits both reviewed):"
    )
    print(format_pair_table(paired_recall(findings, reviews)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
