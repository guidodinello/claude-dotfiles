## GitHub Accounts (two accounts on this machine)

| Account | Purpose | SSH host in remotes | Key |
|---|---|---|---|
| `guidodinello` | Personal | `github.com` (default) | `~/.ssh/id_ed25519` |
| `gdinlightit` | Work | `github.com-work` | `~/.ssh/lightit` |

`~/.ssh/config` is the source of truth for the aliases; check it if this table looks wrong.

- **Personal repos** use plain remotes: `git@github.com:guidodinello/<repo>.git`.
  `gh repo create ... --source .` already sets that up, so no remote rewrite is needed.
- **Work repos** need the alias in the remote:
  `git@github.com-work:<org>/<repo>.git`. A plain `github.com` remote authenticates as
  the personal account and fails on work repos.
- **`gh` CLI**: logged in as `guidodinello` only, as of 2026-11-17 (`gh auth status`).
  To act as the work account, log it in (`gh auth login`) and pass its token per
  command or per repo: `GH_TOKEN=$(gh auth token -u gdinlightit) gh ...`.
