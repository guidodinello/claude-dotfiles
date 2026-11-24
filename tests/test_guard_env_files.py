"""Tests for .claude/hooks/guard-env-files.sh. Run: python3 -m unittest discover -s tests

Every file here is fake: names only, empty contents, in a throwaway directory."""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GUARD = REPO / ".claude" / "hooks" / "guard-env-files.sh"

BLOCK = 2
ALLOW = 0

# (expected exit code, path relative to a throwaway HOME). Secret files that are not env files.
SECRET_PATHS = [
    (BLOCK, ".dev.vars"),
    (BLOCK, "proj/.dev.vars"),
    (BLOCK, "proj/.dev.vars.staging"),
    # Over-blocked on purpose: the anchored deny rule `.dev.vars.*` cannot take a `!`
    # carve-out, so the hook matches it rather than allow what the rule denies.
    (BLOCK, "proj/.dev.vars.example"),
    (BLOCK, ".aws/credentials"),
    (BLOCK, ".aws/config"),
    (BLOCK, ".ssh/id_rsa"),
    (BLOCK, ".ssh/id_ed25519"),
    (BLOCK, ".ssh/deploy.pem"),
    (BLOCK, ".npmrc"),
    (ALLOW, ".ssh/id_rsa.pub"),
    (ALLOW, ".ssh/id_ed25519.pub"),
    (ALLOW, ".ssh/config"),
    (ALLOW, ".ssh/known_hosts"),
    (ALLOW, "proj/.npmrc"),
    (ALLOW, "proj/dev.vars"),
]

# (expected exit code, basename). Judged wherever the file sits.
NAMES = [
    (BLOCK, ".env"),
    (BLOCK, ".env.local"),
    (BLOCK, ".env.development.local"),
    (BLOCK, ".env.backup"),
    (BLOCK, ".env.prod"),
    (BLOCK, ".envrc"),
    (BLOCK, "prod.env"),
    (BLOCK, ".ENV"),
    (BLOCK, ".Env.Backup"),
    (ALLOW, ".env.example"),
    (ALLOW, ".env.prod.example"),
    (ALLOW, ".env.sample"),
    (ALLOW, ".env.template"),
    (ALLOW, ".ENV.EXAMPLE"),
    (ALLOW, "environment.ts"),
    (ALLOW, "env.py"),
    (ALLOW, "README.md"),
]


def run_guard(stdin: str, cwd: Path | None = None, home: Path | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, **({"HOME": str(home)} if home else {})}
    return subprocess.run(
        ["bash", str(GUARD)], input=stdin, capture_output=True, text=True, timeout=30, cwd=cwd, env=env
    )


def hook_input(tool: str, **tool_input) -> str:
    return json.dumps({"tool_name": tool, "tool_input": tool_input})


class GuardEnvFilesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp)

    def test_file_tools_judge_the_basename(self):
        for tool in ("Read", "Edit", "Write"):
            for want, name in NAMES:
                with self.subTest(tool=tool, name=name):
                    path = str(self.tmp / "nested" / name)  # does not exist: the name decides
                    self.assertEqual(run_guard(hook_input(tool, file_path=path)).returncode, want)

    def test_secret_files_that_are_not_env_files(self):
        home = self.tmp / "home"
        home.mkdir()
        for want, rel in SECRET_PATHS:
            with self.subTest(path=rel):
                path = str(home / rel)
                self.assertEqual(run_guard(hook_input("Read", file_path=path), home=home).returncode, want)

    def test_tilde_secret_paths(self):
        home = self.tmp / "home"
        home.mkdir()
        for path, want in (("~/.aws/credentials", BLOCK), ("~/.npmrc", BLOCK), ("~/.ssh/config", ALLOW)):
            with self.subTest(path=path):
                self.assertEqual(run_guard(hook_input("Read", file_path=path), home=home).returncode, want)

    def test_symlink_to_a_secret_file_is_blocked(self):
        (self.tmp / ".dev.vars").write_text("")
        (self.tmp / "notes").symlink_to(".dev.vars")
        self.assertEqual(run_guard(hook_input("Read", file_path=str(self.tmp / "notes"))).returncode, BLOCK)

    def test_a_symlinked_directory_does_not_hide_a_secret_file(self):
        """/tmp/x/credentials is ~/.aws/credentials when x is a link to the .aws directory."""
        secrets = self.tmp / "home" / ".aws"
        secrets.mkdir(parents=True)
        (secrets / "credentials").write_text("")
        (self.tmp / "link").symlink_to(secrets)
        self.assertEqual(run_guard(hook_input("Read", file_path=str(self.tmp / "link" / "credentials"))).returncode, BLOCK)
        ssh = self.tmp / "home" / ".ssh"
        ssh.mkdir()
        (self.tmp / "sshlink").symlink_to(ssh)
        self.assertEqual(run_guard(hook_input("Read", file_path=str(self.tmp / "sshlink" / "id_rsa"))).returncode, BLOCK)
        self.assertEqual(run_guard(hook_input("Read", file_path=str(self.tmp / "sshlink" / "id_rsa.pub"))).returncode, ALLOW)

    def test_relative_and_absolute_paths(self):
        for path, want in (
            (".env.backup", BLOCK),
            ("./a/b/.env", BLOCK),
            ("/private/tmp/x/.env.staging", BLOCK),
            ("/private/tmp/x/.env.example", ALLOW),
            ("../.env.sample", ALLOW),
        ):
            with self.subTest(path=path):
                self.assertEqual(run_guard(hook_input("Read", file_path=path)).returncode, want)

    def test_notebook_edit_uses_notebook_path(self):
        self.assertEqual(run_guard(hook_input("NotebookEdit", notebook_path="/x/.env")).returncode, BLOCK)
        self.assertEqual(run_guard(hook_input("NotebookEdit", notebook_path="/x/a.ipynb")).returncode, ALLOW)

    def test_symlink_to_an_env_file_is_blocked(self):
        real = self.tmp / ".env.backup"
        real.write_text("")
        link = self.tmp / "notes"
        link.symlink_to(real)
        chained = self.tmp / "more-notes"
        chained.symlink_to(link)
        for path in (link, chained):
            with self.subTest(path=path.name):
                self.assertEqual(run_guard(hook_input("Read", file_path=str(path))).returncode, BLOCK)

    def test_symlink_to_an_example_is_allowed(self):
        real = self.tmp / ".env.example"
        real.write_text("")
        link = self.tmp / "notes"
        link.symlink_to(real.name)  # relative target
        self.assertEqual(run_guard(hook_input("Read", file_path=str(link))).returncode, ALLOW)

    def test_relative_symlink_resolves_against_the_link_directory(self):
        """A bare relative path (no slash) and a relative target both resolve against the
        directory the link sits in, not the path text itself."""
        (self.tmp / ".env.backup").write_text("")
        (self.tmp / "notes").symlink_to(".env.backup")
        sub = self.tmp / "sub"
        sub.mkdir()
        (sub / "notes").symlink_to("../.env.backup")
        for path, cwd in (("notes", self.tmp), ("sub/notes", self.tmp), ("notes", sub)):
            with self.subTest(path=path, cwd=cwd.name):
                self.assertEqual(run_guard(hook_input("Read", file_path=path), cwd=cwd).returncode, BLOCK)

    def test_tilde_path_is_followed_through_home(self):
        home = self.tmp / "home"
        home.mkdir()
        (home / ".env.backup").write_text("")
        (home / "notes").symlink_to(home / ".env.backup")
        self.assertEqual(run_guard(hook_input("Read", file_path="~/notes"), home=home).returncode, BLOCK)

    def test_symlink_loop_and_long_chain_fail_closed(self):
        (self.tmp / "a").symlink_to("b")
        (self.tmp / "b").symlink_to("a")
        self.assertEqual(run_guard(hook_input("Read", file_path=str(self.tmp / "a"))).returncode, BLOCK)

    def test_every_path_field_is_judged(self):
        """A call carrying both fields is blocked when either one is an env file."""
        both = lambda f, n: hook_input("Read", file_path=f, notebook_path=n)  # noqa: E731
        self.assertEqual(run_guard(both("/x/a.txt", "/x/.env")).returncode, BLOCK)
        self.assertEqual(run_guard(both("/x/.env", "/x/a.ipynb")).returncode, BLOCK)
        self.assertEqual(run_guard(both("/x/a.txt", "/x/a.ipynb")).returncode, ALLOW)
        self.assertEqual(run_guard(both("/x/a.txt", 5)).returncode, BLOCK)

    def test_grep_glob_aimed_at_env_files_is_blocked(self):
        for glob in (".env*", "*.env", ".env.backup", "**/.env.local"):
            with self.subTest(glob=glob):
                result = run_guard(hook_input("Grep", pattern="x", path=str(self.tmp), glob=glob))
                self.assertEqual(result.returncode, BLOCK)
        for glob in ("*.ts", "!.env*", ".env.example"):
            with self.subTest(glob=glob):
                result = run_guard(hook_input("Grep", pattern="x", path=str(self.tmp), glob=glob))
                self.assertEqual(result.returncode, ALLOW)
        self.assertEqual(run_guard(hook_input("Grep", pattern="x", glob=5)).returncode, BLOCK)

    def test_grep_blocks_an_env_file_path(self):
        for name in (".env", ".env.backup", "prod.env"):
            with self.subTest(name=name):
                result = run_guard(hook_input("Grep", pattern="x", path=str(self.tmp / name)))
                self.assertEqual(result.returncode, BLOCK)

    def test_grep_allows_examples_directories_and_no_path(self):
        (self.tmp / ".env.d").mkdir()
        self.assertEqual(run_guard(hook_input("Grep", pattern="x", path=str(self.tmp / ".env.example"))).returncode, ALLOW)
        self.assertEqual(run_guard(hook_input("Grep", pattern="x", path=str(self.tmp))).returncode, ALLOW)
        self.assertEqual(run_guard(hook_input("Grep", pattern="x", path=str(self.tmp / ".env.d"))).returncode, ALLOW)
        self.assertEqual(run_guard(hook_input("Grep", pattern="x")).returncode, ALLOW)

    def test_grep_with_a_path_that_is_not_a_string_fails_closed(self):
        for path in (1, ["a"], {"a": 1}, True):
            with self.subTest(path=path):
                self.assertEqual(run_guard(hook_input("Grep", pattern="x", path=path)).returncode, BLOCK)

    def test_unreadable_input_fails_closed(self):
        for stdin in (
            "",
            "not json",
            "{}",
            '{"tool_name": 1}',
            '{"tool_name": "Read"}',
            '{"tool_name": "Read", "tool_input": {}}',
            '{"tool_name": "Read", "tool_input": {"file_path": ""}}',
            '{"tool_name": "Read", "tool_input": {"file_path": 7}}',
            '{"tool_name": "Edit", "tool_input": {"path": "/x/a.txt"}}',
        ):
            with self.subTest(stdin=stdin):
                self.assertEqual(run_guard(stdin).returncode, BLOCK)

    def test_block_message_goes_to_stderr(self):
        result = run_guard(hook_input("Read", file_path="/x/.env.backup"))
        self.assertIn("BLOCKED", result.stderr)
        self.assertEqual(result.stdout, "")


class DenyRuleParityTest(unittest.TestCase):
    """settings.base.json lists the secret-file shapes as `~/` and `//` deny rules and
    the guard's is_secret_path lists them again. Nothing else ties the two, so the
    shapes are checked against each other here."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.home = self.tmp / "home"
        self.home.mkdir()
        base = json.loads((REPO / ".claude" / "settings.base.json").read_text())
        self.rules = {"Read": [], "Edit": []}
        for rule in base["permissions"]["deny"]:
            tool, _, rest = rule.partition("(")
            body = rest.removesuffix(")")
            if tool in self.rules and body.startswith(("~/", "//")):
                self.rules[tool].append(body)

    def anchored(self, body: str) -> str:
        return str(self.home) + "/" + body[2:] if body.startswith("~/") else body[1:]

    def sample(self, body: str) -> str:
        """A real path that the rule matches."""
        path = self.anchored(body).replace("**/", "x/").replace("**", "x").replace("*", "x")
        return path

    def matches(self, body: str, path: str) -> bool:
        """Gitignore-style match: `**/` is any directories, `*` stays in one segment."""
        regex = ""
        pattern = self.anchored(body)
        i = 0
        while i < len(pattern):
            if pattern.startswith("**/", i):
                regex += "(?:.*/)?"
                i += 3
            elif pattern.startswith("**", i):
                regex += ".*"
                i += 2
            elif pattern[i] == "*":
                regex += "[^/]*"
                i += 1
            else:
                regex += re.escape(pattern[i])
                i += 1
        return re.fullmatch(regex, path) is not None

    def test_read_and_edit_rules_list_the_same_shapes(self):
        self.assertTrue(self.rules["Read"])
        self.assertEqual(sorted(self.rules["Read"]), sorted(self.rules["Edit"]))

    def test_the_guard_blocks_a_path_every_deny_rule_matches(self):
        for body in self.rules["Read"]:
            path = self.sample(body)
            with self.subTest(rule=body, path=path):
                self.assertTrue(self.matches(body, path))
                result = run_guard(hook_input("Read", file_path=path), home=self.home)
                self.assertEqual(result.returncode, BLOCK)

    def test_a_deny_rule_matches_every_secret_path_the_guard_blocks(self):
        for want, rel in SECRET_PATHS:
            path = str(self.home / rel)
            covered = any(self.matches(body, path) for body in self.rules["Read"])
            with self.subTest(path=rel):
                self.assertEqual(covered, want == BLOCK)


if __name__ == "__main__":
    unittest.main()
