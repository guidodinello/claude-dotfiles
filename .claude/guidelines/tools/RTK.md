# RTK - Rust Token Killer
Token-optimized CLI proxy. No hook rewrites commands for you (history: the comment above `RETIRED_HOOK_COMMANDS` in this repo's `sync.sh`), so prefix `rtk` yourself where output is large: `rtk grep`, `rtk gh pr diff`, `rtk read`, `rtk pytest`.
Use the plain command when exact output matters: RTK can return wrong or regrouped output for `ls`, `diff`, `grep`. `rtk proxy <cmd>` runs a command unfiltered.
A command you write as `rtk ...` is classified as written, so it never voids an auto-mode verdict.
