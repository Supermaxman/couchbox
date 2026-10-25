"""Pairing Bluetooth remotes (the Fire TV remote first) with BlueZ over D-Bus.

pair(progress, mac="", seconds=45) finds a remote in pairing mode (hold Home ~10 s on a
Fire TV remote), pairs it (retrying its flaky first attempts), trusts and connects it.
It registers its own agent: the Fire remote asks the host to confirm pairing, and no
answer means AuthenticationCanceled. progress(state, detail) reports each step:
  searching, found, pairing, paired, failed, stopped

Don't factory-reset a Fire remote (Menu + Back + Left): that erases the TV infrared codes,
which its Power button needs (couchbox-cec can store them again for some TVs).
"""

import asyncio
import re
from collections.abc import Callable
from typing import Any

from dbus_fast import BusType, Message, MessageType, Variant
from dbus_fast.aio import MessageBus
from dbus_fast.service import ServiceInterface, method

NAME_RE = re.compile(r"^(AR|Amazon|Fire|.*[Rr]emote)")
ADAPTER = "/org/bluez/hci0"
AGENT_PATH = "/couchbox/pair_agent"
PAIR_TRIES = 4

Progress = Callable[[str, dict[str, Any]], None]


class Agent(ServiceInterface):
    """Accepts every pairing request: the user started this pairing on purpose."""

    def __init__(self):
        super().__init__("org.bluez.Agent1")

    @method()
    def Release(self):
        pass

    @method()
    def RequestPinCode(self, device: "o") -> "s":  # noqa: F821
        return "0000"

    @method()
    def DisplayPinCode(self, device: "o", pincode: "s"):  # noqa: F821
        pass

    @method()
    def RequestPasskey(self, device: "o") -> "u":  # noqa: F821
        return 0

    @method()
    def DisplayPasskey(self, device: "o", passkey: "u", entered: "q"):  # noqa: F821
        pass

    @method()
    def RequestConfirmation(self, device: "o", passkey: "u"):  # noqa: F821
        pass

    @method()
    def RequestAuthorization(self, device: "o"):  # noqa: F821
        pass

    @method()
    def AuthorizeService(self, device: "o", uuid: "s"):  # noqa: F821
        pass

    @method()
    def Cancel(self):
        pass


async def call(bus, path, iface, member, sig="", body=None, timeout=None):
    msg = Message(destination="org.bluez", path=path, interface=iface, member=member, signature=sig, body=body or [])
    coro = bus.call(msg)
    reply = await (asyncio.wait_for(coro, timeout) if timeout else coro)
    if reply.message_type == MessageType.ERROR:
        raise RuntimeError(f"{reply.error_name}: {' '.join(map(str, reply.body))}")
    return reply.body


async def set_prop(bus, path, iface, prop, sig, value):
    await call(bus, path, "org.freedesktop.DBus.Properties", "Set", "ssv", [iface, prop, Variant(sig, value)])


async def devices(bus) -> list[tuple[str, dict[str, Any]]]:
    (objs,) = await call(bus, "/", "org.freedesktop.DBus.ObjectManager", "GetManagedObjects")
    found = []
    for path, ifaces in objs.items():
        dev = ifaces.get("org.bluez.Device1")
        if dev and path.startswith(ADAPTER + "/"):
            found.append((path, {k: v.value for k, v in dev.items()}))
    return found


def looks_like_remote(d: dict[str, Any], mac: str = "") -> bool:
    if mac:
        return d.get("Address", "").upper() == mac.upper()
    name = d.get("Name", "") or d.get("Alias", "")
    # HID remotes: appearance 0x0180 (remote control) or a keyboard/peripheral class with a remote-ish name
    return bool(NAME_RE.match(name)) or d.get("Appearance") == 0x0180


def describe(d: dict[str, Any]) -> dict[str, Any]:
    return {
        "address": d.get("Address", ""),
        "name": d.get("Alias") or d.get("Name") or d.get("Address", ""),
        "paired": bool(d.get("Paired")),
        "connected": bool(d.get("Connected")),
        "trusted": bool(d.get("Trusted")),
        "battery": d.get("Battery"),
        "remote": looks_like_remote(d),
    }


async def list_devices() -> list[dict[str, Any]]:
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    try:
        return [describe(d) for _, d in await devices(bus) if d.get("Paired")]
    finally:
        bus.disconnect()


async def forget(address: str) -> None:
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    try:
        for path, d in await devices(bus):
            if d.get("Address", "").upper() == address.upper():
                await call(bus, ADAPTER, "org.bluez.Adapter1", "RemoveDevice", "o", [path])
    finally:
        bus.disconnect()


async def pair(progress: Progress, mac: str = "", seconds: float = 45, stop: asyncio.Event | None = None) -> dict[str, Any] | None:
    """Pair the first remote found (or this address). seconds=0: keep looking until stopped."""
    stop = stop or asyncio.Event()
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    bus.export(AGENT_PATH, Agent())
    try:
        await call(bus, "/org/bluez", "org.bluez.AgentManager1", "RegisterAgent", "os", [AGENT_PATH, "KeyboardDisplay"])
        await call(bus, "/org/bluez", "org.bluez.AgentManager1", "RequestDefaultAgent", "o", [AGENT_PATH])
        await set_prop(bus, ADAPTER, "org.bluez.Adapter1", "Powered", "b", True)
        await set_prop(bus, ADAPTER, "org.bluez.Adapter1", "Pairable", "b", True)
        # Start clean: an earlier failed attempt leaves an unpaired record that confuses retries.
        for path, d in await devices(bus):
            if looks_like_remote(d, mac) and not d.get("Paired"):
                try:
                    await call(bus, ADAPTER, "org.bluez.Adapter1", "RemoveDevice", "o", [path])
                except RuntimeError:
                    pass
        await call(bus, ADAPTER, "org.bluez.Adapter1", "StartDiscovery")
        progress("searching", {"seconds": seconds})
        loop = asyncio.get_running_loop()
        end = loop.time() + seconds if seconds else None
        path = d = None
        while not stop.is_set() and (end is None or loop.time() < end):
            for p, dd in await devices(bus):
                if looks_like_remote(dd, mac) and not dd.get("Paired"):
                    path, d = p, dd
                    break
            if path:
                break
            await asyncio.sleep(0.5)
        if not path:
            await _stop_discovery(bus)
            progress("stopped" if stop.is_set() else "failed", {"reason": "not found"})
            return None
        progress("found", describe(d))
        ok = False
        for attempt in range(1, PAIR_TRIES + 1):
            try:
                progress("pairing", {"attempt": attempt, **describe(d)})
                await call(bus, path, "org.bluez.Device1", "Pair", timeout=40)
                ok = True
                break
            except (TimeoutError, RuntimeError) as err:
                msg = str(err) or "timed out"
                if "AlreadyExists" in msg:
                    ok = True
                    break
                await asyncio.sleep(4 if "InProgress" in msg else 2)
        await _stop_discovery(bus)
        if not ok:
            progress("failed", {"reason": "pairing refused", **describe(d)})
            return None
        await set_prop(bus, path, "org.bluez.Device1", "Trusted", "b", True)
        try:
            await call(bus, path, "org.bluez.Device1", "Connect", timeout=20)
        except (TimeoutError, RuntimeError):
            pass  # it reconnects on the next key press
        result = next((describe(x) for p, x in await devices(bus) if p == path), describe(d))
        progress("paired", result)
        return result
    finally:
        try:
            await call(bus, "/org/bluez", "org.bluez.AgentManager1", "UnregisterAgent", "o", [AGENT_PATH])
        except RuntimeError:
            pass
        bus.disconnect()


async def _stop_discovery(bus) -> None:
    try:
        await call(bus, ADAPTER, "org.bluez.Adapter1", "StopDiscovery")
    except RuntimeError:
        pass
