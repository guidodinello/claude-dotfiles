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

The hook is removed because its rewrite voids auto-mode verdicts. The options, the token numbers
and the trade-off are recorded once, in Fitted Issue 389
(`docs/process/issues/389-rtk-hook-rewrite-invalidates-auto-mode-verdicts.md`). To retire another
hook, follow the comment above `RETIRED_HOOK_COMMANDS` in `sync.sh`.
