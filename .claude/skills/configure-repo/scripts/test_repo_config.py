"""Tests for repo_config.py. Run: python3 -m unittest test_repo_config."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import repo_config as rc  # ty: ignore[unresolved-import]


def tool_use(name, **inp):
    return {"type": "assistant", "timestamp": "2026-01-02T00:00:00Z",
            "message": {"content": [{"type": "tool_use", "id": "x", "name": name, "input": inp}]}}


def user(text):
    return {"type": "user", "timestamp": "2026-01-01T00:00:00Z", "message": {"content": text}}


class RepoConfigTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.cfg = self.root / "cfg"
        self.project = self.root / "work" / "my-repo"  # not a git repo: no worktree list
        self.project.mkdir(parents=True)
        base = rc.encode(str(self.project))
        self.write(base, [tool_use("mcp__claude_ai_Linear__get_issue"), tool_use("Bash"),
                          tool_use("Skill", skill="remind"),
                          user("<command-name>/code-review</command-name>")])
        self.write(base + "--claude-worktrees-a1", [tool_use("mcp__engram__mem_save")])
        self.write(base + "-sibling", [tool_use("mcp__claude_ai_Slack__send")])

    def write(self, dirname, records):
        d = self.cfg / "projects" / dirname
        d.mkdir(parents=True)
        (d / "s.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\nnot json\n")

    def test_scan_counts_repo_and_worktrees_but_not_siblings(self):
        r = rc.scan(self.project, self.cfg)
        self.assertEqual(r["sessions"], 2)
        self.assertEqual(r["mcp_servers"], {"claude_ai_Linear": 1, "engram": 1})
        self.assertEqual(r["skills_by_model"], {"remind": 1})
        self.assertEqual(r["commands_by_user"], {"code-review": 1})
        self.assertEqual((r["first"], r["last"]), ("2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"))

    def test_disable_mcp_merges_and_backs_up(self):
        cj = self.cfg / ".claude.json"
        key = str(self.project.resolve())
        cj.write_text(json.dumps({"projects": {key: {"disabledMcpServers": ["claude.ai Slack"]}},
                                  "other": 1}))
        rc.main(["disable-mcp", "--project", str(self.project), "--config-dir", str(self.cfg),
                 "claude.ai Slack", "claude.ai Figma"])
        data = json.loads(cj.read_text())
        self.assertEqual(data["projects"][key]["disabledMcpServers"],
                         ["claude.ai Slack", "claude.ai Figma"])
        self.assertEqual(data["other"], 1)
        self.assertEqual(len(list(self.cfg.glob(".claude.json.bak-*"))), 1)


if __name__ == "__main__":
    unittest.main()
