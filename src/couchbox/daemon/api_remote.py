"""Remote pairing for Settings and the setup wizard: pairing runs in the daemon and reports
progress as remote.pairing events, so the screen can follow it."""

import asyncio
import logging
from typing import Any

from . import events
from .api import UserError, method

log = logging.getLogger("couchboxd.remote")
_task: asyncio.Task | None = None
_stop: asyncio.Event | None = None
_last: dict[str, Any] = {"state": "idle"}


def _progress(state: str, detail: dict[str, Any]) -> None:
    _last.clear()
    _last.update({"state": state, **detail})
    events.publish("remote.pairing", dict(_last))


@method("remote.pair_start")
async def pair_start(seconds: float = 45, address: str = "") -> dict[str, Any]:
    """Start looking for a remote in pairing mode. seconds=0: until pair_stop (the wizard)."""
    global _task, _stop
    from couchbox import remote

    if _task and not _task.done():
        return dict(_last)
    _stop = asyncio.Event()

    async def run():
        try:
            await remote.pair(_progress, mac=address, seconds=seconds, stop=_stop)
        except Exception as e:  # noqa: BLE001
            log.exception("pairing")
            _progress("failed", {"reason": str(e)})

    _task = asyncio.create_task(run())
    await asyncio.sleep(0)
    return {"state": "searching"}


@method("remote.pair_stop")
async def pair_stop() -> dict[str, Any]:
    if _stop:
        _stop.set()
    return dict(_last)


@method("remote.pair_status", write=False)
async def pair_status() -> dict[str, Any]:
    return dict(_last)


@method("remote.devices", write=False)
async def remote_devices() -> list[dict[str, Any]]:
    from couchbox import remote

    try:
        return await remote.list_devices()
    except Exception as e:  # noqa: BLE001
        raise UserError(f"Bluetooth isn't available: {e}") from None


@method("remote.forget")
async def remote_forget(address: str) -> list[dict[str, Any]]:
    from couchbox import remote

    await remote.forget(address)
    return await remote.list_devices()
