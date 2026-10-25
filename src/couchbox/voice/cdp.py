"""Minimal Chrome DevTools Protocol client: run JavaScript in the TV apps' pages.

YouTube (VacuumTube, Electron) listens on 127.0.0.1:9222, the Chromium web apps (Dropout,
Nebula, Twitch, and Jellyfin's web app) on 9223 and Jellyfin Desktop (Qt WebEngine) on 9224;
the ports are opened by their launchers (couchbox-home, couchbox-web-apps, couchbox-jellyfin)."""

import json
import urllib.request

import websocket

YOUTUBE_PORT = 9222
WEB_PORT = 9223
JELLYFIN_PORT = 9224


class CdpError(Exception):
    pass


def pages(port):
    """Open pages on a DevTools port ([] if the app isn't running)."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=2) as r:
            return [p for p in json.load(r) if p.get("type") == "page"]
    except OSError:
        return []


def evaluate(page, expr, timeout=20):
    """Evaluate a JS expression (promises awaited) in a page and return its JSON value."""
    ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=timeout, suppress_origin=True)
    try:
        ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {"expression": expr, "returnByValue": True, "awaitPromise": True, "userGesture": True},
                }
            )
        )
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == 1:
                break
    finally:
        ws.close()
    if "error" in msg:
        raise CdpError(msg["error"].get("message", "DevTools error"))
    res = msg["result"]
    if "exceptionDetails" in res:
        d = res["exceptionDetails"]
        ex = d.get("exception") or {}
        raise CdpError(str(ex.get("value") or ex.get("description") or d.get("text") or "JS error").split("\n")[0])
    return res.get("result", {}).get("value")


def call(page, fn, *args, timeout=20):
    """Call a JS function source with JSON arguments: call(page, "(a, b) => a + b", 1, 2)."""
    return evaluate(page, f"({fn})(...{json.dumps(list(args))})", timeout=timeout)


def send(page, method, params=None, timeout=10):
    """Send one DevTools command to a page and return its result."""
    ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=timeout, suppress_origin=True)
    try:
        ws.send(json.dumps({"id": 1, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == 1:
                break
    finally:
        ws.close()
    if "error" in msg:
        raise CdpError(msg["error"].get("message", "DevTools error"))
    return msg.get("result", {})
