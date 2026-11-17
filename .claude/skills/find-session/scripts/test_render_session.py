"""Unit tests for render_session.py. Run: python3 -m unittest test_render_session (from this directory)."""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_session as rs  # ty: ignore[unresolved-import]


def rec(kind, ts, content, **extra):
    return {"type": kind, "timestamp": ts, "message": {"content": content}, **extra}


def tool_use(ts, tid, name="Bash"):
    return rec("assistant", ts, [{"type": "tool_use", "id": tid, "name": name, "input": {"command": "ls"}}])


def tool_result(ts, tid, body, is_error=False):
    return rec("user", ts, [{"type": "tool_result", "tool_use_id": tid, "content": body, "is_error": is_error}])


SESSION = [
    rec("user", "2026-11-01T09:00:00.000Z", "hello"),
    tool_use("2026-11-01T09:00:01.000Z", "t1"),
    tool_result("2026-11-01T09:00:02.000Z", "t1", "boom", is_error=True),
    tool_use("2026-11-02T10:00:00.000Z", "t2", "Read"),
    tool_result("2026-11-02T10:00:01.000Z", "t2", "fine"),
    tool_result("2026-11-02T10:00:02.000Z", "t2", "bad read", is_error=True),
    rec("assistant", "2026-11-02T11:00:00.000Z", [{"type": "text", "text": "done"}]),
    rec("user", "2026-11-02T12:00:00.000Z", "side", isSidechain=True),
    rec("user", "2026-11-03T00:00:00.000Z", "summary text", isCompactSummary=True),
    {"type": "user", "message": {"content": "no timestamp"}},
]


class RenderTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.path = self.tmp / "abc.jsonl"
        self.write(self.path, SESSION)

    @staticmethod
    def write(path, records):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(r) for r in records) + "\nnot json\n")

    def render(self, path=None, **kw):
        return list(rs.condense(path or self.path, **kw))

    def test_full_render_drops_sidechain_and_tags_compact_summary(self):
        text = "\n".join(self.render())
        self.assertNotIn("side", text.replace("sidechain", ""))
        self.assertIn("COMPACT SUMMARY: summary text", text)
        self.assertIn("CALL Bash", text)

    def test_errors_only_keeps_only_tool_errors_with_tool_name(self):
        lines = self.render(errors_only=True)
        self.assertEqual(len(lines), 2)
        self.assertTrue(all("TOOL_ERR" in line for line in lines))
        self.assertIn("TOOL_ERR (Bash): boom", lines[0])
        self.assertIn("TOOL_ERR (Read): bad read", lines[1])

    def test_since_until_window_and_drops_timestampless(self):
        lines = self.render(since="2026-11-02T00:00:00", until="2026-11-02T23:59:59")
        self.assertTrue(lines)
        self.assertTrue(all(line.startswith("[2026-11-02 ") for line in lines))

    def test_date_only_until_is_inclusive(self):
        until = rs.parse_bound("2026-11-02", end_of_day=True).strftime(rs.TS_FORMAT)
        self.assertEqual(until, "2026-11-02T23:59:59")
        lines = self.render(until=until)
        self.assertIn("ASSISTANT: done", "\n".join(lines))
        self.assertNotIn("COMPACT", "\n".join(lines))

    def test_naive_bound_is_utc_and_offsets_convert(self):
        self.assertEqual(rs.parse_bound("2026-11-02T10:00", end_of_day=False).hour, 10)
        self.assertEqual(rs.parse_bound("2026-11-02T10:00:00+02:00", end_of_day=False).hour, 8)
        self.assertEqual(rs.parse_bound("2026-11-02T10:00:00Z", end_of_day=False).hour, 10)

    def test_subagent_file_keeps_sidechain_records(self):
        sub = self.tmp / "abc" / "subagents" / "agent-1.jsonl"
        self.write(sub, [rec("user", "2026-11-01T09:00:00Z", "task", isSidechain=True)])
        self.assertEqual(len(self.render(sub)), 1)

    def test_max_chars_truncates(self):
        self.write(self.path, [rec("user", "2026-11-01T09:00:00Z", "x" * 500)])
        (line,) = self.render(max_chars=50)
        self.assertIn("…[+450]", line)

    def test_write_parts_splits_and_renames_single_part(self):
        out = self.tmp / "out"
        out.mkdir()
        names, count, _ = rs.write_parts(iter(["a" * 10] * 5), out, "t", 25)
        self.assertEqual(names, ["t.part0.txt", "t.part1.txt", "t.part2.txt"])
        self.assertEqual(count, 5)
        names, _, _ = rs.write_parts(iter(["a"]), out, "one", 1000)
        self.assertEqual(names, ["one.txt"])
        names, count, _ = rs.write_parts(iter([]), out, "none", 1000)
        self.assertEqual((names, count), (["none.txt"], 0))

    def test_projects_dirs_flag_then_env(self):
        flag_dir, env_dir = self.tmp / "flag", self.tmp / "env"
        (flag_dir / "projects").mkdir(parents=True)
        (env_dir / "projects").mkdir(parents=True)
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(env_dir)}):
            self.assertEqual(rs.projects_dirs(str(flag_dir)), [flag_dir / "projects"])
            self.assertEqual(rs.projects_dirs(None), [env_dir / "projects"])

    def test_explicit_config_dir_without_projects_exits_with_clear_message(self):
        with self.assertRaises(SystemExit) as ctx:
            rs.projects_dirs(str(self.tmp / "nope"))
        self.assertIn(f"no projects dir at {self.tmp / 'nope' / 'projects'}", str(ctx.exception))
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.tmp / "nope")}):
            with self.assertRaises(SystemExit):
                rs.projects_dirs(None)

    def test_errors_only_since_names_tool_registered_before_window(self):
        lines = self.render(errors_only=True, since="2026-11-01T09:00:02")
        self.assertEqual(len(lines), 2)
        self.assertIn("TOOL_ERR (Bash): boom", lines[0])

    def test_path_slug_matches_claude_project_dir_names(self):
        self.assertEqual(rs.path_slug("/a/b.c/d"), "-a-b-c-d")
        self.assertEqual(rs.path_slug("~/orca"), rs.path_slug(str(Path.home() / "orca")))

    def test_matched_prefix_takes_longest_and_respects_the_dash_boundary(self):
        prefixes = ["-r", "-r-wt"]
        self.assertEqual(rs.matched_prefix("-r", prefixes), "-r")
        self.assertEqual(rs.matched_prefix("-r-wt-x", prefixes), "-r-wt")
        self.assertEqual(rs.matched_prefix("-r-other", prefixes), "-r")
        self.assertIsNone(rs.matched_prefix("-rx", prefixes))
        self.assertIsNone(rs.matched_prefix("-other", prefixes))

    def test_role_guess(self):
        self.assertEqual(rs.role_guess("-r", ""), "-")
        self.assertEqual(rs.role_guess("-r", "-r"), "main checkout")
        self.assertEqual(rs.role_guess("-r-wt-a", "-r"), "worker")
        self.assertEqual(rs.role_guess("-r-wt-rev-a", "-r"), "reviewer")
        self.assertEqual(rs.role_guess("-o-r-feat", "-o-r", extra=True), "worker")
        self.assertEqual(rs.role_guess("-o-r", "-o-r", extra=True), "main checkout")

    def run_repo_mode(self, *extra_args):
        repo, orca = self.tmp / "repo", self.tmp / "orca" / "repo"
        projects = self.tmp / "cfg" / "projects"
        stamp = "2026-11-02T10:00:00.000Z"
        for dirname, sid in [
            (rs.path_slug(str(repo)), "main0001"),
            (rs.path_slug(str(repo)) + "-wt-a", "wt000001"),
            (rs.path_slug(str(orca)) + "-feat", "orca0001"),
            (rs.path_slug(str(repo)) + "2", "other001"),
        ]:
            self.write(projects / dirname / f"{sid}.jsonl", [rec("user", stamp, "hello")])
        argv = ["render_session.py", "--repo", str(repo), "--out", str(self.tmp / "out"), "--config-dir"]
        argv += [str(self.tmp / "cfg"), *extra_args]
        stdout = io.StringIO()
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(stdout):
            self.assertEqual(rs.main(), 0)
        return stdout.getvalue(), sorted(p.name for p in (self.tmp / "out").iterdir())

    def test_repo_mode_without_also_prefix_misses_orca_and_lookalike_dirs(self):
        manifest, files = self.run_repo_mode()
        self.assertEqual(files, ["main_main0001.txt", "wt-a_wt000001.txt"])
        self.assertNotIn("orca0001", manifest)
        self.assertNotIn("other001", manifest)

    def test_repo_mode_also_prefix_includes_orca_sessions_as_workers(self):
        manifest, files = self.run_repo_mode("--also-prefix", str(self.tmp / "orca" / "repo"))
        self.assertEqual(files, ["feat_orca0001.txt", "main_main0001.txt", "wt-a_wt000001.txt"])
        (row,) = [line for line in manifest.splitlines() if line.startswith("orca0001")]
        self.assertIn("worker", row)

    def test_also_prefix_requires_repo(self):
        argv = ["render_session.py", "--session", "abc", "--also-prefix", "/x", "--out", str(self.tmp / "out")]
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                rs.main()
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
