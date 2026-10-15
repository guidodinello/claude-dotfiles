#!/usr/bin/env python3
"""Drive real iOS Safari in an Xcode Simulator through its Web Inspector socket.

No safaridriver, no admin rights, no project file. Stdlib only. Run with `python3 -I`.

The simulator exposes a user-owned unix socket (`simctl getenv <udid> RWI_LISTEN_SOCKET`).
Framing is a 4-byte big-endian length followed by a binary plist, carrying the private
WebKit Remote Inspector (WIR) RPC. This protocol is undocumented and can change with a
future Xcode: run `selftest` first and treat a failure as a stop, not a retry.

Usage:
  wir.py hold     <udid>          # run in the background for the whole session
  wir.py selftest <udid>
  wir.py pages    <udid>
  wir.py wait     <udid> <url-substring> [--timeout 30]
  wir.py eval     <udid> <url-substring> <js>
  wir.py measure  <udid> <url-substring>
  wir.py fill     <udid> <url-substring> <css-selector> <value>
  wir.py click    <udid> <url-substring> <css-selector>

`<url-substring>` is matched against each Safari tab's URL. Use "" for any tab.
Every command opens a fresh connection and re-resolves the page, so it survives
navigations (the page identifier changes when the URL changes).
"""
import argparse
import json
import os
import plistlib
import select
import signal
import socket
import struct
import subprocess
import sys
import time
import uuid

SAFARI = "com.apple.mobilesafari"
SETTLE_SECONDS = 6  # per connection: wait for Safari and its tabs to be announced
RETRY_SECONDS = 20  # per command: reconnect while the daemon respawns

# Measures viewport units without touching any project file: temporary off-screen
# divs are appended, read, and removed in the same tick.
MEASURE_JS = r"""
(() => {
  const probe = (h) => {
    const d = document.createElement('div');
    d.style.cssText = 'position:absolute;top:0;left:-9999px;width:1px;height:' + h;
    document.body.appendChild(d);
    const v = d.offsetHeight;
    d.remove();
    return v;
  };
  const inset = (side) => {
    const d = document.createElement('div');
    d.style.cssText = 'position:absolute;left:-9999px;padding-' + side + ':env(safe-area-inset-' + side + ')';
    document.body.appendChild(d);
    const v = parseFloat(getComputedStyle(d)['padding' + side[0].toUpperCase() + side.slice(1)]) || 0;
    d.remove();
    return v;
  };
  const se = document.scrollingElement;
  const r = {
    url: location.href,
    userAgent: navigator.userAgent,
    vh: probe('100vh'), dvh: probe('100dvh'), svh: probe('100svh'), lvh: probe('100lvh'),
    innerHeight: innerHeight,
    visualViewportHeight: window.visualViewport ? window.visualViewport.height : null,
    clientHeight: se.clientHeight,
    scrollHeight: se.scrollHeight,
    scrollYStart: scrollY,
    safeArea: { top: inset('top'), right: inset('right'), bottom: inset('bottom'), left: inset('left') },
  };
  const before = scrollY;
  se.scrollTo(0, se.scrollHeight);
  r.maxScrollY = scrollY;
  se.scrollTo(0, before);
  r.overflowPx = r.scrollHeight - r.clientHeight;
  return JSON.stringify(r);
})()
"""

# React-controlled inputs ignore `el.value = x`: use the native setter, then dispatch events.
FILL_JS = r"""
((sel, val) => {
  const el = document.querySelector(sel);
  if (!el) return JSON.stringify({ok: false, error: 'no element for ' + sel});
  const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, val);
  el.dispatchEvent(new Event('input', {bubbles: true}));
  el.dispatchEvent(new Event('change', {bubbles: true}));
  return JSON.stringify({ok: true});
})(%s, %s)
"""

CLICK_JS = r"""
((sel) => {
  const el = document.querySelector(sel);
  if (!el) return JSON.stringify({ok: false, error: 'no element for ' + sel});
  el.click();
  return JSON.stringify({ok: true});
})(%s)
"""


class WirError(Exception):
    pass


class TransientError(WirError):
    """The inspector daemon was not ready (it exits when its last client disconnects and
    respawns on the next connection, so back-to-back commands can race it). Safe to retry."""


class Wir:
    def __init__(self, udid):
        try:
            path = subprocess.check_output(
                ["xcrun", "simctl", "getenv", udid, "RWI_LISTEN_SOCKET"],
                text=True, stderr=subprocess.PIPE,
            ).strip()
        except subprocess.CalledProcessError as exc:
            raise WirError(
                "cannot read RWI_LISTEN_SOCKET: is %s booted? (%s)" % (udid, exc.stderr.strip())
            )
        if not path:
            raise WirError("empty RWI_LISTEN_SOCKET: the simulator is not booted")
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            self.sock.connect(path)
        except OSError:
            self.sock.close()
            raise
        self.conn = str(uuid.uuid4()).upper()
        self.sender = str(uuid.uuid4()).upper()
        self.buf = b""
        self.page = None  # (app_id, page_id)
        self.target = None
        self.next_id = 1
        self.send("_rpc_reportIdentifier:", {})

    def close(self):
        self.sock.close()

    def send(self, selector, arg):
        arg = {"WIRConnectionIdentifierKey": self.conn, **arg}
        data = plistlib.dumps({"__selector": selector, "__argument": arg}, fmt=plistlib.FMT_BINARY)
        self.sock.sendall(struct.pack(">I", len(data)) + data)

    def recv(self, timeout):
        end = time.time() + timeout
        while True:
            if len(self.buf) >= 4:
                n = struct.unpack(">I", self.buf[:4])[0]
                if len(self.buf) >= 4 + n:
                    msg = plistlib.loads(self.buf[4:4 + n])
                    self.buf = self.buf[4 + n:]
                    return msg
            left = end - time.time()
            if left <= 0 or not select.select([self.sock], [], [], left)[0]:
                return None
            chunk = self.sock.recv(65536)
            if not chunk:
                return None
            self.buf += chunk

    def wait_for(self, selector, timeout):
        end = time.time() + timeout
        while time.time() < end:
            msg = self.recv(end - time.time())
            if msg is None:
                break
            if msg.get("__selector") == selector:
                return msg.get("__argument") or {}
        return None

    def safari_app(self, settle):
        # A fresh connection can receive an empty application list before the
        # simulator has announced Safari, so ask again until it shows up.
        end = time.time() + settle
        while time.time() < end:
            self.send("_rpc_getConnectedApplications:", {})
            apps = (self.wait_for("_rpc_reportConnectedApplicationList:", 2) or {}).get(
                "WIRApplicationDictionaryKey", {}
            )
            for app_id, app in apps.items():
                if app.get("WIRApplicationBundleIdentifierKey") == SAFARI:
                    return app_id
        return None

    def pages(self, settle=SETTLE_SECONDS):
        end = time.time() + settle
        app_id = self.safari_app(settle)
        while app_id is not None:
            self.send("_rpc_forwardGetListing:", {"WIRApplicationIdentifierKey": app_id})
            listing = self.wait_for("_rpc_applicationSentListing:", 2) or {}
            pages = [
                {"id": p.get("WIRPageIdentifierKey"), "url": p.get("WIRURLKey") or "", "title": p.get("WIRTitleKey") or ""}
                for p in listing.get("WIRListingKey", {}).values()
                if p.get("WIRTypeKey") == "WIRTypeWebPage"
            ]
            if pages or time.time() >= end:
                return app_id, pages
        return None, []

    def attach(self, url_part):
        end = time.time() + SETTLE_SECONDS
        while True:
            app_id, pages = self.pages()
            matches = [p for p in pages if url_part in p["url"]]
            if matches or time.time() >= end:
                break
            time.sleep(0.5)
        if not pages:
            raise TransientError("Safari reported no tabs (inspector daemon not ready?)")
        if not matches:
            seen = ", ".join(p["url"] for p in pages)
            raise WirError("no Safari tab matches %r (tabs: %s)" % (url_part, seen))
        page = matches[-1]
        self.page = (app_id, page["id"])
        ids = self._ids()
        self.send("_rpc_forwardSocketSetup:", ids)
        self.target = None
        end = time.time() + 5
        while time.time() < end and self.target is None:
            msg = self.inbound(end - time.time())
            if msg is None:
                break
            if msg.get("method") == "Target.targetCreated":
                self.target = msg["params"]["targetInfo"]["targetId"]
        return page

    def _ids(self):
        return {
            "WIRApplicationIdentifierKey": self.page[0],
            "WIRPageIdentifierKey": self.page[1],
            "WIRSenderKey": self.sender,
        }

    def inbound(self, timeout):
        arg = self.wait_for("_rpc_applicationSentData:", timeout)
        if arg is None:
            return None
        return json.loads(arg["WIRMessageDataKey"])

    def raw(self, obj):
        self.send("_rpc_forwardSocketData:", {**self._ids(), "WIRSocketDataKey": json.dumps(obj).encode()})

    def evaluate(self, expression, timeout=15):
        cmd_id = self.next_id
        self.next_id += 1
        cmd = {
            "id": cmd_id,
            "method": "Runtime.evaluate",
            "params": {"expression": expression, "returnByValue": True, "awaitPromise": True},
        }
        if self.target:
            self.raw({
                "id": 1000 + cmd_id,
                "method": "Target.sendMessageToTarget",
                "params": {"targetId": self.target, "message": json.dumps(cmd)},
            })
        else:
            self.raw(cmd)
        end = time.time() + timeout
        while time.time() < end:
            msg = self.inbound(end - time.time())
            if msg is None:
                break
            if msg.get("method") == "Target.dispatchMessageFromTarget":
                msg = json.loads(msg["params"]["message"])
            if msg.get("id") == cmd_id:
                if "error" in msg:
                    raise WirError("inspector error: %s" % json.dumps(msg["error"]))
                res = msg.get("result", {})
                if res.get("wasThrown"):
                    raise WirError("page threw: %s" % json.dumps(res.get("result")))
                return res.get("result", {}).get("value")
        raise WirError("no reply to Runtime.evaluate within %ss" % timeout)


def run(udid, operation, patience=RETRY_SECONDS):
    """Open a connection, run `operation(wir)`, and retry on a fresh connection while the
    failure is transient (dropped socket or daemon not ready). Real errors propagate."""
    end = time.time() + patience
    while True:
        wir = None
        try:
            wir = Wir(udid)
            return operation(wir)
        except (OSError, TransientError) as exc:
            if time.time() >= end:
                raise WirError(
                    "inspector kept failing for %ss: %s (start `wir.py hold` first, or wait ~10s "
                    "between commands: launchd throttles the daemon's respawn)" % (patience, exc)
                )
        finally:
            if wir is not None:
                wir.close()
        time.sleep(2)


def cmd_hold(args):
    """Keep one inspector connection open until SIGTERM/SIGINT.

    webinspectord exits when its last client disconnects, and launchd then throttles its
    respawn, so chained commands fail with Broken pipe. While `hold` runs, the daemon stays
    up and every other command connects to it immediately. Start it in the background before
    `selftest`, record its PID, and stop only that PID at cleanup."""
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    end = time.time() + RETRY_SECONDS
    while True:
        try:
            w = Wir(args.udid)
            break
        except OSError as exc:
            if time.time() >= end:
                raise WirError("cannot connect to the inspector socket: %s" % exc)
            time.sleep(2)
    print("holding inspector connection (pid %d)" % os.getpid(), flush=True)
    while True:
        if select.select([w.sock], [], [], 30)[0] and not w.sock.recv(65536):
            raise WirError("inspector closed the held connection (simulator shut down?)")


def cmd_selftest(args):
    def operation(w):
        _, pages = w.pages()
        if not pages:
            # `simctl openurl about:blank` is rejected (LSApplicationWorkspaceErrorDomain 115),
            # so launching Safari itself is the way to get an inspectable tab.
            launched = subprocess.run(
                ["xcrun", "simctl", "launch", args.udid, SAFARI], capture_output=True, text=True
            )
            if launched.returncode != 0:
                raise WirError("cannot launch Safari: %s" % launched.stderr.strip())
            _, pages = w.pages(settle=15)
        if not pages:
            raise TransientError("Safari is running but shows no inspectable tab")
        w.attach("")
        return w.evaluate("1+1")

    value = run(args.udid, operation)
    if value != 2:
        raise WirError("1+1 returned %r" % (value,))
    print("ok: 1+1 = 2 in iOS Safari")


def cmd_pages(args):
    print(json.dumps(run(args.udid, lambda w: w.pages()[1]), indent=2))


def cmd_wait(args):
    end = time.time() + args.timeout
    seen = []
    while time.time() < end:
        try:
            seen = run(args.udid, lambda w: w.pages()[1], patience=RETRY_SECONDS)
        except WirError:
            seen = []
        for p in seen:
            if args.url in p["url"]:
                print(json.dumps(p))
                return
        time.sleep(1)
    raise WirError(
        "no tab matching %r after %ss (tabs: %s)" % (args.url, args.timeout, [p["url"] for p in seen])
    )


def with_page(args, expression):
    def operation(w):
        w.attach(args.url)
        return w.evaluate(expression)

    return run(args.udid, operation)


def cmd_eval(args):
    print(json.dumps(with_page(args, args.js)))


def cmd_measure(args):
    print(with_page(args, MEASURE_JS))


def cmd_fill(args):
    print(with_page(args, FILL_JS % (json.dumps(args.selector), json.dumps(args.value))))


def cmd_click(args):
    print(with_page(args, CLICK_JS % json.dumps(args.selector)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("hold", help="keep the inspector daemon alive until killed (run in background)")
    p.add_argument("udid")
    p.set_defaults(fn=cmd_hold)

    p = sub.add_parser("selftest", help="evaluate 1+1 in Safari; preflight gate")
    p.add_argument("udid")
    p.set_defaults(fn=cmd_selftest)

    p = sub.add_parser("pages", help="list inspectable Safari tabs")
    p.add_argument("udid")
    p.set_defaults(fn=cmd_pages)

    p = sub.add_parser("wait", help="wait until a tab URL contains a substring")
    p.add_argument("udid")
    p.add_argument("url")
    p.add_argument("--timeout", type=float, default=30)
    p.set_defaults(fn=cmd_wait)

    p = sub.add_parser("eval", help="evaluate a JS expression in a tab")
    p.add_argument("udid")
    p.add_argument("url")
    p.add_argument("js")
    p.set_defaults(fn=cmd_eval)

    p = sub.add_parser("measure", help="viewport units, scroll overflow, safe areas")
    p.add_argument("udid")
    p.add_argument("url")
    p.set_defaults(fn=cmd_measure)

    p = sub.add_parser("fill", help="set an input value (React-safe)")
    p.add_argument("udid")
    p.add_argument("url")
    p.add_argument("selector")
    p.add_argument("value")
    p.set_defaults(fn=cmd_fill)

    p = sub.add_parser("click", help="click an element")
    p.add_argument("udid")
    p.add_argument("url")
    p.add_argument("selector")
    p.set_defaults(fn=cmd_click)

    args = ap.parse_args()
    try:
        args.fn(args)
    except (WirError, subprocess.CalledProcessError) as exc:
        sys.exit("wir.py: %s\n(If selftest fails on a newer Xcode, the private WIR protocol may have "
                 "changed: stop and report; do not retry blindly.)" % exc)


if __name__ == "__main__":
    main()
