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
        sibling = self.root / "work" / "my-repo-sibling"  # exists, not this repo's git dir
        sibling.mkdir()
        self.write(base + "-sibling", [dict(user("hi"), cwd=str(sibling)),
                                       tool_use("mcp__claude_ai_Slack__send")])
        gone = str(self.project) + "-wt-1"  # deleted worktree: its cwd no longer exists
        self.write(base + "-wt-1", [dict(user("hi"), cwd=gone), tool_use("Skill", skill="remind")])
        sub = self.cfg / "projects" / base / "s" / "subagents"
        sub.mkdir(parents=True)
        (sub / "a.jsonl").write_text(json.dumps(tool_use("mcp__engram__mem_search")) + "\n")

    def write(self, dirname, records):
        d = self.cfg / "projects" / dirname
        d.mkdir(parents=True)
        (d / "s.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\nnot json\n")

    def test_scan_counts_repo_and_worktrees_but_not_siblings(self):
        r = rc.scan(self.project, self.cfg, skip_session="")
        self.assertEqual(r["sessions"], 3)  # subagent transcripts count calls, not sessions
        self.assertEqual(r["mcp_servers"], {"engram": 2, "claude_ai_Linear": 1})
        self.assertEqual(r["skills_by_model"], {"remind": 2})
        self.assertEqual(r["skills_used"], {"remind": 2, "code-review": 1})
        tags = r["session_dirs"]
        self.assertEqual(tags[rc.encode(str(self.project)) + "-wt-1"],
                         "deleted worktree (matched by name)")
        self.assertNotIn(rc.encode(str(self.project)) + "-sibling", tags)
        self.assertEqual(r["commands_by_user"], {"code-review": 1})
        self.assertEqual((r["first"], r["last"]), ("2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"))

    def test_scan_skips_the_running_session(self):
        base = rc.encode(str(self.project))
        self.write_file(base, "me.jsonl", [user("<command-name>/configure-repo</command-name>")])
        self.write_file(base, "me/subagents/a.jsonl", [tool_use("mcp__claude_ai_Gmail__send")])
        r = rc.scan(self.project, self.cfg, skip_session="me")
        self.assertNotIn("configure-repo", r["skills_used"])
        self.assertNotIn("claude_ai_Gmail", r["mcp_servers"])
        self.assertEqual(r["sessions"], 3)

    def test_unused_connectors_match_tool_prefixes(self):
        listed = rc.parse_mcp_list(
            "Checking MCP server health…\n\nclaude.ai Linear: https://x - ✓ Connected\n"
            "claude.ai monday.com: https://y - ! Needs authentication\n"
            "claude.ai Google Sheets: https://z - ✓ Connected\nengram: engram mcp - ✓ Connected\n")
        self.assertEqual(listed, ["claude.ai Linear", "claude.ai monday.com", "claude.ai Google Sheets"])
        used = {"claude_ai_Linear": 3, "engram": 9}
        self.assertEqual(rc.unused_connectors(listed, used, keep=["claude.ai Google Sheets"]),
                         ["claude.ai monday.com"])

    def write_file(self, dirname, rel, records):
        f = self.cfg / "projects" / dirname / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("\n".join(json.dumps(r) for r in records) + "\n")

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
