"""Tests for .claude/hooks/guard-bash.sh. Run: python3 -m unittest discover -s tests"""

import json
import os
import subprocess
import unittest
from pathlib import Path

GUARD = Path(__file__).resolve().parent.parent / ".claude" / "hooks" / "guard-bash.sh"

BLOCK = 2
ALLOW = 0

# (expected exit code, command)
CASES = [
    # Docker volumes
    (BLOCK, "docker compose down -v"),
    (BLOCK, "docker compose -f a.yml down --volumes"),
    (BLOCK, "cd x && docker stack foo down -v"),
    (BLOCK, "docker volume rm data"),
    (BLOCK, 'docker "volume" prune'),
    (BLOCK, "docker vol\\ume rm x"),
    (ALLOW, "docker compose down"),
    (ALLOW, "docker compose up -d --verbose"),
    (ALLOW, "docker volume ls"),
    (ALLOW, "docker compose logs download-vfoo"),
    # wrangler d1: needs an unquoted call with a standalone --local after it
    (BLOCK, 'wrangler d1 execute db --command "select 1"'),
    (BLOCK, "npx wrangler d1 execute db --remote --command x"),
    (BLOCK, "wrangler d1 migrations apply db"),
    (ALLOW, "wrangler d1 migrations apply db --local"),
    (ALLOW, "wrangler d1 execute db --local --command x"),
    (ALLOW, 'wrangler d1 execute db --local --command "select 1; select 2"'),
    (ALLOW, 'wrangler d1 execute "my db" --local --file ./x.sql'),
    (ALLOW, "wrangler d1 execute db --command x --local"),
    (ALLOW, "wrangler d1 execute db --command x --local > out.txt"),
    (ALLOW, "wrangler d1 execute db --command x --local 2>&1"),
    (ALLOW, 'cd app && npx wrangler d1 execute db --local --command "select 1" | jq .'),
    # --local borrowed from a neighbouring command or a quoted string
    (BLOCK, "wrangler d1 execute db --local && wrangler d1 execute db"),
    (BLOCK, "wrangler d1 execute db --remote && echo --local"),
    (BLOCK, "wrangler d1 execute db --remote; echo --local"),
    (BLOCK, 'wrangler d1 execute db --command "select --local "'),
    (BLOCK, "echo --local wrangler d1 execute db"),
    # flags that undo --local
    (BLOCK, "wrangler d1 execute db --local --remote"),
    (BLOCK, 'wrangler d1 execute db --local "--remote"'),
    (BLOCK, "wrangler d1 execute db --local --no-local"),
    (BLOCK, "wrangler d1 execute db --local --local=false"),
    (BLOCK, "wrangler d1 execute db --local false"),
    (BLOCK, "wrangler d1 execute db --local FALSE"),
    (BLOCK, "wrangler d1 execute db --local 0"),
    (BLOCK, "wrangler d1 execute db --local $X"),
    (BLOCK, "wrangler d1 execute --local db"),
    (BLOCK, 'wrangler d1 execute db --command x --local "false"'),
    (BLOCK, "wrangler d1 execute db --local-ish"),
    # the call hidden in quotes, a version suffix, escapes, substitutions
    (BLOCK, 'sh -c "wrangler d1 execute db" --local'),
    (BLOCK, 'sh -c "wrangler d1 execute db --remote" --local'),
    (BLOCK, "npx wrangler@3 d1 execute db"),
    (ALLOW, "npx wrangler@3 d1 execute db --local"),
    (BLOCK, '"wrangler" d1 execute db'),
    (BLOCK, "w\\rangler d1 execute db"),
    (BLOCK, 'wrangler --config "a;b" d1 execute db'),
    (BLOCK, "echo $(wrangler d1 execute db)"),
    (BLOCK, 'wrangler d1 execute db --command "unterminated'),
    # too long to analyse
    (BLOCK, "wrangler d1 execute db --local --command '" + "y" * 4100 + "'"),
    # unrelated
    (ALLOW, "wrangler deploy"),
    (ALLOW, "wrangler d1 list"),
    (ALLOW, "git status"),
    (ALLOW, "echo wrangler " + "x" * 300_000),
]

CLOUDFLARE_ENV_CASES = [
    (BLOCK, "wrangler deploy"),
    (BLOCK, "npx wrangler@3 deploy"),
    (ALLOW, "ls"),
]


def run_guard(stdin: str, cloudflare_env: str | None = None) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "CLOUDFLARE_ENV"}
    if cloudflare_env is not None:
        env["CLOUDFLARE_ENV"] = cloudflare_env
    return subprocess.run(
        ["bash", str(GUARD)], input=stdin, capture_output=True, text=True, env=env, timeout=30
    )


def hook_input(command: str) -> str:
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})


class GuardBashTest(unittest.TestCase):
    def test_commands(self):
        for want, command in CASES:
            with self.subTest(command=command[:80]):
                self.assertEqual(run_guard(hook_input(command)).returncode, want)

    def test_cloudflare_env_blocks_any_wrangler(self):
        for want, command in CLOUDFLARE_ENV_CASES:
            with self.subTest(command=command):
                self.assertEqual(run_guard(hook_input(command), "prod").returncode, want)

    def test_block_message_goes_to_stderr(self):
        result = run_guard(hook_input("docker volume rm data"))
        self.assertIn("BLOCKED", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_unreadable_input_fails_closed(self):
        for stdin in ("not json", "{}", '{"command": "ls"}', '{"tool_input": {"command": 1}}'):
            with self.subTest(stdin=stdin):
                self.assertEqual(run_guard(stdin).returncode, BLOCK)


if __name__ == "__main__":
    unittest.main()
