# RTK - Rust Token Killer

**Usage**: Token-optimized CLI proxy (cuts up to 90% of bash output)

## Meta Commands (always use rtk directly)

```bash
rtk gain              # Show token savings analytics
rtk gain --history    # Show command usage history with savings
rtk discover          # Analyze Claude Code history for missed opportunities
rtk proxy <cmd>       # Execute raw command without filtering (for debugging)
```

## Installation Verification

```bash
rtk --version         # Should show: rtk X.Y.Z
rtk gain              # Should work (not "command not found")
which rtk             # Verify correct binary
```

⚠️ **Name collision**: If `rtk gain` fails, you may have reachingforthejack/rtk (Rust Type Kit) installed instead.

## Opt-in usage (no hook)

The `rtk hook claude` PreToolUse hook is removed (Issue 389). Nothing is rewritten for you.
Prefix `rtk` yourself where output is large: `rtk grep`, `rtk gh pr diff`, `rtk read`, `rtk pytest`.
Use the plain command when exact output matters (see the shell-output memory: RTK can return wrong
or regrouped output for `ls`, `diff`, `grep`). A command you write as `rtk ...` is classified as
written, so it never voids a verdict.

## Rule: rewritten commands travel alone

A command RTK rewrites must be the only Bash call in its response.

Applies until a fresh session verifies the fix (Issue 389). A rewrite voids the auto-mode verdict of
every other tool call in the same response, WebFetch included, not only Bash. The error reads "gave
no verdict ... another call in this response was changed by a hook". It still applies to any config
dir or tool that keeps the hook.

## Decision (Issue 389): drop the hook

Why: the classifier is server-side and runs before any PreToolUse hook, so RTK cannot run first.
`rtk hook claude` has no mode that changes this.

Options considered, last 30 days (rows capped at 7.5k input tokens, which reproduces `rtk gain`):

| Option | Fixes the cause | Tokens given up (of 2.62M saved) |
|--------|-----------------|----------------------------------|
| (a) `exclude_commands` for git/gh/grep/ssh | No: read, pytest, wc, ruff, find, rg, uv still rewrite | 1.40M (53%), grep 0.94M |
| (b) drop the hook (chosen) | Yes | up to 2.62M, less what opt-in `rtk` wins back |
| (c) run RTK before the classifier | Not possible | n/a |

Trade-off: grep, read, ls, pytest and gh output gets bigger unless you opt in. Follow-up, not
done: `rtk llm-proxy` compresses at the API layer and leaves tool input alone, but needs Claude
Code repointed at a local proxy.

To retire a hook, delete it from `settings.base.json` and add its command to
`RETIRED_HOOK_COMMANDS` in `sync.sh`, or the union with the live file keeps it.
