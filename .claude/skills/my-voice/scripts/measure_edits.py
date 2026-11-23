#!/usr/bin/env python3
"""Score how much Guido edits Claude's drafts before sending, before vs after a cutoff (e.g. a skill or rule change).

Usage: measure_edits.py <sent-corpus.md> <project-substring> --since "YYYY-MM-DD HH:MM" [--utc-offset -3] [--floor 0.40]

The corpus format is `### <YYYY-MM-DD HH:MM> <header>` sections with the message as `> ` blockquote lines,
times in local time. Per sent message:
  first  = similarity (difflib, 0-1) to the earliest Claude draft scoring >= floor. The score to track.
  best   = closest draft. Inflated when Claude re-prints the user's own edit; don't track it.
  drafts = distinct drafts >= floor before sending (chat iterations).
Only drafts written before the send time count. A message with no draft >= floor is reported, not dropped.
Lines that are mostly Spanish function words are removed from drafts (chat notes around an English draft).
Output contains client text: write it inside the project, never into a public repo.
"""
import argparse
import json
import glob
import os
import re
import sys
import difflib
import datetime as dt
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("corpus"); ap.add_argument("project")
ap.add_argument("--since", required=True); ap.add_argument("--utc-offset", type=float, default=-3)
ap.add_argument("--floor", type=float, default=0.40)
ap.add_argument("--config-dir", default=os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude"))
a = ap.parse_args()
to_utc = lambda t: t - dt.timedelta(hours=a.utc_offset)
since = to_utc(dt.datetime.fromisoformat(a.since))

sent = []
for sec in re.split(r'\n### ', '\n' + open(a.corpus).read())[1:]:
    head = sec.split('\n', 1)[0]
    m = re.match(r'(\d{4}-\d{2}-\d{2}) ~?(\d{2}:\d{2})', head)
    body = '\n'.join(l[2:] if l.startswith('> ') else '' for l in sec.split('\n') if l.startswith('>'))
    if m and len(body) > 120:
        t = to_utc(dt.datetime.fromisoformat(f"{m[1]} {m[2]}"))
        sent.append((t, head, body, 'after' if t >= since else 'before'))

ES = set('que el la los las porque va es del con para lo una un como pero si ya te le se acá así más'.split())
def clean(blk):
    keep = []
    for l in blk.split('\n'):
        l = re.sub(r'^\s*>\s?', '', l)
        w = re.findall(r'[a-záéíóúñ]+', l.lower())
        if not (w and sum(x in ES for x in w) / len(w) > 0.2): keep.append(l)
    return '\n'.join(keep)
def norm(s):
    s = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', s); s = re.sub(r'<[^|>]+\|([^>]+)>', r'\1', s)
    s = re.sub(r'https?://\S+', '', s); s = re.sub(r'[*_•\-]', ' ', s)
    return re.sub(r'\s+', ' ', s.replace('’', "'").replace('`', '')).strip().lower()
def toks(s): return set(re.findall(r'[a-z0-9]{3,}', s))

dirs = [d for d in glob.glob(os.path.expanduser(a.config_dir) + "/projects/*/")
        if a.project in os.path.basename(d.rstrip("/")) and 'scratchpad' not in d]
cands = []
for f in [f for d in dirs for f in glob.glob(d + '*.jsonl')]:
    for line in open(f, errors='ignore'):
        if '"assistant"' not in line: continue
        try: o = json.loads(line)
        except ValueError: continue
        if o.get('type') != 'assistant' or o.get('isSidechain'): continue
        t = ' \n'.join(p.get('text', '') for p in o.get('message', {}).get('content') or []
                       if isinstance(p, dict) and p.get('type') == 'text')
        if len(t) < 100: continue
        ts = dt.datetime.fromisoformat(o['timestamp'][:19])
        for blk in re.split(r'```|\n---\s*\n', t):
            n = norm(clean(blk))
            if len(n) > 80: cands.append((ts, n, toks(n)))
print(len(sent), 'sent;', len(cands), 'draft blocks', file=sys.stderr)

rows = []
for t, head, body, era in sorted(sent):
    nb = norm(body); tb = toks(nb); hits = []
    for ts, nk, tk in cands:
        if ts > t + dt.timedelta(minutes=5) or not tk or len(tb & tk) / len(tb | tk) < 0.25: continue
        r = difflib.SequenceMatcher(None, nk, nb, autojunk=False).ratio()
        if r >= a.floor: hits.append((ts, r, nk))
    hits.sort()
    first = hits[0][1] if hits else None
    best = max((h[1] for h in hits), default=None)
    rows.append((era, first, len({h[2] for h in hits})))
    f = lambda x: f'{x:.2f}' if x is not None else '-'
    print(f"{era:6} | {head[:58]:58} | first={f(first)} best={f(best)} drafts={len({h[2] for h in hits})}")
med = lambda xs: f'{sorted(xs)[len(xs) // 2]:.2f}' if xs else '-'
print("\n| | msgs | with Claude draft | median first | median drafts |\n|---|---|---|---|---|")
for era in ('before', 'after'):
    rs = [r for r in rows if r[0] == era]; m = [r for r in rs if r[1] is not None]
    print(f"| {era} | {len(rs)} | {len(m)} | {med([r[1] for r in m])} | {med([r[2] for r in m])} |")
