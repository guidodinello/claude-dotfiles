# Orchestration method

Placeholders in `<angle brackets>` come from the project profile (`README.md` in the docs folder) or the run. `$S` below means the scripts dir, invoked as the skill's Helper scripts section says: `python3 -I <home>/.claude/skills/orca-orchestration/scripts/<script>`.

## 0. Kickoff contract

Before any worktree exists, confirm these with the user (fill from the profile, ask only what is missing). Paste them into the run doc:

```text
Orchestrate the implementation of <story id> subtasks with the orca CLI.
- Workers: new Orca worktrees with Claude Code, model opusplan, plan mode.
- Initial prompts go through <worktree>/.task-brief.md; the worker is told to read it.
  The brief asks the worker to open the PR when done.
- Plans: the orchestrator answers their questions; an approved plan switches the worker
  to auto mode ("Yes, and use auto mode").
- Base: <integration branch per repo, or the base branch for single-PR repos>.
  Children merge into the integration branch with merge commits; one final <squash>
  to <base branch> after the user validates.
- Review: <review tool>. Then the worker addresses the comments. Then the orchestrator
  merges into the integration branch.
- The orchestrator may merge: <reviewed children into the integration branch>.
  The user keeps: <final merge to base, infra merges, anything waiting on sign-off>.
```

## 1. Pre-flight

- **Consent gates.** Check any repo-level gate that prompts before commits (a review-mode tool, a commit hook asking for input) in every repo in play. If one is on, workers stall at its prompt: ask the user before launching.
- **CLI flags.** `claude --help | rg permission-mode` confirms `--model opusplan --permission-mode plan` still exist.
- **Orca repo setup.** `orca repo show --repo id:<id> --json` shows the worktree Setup Script (dependency install, env file) is still wired.
- **Git exclude for the brief and answers files**, in every repo in play. Worktrees share the common `.git`, so one entry covers them all:

  ```bash
  common=$(git -C <repo> rev-parse --path-format=absolute --git-common-dir)
  printf '%s\n' .task-brief.md .orchestrator-answers.md >> "$common/info/exclude"
  ```

  Without `--path-format=absolute`, `rev-parse --git-common-dir` can return a relative `.git` that resolves against your cwd and lands in the wrong repo.
- **Permission rules** in the orchestrator's settings (`.claude/settings.local.json` of the session cwd), or the auto-mode classifier blocks plan approvals and watchers ("Create Unsafe Agents"):
  - `Bash(orca terminal send:*)`: approvals and answers.
  - `Bash(python3 -I <home>/.claude/skills/orca-orchestration/scripts/*)`: the watchers, literally the invocation you will use.
  - `Bash(gh pr merge:*)`: only if integration merges should run unattended.
- **Unregistered repo.** `orca repo add --path <repo>` first. Its first Claude session shows a folder-trust prompt: answer Down then Enter (`--text $'\x1b[B'`, then a bare Enter).
- `git fetch` every repo before branching anything.

## 2. Integration branch (only for a repo with 2+ PRs)

- Create it from the fetched remote base, never a local branch, **through the API, not `git push`**:

  ```bash
  gh api repos/<owner>/<repo>/git/refs -f ref=refs/heads/<integration> -f sha=$(git -C <repo> rev-parse origin/<base>)
  ```

  A push from a main checkout runs pre-push hooks against its possibly stale dependencies and can fail even though the ref equals the base.
- Name it per the profile's branch rule (issue automations often parse the ticket id from the branch name).
- Its PR to the base can only open once it has a commit (GitHub refuses a zero-commit PR). Open it as a draft after the first child merges. Its body lists "Merged so far" (update it on every merge) and the **ship order** across repos. A change that alters a wire contract forces both sides to ship in the same window, overriding the usual backend-first order.
- Doctrine (why this shape works):
  - Child → integration: **merge commit**, never squash. The original SHAs survive, so anything stacked on a child shares real ancestry with the integration branch.
  - Integration → base: **squash once**, at the very end, if the profile says so.
  - Every child PR's base is the integration branch, even when its git ancestry is stacked on a sibling: no PR depends on another child's branch surviving.
  - Never delete a branch that is still the base of an open PR: GitHub closes that PR. Retarget first.

## 3. Waves

- Derive waves from the tracker's task dependencies. Parallel lanes off the integration branch are fine. A dependent task branches from the integration branch **after its dependencies merged there**, never from a sibling branch, unless it stacks (below).
- A consumer task (e.g. front end) of an API built in the same wave: start both, have the consumer state its "Assumed contract" in its plan, and reconcile it against the producer's plan before approving either. The drift happens every time.
- **Stacking on a reviewed but unmerged sibling.** Waiting for every merge stalls the waves. The dependent brief gets a Step 0 `git merge --no-ff origin/<sibling>` (merge commit, never rebase); its PR base stays the integration branch. Consequences:
  - Until the sibling merges, the stacked PR's diff includes the sibling's commits. Review it after the sibling merges, or pass the sibling as the review tool's diff base.
  - If the sibling gets more commits before it merges, the stacked branch has **two merge bases** with the integration branch and GitHub keeps showing the sibling's changes after it merges. Have the worker merge the integration branch before review. `git diff <integration> <branch>` (two dots) shows the real delta.
  - A textual `git merge-tree` check is not enough before merging a child built without its latest siblings, especially when children targeting the integration branch get no CI. Have the worker merge the integration branch and run lint, type-check and tests, then merge.

## 4. Design sign-off (optional, UI work)

When the profile enables it, a new screen or sizeable UI change (not copy, spacing or a single control) gets a mockup and the user's sign-off **before** the UI worker's plan is approved.

- Build it with the Artifact tool's Design type: one canvas, desktop (1440×900) and mobile (390×844) artboards per screen and state.
- Match the app: the profile's font and design-token paths; expose a themable brand color as a tweak if the app themes per tenant.
- It can run in parallel with the workers' planning: launch them, build the mockup while they investigate, hold the UI plan's approval.
- The user comments on the canvas. Apply each comment, resolve the thread, and copy every resulting decision into that worker's `.orchestrator-answers.md` in words.
- **Hand the worker the mockup source, not a description.** It cannot open a private artifact, and workers given written descriptions shipped visibly drifted UI.
  - Copy the signed-off artboard files into the docs folder (`runs/<run>/mockup-v<n>/`); the scratchpad dies with the session.
  - Point the brief at that absolute path. Do not copy them into the worktree: formatters and hooks may scan untracked files even when excluded.
  - The brief says the mockup is the source of truth for layout, icons, tags, button variant and position, and copy (verbatim), and to map colors to design tokens, never raw hex.
- Put the artifact link in the PR body for the reviewer.

## 5. Launch one worker

```bash
orca worktree create --repo id:<repoId> --name <worktree-name> --no-parent \
  --base-branch origin/<integration-or-base> --comment "<task id> planning" --json
git -C <worktree> branch -m <branch>          # Orca names it <user>/<name>
python3 -I <run-dir>/make-brief.py <run-dir> <task-key>
orca terminal create --worktree id:<repoId>::<worktree> --title <task-id>-claude \
  --command 'claude --model opusplan --permission-mode plan' --json
orca terminal wait --terminal <h> --for tui-idle --timeout-ms 120000 --json
# confirm the TUI really started: the preview shows "plan mode on"
orca terminal send --terminal <h> --text "<one-line prompt>" --json   # no --enter
orca terminal send --terminal <h> --text "" --enter --json             # separate bare Enter
```

- Always pass `--repo`. From a workspace cwd, Orca would otherwise infer the workspace repo.
- `--agent claude` cannot forward arguments, hence the two-step path.
- `--wait-submit` rejects an empty `--text`: send the text without `--enter`, then a bare Enter.
- Rename the branch **before anything is pushed**, so it never exists remotely under a name without the task id.
- One-line prompt: *"Read .task-brief.md in this worktree root and follow it exactly: investigate, then write your implementation plan with an explicit Open questions section. Do not implement until the orchestrator approves the plan. When implementation is done, open the PR as the brief specifies."*
- Move the task (and the parent story, if it is the first) to the profile's in-progress status yourself. Tracker automations keyed on branch creation only fire at the worker's first push.
- Record the worktree, branch and terminal handle in the run's `ids.json`.

## 6. The brief (`.task-brief.md`)

**Generate it from a script**, never by hand: copy `scripts/make-brief.py` into the run folder and adapt it. Keep task ids in the run's `ids.json`. Sections:

- Role and loop: plan mode, plan with an **Open questions** section, no code before approval, the answers-file protocol, then commit, push, PR, reply with the URL.
- **Read first:** the workspace or project `CLAUDE.md` by absolute path. Worktrees live outside the workspace, so it is not auto-loaded. Plus any product-context files the profile lists.
- The task body and the parent story body, verbatim. A worker may not be able to resolve tracker references from its worktree, so give it everything.
- **Baseline:** "this branch = `<integration>` + these merged siblings". Paths and names in the task are leads to confirm: tasks drafted before sibling work landed carry stale names, so list renames in the notes.
- **Ownership between parallel siblings:** which sibling owns which shared file, and which names a sibling took that must not be reused.
- Step 0 merges for stacked tasks.
- Hard git and PR rules: branch already set, PR base, title format, tracker link format, attribution policy, never `--no-verify`, `git status` before commit, never commit the brief or answers file.
- Per-repo rules from the profile (`brief-rules/<repo>.md`): stack and test commands, pre-push setup (e.g. raised tool timeouts), migrations, which tests are required or exempt, the API contract to paste verbatim into a consumer's brief, the mockup path.

## 7. Supervision loop

- **Do not trust `tui-idle`.** It fires when a worker waits on its own subagents.
- Read state from the transcript: `wstat.py <worktree>` (pending tool, last text); `wwatch2.py <minutes> <worktree>...` in the background (`run_in_background`), one per group of workers.
  - A pending `Bash` gets 15 min before STUCK: almost always a long suite or hook run.
  - A parent waiting on its writer subagent counts the subagent's transcript (`<session>/subagents/*.jsonl`) as activity. Workers delegating implementation to a subagent is expected.
  - A plan or question already pending when the watcher starts is reported only after a grace period (`WWATCH_GRACE_SECS`, default 90s), so a watcher started right after an approval does not report the still-pending plan. A new plan is reported at once.
  - Permission prompts do not show in the transcript: a STUCK on an MCP tool usually is one. Read the screen.
- **Plan ready** (pending `ExitPlanMode`): read it with `wplan.py`.
  - To answer, pick the plan menu's "Tell Claude what to change" option (observed: **3**; read the menu first) with a one-line pointer, or `fb.sh`.
  - Put the answers in `<worktree>/.orchestrator-answers.md`, then send: "Read .orchestrator-answers.md, fold it into the plan and re-present it". Keep shell-quoted texts free of apostrophes.
  - When the plan comes back, check it contains the answers (`wplan.py <worktree> | rg <keyword>`), then approve with "Yes, and use auto mode" (observed: **1**), sent as a bare number.
- **Question** (pending `AskUserQuestion`): send the option number, then a follow-up message with any constraints.
- **Permission prompt** for a tool you allow: read the last screen lines, then send the option that allows it. Never answer with a keyword loop: a plan text that mentions the tool would get the same keystroke, and on the plan menu that number means something else. Tools that prompt on every call need an answer every time.
- **Network drop** (`ENOTFOUND` on the worker screen): check the API host is reachable, then tell the worker to continue where it left off. The same outage makes review models "fail".
- **Long hook or suite killed by a tool timeout** on push: raise the timeout at the tool's global config inside the container or environment, never by editing the project's config or skipping hooks.
- **Sessions you did not launch** in a worktree (a tool's read-only PR reviewers, another agent's tab): take their findings into one review comment, then close them with `orca terminal close --terminal <h> --tab`. The user's own sessions stay open.
- **Pre-existing hook failure:** the worker asks. Allow a minimal, separately committed fix of the broken check, never `--no-verify`. Check whether the base already fixed it; that makes the workaround redundant later and may need a revert.
- **A worker cannot write a protected file** (env files under a deny rule): its auto-mode classifier cannot see an approval given in the orchestrator's chat. The orchestrator writes the file in the worktree and tells the worker in a typed message.

## 8. PR, review, address, merge

1. **Check the PR:** base, title format, tracker link format, attribution policy (workers still append attribution footers; strip them with `gh pr edit --body-file`).
2. Move the task to the profile's PR status.
3. **Review** with the profile's review tool and diff-base argument for stacked PRs.
   - Trust a review only if it has a verdict; an empty run is not "no issues".
   - Check the posted reviews (`gh api repos/<owner>/<repo>/pulls/<n>/reviews`) against the tool's output. If a review is void, say so in a PR comment so nobody reads it as approval.
   - If every model returns zero findings on a large PR, say so; do not silently substitute another review.
4. **Address:** tell the worker to run the comment-addressing pass. Review models often claim something is missing or broken when it is not; the worker verifies and declines with evidence.
5. **Merge** into the integration branch once every thread has a reply: `gh pr merge <n> --merge`. Count the threads yourself; a worker's "declined N, fixed M" summary may not add up. For a child built without its latest siblings, run §3's merge-and-check first.
6. **Tracker statuses:** apply the profile's rules. Automations that move tasks on any merge (even into an integration branch) need a reset, and may fire again minutes later: reset right after the merge, then sweep every task and story once more before reporting.
7. **Stop that worker's per-worktree stack** right after its PR merges (profile command; reversible). Idle stacks eat CPU and memory while other workers run suites. Keep the main checkout's stack for the final pass.
8. **Worker gone** (a session restart kills its process): small follow-ups can be done by the orchestrator in a spare worktree, on a new branch off the integration branch.

## 9. Verification and ship

1. **Run it locally** on the main checkouts, switched to the integration branches, with the profile's install, migrate and dev commands. The first full pre-push from a main checkout can surface env-dependent tests that fresh worktrees never hit.
2. **Screenshots** of the result go into the docs location the profile names.
3. **Keep integration branches current:** merge the base into them with a merge commit (a forced rebase also works; then verify the feature diff is identical).
4. **Project-specific pre-ship steps** from the profile (regenerated code, docblocks, lockfiles), committing only what this feature changed.
5. **Ship:** take the integration PRs out of draft (often the first CI run over the whole feature), rewrite their bodies as a feature summary (it becomes the squash description), merge in the ship order (the user's call unless the profile delegates it), and check every task reached the profile's post-merge status; move by hand any the automation missed.
6. **Close out:** run the profile's close-out steps (decision capture, docs), then switch the main checkouts back to the base branch.

## 10. Cleanup

- Close every terminal you opened (`orca terminal close`), remove each worktree once its PR merged, stop the per-worktree stacks, and delete local branches that merged.
- Leave the run doc with the final state and fold lessons into `gotchas.md`.

## Gotchas (generic, all hit live)

| Symptom | Cause | Fix |
|---|---|---|
| Integration branch push fails in pre-push | Main checkout dependencies stale | Create the ref with `gh api .../git/refs` |
| `--wait-submit` error on Enter | Empty `--text` is not allowed with it | Text without `--enter`, then a bare Enter |
| Watcher fires, worker still busy | `tui-idle` counts waiting on subagents | Transcript-based `wwatch2.py` |
| Watcher reports READY right after an approval | The approved plan's tool result is not written yet | Grace period for a plan already pending at start (`WWATCH_GRACE_SECS`) |
| `wwatch2.py` crashed with `max() iterable argument is empty` | Started before the worker wrote its first transcript | Fixed: it waits, and reports `NOTRANSCRIPT` after the idle limit; `wstat.py` exits 2 |
| Plan approval or watcher denied ("Create Unsafe Agents") | The auto-mode classifier | Permission rules in pre-flight, matching the literal invocation |
| A menu number sent with `--enter` is rejected (`agent_prompt_blocked`, seen on Orca 1.4.207) | Menus take the bare keystroke | Send menu choices as a bare number, no `--enter` |
| Worker received only the tail of a message | Long `orca terminal send` text is truncated | `.orchestrator-answers.md` plus a one-line pointer |
| Text after the prompt marker "looks sent" | It is Claude Code's grey prompt suggestion, not a draft; a bare Enter does nothing | Always type the full message with `--text`, then a separate Enter |
| "No issues found" with no real review | A review model spent its turn on rejected tool calls | Require a verdict marker; read the raw output |
| A review slot "succeeded" but nothing is posted | One finding anchored outside the diff (GitHub 422) | Post unanchorable findings in the review body |
| Every review model "fails" at once | Expired credential, renamed models, or a network outage | Test one model by hand, refresh credentials or model names |
| A stacked PR shows the sibling's files | Unmerged sibling, or two merge bases | Review after the sibling merges; worker merges the integration branch |
| Worktree type-check: module not found | The base added a dependency after a merge | Install dependencies in that worktree |
| Worktree misses a new env key | Env file was created before `.env.example` gained the key | Re-run the worktree bootstrap after merging the base |
| Scratchpad files vanish | New session, new scratchpad | Keep durable things in the docs folder |
| Shipped UI drifts from the signed-off mockup | Worker got the design as a written description | Point the brief at the saved mockup files |
| Worker cannot edit a protected file even after the user approves | Its classifier cannot see approvals given to the orchestrator | The orchestrator writes it; the worker commits it |
| `wstat.py` shows another session's state | The scripts read the newest transcript in the worktree's project dir; a second session there (a tool's reviewer, the user's own) shares it | Check the `file:` line of `wstat.py`; read the right `.jsonl` by hand while the other session is active |
| Task status flips after an integration merge, and again after a reset | Tracker automation fires on any merge, with a delay | Reset, then sweep all tasks once more before reporting |
