"""Tests for .claude/statusline.sh: herdr feed lookup and the per-user git cache.

Every run uses a throwaway HOME and a throwaway git repo as the workspace, with
XDG_* unset, so nothing touches the real ~/.claude, ~/.config or ~/.cache.
"""
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / ".claude" / "statusline.sh"


@unittest.skipUnless(shutil.which("jq") and shutil.which("git"), "needs jq and git")
class StatuslineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="statusline-test-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.repo = self.tmp / "work" / "demo"
        self.repo.mkdir(parents=True)
        git = ["git", "-C", str(self.repo)]
        subprocess.run(git + ["init", "-q", "-b", "feature-x"], check=True)
        # Orphan branch with no commits is enough: `branch --show-current` still reports it.

    def render(self, session_id="sess1", extra_env=None):
        payload = {
            "model": {"display_name": "TestModel"},
            "workspace": {"current_dir": str(self.repo)},
            "session_id": session_id,
        }
        env = {k: v for k, v in os.environ.items() if not k.startswith("XDG_")}
        env["HOME"] = str(self.home)
        env.update(extra_env or {})
        return subprocess.run(
            ["/bin/bash", str(SCRIPT)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )

    def cache_dir(self):
        return self.home / ".cache" / "claude-statusline"

    def test_renders_model_dir_and_branch_without_herdr_plugin(self):
        res = self.render()
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stderr, "")
        for expected in ("TestModel", "demo", "feature-x"):
            self.assertIn(expected, res.stdout)

    def test_herdr_runner_receives_stdin_payload(self):
        bin_dir = self.home / ".config" / "herdr" / "plugins" / "github" / "usagebar-abc" / "bin"
        bin_dir.mkdir(parents=True)
        marker = self.tmp / "marker.json"
        runner = bin_dir / "run-statusline.sh"
        runner.write_text('#!/bin/bash\ncat > "%s"\n' % marker)
        runner.chmod(0o755)

        res = self.render()
        self.assertEqual(res.returncode, 0, res.stderr)
        deadline = time.time() + 2
        while time.time() < deadline and not (marker.exists() and marker.stat().st_size):
            time.sleep(0.05)
        self.assertTrue(marker.exists(), "herdr runner was not invoked")
        self.assertEqual(json.loads(marker.read_text())["session_id"], "sess1")

    def test_git_cache_lives_in_per_user_cache_dir(self):
        res = self.render(session_id="abc123")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue((self.cache_dir() / "git-abc123").is_file())

    def test_session_id_cannot_escape_cache_dir(self):
        res = self.render(session_id="../../evil")
        self.assertEqual(res.returncode, 0, res.stderr)
        files = [p for p in self.cache_dir().iterdir()]
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].parent, self.cache_dir())
        self.assertFalse((self.home / "evil").exists())
        self.assertFalse((self.home / ".cache" / "evil").exists())

    def test_stale_cache_files_are_pruned(self):
        self.cache_dir().mkdir(parents=True)
        old = self.cache_dir() / "git-old"
        old.write_text("main|0|0")
        three_days_ago = time.time() - 3 * 86400
        os.utime(old, (three_days_ago, three_days_ago))
        res = self.render(session_id="fresh")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertFalse(old.exists(), "stale cache file was not pruned")
        self.assertTrue((self.cache_dir() / "git-fresh").exists())


if __name__ == "__main__":
    unittest.main()
