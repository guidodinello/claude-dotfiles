# RTK - Rust Token Killer
Token-optimized CLI proxy. No hook rewrites commands for you (history: the comment above `RETIRED_HOOK_COMMANDS` in the claude-dotfiles repo's `sync.sh`), so prefix `rtk` yourself where output is large: `rtk grep`, `rtk gh pr diff`, `rtk read`, `rtk pytest`.
The hook is only removed from a config dir when `sync.sh` runs there. If a command is still rewritten (the error reads "gave no verdict ... another call in this response was changed by a hook"), run it as the only tool call in its response: a rewrite voids the auto-mode verdict of every other call in the same response.
Use the plain command when exact output matters: RTK can return wrong or regrouped output for `ls`, `diff`, `grep`. `rtk proxy <cmd>` runs a command unfiltered.
A command you write as `rtk ...` is classified as written, so it never voids an auto-mode verdict.
