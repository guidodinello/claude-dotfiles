---
name: qa-check
description: Discover lint/typecheck/test commands from project config files, then delegate to the quality-checker subagent to run them. Stack-agnostic.
---

## Step 1 — Discover commands

Read the following files if they exist in the current working directory (do not fail if missing):

- `package.json` — look at the `scripts` section for keys matching: `lint`, `typecheck`, `type-check`, `check`, `test`, `fixer`, `format`, `validate`
- `composer.json` — look at the `scripts` section for keys matching: `test`, `lint`, `analyse`, `analyze`, `check`, `pint`, `phpstan`
- `phpunit.xml` / `phpunit.xml.dist` — presence means a PHP test runner exists
- `biome.json` / `.eslintrc*` / `eslint.config.*` — presence signals a JS linter
- `pnpm-workspace.yaml` / `turbo.json` — presence means monorepo; prefer workspace-level scripts
- `.pre-commit-config.yaml` — presence means pre-commit hooks are configured; read it to identify which hooks are active (ruff, mypy, black, isort, flake8, pytest, etc.)
- `pyproject.toml` — look for `[tool.pytest.ini_options]`, `[tool.ruff]`, `[tool.mypy]`, `[tool.black]` sections
- `setup.cfg` / `tox.ini` — may define test and lint commands

Use this heuristic to build a command list:

| Category | Prefer (in order) |
|---|---|
| JS lint/format | `pnpm run lint`, `pnpm run fixer --check`, `pnpm run check` |
| JS typecheck | `pnpm run typecheck`, `pnpm run type-check` |
| JS tests | `pnpm run test` |
| PHP tests | `sail test`, `php artisan test`, `./vendor/bin/phpunit` |
| PHP lint | `sail pint --test`, `./vendor/bin/pint --test` |
| PHP static analysis | `sail phpstan analyse`, `./vendor/bin/phpstan analyse` |
| Python pre-commit | `pre-commit run --all-files` (if `.pre-commit-config.yaml` exists) |
| Python lint | `ruff check .` (if ruff hook present or `[tool.ruff]` in pyproject.toml) |
| Python format | `ruff format --check .` or `black --check .` (based on which is configured) |
| Python typecheck | `mypy .` (if mypy hook present or `[tool.mypy]` in pyproject.toml) |
| Python tests | `pytest` (if pytest hook present or `[tool.pytest.ini_options]` in pyproject.toml) |

For Python projects, prefer `pre-commit run --all-files` over running individual tools — it respects the project's own hook configuration. Only fall back to individual tool commands if pre-commit is not configured.

Only include a command if there is evidence for it (script key exists, config file present, or tool binary likely available). Do not invent commands.

## Step 2 — Delegate

Pass the discovered command list to the `quality-checker` subagent as its input prompt, formatted as:

```
Run the following quality pipeline commands and summarize results:

**Frontend**
- <command>
- <command>

**Backend**
- <command>
- <command>
```

Omit any section that has no commands.

## Step 3 — Report

Present the subagent's output as-is, then ask if any of the failures should be fixed now.