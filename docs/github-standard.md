# GitHub repo config standardization

Personal repos under `guidodinello` had drifted: of 21 active repos, only 4 carried a
branch ruleset, each hand-configured under a different name, and only 4 had
`delete_branch_on_merge` set. `github-standard.py` + `github-standard.json` in the repo
root fix that the same way `push-guidelines.sh` fixes guideline drift — a declarative
source of truth plus an idempotent script, dry-run by default.

```bash
cd ~/claude-dotfiles
./github-standard.py                  # audit every repo in the config, report drift
./github-standard.py --apply          # actually write
./github-standard.py knowledger-bot   # one repo only
```

## Why Python, not bash+jq

Every other sync tool in this repo (`sync.sh`, `push-guidelines.sh`) is bash, because
the thing being synced is *files* and rsync is the right tool for that. This syncs
*structured API state* — ruleset bodies are JSON, GitHub returns fields in its own
order, and a correct diff has to merge partial per-rule overrides and compare
order-insensitively. That's native in Python and fragile in jq, so this one script
breaks the house-bash pattern deliberately.

## The baseline

Applied to every repo at tier `settings` or above:

- `delete_branch_on_merge: true`, `allow_auto_merge: true`
- `allow_squash_merge: true`, `allow_merge_commit: false`, `allow_rebase_merge: false`
  (matches the ruleset's squash-only rule so the repo UI doesn't offer a method the
  ruleset would reject anyway)
- Dependabot vulnerability alerts + automated security fixes (free on public and
  private repos)
- Secret scanning + push protection **on public repos only** — these need GitHub
  Advanced Security on private repos and the API call errors without it, so the
  script checks `private` and skips the PATCH entirely rather than failing.

Repos at tier `ruleset` additionally get a branch ruleset on `main` (rulesets, not
classic branch protection — GitHub's newer, evaluatable mechanism):

| Rule | Setting | Why |
|---|---|---|
| `deletion` | on | can't delete `main` |
| `non_fast_forward` | on | no force-push |
| `copilot_code_review` | `review_on_push: false` | Copilot reviews PRs, not every push |
| `required_signatures` | on | every commit GPG-signed — machine-wide `commit.gpgsign true` makes this free |
| `pull_request` | squash-only, **0 required approvals**, thread resolution required | changes land through a PR, but nothing blocks a solo maintainer from merging their own |
| `code_quality` | `severity: errors` | GitHub's built-in code-quality check gates on errors, not warnings |
| `bypass_actors` | `[]` — none | no one, including the owner, can push straight to `main`; the escape hatch is flipping the ruleset to `evaluate`/`disabled` in the UI, not a bypass actor |

**`required_approving_review_count: 0` is load-bearing, not an oversight.** GitHub's
ruleset UI defaults this to `1`, which on a solo repo makes every PR permanently
unmergeable (no one else exists to approve it). The template hardcodes `0`.

Repos with real CI additionally get `required_status_checks` — see below.

**Snyk is deliberately never a required check.** It's informational-only: on the free
plan, quota exhaustion marks the check failed/canceled, and a required Snyk check
would then block every merge for a reason that has nothing to do with the PR's
content. If a repo's CI includes a Snyk step, leave its context out of the config.

## Tiers

- **`settings`** — repo settings + security only, no ruleset. For scratch repos pushed
  to directly (`dotfiles`, `anki`, `ig`, `metodos-montecarlo`, `skipper`, `deployer`) —
  a `pull_request` rule there would be friction with no payoff.
- **`ruleset`** — adds the baseline ruleset on `main`, no required checks. For repos
  with no CI worth gating on, or where the only workflow is a Claude review bot
  (`claude-dotfiles`) or a cron job (`pencast`) rather than a pass/fail gate.
- **`ruleset` + checks** — the above, plus `required_status_checks` with real,
  hand-curated contexts.

**Required-check contexts are never derived from workflow YAML.** A context is a job's
*display name*, not its file or step name, and picking the wrong ones silently makes
the required-check rule toothless. Read the actual contexts off a recent commit —
`gh api repos/{org}/{repo}/commits/{branch}/check-runs --jq '[.check_runs[].name]'`
— then hand-write them into the config. Treat the config as authoritative afterward;
don't regenerate it from CI on every run.

## Pinned exceptions

Two repos deliberately don't match the baseline. The config documents both inline
(`_comment` fields in `github-standard.json`) so a future edit doesn't "fix" them back
into a bug — read the comment before touching either.

**`fitted`** — `development` → `main` uses a **merge commit, never squash**, per
[ADR-027](../../fitted/docs/process/adr/027-development-branch-as-deploy-gate.md).
`development` and `main` are both long-lived branches; a squash merge creates a new
commit on `main` with no ancestry link back to `development`, so the merge-base never
advances and every later release PR shows a phantom diff of already-deployed code
(this happened — releases #391/#394 are the incident record). Repo-wide
`allow_merge_commit` stays `true` for the same reason (ADR-027 §Repository
configuration). `required_signatures` was a genuine gap — no ADR reason it was
missing, and the commit history was already GPG-verified — so it was added, not
carried as an exception.

**`pullscope`** — a published, public Firefox add-on with a committed `CODEOWNERS`.
The OSS posture needs real review of external contributions, which the 0-approval
baseline doesn't provide: `required_approving_review_count: 1`,
`require_code_owner_review: true`, `dismiss_stale_reviews_on_push: true`, plus admin
`bypass_actors` (`RepositoryRole` 2 and 5, `bypass_mode: always`) so the owner can
still merge their own PRs past a review requirement aimed at everyone else.
`required_review_thread_resolution: false` and the `creation`/`update` rules were
incidental drift from an earlier hand-configuration, not policy — they're reconciled
to the baseline. `copilot_code_review.review_on_push: true` and
`required_linear_history` were left exactly as they were: neither was identified as
drift during the audit that produced this baseline, so they're preserved as
pre-existing choices rather than silently normalized away.

## No upsert — match by name, never blind-create

GitHub allows multiple rulesets with the same name on one repo, and there is no
upsert endpoint. `github-standard.py` lists existing rulesets, matches by name against
the config's branch keys (canonically the branch name itself, e.g. `main`,
`development`), and only then decides `PUT` (exists) vs. `POST` (create). A ruleset
whose name doesn't match any configured branch is reported as **unmanaged** and left
alone — it is never auto-renamed, because renaming changes what the ruleset *is*
without discussion. Renaming a legacy ruleset (e.g. `rl-tournament-notification-bot`'s
original `Copilot review for main branch`, or `pullscope`'s `pr-to-main`) to bring it
under management is a one-time manual step:

```bash
echo '{"name":"main"}' | gh api -X PUT repos/guidodinello/<repo>/rulesets/<id> --input -
```

Do this *before* running `--apply` on that repo — otherwise the script correctly sees
"no ruleset named `main`" and creates a second one, doubling enforcement.

## Failure handling

Each repo is independent: a failure on one (bad auth, a repo that's gone private,
rate-limiting) is reported and skipped, not a hard stop — same pattern as
`push-guidelines.sh`. The script exits non-zero if anything failed, so CI or a human
running it can tell partial success from a clean run. Preflight checks `gh auth
status` and that the active token carries the `repo` scope before writing anything, so
an auth problem surfaces once instead of as 20 misleading per-repo 403s.

## Scope

Applies to active (non-fork, non-archived, pushed within ~18 months) repos under the
`guidodinello` personal account. Deliberately out of scope: `guidodinello-org` (empty),
`mialergia` (work/client repos, different account), forks, archived repos, and ~40
dormant university-era repos from 2022–2023 — those are left untouched, not tiered to
`settings`.

`claude-dotfiles` itself is tier `ruleset` but was applied **last**, after this script
and its config were committed — applying a zero-bypass `pull_request` rule to the repo
you're actively editing mid-project would lock you out of pushing to it, and the only
escape hatch is the manual UI toggle this project exists to replace.

## Adding a new repo

Add an entry under `"repos"` in `github-standard.json` — `{"tier": "settings"}` for a
scratch repo, `{"tier": "ruleset"}` once it's meant to take PRs, plus a `branches`
block with `extra_rules` for `required_status_checks` once it has real CI. Then
`./github-standard.py <repo> --apply`.
