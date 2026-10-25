"""couchboxd: the one privileged service. JSON-RPC over /run/couchbox/couchboxd.sock.

The socket is root:couchbox 0660. Every connection's peer is checked (SO_PEERCRED): calls
that change the system need root or the couchbox group; read-only calls are open to any
local user who can reach the socket. Handlers live in couchbox.daemon.api.
"""

import asyncio
import grp
import inspect
import json
import logging
import os
import pwd
import socket
import struct
from typing import Any

from couchbox import paths

from . import api, events

log = logging.getLogger("couchboxd")
GROUP = os.environ.get("COUCHBOX_GROUP", "couchbox")


def peer(sock: socket.socket) -> tuple[int, int, int]:
    creds = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    return struct.unpack("3i", creds)  # pid, uid, gid


def allowed_to_write(uid: int, gid: int) -> bool:
    if uid == 0 or uid == os.getuid():
        return True
    try:
        g = grp.getgrnam(GROUP)
    except KeyError:
        return False
    if gid == g.gr_gid:
        return True
    try:
        user = pwd.getpwuid(uid).pw_name
    except KeyError:
        return False
    return g.gr_gid in os.getgrouplist(user, gid)


async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    sock = writer.get_extra_info("socket")
    pid, uid, gid = peer(sock)
    can_write = allowed_to_write(uid, gid)

    async def send(obj: dict[str, Any]) -> None:
        writer.write((json.dumps(obj) + "\n").encode())
        await writer.drain()

    try:
        while line := await reader.readline():
            try:
                req = json.loads(line)
                rid, name, params = req.get("id"), req["method"], req.get("params") or {}
            except (ValueError, KeyError, AttributeError):
                await send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Bad request"}})
                continue
            if name == "events.subscribe":
                await _stream_events(params.get("topics") or [], send)
                return
            m = api.METHODS.get(name)
            if not m:
                await send({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"No such method: {name}"}})
                continue
            if m.write and not can_write:
                log.warning("denied %s for uid %d (pid %d)", name, uid, pid)
                await send({"jsonrpc": "2.0", "id": rid, "error": {"code": -32003, "message": "Not allowed from this account."}})
                continue
            try:
                if not isinstance(params, dict):
                    raise TypeError("params must be an object")
                if inspect.iscoroutinefunction(m.fn):
                    result = await m.fn(**params)
                else:
                    result = await asyncio.get_running_loop().run_in_executor(None, lambda: m.fn(**params))
                await send({"jsonrpc": "2.0", "id": rid, "result": result})
            except api.UserError as e:
                await send({"jsonrpc": "2.0", "id": rid, "error": {"code": -32000, "message": str(e)}})
            except TypeError as e:
                await send({"jsonrpc": "2.0", "id": rid, "error": {"code": -32602, "message": f"Bad parameters: {e}"}})
            except Exception as e:  # noqa: BLE001 - report, keep serving
                log.exception("%s failed", name)
                await send({"jsonrpc": "2.0", "id": rid, "error": {"code": -32000, "message": f"{name} failed: {e}"}})
    except (ConnectionError, asyncio.IncompleteReadError):
        pass
    finally:
        writer.close()


async def _stream_events(topics: list[str], send) -> None:
    q = events.listen(topics)
    try:
        await send({"jsonrpc": "2.0", "id": 0, "result": {"subscribed": topics}})
        while True:
            topic, data = await q.get()
            await send({"jsonrpc": "2.0", "method": "event", "params": {"topic": topic, "data": data}})
    except (ConnectionError, BrokenPipeError):
        pass
    finally:
        events.unlisten(q)


async def serve(path=None) -> None:
    path = path or paths.socket_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    events.bind_loop(asyncio.get_running_loop())
    server = await asyncio.start_unix_server(handle, path=str(path))
    os.chmod(path, 0o660)
    try:
        os.chown(path, 0, grp.getgrnam(GROUP).gr_gid)
    except (KeyError, PermissionError):
        pass
    log.info("listening on %s", path)
    await api.startup()
    async with server:
        await server.serve_forever()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    asyncio.run(serve())


if __name__ == "__main__":
    main()
