#!/usr/bin/env python3
"""Find past Claude Code sessions by keywords you remember.

Every term must appear (case-insensitive substring) somewhere in the session's
conversation text: your prompts and Claude's replies. Tool output is skipped
unless --tools is given, because it is mostly file dumps that match everything.
Sessions are ranked by TF-IDF with square-root length normalization (Lucene's
classic scoring): a term found in few sessions counts for more, and hits are
divided by sqrt(session size) so a session about the topic beats a long one
that mentions it in passing. Hits in your own prompts weigh more. BM25 was
tried and ranked worse: sessions are so long that its term-frequency
saturation flattens every long session to the same score.

Document frequency counts only user/assistant lines, because every transcript
also stores the injected system prompt, which mentions many common words.

--pick lists the ranked sessions in fzf with a preview pane; Enter resumes the
chosen one in its own directory.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

PROJECTS_DIR = Path.home() / ".claude" / "projects"
USER_WEIGHT = 3
SNIPPET_WIDTH = 160
MARKUP = re.compile(r"</?(?:pasted_content|bash-[a-z]+|(?:local-)?command-[a-z]+|system-reminder|task-notification)\b[^>]*>|```")
NOISE_PREFIXES = ("<command-", "<task-notification", "<local-command", "<system-reminder", "Caveat:", "[Request interrupted")


@dataclass
class Session:
    path: Path
    session_id: str = ""
    cwd: str = ""
    title: str = ""
    first_prompt: str = ""
    started: str = ""
    prs: list[str] = field(default_factory=list)
    user_texts: list[str] = field(default_factory=list)
    assistant_texts: list[str] = field(default_factory=list)
    tool_texts: list[str] = field(default_factory=list)


def in_project(path: Path, project: str | None) -> bool:
    return not project or project.lower() in path.parent.name.lower()


def corpus_size(project: str | None) -> int:
    return sum(1 for p in PROJECTS_DIR.glob("*/*.jsonl") if in_project(p, project))


def files_containing(term: str, project: str | None) -> set[Path]:
    conversation_line = f'^(?=.*"type":"(user|assistant)")(?=.*{re.escape(term)})'
    cmd = ["rg", "-l", "-i", "-P", "--max-depth", "2", "-g", "*.jsonl", "-e", conversation_line, str(PROJECTS_DIR)]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    return {Path(line) for line in out.splitlines() if line and in_project(Path(line), project)}


def idf(df: int, n: int) -> float:
    return math.log((n - df + 0.5) / (df + 0.5) + 1)


def tf_idf(tfs: list[int], idfs: list[float], kchars: float) -> float:
    return sum(w * tf for tf, w in zip(tfs, idfs)) / math.sqrt(kchars + 1)


def block_texts(content, wanted: str) -> list[str]:
    if isinstance(content, str):
        return [content] if wanted == "text" else []
    texts = []
    for block in content or []:
        if not isinstance(block, dict) or block.get("type") != wanted:
            continue
        if wanted == "text":
            texts.append(block.get("text", ""))
        else:
            inner = block.get("content")
            if isinstance(inner, str):
                texts.append(inner)
            elif isinstance(inner, list):
                texts += [b.get("text", "") for b in inner if isinstance(b, dict)]
    return texts


def is_noise(text: str) -> bool:
    return not text.strip() or text.lstrip().startswith(NOISE_PREFIXES)


def parse(path: Path, with_tools: bool) -> Session:
    s = Session(path=path, session_id=path.stem)
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = rec.get("type")
            if kind == "ai-title":
                s.title = s.title if s.title.startswith("*") else rec.get("aiTitle", s.title)
            elif kind == "custom-title":
                s.title = "*" + rec.get("customTitle", "")
            elif kind == "pr-link" and rec.get("prUrl") not in s.prs:
                s.prs.append(rec.get("prUrl"))
            elif kind in ("user", "assistant") and not rec.get("isSidechain"):
                s.cwd = s.cwd or rec.get("cwd", "")
                s.started = s.started or rec.get("timestamp", "")
                content = (rec.get("message") or {}).get("content")
                if kind == "assistant":
                    s.assistant_texts += block_texts(content, "text")
                    continue
                if with_tools:
                    s.tool_texts += block_texts(content, "tool_result")
                if rec.get("isMeta"):
                    continue
                for text in block_texts(content, "text"):
                    if is_noise(text):
                        continue
                    s.user_texts.append(text)
                    s.first_prompt = s.first_prompt or text
    return s


def count_hits(texts: list[str], pattern: re.Pattern) -> int:
    return sum(len(pattern.findall(t)) for t in texts)


def snippets(texts: list[str], patterns: list[re.Pattern], limit: int) -> list[str]:
    found = []
    for text in texts:
        for p in patterns:
            m = p.search(text)
            if not m:
                continue
            start = max(0, m.start() - SNIPPET_WIDTH // 3)
            snippet = " ".join(text[start : start + SNIPPET_WIDTH].split())
            found.append(("…" if start else "") + snippet + "…")
            break
        if len(found) >= limit:
            break
    return found


def one_line(text: str, width: int = 110) -> str:
    flat = " ".join(MARKUP.sub(" ", text).split())
    return flat if len(flat) <= width else flat[: width - 1] + "…"


def describe(s: Session, score: float, mtime: float, patterns: list[re.Pattern], n_snippets: int) -> str:
    last = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
    lines = [f"● {s.session_id}  score {score}  last active {last}", f"  project: {s.cwd or s.path.parent.name}"]
    if s.title:
        lines.append(f"  title:   {s.title.lstrip('*')}")
    if s.first_prompt:
        lines.append(f"  opened:  {one_line(s.first_prompt)}")
    lines += [f"  pr:      {pr}" for pr in s.prs[:5]]
    found = snippets(s.user_texts, patterns, n_snippets) or snippets(s.assistant_texts, patterns, n_snippets)
    lines += [f"  match:   {snip}" for snip in found]
    lines.append(f"  resume:  cd {s.cwd or '.'} && claude --resume {s.session_id}")
    return "\n".join(lines)


def pick(ranked: list[tuple[float, float, Session]], patterns: list[re.Pattern]) -> int:
    if not shutil.which("fzf"):
        print("fzf is not installed (brew install fzf)", file=sys.stderr)
        return 1
    by_id = {s.session_id: s for _, _, s in ranked}
    with tempfile.TemporaryDirectory() as tmp:
        rows = []
        for score, mtime, s in ranked:
            Path(tmp, f"{s.session_id}.txt").write_text(describe(s, score, mtime, patterns, 8))
            label = s.title.lstrip("*") or one_line(s.first_prompt, 60)
            date = datetime.fromtimestamp(mtime).strftime("%m-%d %H:%M")
            project = Path(s.cwd).name if s.cwd else s.path.parent.name
            rows.append(f"{s.session_id}\t{score:>5}  {date:<11}  {project:<22.22}  {label}  · {one_line(s.first_prompt, 80)}")
        fzf = subprocess.run(
            ["fzf", "--delimiter", "\t", "--with-nth", "2..", "--no-sort", "--layout", "reverse",
             "--header", f"{'score':>5}  {'last active':<11}  {'project':<22}  title · opened   (Enter resumes)",
             "--preview", f"cat {tmp}/{{1}}.txt", "--preview-window", "down,55%,wrap"],
            input="\n".join(rows), capture_output=False, stdout=subprocess.PIPE, text=True,
        )
    choice = fzf.stdout.strip().split("\t", 1)[0]
    if fzf.returncode != 0 or choice not in by_id:
        return 130
    s = by_id[choice]
    if s.cwd and Path(s.cwd).is_dir():
        os.chdir(s.cwd)
    os.execvp("claude", ["claude", "--resume", choice])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("terms", nargs="+", help="keywords; all must match (case-insensitive)")
    ap.add_argument("-p", "--project", help="substring of the project dir name, e.g. allswell")
    ap.add_argument("-d", "--days", type=int, help="only sessions active in the last N days")
    ap.add_argument("-n", "--limit", type=int, default=5, help="sessions to show (default 5)")
    ap.add_argument("--tools", action="store_true", help="also search tool output (noisy)")
    ap.add_argument("--include-current", action="store_true", help="do not hide the running session")
    ap.add_argument("--pick", action="store_true", help="choose interactively in fzf and resume it")
    args = ap.parse_args()

    patterns = [re.compile(re.escape(t), re.IGNORECASE) for t in args.terms]
    current = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    cutoff = time.time() - args.days * 86400 if args.days else 0

    containing = [files_containing(t, args.project) for t in args.terms]
    n = corpus_size(args.project)
    idfs = [idf(len(files), n) for files in containing]

    matched = []
    for path in set.intersection(*containing):
        mtime = path.stat().st_mtime
        if mtime < cutoff or (path.stem == current and not args.include_current):
            continue
        s = parse(path, args.tools)
        others = s.assistant_texts + s.tool_texts
        tfs = [USER_WEIGHT * count_hits(s.user_texts, p) + count_hits(others, p) for p in patterns]
        if 0 in tfs:
            continue
        kchars = sum(map(len, s.user_texts + others)) / 1000
        matched.append((tfs, kchars, mtime, s))

    if not matched:
        print("No session matches all of: " + ", ".join(args.terms), file=sys.stderr)
        return 1

    ranked = sorted(
        ((round(tf_idf(tfs, idfs, kchars), 2), mtime, s) for tfs, kchars, mtime, s in matched),
        key=lambda r: (r[0], r[1]), reverse=True,
    )
    if args.pick:
        return pick(ranked, patterns)

    print(f"{len(ranked)} matching session(s), top {min(args.limit, len(ranked))}:\n")
    for score, mtime, s in ranked[: args.limit]:
        print(describe(s, score, mtime, patterns, 3) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
