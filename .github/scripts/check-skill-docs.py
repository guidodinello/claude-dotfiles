#!/usr/bin/env python3
"""Fail when the docs and .claude/skills/ disagree about which skills exist.

Two checks, run from the repo root:
  1. Table sync: docs/skills.md has exactly one table row per skill directory,
     and no row for a directory that is gone.
  2. Reference check: every backticked `/name` in the docs resolves to a skill
     directory, unless it is listed in NOT_SKILLS.
"""
import glob
import os
import re
import sys

SKILLS_DIR = '.claude/skills'
TABLE_DOC = 'docs/skills.md'
DOC_GLOBS = ('README.md', 'CLAUDE.md', 'docs/**/*.md')

# Backticked `/name` tokens that are legitimately not skills in this repo.
NOT_SKILLS = {
    'skill-name',  # placeholder used in prose
    'compact',     # Claude Code built-in commands
    'mcp',
    'usage',
}

TABLE_ROW = re.compile(r'^\| `/([a-z][a-z0-9-]*)` \|')
REFERENCE = re.compile(r'`/([a-z][a-z0-9-]*)`')


def main():
    skills = {
        os.path.basename(os.path.dirname(path))
        for path in glob.glob(f'{SKILLS_DIR}/*/SKILL.md')
    }
    if not skills:
        sys.exit(f'No skills found under {SKILLS_DIR} -- has the layout changed?')

    problems = []

    rows = []
    with open(TABLE_DOC, encoding='utf-8') as handle:
        for line in handle:
            match = TABLE_ROW.match(line)
            if match:
                rows.append(match.group(1))
    if not rows:
        sys.exit(f'No skill table rows found in {TABLE_DOC} -- has the format changed?')

    for name in sorted(skills - set(rows)):
        problems.append(f'{TABLE_DOC}: skill `{name}` has no table row')
    for name in sorted(set(rows) - skills):
        problems.append(f'{TABLE_DOC}: row `/{name}` has no skill directory')
    for name in sorted({name for name in rows if rows.count(name) > 1}):
        problems.append(f'{TABLE_DOC}: row `/{name}` appears more than once')

    docs = sorted({path for pattern in DOC_GLOBS for path in glob.glob(pattern, recursive=True)})
    for path in docs:
        with open(path, encoding='utf-8') as handle:
            for number, line in enumerate(handle, start=1):
                for name in REFERENCE.findall(line):
                    if name not in skills and name not in NOT_SKILLS:
                        problems.append(f'{path}:{number}: `/{name}` is not a skill in {SKILLS_DIR}')

    for problem in problems:
        print(problem)
    print(f'\nchecked {len(skills)} skills across {len(docs)} docs, {len(problems)} problem(s)')
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
