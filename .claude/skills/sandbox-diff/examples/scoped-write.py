#!/usr/bin/env python3
"""Skeleton: scoped sandbox writes for one allowlisted test account.

usage: python3 -I scoped-write.py <env-file> <mode> [args]
  show <target>                read-only: this account's records on an allowlisted target
  create <target> <variant>    create one record on an allowlisted target for the test account
  flag <target> <record-id>    change one record, only if it belongs to the test account and target

Copy into the project's harness scripts folder; fill the constants and the vendor calls.
Credentials are parsed from the env file inside this process and never printed. The API host
is printed first and anything but the sandbox host is refused. Output is ids and statuses only.
Log every write in the project's write log right after it runs.
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

SANDBOX_HOST = "sandbox.vendor.example"
TEST_ACCOUNT = "<allowlisted test account id>"
ALLOWED_TARGETS = frozenset({"<allowlisted target id>"})

BASE_URL_KEY = "VENDOR_API_BASE_URL"
TOKEN_KEY = "VENDOR_API_TOKEN"


class Refused(Exception):
    pass


def read_env(path):
    values = {}
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.removeprefix("export ").partition("=")
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                value = value[1:-1]
            values[key.strip()] = value
    return values


def sandbox_base(env):
    base = env.get(BASE_URL_KEY, "")
    host = urllib.parse.urlsplit(base).netloc if base else "(none)"
    print(f"host: {host}", file=sys.stderr)
    if host != SANDBOX_HOST:
        raise Refused(f"{host} is not the sandbox host")
    return base.rstrip("/")


def require_target(target):
    if target not in ALLOWED_TARGETS:
        raise Refused(f"target {target!r} is not allowlisted")
    return target


class Client:
    def __init__(self, base, token):
        self.base = base
        self._headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=self._headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                return json.loads(res.read() or b"null")
        except urllib.error.HTTPError as err:
            raise RuntimeError(f"{method} {path.split('?')[0]} failed: HTTP {err.code}") from None

    def mine(self, target):
        query = urllib.parse.urlencode({"resource": target, "account": TEST_ACCOUNT, "limit": 100})
        page = self.call("GET", f"/records?{query}") or {}
        return [r for r in page.get("data", []) if r.get("account") == TEST_ACCOUNT and r.get("resource") == target]


def summary(record):
    return {"id": record.get("id"), "status": record.get("status"), "created_at": record.get("created_at")}


def run(argv):
    if len(argv) < 3:
        raise SystemExit(__doc__)
    env = read_env(argv[0])
    base = sandbox_base(env)
    mode, target, rest = argv[1], require_target(argv[2]), argv[3:]
    client = Client(base, env.get(TOKEN_KEY, ""))

    if mode == "show":
        return [summary(r) for r in client.mine(target)]
    if mode == "create" and len(rest) == 1:
        created = client.call("POST", "/records", {"resource": target, "account": TEST_ACCOUNT, "variant": rest[0]})
        if created.get("account") != TEST_ACCOUNT or created.get("resource") != target:
            raise Refused(f"created record {created.get('id')} is not the scoped one: stop and log it")
        return [{"created": summary(created)}]
    if mode == "flag" and len(rest) == 1:
        if not any(r.get("id") == rest[0] for r in client.mine(target)):
            raise Refused("not one of the test account records")
        client.call("POST", f"/records/{rest[0]}", {"flagged": True})
        return [{"flagged": rest[0]}]
    raise SystemExit(__doc__)


def main():
    try:
        for row in run(sys.argv[1:]):
            print(json.dumps(row))
    except Refused as err:
        print(f"refused: {err}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
