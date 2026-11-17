## 1Password CLI (`op`)

- Never print a secret. Pipe `op read 'op://<vault>/<item>/<field>'` straight into the consumer, or pass it as an env var with `op run`. An `op://` reference is not a secret and may be committed.
- App-integration auth is per terminal session: 10 min idle, 12 h hard limit, extends to sub-shells on macOS, but a new window or tab re-prompts ([docs](https://www.1password.dev/cli/app-integration-security)). Repeated fingerprint prompts in one run mean the `op` calls don't share a session; each Bash tool call is a fresh shell (likely cause, not verified).
- One prompt per script: put the references in an env file and wrap the whole run, `op run --env-file=refs.env -- ./script.sh`. Inside, read the env vars; don't call `op` again. `op run` masks those values in the child's stdout. Trade-off: every secret is in the child's env for the whole run.
- If the secret only logs in to something, cache the downstream session token in a gitignored file instead, so later runs skip `op`.
- Unattended (cron, cloud routine): a service account (`OP_SERVICE_ACCOUNT_TOKEN`), no biometrics, scoped to the vaults granted. Keep it to one vault; the token is itself a secret.
