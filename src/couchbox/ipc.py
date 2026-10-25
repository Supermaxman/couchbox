"""Talking to couchboxd: JSON-RPC 2.0, one JSON object per line, over a Unix socket.

    from couchbox.ipc import call
    call("settings.get", keys=["voice.mode"])     -> {"voice.mode": "off"}

    for event in subscribe(["settings", "updates"]): ...

Errors come back as IpcError with a message meant for the screen.
"""

import itertools
import json
import socket
from collections.abc import Iterator
from typing import Any

from couchbox import paths


class IpcError(RuntimeError):
    def __init__(self, message: str, code: int = -32000):
        super().__init__(message)
        self.code = code


_ids = itertools.count(1)


def _connect(timeout: float | None) -> socket.socket:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(str(paths.socket_path()))
    except (FileNotFoundError, ConnectionRefusedError):
        s.close()
        raise IpcError("The Couchbox service isn't running.", -32001) from None
    except PermissionError:
        s.close()
        raise IpcError("Not allowed to change settings from this account.", -32003) from None
    return s


def _readline(f) -> dict[str, Any]:
    line = f.readline()
    if not line:
        raise IpcError("The Couchbox service closed the connection.", -32002)
    return json.loads(line)


def call(method: str, timeout: float = 30, **params: Any) -> Any:
    s = _connect(timeout)
    try:
        rid = next(_ids)
        s.sendall((json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": params}) + "\n").encode())
        with s.makefile("r", encoding="utf-8") as f:
            while True:
                msg = _readline(f)
                if msg.get("id") == rid:
                    break
    finally:
        s.close()
    if "error" in msg:
        raise IpcError(msg["error"].get("message", "error"), msg["error"].get("code", -32000))
    return msg.get("result")


def subscribe(topics: list[str]) -> Iterator[dict[str, Any]]:
    """Events as {"topic": ..., "data": ...}, until the daemon goes away."""
    s = _connect(None)
    s.sendall((json.dumps({"jsonrpc": "2.0", "id": 0, "method": "events.subscribe", "params": {"topics": topics}}) + "\n").encode())
    with s, s.makefile("r", encoding="utf-8") as f:
        while True:
            msg = _readline(f)
            if msg.get("method") == "event":
                yield msg["params"]
