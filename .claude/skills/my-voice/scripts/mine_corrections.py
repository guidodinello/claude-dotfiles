#!/usr/bin/env python3
"""List user messages in Claude Code transcripts that look like wording corrections to a draft.

Each hit prints the tail of the assistant message before it (the draft) and the user message.
Output can contain client text: print it or write it inside the project, never into a public repo.
"""
import argparse
import glob
import json
import os
import re
import sys
import time

DRAFT = re.compile(r"(^|\n)---\s*\n|```|\bdraft\b|\bslack\b|\bmessage\b|\breply\b", re.I)
CORRECTION = re.compile(
    r"(don'?t like|doesn'?t (feel|sound|read)|not (so )?natural|machine like|too (formal|long|much|strong|stiff)"
    r"|tone (it )?down|sounds? (weird|off|robotic|better|good)|i'?d (say|write|rather)|i would (say|write)"
    r"|instead of|rather than|rephrase|reword|phrased? (it )?differently|drop the|remove (the|that)"
    r"|exclamation|colon|is it natural|reads (bad|wrong|like)|my voice|more casual|less formal)",
    re.I,
)


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text")
    return ""


def scan(path, tail):
    prev = ""
    with open(path, errors="ignore") as fh:
        for line in fh:
            try:
                o = json.loads(line)
            except ValueError:
                continue
            if o.get("isSidechain") or o.get("isMeta"):
                continue
            t = text_of(o.get("message", {}).get("content"))
            if o.get("type") == "assistant":
                if t.strip():
                    prev = t
                continue
            if o.get("type") != "user" or not t.strip() or t.lstrip().startswith("<") or len(t) > 2000:
                continue
            if CORRECTION.search(t) and DRAFT.search(prev):
                yield o.get("timestamp", "")[:16], prev[-tail:], t


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("project", help="substring of the project dir under ~/.claude/projects")
    ap.add_argument("-d", "--days", type=int, help="only transcripts modified in the last N days")
    ap.add_argument("--tail", type=int, default=500, help="chars of the draft to show (default 500)")
    ap.add_argument("--config-dir", default=os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude"))
    a = ap.parse_args()

    root = os.path.expanduser(a.config_dir) + "/projects/"
    files = [f for f in glob.glob(root + "*/*.jsonl") if a.project in os.path.basename(os.path.dirname(f))]
    if a.days:
        cutoff = time.time() - a.days * 86400
        files = [f for f in files if os.path.getmtime(f) >= cutoff]

    n = 0
    seen = set()
    for f in sorted(files, key=os.path.getmtime):
        for ts, draft, user in scan(f, a.tail):
            if user in seen:
                continue
            seen.add(user)
            n += 1
            print(f"## {os.path.basename(f)[:8]} {ts}\nDRAFT …{' '.join(draft.split())}\nUSER  {' '.join(user.split())}\n")
    print(f"{n} hits in {len(files)} transcripts", file=sys.stderr)


if __name__ == "__main__":
    main()
