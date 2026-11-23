"""Tests for push-guidelines.sh, which writes into project repos outside this one.
Runs a throwaway copy of the script against throwaway dotfiles and projects dirs.
Run: python3 -m unittest discover -s tests"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def rsync_is_openrsync() -> bool:
    """macOS ships openrsync, whose --existing still creates empty directories."""
    out = subprocess.run(["rsync", "--version"], capture_output=True, text=True)
    return "openrsync" in (out.stdout + out.stderr)


def snapshot(root: Path) -> dict:
    """Every path under root mapped to its bytes (None for a directory)."""
    return {
        str(p.relative_to(root)): (p.read_bytes() if p.is_file() else None)
        for p in sorted(root.rglob("*"))
    }


class PushGuidelinesCase(unittest.TestCase):
    def setUp(self):
        # realpath: /tmp is a symlink on macOS and the script resolves paths.
        tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, tmp)
        self.dotfiles = tmp / "dotfiles"
        self.projects = tmp / "projects"
        self.home = tmp / "home"
        self.home.mkdir()
        self.projects.mkdir()
        self.dotfiles.mkdir()
        shutil.copy2(REPO / "push-guidelines.sh", self.dotfiles / "push-guidelines.sh")

        # Source of truth: new content for every file.
        self.write(self.dotfiles / ".claude/rules/php.md", "php NEW\n")
        self.write(self.dotfiles / ".claude/rules/only-in-source.md", "source only\n")
        self.write(self.dotfiles / ".claude/guidelines/style.md", "style NEW\n")
        self.write(self.dotfiles / ".claude/skills/shared/SKILL.md", "shared NEW\n")
        self.write(self.dotfiles / ".claude/skills/new-skill/SKILL.md", "brand new\n")

        # A project that carries stale committed copies plus its own files.
        self.proj = self.projects / "app"
        self.write(self.proj / ".claude/rules/php.md", "php OLD\n")
        self.write(self.proj / ".claude/rules/project-own.md", "mine\n")
        self.write(self.proj / ".claude/guidelines/style.md", "style OLD\n")
        self.write(self.proj / ".claude/skills/shared/SKILL.md", "shared OLD\n")
        self.write(self.proj / ".claude/skills/project-skill/SKILL.md", "own skill\n")

    @staticmethod
    def write(path: Path, text: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def run_script(self, *args: str) -> subprocess.CompletedProcess:
        env = {**os.environ, "HOME": str(self.home), "PROJECTS_DIR": str(self.projects)}
        return subprocess.run(
            ["bash", str(self.dotfiles / "push-guidelines.sh"), *args],
            capture_output=True, text=True, env=env,
        )

    def read(self, relative: str) -> str:
        return (self.proj / relative).read_text()

    def assert_refreshed(self):
        self.assertEqual(self.read(".claude/rules/php.md"), "php NEW\n")
        self.assertEqual(self.read(".claude/guidelines/style.md"), "style NEW\n")
        self.assertEqual(self.read(".claude/skills/shared/SKILL.md"), "shared NEW\n")

    # -- dry run is the default ------------------------------------------------

    def test_default_run_is_a_dry_run_that_writes_nothing(self):
        before = snapshot(self.projects)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(snapshot(self.projects), before)
        self.assertIn("Dry run", result.stdout)

    def test_dry_run_reports_the_stale_files_and_not_the_missing_ones(self):
        result = self.run_script()
        self.assertIn(">f", result.stdout)
        for stale in ("php.md", "style.md", "SKILL.md"):
            self.assertIn(stale, result.stdout)
        self.assertNotIn("only-in-source.md", result.stdout)
        self.assertNotIn("new-skill/SKILL.md", result.stdout)

    def test_dry_run_of_a_project_already_in_sync_reports_nothing_to_do(self):
        self.run_script("--apply")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Everything already in sync", result.stdout)
        self.assertNotIn(">f", result.stdout)

    # -- --apply ---------------------------------------------------------------

    def test_apply_overwrites_files_the_project_already_has(self):
        result = self.run_script("--apply")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_refreshed()

    def test_apply_never_creates_files(self):
        self.run_script("--apply")
        self.assertFalse((self.proj / ".claude/rules/only-in-source.md").exists())
        self.assertFalse((self.proj / ".claude/skills/new-skill/SKILL.md").exists())

    @unittest.skipIf(
        rsync_is_openrsync(),
        "openrsync (stock macOS) creates empty directories under --existing; "
        "see the audit-F report. GNU rsync does not.",
    )
    def test_apply_never_creates_directories(self):
        self.run_script("--apply")
        self.assertFalse((self.proj / ".claude/skills/new-skill").exists())

    def test_apply_never_deletes_project_only_files(self):
        self.run_script("--apply")
        self.assertEqual(self.read(".claude/rules/project-own.md"), "mine\n")
        self.assertEqual(self.read(".claude/skills/project-skill/SKILL.md"), "own skill\n")

    def test_apply_does_not_opt_a_directory_in(self):
        # Only rules/ exists in this project: guidelines/ and skills/ must not appear.
        lean = self.projects / "lean"
        self.write(lean / ".claude/rules/php.md", "php OLD\n")
        self.run_script("--apply")
        self.assertEqual((lean / ".claude/rules/php.md").read_text(), "php NEW\n")
        self.assertFalse((lean / ".claude/guidelines").exists())
        self.assertFalse((lean / ".claude/skills").exists())

    def test_apply_leaves_projects_without_opt_in_directories_untouched(self):
        bare = self.projects / "bare"
        self.write(bare / "README.md", "hello\n")
        self.write(bare / ".claude/settings.json", "{}\n")
        before = snapshot(bare)
        self.run_script("--apply")
        self.assertEqual(snapshot(bare), before)

    def test_the_source_checkout_is_never_a_target(self):
        # With PROJECTS_DIR one level above the dotfiles checkout, the checkout
        # itself matches the */.claude/<sub> glob; the script must skip it.
        env = {**os.environ, "HOME": str(self.home), "PROJECTS_DIR": str(self.dotfiles.parent)}
        # Remove the sibling project so the checkout is the only candidate.
        shutil.rmtree(self.projects)
        before = snapshot(self.dotfiles)
        result = subprocess.run(
            ["bash", str(self.dotfiles / "push-guidelines.sh"), "--apply"],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("nothing to do", result.stdout)
        self.assertEqual(snapshot(self.dotfiles), before)

    # -- git is never touched --------------------------------------------------

    def git(self, *args: str) -> str:
        env = {
            **os.environ, "HOME": str(self.home),
            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
        }
        result = subprocess.run(
            ["git", "-c", "commit.gpgsign=false", *args],
            cwd=self.proj, capture_output=True, text=True, env=env,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def test_apply_leaves_git_history_and_index_alone(self):
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "initial")
        head = self.git("rev-parse", "HEAD")
        branches = self.git("branch", "--list")

        self.run_script("--apply")

        self.assertEqual(self.git("rev-parse", "HEAD"), head)
        self.assertEqual(self.git("branch", "--list"), branches)
        self.assertEqual(self.git("stash", "list"), "")
        status = sorted(self.git("status", "--porcelain").splitlines())
        # Refreshed files are modified in the work tree, never staged or committed.
        self.assertEqual(
            status,
            [
                " M .claude/guidelines/style.md",
                " M .claude/rules/php.md",
                " M .claude/skills/shared/SKILL.md",
            ],
        )

    # -- single project argument -----------------------------------------------

    def test_single_project_argument_defaults_to_a_dry_run(self):
        before = snapshot(self.projects)
        result = self.run_script(str(self.proj))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(snapshot(self.projects), before)
        self.assertIn("Dry run", result.stdout)

    def test_single_project_argument_with_apply_pushes_only_there(self):
        other = self.projects / "other"
        self.write(other / ".claude/rules/php.md", "php OLD\n")
        result = self.run_script(str(self.proj), "--apply")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_refreshed()
        self.assertEqual((other / ".claude/rules/php.md").read_text(), "php OLD\n")

    def test_single_project_without_opt_in_directories_warns_and_writes_nothing(self):
        bare = self.projects / "bare"
        bare.mkdir()
        result = self.run_script(str(bare), "--apply")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("nothing to push", result.stdout)
        self.assertEqual(snapshot(bare), {})

    # -- arguments -------------------------------------------------------------

    def test_unknown_argument_fails_without_writing(self):
        before = snapshot(self.projects)
        result = self.run_script("--wipe")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Unknown argument", result.stderr)
        self.assertEqual(snapshot(self.projects), before)


if __name__ == "__main__":
    unittest.main()
