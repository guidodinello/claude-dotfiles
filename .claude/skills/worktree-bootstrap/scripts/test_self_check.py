"""Runs the worktree-bootstrap self-check so CI enforces it. Run: python3 -m unittest test_self_check (from this directory)."""

import subprocess
import unittest
from pathlib import Path

SELF_CHECK = Path(__file__).resolve().parent / "self-check.sh"


class SelfCheckTest(unittest.TestCase):
    def test_self_check_passes(self):
        result = subprocess.run(["bash", str(SELF_CHECK)], capture_output=True, text=True, timeout=300)
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("self-check passed", result.stdout)
        self.assertNotIn("FAIL ", result.stderr)


if __name__ == "__main__":
    unittest.main()
