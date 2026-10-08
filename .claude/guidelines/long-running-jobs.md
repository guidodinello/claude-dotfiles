## Long-running jobs
Applies to anything longer than a few minutes or anything measured: training, eval, benchmark, timing smoke, league.
- **Run it in a named tmux session, logging to a file.** `tmux new -d -s <name> '<cmd> 2>&1 | tee <log>'`. Never use a harness background shell for these; background shells are for short waits and polls only.
- **Refuse duplicates.** Before launch, check `pgrep -af '[e]ntrypoint.py'` and `tmux ls`. If an instance is already running, don't start another. The bracket stops pgrep from matching the agent's own `bash -c` wrapper, whose command line contains the pattern.
- **A dead wrapper isn't a dead job.** If a job seems to have died, check `pgrep` before relaunching. A killed or reaped wrapper shell can leave its children orphaned and still running. Relaunching on top of an orphaned 16-worker eval once froze the laptop.
- **Size workers by free RAM, not cores.** On the laptop, check `free -g` and budget per-worker memory.
- **Stop jobs precisely.** Use the job's STOP file, or `tmux send-keys -t <name> C-c` / SIGTERM to the session's process. Never use a `pkill -f` pattern broad enough to match unrelated processes; one agent killed its own shell that way.
