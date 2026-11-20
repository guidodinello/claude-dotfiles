"""Unit tests for check_index.py. Run: python3 -I test_check_index.py."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_index as ci  # ty: ignore[unresolved-import]


class CheckTreeTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "my-dev-things"
        self.root.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write(self, rel: str, text: str = "") -> None:
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def findings(self) -> list[str]:
        return [f.replace(str(self.root), "ROOT") for f in ci.check_tree(self.root)]

    def test_clean_tree_has_no_findings(self) -> None:
        self.write("README.md", "- [a/](./a/README.md)\n- `notes.md`\n")
        self.write("notes.md")
        self.write("a/README.md", "`doc.md`")
        self.write("a/doc.md")
        self.assertEqual(self.findings(), [])

    def test_root_without_readme(self) -> None:
        self.assertEqual(self.findings(), ["ROOT: no README.md"])

    def test_folder_with_docs_needs_readme_and_parent_mention(self) -> None:
        self.write("README.md", "index")
        self.write("inv/report.md")
        self.assertEqual(
            self.findings(),
            ["ROOT/inv: no README.md", "ROOT/README.md: does not name subfolder inv/"],
        )

    def test_data_or_code_only_folder_needs_nothing(self) -> None:
        self.write("README.md", "index")
        self.write("shots/a.png")
        self.write("harness/run.py")
        self.write("pages/v1.html")
        self.assertEqual(self.findings(), [])

    def test_existing_readme_must_name_scripts_and_html(self) -> None:
        self.write("README.md", "`kept.sh`")
        self.write("kept.sh")
        self.write("new.mjs")
        self.write("page.html")
        self.write("data.json")
        self.assertEqual(
            self.findings(),
            ["ROOT/README.md: does not name new.mjs", "ROOT/README.md: does not name page.html"],
        )

    def test_backticked_glob_covers_files(self) -> None:
        self.write("README.md", "Dailies: `*-daily.md`")
        self.write("2026-10-21-daily.md")
        self.write("2026-10-22-daily.md")
        self.assertEqual(self.findings(), [])

    def test_bare_wildcards_do_not_count_as_listing(self) -> None:
        self.write("README.md", "Sessions are `aw-*`, select `*`, open `x?token=1`.")
        self.write("tool.mjs")
        self.assertEqual(self.findings(), ["ROOT/README.md: does not name tool.mjs"])

    def test_broken_link_reported_and_urls_ignored(self) -> None:
        self.write("README.md", "[x](./gone.md) [y](https://example.com/a) [z](#top) [w](mailto:a@b.c)")
        self.assertEqual(self.findings(), ["ROOT/README.md: broken link ./gone.md"])

    def test_links_in_code_are_examples(self) -> None:
        self.write("README.md", "Write `[x](./gone.md)` like this.\n\n```md\n[y](./also-gone.md)\n```\n")
        self.assertEqual(self.findings(), [])

    def test_percent_encoded_link_resolves(self) -> None:
        self.write("README.md", "[it](./my%20doc.md) `my doc.md`")
        self.write("my doc.md")
        self.assertEqual(self.findings(), [])

    def test_link_with_anchor_resolves_on_the_path(self) -> None:
        self.write("README.md", "[x](./doc.md#section) `doc.md`")
        self.write("doc.md")
        self.assertEqual(self.findings(), [])

    def test_index_ignore_bare_pattern_applies_below(self) -> None:
        self.write("README.md", "- [runs/](./runs/README.md)")
        self.write("runs/README.md", "- [r1/](./r1/README.md)")
        self.write("runs/.index-ignore", "# scaffolding\ntask-*.md\n")
        self.write("runs/r1/README.md", "run")
        self.write("runs/r1/task-back.md")
        self.assertEqual(self.findings(), [])

    def test_index_ignore_skips_whole_folder(self) -> None:
        self.write("README.md", "index")
        self.write(".index-ignore", "vendor/\n")
        self.write("vendor/pkg/notes.md")
        self.assertEqual(self.findings(), [])

    def test_node_modules_always_skipped(self) -> None:
        self.write("README.md", "index")
        self.write("tools/README.md", "")
        self.write("node_modules/x/README.md")
        self.write("node_modules/x/CHANGELOG.md")
        self.assertEqual(self.findings(), ["ROOT/README.md: does not name subfolder tools/"])

    def test_name_is_matched_as_plain_text(self) -> None:
        self.write("README.md", "See logs/ for the output; report.md has the result.")
        self.write("report.md")
        self.write("logs/README.md", "")
        self.assertEqual(self.findings(), [])


class MainTest(unittest.TestCase):
    def test_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(ci.main([str(root / "missing")]), 2)
            self.assertEqual(ci.main([tmp]), 1)
            (root / "README.md").write_text("index")
            self.assertEqual(ci.main([tmp]), 0)


if __name__ == "__main__":
    unittest.main()
