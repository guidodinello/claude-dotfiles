# Stack notes

Lessons that apply to one stack or one kind of file. The helpers stay generic; these go in the per-repo script.

## Env files

- **Copy from the main checkout, do not build from the template.** The main checkout's env file is the one known to work. Fall back to `cp .env.example .env` only when the template is complete for local runs, and then run one-time init steps (an app key, a local secret) only when the file was just created.
- **Fill keys the template gained later.** A worktree created before a merge misses keys added to `.env.example` since; `fill_missing_env_keys` appends them with the template's default. Re-run the bootstrap after merging the base branch.
- **Rewrite only values you own or know to be wrong.** Ports, project names and local URLs are the bootstrap's. A template default known to be wrong (a placeholder host, a stale port) may be rewritten when it matches exactly; a value someone set on purpose (a staging API, a tunnel) is left alone.
- **A single-origin CORS setting cannot serve several worktree frontends.** If the app accepts one literal origin, either derive it per worktree or delete the key in the worktree copy when the API's fallback is safe (for example, token auth without cookies).
- A tool that loads an env file and fails fast without it should keep failing with its own message: never create an empty file to make the copy step "succeed".

## Docker Compose

- Host ports hardcoded in the base compose file need `ports: !override` in a local `docker-compose.override.yml`; a plain override appends instead of replacing. `!override` needs a Compose release that supports merge tags, so check `docker compose version` on the machine.
- Put schedulers and heavy optional services behind `profiles:` in that override, so `up -d` skips them and `--profile <name>` brings them back on purpose.
- Teardown should read `COMPOSE_PROJECT_NAME` from the worktree's env file before recomputing it: the file holds the name compose actually used.
- Testing a teardown: start a real service with `docker compose up -d <service>`. A container made with `docker run --label com.docker.compose.project=...` lacks the rest of compose's labels, so `compose down` does not find it and the test proves nothing.
- `docker compose -p <name>` acts on every container labeled with that project, including ones from another workspace that reused a generic name. Prefixed worktree names avoid this; never `down` a generic main-checkout name from a script.

## Laravel Sail

- Sail's compose file reads `APP_PORT`, `VITE_PORT` and `FORWARD_*_PORT` (DB, Redis, Mailpit, MinIO, ...) from `.env`, so isolation is setting those keys plus `COMPOSE_PROJECT_NAME`; no override file is needed.
- Tear down with `COMPOSE_PROJECT_NAME=<project> vendor/bin/sail down -v --remove-orphans` when `vendor/bin/sail` exists, else plain `docker compose -p <project> down -v --remove-orphans`.
- Artisan commands run on the host (outside Sail) cannot resolve the compose network's DB host; disable watchers that try to log to the DB for that one call.
- Packages with post-migrate hooks that rewrite tracked files (model docblock generators) dirty the worktree on every migrate: empty the hook in the local config and `skip_worktree` that config file.

## Composer and git hooks

- In a worktree `.git` is a file, not a directory. Composer plugins that install git hooks can fail there and make `composer install` exit non-zero even though the packages installed. Judge the install by its artifact (`vendor/autoload.php`), not by the exit code.

## Node and Vite

- Use the repo's pinned package manager through corepack (`corepack pnpm ...`), not a global one, which may refuse the pinned Node. Corepack's download and auto-pin prompts are turned off by `use_repo_node`.
- A Vite config that pins `server.port` with `strictPort` lets one worktree at a time hold that port. Start worktree dev servers with an explicit `--port <base+offset> --strictPort`.
- Vite inlines env at startup: after the bootstrap rewrites `VITE_*` keys, restart a running dev server.

## Tracked files that tooling rewrites

- Tool caches or registries that are committed but rewritten every session cannot be hidden by `info/exclude`, because ignore rules skip tracked files. `skip_worktree <dir> <path>...` hides them per worktree; a pull that changes them upstream then refuses to overwrite, so undo with `git update-index --no-skip-worktree <path>`.
