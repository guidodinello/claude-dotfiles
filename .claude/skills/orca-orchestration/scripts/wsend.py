#!/usr/bin/env python3
"""Send one line to an Orca terminal, the way a Claude Code prompt needs it.

usage: wsend.py <handle> "<one-line text>"   text without Enter, a pause, then a bare Enter
       wsend.py <handle> --menu <n>          the bare option number, no Enter

The handle is passed as `--terminal <handle>`, never as a positional argument (Orca
answers "Unknown command" to that). Text must be one line of at most 400 chars: longer
text goes to <worktree>/.orchestrator-answers.md plus a one-line pointer.
Exit: 0 sent, 1 orca failed, 2 text refused.
"""
import argparse
import importlib.util
import os
import sys

sys.dont_write_bytecode = True
_spec = importlib.util.spec_from_file_location(
    "_orca", os.path.join(os.path.dirname(os.path.abspath(__file__)), "_orca.py")
)
_orca = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_orca)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("handle")
    ap.add_argument("text", nargs="?")
    ap.add_argument("--menu", type=int, metavar="N")
    args = ap.parse_args(argv)
    if (args.text is None) == (args.menu is None):
        ap.error("give either the text or --menu N")
    try:
        if args.menu is not None:
            _orca.send_menu_choice(args.handle, args.menu)
        else:
            _orca.send_line(args.handle, args.text)
    except ValueError as exc:
        print(f"wsend: {exc}", file=sys.stderr)
        return 2
    except _orca.OrcaError as exc:
        print(f"wsend: {exc}", file=sys.stderr)
        return 1
    print("sent", args.handle)
    return 0


if __name__ == "__main__":
    sys.exit(main())
