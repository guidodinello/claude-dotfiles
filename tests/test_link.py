"""Tests for the linker (lib/link.sh) as driven by sync.sh, select.sh, add_file.sh and
promote.sh: repair, prune, verify, backups, config-dir markers, tracked-only linking,
`sync.sh --check`. Throwaway copy of the scripts and a throwaway HOME, run with
/bin/bash (3.2 on macOS). Run: python3 -m unittest discover -s tests"""

import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

try:
    from test_sync import ScriptCase  # discovery: tests/ is on sys.path
except ImportError:
    from tests.test_sync import ScriptCase

REPO = Path(__file__).resolve().parent.parent


def snapshot(root: Path) -> dict:
    """Everything under root: link targets or file bytes, plus mtimes."""
    out = {}
    for p in sorted(root.rglob("*")):
        st = p.lstat()
        if p.is_symlink():
            content = os.readlink(p)
        elif p.is_file():
            content = p.read_bytes()
        else:
            content = None
        out[str(p)] = (content, st.st_mtime_ns)
    return out


class LinkCase(ScriptCase):
    def run_script(self, name, *args, check=True, path_prefix=None, repo=None):
        env = {**os.environ, "HOME": str(self.home)}
        if path_prefix is not None:
            env["PATH"] = f"{path_prefix}{os.pathsep}{env['PATH']}"
        result = subprocess.run(
            ["/bin/bash", str((repo or self.repo) / name), *args],
            capture_output=True,
            text=True,
            env=env,
        )
        if check:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def sync(self, *args, check=True, **kw):
        return self.run_script("sync.sh", *args, check=check, **kw)

    @staticmethod
    def out(result) -> str:
        return result.stdout + result.stderr

    def git_track(self):
        """Make the fake repo a git checkout with everything staged (no commit, so no
        identity or signing is needed)."""
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(["git", "add", "-A"], cwd=self.repo, check=True)

    def copy_checkout(self, name="repo2") -> Path:
        other = self.repo.parent / name
        shutil.copytree(self.repo, other, symlinks=True)
        return other

    def dangling_links(self, root: Path) -> list[Path]:
        return [p for p in root.rglob("*") if p.is_symlink() and not p.exists()]


class RepairTest(LinkCase):
    def test_relocated_checkout_is_repaired_and_gone_files_pruned(self):
        self.write(self.src / "agents" / "gone.md", "x")
        self.sync()
        (self.src / "agents" / "gone.md").unlink()
        moved = self.repo.parent / "moved"
        shutil.move(self.repo, moved)
        self.repo = moved
        self.src = moved / ".claude"

        result = self.sync()

        self.assertEqual(self.dangling_links(self.cfg), [])
        for rel in ("agents/a.md", "hooks/h.sh", "skills/s/SKILL.md"):
            self.assertEqual(os.readlink(self.cfg / rel), str(self.src / rel))
        self.assertFalse((self.cfg / "agents" / "gone.md").is_symlink())
        self.assertIn("Repointing", self.out(result))

    def test_link_to_another_existing_checkout_is_refused_without_relink(self):
        self.sync()
        other = self.copy_checkout()
        before = os.readlink(self.cfg / "agents" / "a.md")

        result = self.sync(check=False, repo=other)

        self.assertNotEqual(result.returncode, 0)
        output = self.out(result)
        self.assertIn(str(self.repo), output)
        self.assertIn(str(other), output)
        self.assertIn("--relink", output)
        self.assertNotIn("Done!", output)
        self.assertEqual(os.readlink(self.cfg / "agents" / "a.md"), before)
        self.assertEqual(output.count("re-run with --relink"), 1, "named once per old root, not per file")

    def test_relink_moves_links_to_another_existing_checkout(self):
        self.sync()
        other = self.copy_checkout()

        self.sync("--relink", repo=other)

        for rel in ("agents/a.md", "hooks/h.sh", "skills/s/SKILL.md"):
            self.assertEqual(os.readlink(self.cfg / rel), str(other / ".claude" / rel))

    def test_users_relative_directory_link_is_left_alone(self):
        shared = self.home / ".agents" / "skills" / "x"
        self.write(shared / "other.md", "theirs")
        link = self.cfg / "skills" / "x"
        link.parent.mkdir(parents=True)
        link.symlink_to("../../.agents/skills/x")
        self.write(self.src / "skills" / "x" / "SKILL.md", "ours")  # same name, tracked

        self.sync()

        self.assertEqual(os.readlink(link), "../../.agents/skills/x")
        self.assertEqual(sorted(p.name for p in shared.iterdir()), ["other.md"], "nothing written through it")

    def test_foreign_absolute_link_at_an_expected_path_is_kept_with_a_warning(self):
        mine = self.write(self.home / "mine.md", "mine")
        link = self.cfg / "agents" / "a.md"
        link.parent.mkdir(parents=True)
        link.symlink_to(mine)

        result = self.sync()

        self.assertEqual(os.readlink(link), str(mine))
        self.assertIn("points outside this repo", self.out(result))

    def test_foreign_dangling_link_does_not_fail_the_run(self):
        foreign = self.cfg / "debug" / "latest"
        foreign.parent.mkdir(parents=True)
        foreign.symlink_to(self.home / "not-there.txt")

        result = self.sync()

        self.assertTrue(foreign.is_symlink())
        self.assertIn("not a link of ours", self.out(result))

    def test_second_run_changes_nothing(self):
        self.sync()
        first = snapshot(self.cfg)
        self.sync()
        self.assertEqual(snapshot(self.cfg), first)


class BackupTest(LinkCase):
    def test_second_name_clash_keeps_both_backups(self):
        bin_dir = self.home / "bin"
        fake_date = self.write(bin_dir / "date", "#!/bin/sh\necho 20260101-000000\n")
        fake_date.chmod(0o755)
        target = self.cfg / "agents" / "a.md"
        self.write(target, "one")
        self.sync(path_prefix=bin_dir)
        target.unlink()
        self.write(target, "two")

        self.sync(path_prefix=bin_dir)

        backups = sorted(p.name for p in target.parent.glob("a.md.*.bak"))
        self.assertEqual(backups, ["a.md.20260101-000000.2.bak", "a.md.20260101-000000.bak"])
        self.assertEqual((target.parent / backups[1]).read_text(), "one")
        self.assertEqual((target.parent / backups[0]).read_text(), "two")

    def test_backups_are_not_linked_back(self):
        self.write(self.cfg / "agents" / "a.md", "mine")
        self.sync()
        self.sync()
        self.assertEqual(len(list((self.cfg / "agents").glob("a.md.*.bak"))), 1)


class ConfigDirTest(LinkCase):
    def test_unmarked_and_copied_dirs_are_not_targets(self):
        backup = self.home / ".claude-backup-2025"
        self.write(backup / "settings.json", '{"keep": "me"}')
        self.write(backup / ".dotfiles-config-dir", str(self.cfg))  # copied from another dir
        mem = self.home / ".claude-mem"
        self.write(mem / "notes.txt", "notes")

        self.sync()

        self.assertEqual((backup / "settings.json").read_text(), '{"keep": "me"}')
        self.assertEqual(sorted(p.name for p in backup.iterdir()), [".dotfiles-config-dir", "settings.json"])
        self.assertEqual(sorted(p.name for p in mem.iterdir()), ["notes.txt"])

    def test_unmarked_dir_holding_our_links_gets_a_warning(self):
        old = self.home / ".claude-old"
        link = old / "agents" / "a.md"
        link.parent.mkdir(parents=True)
        link.symlink_to(self.src / "agents" / "a.md")

        result = self.sync()

        self.assertIn("run ./sync.sh", self.out(result))
        self.assertIn(".claude-old", self.out(result))

    def test_explicit_dir_is_marked_and_synced_by_later_bare_runs(self):
        work = self.home / ".claude-work"
        work.mkdir()
        self.sync(str(work))
        self.assertEqual((work / ".dotfiles-config-dir").read_text().strip(), str(work))

        (work / "agents" / "a.md").unlink()
        self.sync()
        self.assertTrue((work / "agents" / "a.md").is_symlink())


class PruneTest(LinkCase):
    def test_links_whose_name_is_now_skipped_are_pruned_but_repo_files_stay(self):
        self.sync()
        for name in ("settings.local.json", "settings.json.bak"):
            self.write(self.src / name, "{}")
            (self.cfg / name).symlink_to(self.src / name)

        self.sync()

        for name in ("settings.local.json", "settings.json.bak"):
            self.assertFalse((self.cfg / name).is_symlink(), name)
            self.assertTrue((self.src / name).is_file(), f"{name} stays in the repo")
        self.assertTrue((self.cfg / "settings.json").is_file())

    def test_prune_never_removes_a_repo_file(self):
        self.sync()
        before = snapshot(self.src)
        shutil.rmtree(self.cfg / "skills")  # whole dir gone
        self.sync()
        self.assertEqual(snapshot(self.src), before)


class TrackedOnlyTest(LinkCase):
    def test_untracked_files_are_not_linked_in_a_git_checkout(self):
        self.git_track()
        self.write(self.src / ".DS_Store", "junk")
        self.write(self.src / "agents" / "x.swp", "junk")

        self.sync()

        self.assertTrue((self.cfg / "agents" / "a.md").is_symlink())
        self.assertFalse((self.cfg / ".DS_Store").exists())
        self.assertFalse((self.cfg / "agents" / "x.swp").exists())

    def test_a_link_to_an_untracked_file_is_pruned(self):
        self.git_track()
        self.sync()
        stray = self.write(self.src / "agents" / "stray.md", "x")
        (self.cfg / "agents" / "stray.md").symlink_to(stray)

        self.sync()

        self.assertFalse((self.cfg / "agents" / "stray.md").is_symlink())
        self.assertTrue(stray.is_file())

    def test_add_file_links_stages_and_a_later_sync_keeps_the_link(self):
        self.git_track()
        self.sync()
        self.write(self.cfg / "agents" / "new.md", "new")

        result = self.run_script("add_file.sh", str(self.cfg / "agents" / "new.md"))

        self.assertIn("Staged: .claude/agents/new.md", self.out(result))
        staged = subprocess.run(
            ["git", "ls-files", ".claude/agents/new.md"], cwd=self.repo, capture_output=True, text=True
        ).stdout
        self.assertEqual(staged.strip(), ".claude/agents/new.md")
        self.assertTrue((self.cfg / "agents" / "new.md").is_symlink())
        self.sync()
        self.assertEqual((self.cfg / "agents" / "new.md").resolve(), (self.src / "agents" / "new.md").resolve())

    def test_select_offers_tracked_files_only(self):
        self.git_track()
        self.write(self.src / "agents" / "x.swp", "junk")
        bin_dir = self.home / "bin"
        fake_fzf = self.write(bin_dir / "fzf", '#!/bin/sh\ncat > "$HOME/offered.txt"\n')
        fake_fzf.chmod(0o755)
        self.run_script("select.sh", path_prefix=bin_dir, check=False)
        offered = (self.home / "offered.txt").read_text().split()
        self.assertIn("agents/a.md", offered)
        self.assertNotIn("agents/x.swp", offered)


class AddAndPromoteTest(LinkCase):
    def test_add_file_refuses_skipped_symlinked_and_existing(self):
        self.write(self.cfg / "settings.json", "{}")
        refused = self.run_script("add_file.sh", str(self.cfg / "settings.json"), check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertTrue((self.cfg / "settings.json").is_file())
        self.assertFalse((self.src / "settings.json").exists())

        self.sync()  # agents/a.md is now a link into the repo
        refused = self.run_script("add_file.sh", str(self.cfg / "agents" / "a.md"), check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertTrue((self.cfg / "agents" / "a.md").is_symlink())
        self.assertEqual((self.src / "agents" / "a.md").read_text(), "agent")

        (self.cfg / "agents" / "a.md").unlink()
        self.write(self.cfg / "agents" / "a.md", "mine")  # real file, but the repo has one
        refused = self.run_script("add_file.sh", str(self.cfg / "agents" / "a.md"), check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertEqual((self.cfg / "agents" / "a.md").read_text(), "mine")
        self.assertEqual((self.src / "agents" / "a.md").read_text(), "agent")

    def test_promote_refuses_skipped_names(self):
        live = self.write(self.cfg / "settings.json", "{}")
        local = self.write(self.home / "project" / ".claude" / "settings.local.json", "{}")
        for path in (live, local):
            result = self.run_script("promote.sh", str(path), check=False)
            self.assertNotEqual(result.returncode, 0, path)
            self.assertTrue(path.is_file(), f"{path} stays where it was")
        self.assertEqual(sorted(p.name for p in self.src.glob("settings*.json")), ["settings.base.json"])

    def test_promote_refuses_a_symlinked_skill(self):
        real = self.home / ".agents" / "skills" / "sk"
        self.write(real / "SKILL.md", "sk")
        link = self.home / "project" / ".claude" / "skills" / "sk"
        link.parent.mkdir(parents=True)
        link.symlink_to("../../../.agents/skills/sk")

        result = self.run_script("promote.sh", str(link), check=False)

        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(link.is_symlink())
        self.assertTrue((real / "SKILL.md").is_file())
        self.assertFalse((self.src / "skills" / "sk").exists())

    def test_promote_delete_original_is_a_noop_with_a_notice(self):
        skill = self.home / "project" / ".claude" / "skills" / "p"
        self.write(skill / "SKILL.md", "p")

        result = self.run_script("promote.sh", "--delete-original", str(skill))

        self.assertIn("this flag does nothing", self.out(result))
        self.assertIn("Moved out of", self.out(result))
        self.assertNotIn("Safe to remove", self.out(result))
        self.assertFalse(skill.exists())
        self.assertTrue((self.src / "skills" / "p" / "SKILL.md").is_file())
        self.assertTrue((self.cfg / "skills" / "p" / "SKILL.md").is_symlink())


class CheckTest(LinkCase):
    def test_check_on_a_healthy_install_passes(self):
        self.sync()
        result = self.sync("--check")
        self.assertIn("Check passed", self.out(result))

    def assert_check_fails_and_changes_nothing(self, *expected_in_output):
        before_home, before_repo = snapshot(self.home), snapshot(self.repo)
        result = self.sync("--check", check=False)
        self.assertNotEqual(result.returncode, 0)
        for text in expected_in_output:
            self.assertIn(text, self.out(result))
        self.assertEqual(snapshot(self.home), before_home)
        self.assertEqual(snapshot(self.repo), before_repo)

    def test_check_fails_on_a_missing_link(self):
        self.sync()
        (self.cfg / "agents" / "a.md").unlink()
        self.assert_check_fails_and_changes_nothing("agents/a.md: missing")

    def test_check_fails_on_a_dangling_link_of_ours(self):
        self.sync()
        link = self.cfg / "hooks" / "h.sh"
        link.unlink()
        # ours-shaped (ends in /.claude/hooks/h.sh) but the checkout behind it is gone
        link.symlink_to(self.repo.parent / "gone" / ".claude" / "hooks" / "h.sh")
        self.assert_check_fails_and_changes_nothing("hooks/h.sh", "stale")

    def test_check_fails_on_a_link_into_another_existing_checkout(self):
        self.sync()
        other = self.copy_checkout()
        link = self.cfg / "skills" / "s" / "SKILL.md"
        link.unlink()
        link.symlink_to(other / ".claude" / "skills" / "s" / "SKILL.md")
        self.assert_check_fails_and_changes_nothing(str(other), "re-run with --relink")

    def test_check_does_not_fail_on_links_that_are_not_ours(self):
        self.sync()
        (self.cfg / "agents" / "a.md").unlink()
        (self.cfg / "agents" / "a.md").symlink_to(self.write(self.home / "mine.md", "mine"))
        (self.cfg / "debug").mkdir()
        (self.cfg / "debug" / "latest").symlink_to(self.home / "not-there.txt")
        result = self.sync("--check")
        self.assertIn("points outside the repo", self.out(result))

    def test_check_creates_nothing(self):
        result = self.sync("--check", check=False)  # fresh HOME: no ~/.claude at all
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not exist", self.out(result))
        self.assertEqual(list(self.home.iterdir()), [])

        explicit = self.home / ".claude-work"
        explicit.mkdir()
        result = self.sync("--check", str(explicit), check=False)
        self.assertIn("agents/a.md: missing", self.out(result))
        self.assertEqual(list(explicit.iterdir()), [], "no marker, no settings.json, no links")

    def test_check_reports_a_missing_required_tool_instead_of_dying(self):
        bin_dir = self.home / "bin"
        for tool in ("bash", "sh", "git", "python3", "grep", "find", "sort", "head", "dirname", "readlink", "cat", "date", "basename", "mkdir", "rm", "ln", "mv", "rmdir"):
            found = shutil.which(tool)
            if found:
                (bin_dir).mkdir(exist_ok=True)
                (bin_dir / tool).symlink_to(found)
        env = {**os.environ, "HOME": str(self.home), "PATH": str(bin_dir)}
        result = subprocess.run(
            ["/bin/bash", str(self.repo / "sync.sh"), "--check"], capture_output=True, text=True, env=env
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Required tool missing: jq", self.out(result))

    def test_unknown_option_is_rejected(self):
        result = self.sync("--nope", check=False)
        self.assertEqual(result.returncode, 2)


class ExecBitTest(unittest.TestCase):
    def test_every_command_run_directly_from_the_config_dir_is_executable(self):
        """settings.base.json runs `{{CONFIG_DIR}}/hooks/x.sh` with no interpreter, so the
        tracked file needs mode 100755; the hooks are symlinks, so sync.sh cannot chmod them."""
        base = json.loads((REPO / ".claude" / "settings.base.json").read_text())
        commands: list[str] = []

        def walk(node):
            if isinstance(node, dict):
                if isinstance(node.get("command"), str):
                    commands.append(node["command"])
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(base)
        direct = [c.split()[0] for c in commands if c.startswith("{{CONFIG_DIR}}/")]
        self.assertTrue(direct, "expected at least one direct command")
        for command in direct:
            rel = ".claude/" + command[len("{{CONFIG_DIR}}/"):]
            listing = subprocess.run(
                ["git", "ls-files", "-s", "--", rel], cwd=REPO, capture_output=True, text=True, check=True
            ).stdout
            self.assertTrue(listing, f"{rel} is not tracked")
            self.assertEqual(listing.split()[0], "100755", rel)


if __name__ == "__main__":
    unittest.main()
