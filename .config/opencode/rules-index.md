# Agent Guidelines Index (opencode)

This file is the entry point for the path-scoped agent guidelines that Claude
Code loads automatically from `.claude/rules/` via `paths:` frontmatter.
opencode does not read those files on its own — this index is how they reach
it.

## Loading rules

CRITICAL: Do NOT preemptively load every rule below. Read a rule file only
when the task at hand touches a matching path. Loaded rule files are
mandatory instructions for that work — they override defaults. When loading
one of these files, follow any file references it contains recursively.

## Rules

| Rule | Path | Applies to | Load when |
| ---- | ---- | ---------- | --------- |
| CI | `~/.claude/rules/ci.md` | `.github/workflows/**`, `**/.github/workflows/**` | Authoring or reviewing GitHub Actions workflows: permissions, path filtering, summary gates, self-hosted runner gotchas |
| Database | `~/.claude/rules/database.md` | `**/alembic/**`, `**/migrations/**`, `**/*.sql` | Writing schema, constraints, indexes, or migrations; reviewing SQL |
| Docker | `~/.claude/rules/docker.md` | `**/Dockerfile*`, `**/*.dockerfile`, `**/docker-compose*.yml`, `**/docker-compose*.yaml`, `**/.dockerignore` | Writing or reviewing Dockerfiles, Compose files, or `.dockerignore` |
| JavaScript | `~/.claude/rules/javascript.md` | `**/*.js`, `**/*.mjs`, `**/*.cjs`, `**/*.jsx`, `**/*.ts`, `**/*.tsx`, `**/package.json`, `**/tsconfig*.json` | Writing or reviewing JS/TS code, `package.json`, or `tsconfig.json` |
| PHP | `~/.claude/rules/php.md` | `**/*.php`, `**/composer.json` | Writing or reviewing PHP/Laravel code, tests, or Composer config |
| Python | `~/.claude/rules/python.md` | `**/*.py`, `**/pyproject.toml` | Writing or reviewing Python code or `pyproject.toml` |
| Shell | `~/.claude/rules/shell.md` | `**/*.sh`, `**/*.bash` | Writing or reviewing shell scripts |

The `~/.claude/rules/` paths above are symlinks deployed by `sync.sh` and
resolve on any machine with the dotfiles installed.