#!/usr/bin/env python3
"""Pending tool and last text from a worker's transcript.

usage: wstat.py <worktree-path | transcript-dir-name> [chars]
Exit 2 when the worker has not written a transcript yet.
"""
import importlib.util
import json
import os
import sys

sys.dont_write_bytecode = True
_spec = importlib.util.spec_from_file_location(
    "_transcript", os.path.join(os.path.dirname(os.path.abspath(__file__)), "_transcript.py")
)
tx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tx)

if len(sys.argv) < 2:
    sys.exit(__doc__.strip())
n = int(sys.argv[2]) if len(sys.argv) > 2 else 1500
project = tx.resolve(sys.argv[1])
transcript = tx.latest(project)
if not transcript:
    print(f"no transcript yet in {project}", file=sys.stderr)
    sys.exit(2)
pending, last_text, count = tx.state(transcript)
print("file:", os.path.basename(transcript), "rows:", count)
if pending:
    print("PENDING TOOL:", pending.get("name"), json.dumps(pending.get("input"))[:n])
print("LAST TEXT:", last_text[-n:])
