"""A running TV app's control socket: how the voice assistant asks Dropout, 2nd Try, Nebula
and Twitch (couchbox-streaming) for lists, opens things in them and reads what they show.

The app listens on $XDG_RUNTIME_DIR/couchbox/app-<site>.sock (the TV user's, mode 0600; root
can connect). One JSON request per connection, one JSON reply:

    {"op": "ping"}                                   -> {"ok": true, "site": ...}
    {"op": "call", "fn": "search", "args": {...}}    -> the app's own back-end call (its sign-in)
    {"op": "open", "target": "play:ID"}              -> play:ID, series:ID, search:TEXT, home, mylist, series
    {"op": "media", "action": "pause", "seconds": 0} -> play, pause, toggle, forward, back, seek, restart
    {"op": "state"}                                  -> what's on screen: page, title, playing...
"""

import json
import logging
import os
import pwd
import socket
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

log = logging.getLogger("couchbox.appctl")
TV_USER = "tv"


class NotRunning(RuntimeError):
    pass


def sock_path(site: str, uid: int | None = None) -> Path:
    if uid is None:
        if os.geteuid() == 0:
            try:
                uid = pwd.getpwnam(TV_USER).pw_uid
            except KeyError:
                uid = 1000
        else:
            uid = os.geteuid()
    base = os.environ.get("XDG_RUNTIME_DIR") if uid == os.geteuid() and os.environ.get("XDG_RUNTIME_DIR") else f"/run/user/{uid}"
    return Path(base) / "couchbox" / f"app-{site}.sock"


def call(site: str, req: dict[str, Any], timeout: float = 30) -> Any:
    """Send one request to the app; NotRunning if it isn't up."""
    p = sock_path(site)
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(str(p))
    except OSError:
        s.close()
        raise NotRunning(site) from None
    try:
        s.sendall(json.dumps(req).encode() + b"\n")
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
    finally:
        s.close()
    reply = json.loads(buf or b"{}")
    if isinstance(reply, dict) and reply.get("error") and len(reply) <= 2:
        raise RuntimeError(reply["error"])
    return reply


def running(site: str) -> bool:
    try:
        return bool(call(site, {"op": "ping"}, timeout=2).get("ok"))
    except (NotRunning, OSError, ValueError, RuntimeError):
        return False


class Server(threading.Thread):
    """In the app: answers requests with handler(req) -> reply (from this thread)."""

    def __init__(self, site: str, handler: Callable[[dict[str, Any]], Any]):
        super().__init__(name=f"appctl-{site}", daemon=True)
        self.handler = handler
        self.path = sock_path(site)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.unlink(missing_ok=True)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        old = os.umask(0o177)
        try:
            self.sock.bind(str(self.path))
        finally:
            os.umask(old)
        self.sock.listen(8)

    def run(self) -> None:
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self.serve, args=(conn,), daemon=True).start()

    def serve(self, conn: socket.socket) -> None:
        with conn:
            conn.settimeout(60)
            try:
                buf = b""
                while not buf.endswith(b"\n"):
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    buf += chunk
                try:
                    reply = self.handler(json.loads(buf))
                except Exception as err:  # noqa: BLE001 - the caller gets the reason
                    log.exception("appctl request")
                    reply = {"error": str(err) or err.__class__.__name__}
                conn.sendall(json.dumps(reply).encode() + b"\n")
            except OSError:
                pass

    def close(self) -> None:
        try:
            self.sock.close()
        finally:
            self.path.unlink(missing_ok=True)
