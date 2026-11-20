#!/usr/bin/env python3
"""Check that a my-dev-things/ tree is reachable through its README.md indexes.

usage: check_index.py [ROOT ...]

ROOT defaults to ./my-dev-things. Run with `python3 -I`. Prints one finding per line,
`<path>: <problem>`, and exits 1 when there are findings, 0 when the tree is clean.

A folder needs a README.md when it holds a markdown doc or a subfolder that needs one.
Folders of code, generated HTML or data only (a harness, screenshots, JSON, logs) do not:
the skill's rule 5. Once a folder has a README.md, it is an index and must be complete.
For every folder that has one, the checks are:
  - every subfolder that needs a README is named in it
  - every navigational file (NAV_SUFFIXES) directly inside is named in it, by name or by a
    backticked glob such as `*-daily.md`
  - every relative markdown link in it resolves

A `.index-ignore` file in any folder lists glob patterns, one per line (`#` comments),
matched against paths relative to that folder. A match is skipped by every check, and a
matched folder is skipped with everything below it. A pattern without a slash also
matches a bare name at any depth below, so `task-*.md` covers every run folder.
"""

import fnmatch
import re
import sys
from pathlib import Path

NAV_SUFFIXES = {".md", ".sh", ".py", ".mjs", ".html"}
ALWAYS_SKIPPED = {"node_modules", "__pycache__", ".git", ".venv"}
IGNORE_FILE = ".index-ignore"
LINK = re.compile(r"\]\(([^)\s#]+)(?:#[^)]*)?\)")
BACKTICKED = re.compile(r"`([^`\s]+)`")
SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


class Ignores:
    def __init__(self) -> None:
        self._rules: list[tuple[Path, str]] = []

    def load(self, folder: Path) -> None:
        f = folder / IGNORE_FILE
        if not f.is_file():
            return
        for line in f.read_text(errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                self._rules.append((folder, line.rstrip("/")))

    def match(self, path: Path) -> bool:
        for base, pattern in self._rules:
            try:
                rel = path.relative_to(base).as_posix()
            except ValueError:
                continue
            if fnmatch.fnmatch(rel, pattern):
                return True
            if "/" not in pattern and fnmatch.fnmatch(path.name, pattern):
                return True
        return False


def is_nav(path: Path) -> bool:
    return path.suffix in NAV_SUFFIXES and path.name not in {"README.md", IGNORE_FILE}


def mentioned(name: str, text: str, globs: list[str]) -> bool:
    return name in text or any(fnmatch.fnmatch(name, g) for g in globs)


def check_tree(root: Path) -> list[str]:
    findings: list[str] = []
    ignores = Ignores()

    def walk(folder: Path) -> bool:
        """Check folder; return True when it needs a README (so its parent must name it)."""
        ignores.load(folder)
        entries = sorted(folder.iterdir())
        subdirs = [
            p for p in entries
            if p.is_dir() and not p.is_symlink() and p.name not in ALWAYS_SKIPPED
            and not ignores.match(p)
        ]
        nav_files = [p for p in entries if p.is_file() and is_nav(p) and not ignores.match(p)]
        needing = [d for d in subdirs if walk(d)]
        has_docs = any(f.suffix == ".md" for f in nav_files)
        needs_readme = has_docs or bool(needing) or folder == root
        readme = folder / "README.md"
        if not readme.is_file():
            if needs_readme:
                findings.append(f"{folder}: no README.md")
            return needs_readme

        text = readme.read_text(errors="replace")
        globs = [g for g in BACKTICKED.findall(text) if any(c in g for c in "*?[")]
        for d in needing:
            if not mentioned(d.name, text, globs):
                findings.append(f"{readme}: does not name subfolder {d.name}/")
        for f in nav_files:
            if not mentioned(f.name, text, globs):
                findings.append(f"{readme}: does not name {f.name}")
        for target in LINK.findall(text):
            if SCHEME.match(target):
                continue
            if not (folder / target).exists():
                findings.append(f"{readme}: broken link {target}")
        return True

    walk(root)
    return findings


def main(argv: list[str]) -> int:
    roots = [Path(a) for a in argv] or [Path("my-dev-things")]
    findings: list[str] = []
    for root in roots:
        if not root.is_dir():
            print(f"{root}: not a directory", file=sys.stderr)
            return 2
        findings += check_tree(root)
    for line in findings:
        print(line)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
