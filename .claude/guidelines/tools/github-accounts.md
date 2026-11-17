## GitHub Accounts (two accounts, set up differently per machine)

| Account | Purpose |
|---|---|
| `guidodinello` | Personal |
| `gdinlightit` | Work |

**Which SSH host alias maps to which account differs per machine.** On the work laptop,
plain `github.com` is the work account. On the personal laptop, plain `github.com` is
the personal account and the work one is `github.com-work`. This file is synced to
every machine, so it does not say which alias to use. The machine's own
`~/.ssh/config` is the source of truth.

Before setting or fixing a remote:

1. Read the `Host` entries in `~/.ssh/config` to see which aliases exist.
2. Confirm the account behind an alias with `ssh -T git@<alias>`. It replies
   `Hi <account>!`.
3. Use the alias that answers with the repo owner's account:
   `git@<alias>:<owner>/<repo>.git`.

The same applies to the `gh` CLI: which accounts are logged in, and which one is
active, differs per machine. Check with `gh auth status` before any `gh` write. To act
as a logged-in account that is not the active one, pass its token for that command:
`GH_TOKEN=$(gh auth token -u <account>) gh ...`.
