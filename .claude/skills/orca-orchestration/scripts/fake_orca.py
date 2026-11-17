"""Test helper for test_wlaunch.py and test_wsend.py: a fake `orca` binary.

Not a skill script. FakeOrca() writes an executable that logs its argv and answers like
orca 1.4.261 (JSON with ok/result), and points $ORCA_BIN at it for the `with` block.
`previews` is [before, after]: the `terminal show` preview before and after a bare Enter
has been sent to the terminal. `fail` is a "terminal send"-style command that answers ok:false.
"""
import json
import os
import stat
import sys
import tempfile
from unittest import mock

SCRIPT = """#!{python}
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_LOG"], "a") as fh:
    fh.write(json.dumps(args) + "\\n")
with open(os.environ["FAKE_STATE"]) as fh:
    state = json.load(fh)
cmd = " ".join(args[:2])
if state.get("fail") == cmd:
    out = {{"ok": False, "error": "boom"}}
elif cmd == "terminal show":
    preview = state["previews"][1 if state["entered"] else 0]
    out = {{"ok": True, "result": {{"terminal": {{"handle": "term_x", "preview": preview}}}}}}
elif cmd == "terminal create":
    out = {{"ok": True, "result": {{"terminal": {{"handle": "term_x"}}}}}}
elif cmd == "worktree create":
    out = {{"ok": True, "result": {{"worktree": {{"path": "/wt/x"}}}}}}
else:
    out = {{"ok": True, "result": {{}}}}
if cmd == "terminal send" and "--enter" in args and args[args.index("--text") + 1] == "":
    state["entered"] = True
    with open(os.environ["FAKE_STATE"], "w") as fh:
        json.dump(state, fh)
print(json.dumps(out))
sys.exit(0 if out["ok"] else 1)
"""


class FakeOrca:
    def __init__(self, previews=("plan mode on", "plan mode on"), fail=None):
        self._dir = tempfile.TemporaryDirectory()
        root = self._dir.name
        self.log = os.path.join(root, "log.jsonl")
        self.state = os.path.join(root, "state.json")
        self.binary = os.path.join(root, "orca")
        with open(self.state, "w", encoding="utf-8") as fh:
            json.dump({"previews": list(previews), "entered": False, "fail": fail}, fh)
        with open(self.binary, "w", encoding="utf-8") as fh:
            fh.write(SCRIPT.format(python=sys.executable))
        os.chmod(self.binary, os.stat(self.binary).st_mode | stat.S_IXUSR)
        self._patch = mock.patch.dict(
            os.environ, {"ORCA_BIN": self.binary, "FAKE_LOG": self.log, "FAKE_STATE": self.state}
        )

    def __enter__(self):
        self._patch.start()
        return self

    def __exit__(self, *exc):
        self._patch.stop()
        self._dir.cleanup()

    def calls(self):
        """Every logged call as an argv list, without the trailing --json."""
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8") as fh:
            return [json.loads(line)[:-1] for line in fh if line.strip()]
