#!/usr/bin/env python3
"""Pair each sent message in a corpus file with the earliest Claude draft that matches it.

Usage: pair_drafts.py <sent-corpus.md> <project-substring> [--config-dir DIR]
The corpus format is `### <header>` sections with the message as `> ` blockquote lines.
Output contains client text: write it inside the project, never into a public repo.
"""
import argparse
import json
import glob
import os
import re
import sys
import difflib
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("corpus"); ap.add_argument("project")
ap.add_argument("--config-dir", default=os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude"))
a = ap.parse_args()
corpus = open(a.corpus).read()
dirs = [d for d in glob.glob(os.path.expanduser(a.config_dir) + "/projects/*/") if a.project in os.path.basename(d.rstrip("/"))]

# parse sent messages: header + blockquote lines
sent = []
for sec in re.split(r'\n### ', corpus)[1:]:
    head = sec.split('\n', 1)[0]
    body = '\n'.join(l[2:] if l.startswith('> ') else '' for l in sec.split('\n') if l.startswith('>'))
    if len(body) > 120:
        sent.append((head, body))

def norm(s):
    s = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', s)
    s = re.sub(r'https?://\S+', '', s)
    return re.sub(r'\s+', ' ', s.replace('’', "'").replace('`', '')).strip().lower()

def toks(s): return set(re.findall(r'[a-z0-9]{3,}', s))

# candidate drafts: assistant text blocks + user-pasted blocks, split on ``` / --- fences and blank-line groups
cands = []
for f in [f for d in dirs for f in glob.glob(d + '*.jsonl')]:
    for line in open(f, errors='ignore'):
        if '"text"' not in line and '"content":"' not in line: continue
        try: o = json.loads(line)
        except ValueError: continue
        if o.get('type') not in ('assistant', 'user') or o.get('isSidechain'): continue
        c = o.get('message', {}).get('content')
        t = c if isinstance(c, str) else ' \n'.join(p.get('text', '') for p in c or [] if isinstance(p, dict) and p.get('type') == 'text')
        if len(t) < 120: continue
        for blk in re.split(r'```|\n---\s*\n', t):
            if len(blk) > 120: cands.append((o['type'], o.get('timestamp', '')[:16], os.path.basename(f)[:8], blk))
print(len(sent), 'sent;', len(cands), 'candidate blocks', file=sys.stderr)

out = []
pre = [(who, ts, sid, blk, norm(blk)) for who, ts, sid, blk in cands]
pre = [(w, ts, s, b, n, toks(n)) for w, ts, s, b, n in pre]
for head, body in sent:
    nb = norm(body); tb = toks(nb)
    best = []
    for who, ts, sid, blk, nk, tk in pre:
        if not tk or len(tb & tk) / len(tb | tk) < 0.35: continue
        r = difflib.SequenceMatcher(None, nk, nb, autojunk=False).ratio()
        if r >= 0.55 and nk != nb: best.append((r, ts, who, sid, blk))
    best.sort(key=lambda x: (x[1]))
    if best:
        asst = [b for b in best if b[2] == 'assistant']
        top = (asst or best)[0]
        out.append((head, body, top, len(best)))

for head, body, (r, ts, who, sid, blk), n in out:
    print(f"## {head}\nmatch={r:.2f} from={who} session={sid} at={ts} ({n} candidates)\n\n### draft\n{blk.strip()}\n\n### sent\n{body.strip()}\n")
print(len(out), 'paired', file=sys.stderr)
