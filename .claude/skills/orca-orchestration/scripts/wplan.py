#!/usr/bin/env python3
"""Print the latest ExitPlanMode plan from a worker's transcript.

usage: wplan.py <worktree-path | transcript-dir-name>
Exit 2 when there is no transcript or no plan yet.
"""
import importlib.util
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
project = tx.resolve(sys.argv[1])
transcript = tx.latest(project)
if not transcript:
    print(f"no transcript yet in {project}", file=sys.stderr)
    sys.exit(2)
plan = tx.latest_plan(transcript)
if plan is None:
    print("no plan yet", file=sys.stderr)
    sys.exit(2)
print(plan)
