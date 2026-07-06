## GitHub Accounts (two accounts on this machine)

| Account | Purpose | SSH alias |
|---|---|---|
| `guidodinello` | Personal | `github.com-personal` |
| `gdinlightit` | Work | `github.com` (default) |

The `gh` CLI defaults to the work account. For personal repos, **direnv** handles the switch automatically — a `.envrc` in the project root sets `GH_TOKEN` to the personal account token on entry.

To set this up for a personal repo:

1. `brew install direnv`
2. Add `eval "$(direnv hook zsh)"` to `~/.zshrc`
3. Create `.envrc` in the project root:

   ```sh
   export GH_TOKEN=$(gh auth token -u guidodinello)
   ```

4. Run `direnv allow` inside the project directory
