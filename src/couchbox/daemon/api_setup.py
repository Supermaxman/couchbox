"""Setup without a keyboard: install to the SSD, and the phone as the remote even before
the box is online (a setup Wi-Fi hotspot)."""

import re
import secrets as pysecrets
import threading
import time
from typing import Any

from couchbox import install_disk, secrets, settings
from couchbox.system import CommandError, out, sh

from . import api, events
from .api import UserError, method

PHONE_PORT = 8791
HOTSPOT_CON = "couchbox-setup"
HOTSPOT_IP = "10.42.0.1"  # NetworkManager's shared-mode address
OFFLINE_GRACE = 25  # seconds offline before the wizard opens the hotspot

_hotspot: dict[str, Any] = {}  # ssid, password while it's up
_scan_cache: list[dict[str, Any]] = []
_first_offline = 0.0
_hlock = threading.Lock()


# ------------------------------------------------------------------ install to the SSD
@method("install.status", write=False)
def install_status() -> dict[str, Any]:
    return install_disk.status()


@method("install.start")
def install_start(device: str) -> dict[str, Any]:
    try:
        return install_disk.start(device, lambda st: events.publish("install.progress", st))
    except (install_disk.InstallError, CommandError) as e:
        raise UserError(str(e)) from None


@method("system.poweroff")
def system_poweroff() -> dict[str, Any]:
    threading.Timer(2, lambda: sh(["systemctl", "poweroff"], check=False)).start()
    return {"poweroff": True}


# ------------------------------------------------------------------ setup hotspot
def wifi_device() -> str:
    for line in out(["nmcli", "-t", "-f", "DEVICE,TYPE", "device"], check=False).splitlines():
        f = line.split(":")
        if len(f) >= 2 and f[1] == "wifi":
            return f[0]
    return ""


def hotspot_active() -> bool:
    return bool(_hotspot)


def cached_scan() -> list[dict[str, Any]]:
    """While the hotspot is up the radio can't scan: the list from just before."""
    return list(_scan_cache)


def wifi_qr(ssid: str, password: str) -> str:
    esc = lambda s: re.sub(r'([\\;,:"])', r"\\\1", s)  # noqa: E731
    return f"WIFI:T:WPA;S:{esc(ssid)};P:{esc(password)};;"


def hotspot_start() -> dict[str, Any]:
    global _scan_cache
    with _hlock:
        if _hotspot:
            return dict(_hotspot)
        dev = wifi_device()
        if not dev:
            raise UserError("This box has no Wi-Fi.")
        try:
            _scan_cache = api.wifi_scan(rescan=True)
        except Exception:  # noqa: BLE001
            _scan_cache = []
        tag = "".join(pysecrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(4))
        pw = "".join(pysecrets.choice("abcdefghijkmnpqrstuvwxyz23456789") for _ in range(10))
        ssid = f"Couchbox-{tag}"
        sh(["nmcli", "connection", "delete", "id", HOTSPOT_CON], check=False)
        r = sh(
            ["nmcli", "device", "wifi", "hotspot", "ifname", dev, "con-name", HOTSPOT_CON, "ssid", ssid, "band", "bg", "password", pw],
            check=False,
            timeout=60,
        )
        if r.returncode != 0:
            raise UserError("Couldn't start the setup Wi-Fi.")
        sh(["nmcli", "connection", "modify", HOTSPOT_CON, "connection.autoconnect", "no"], check=False)
        _hotspot.update({"ssid": ssid, "password": pw, "device": dev})
    events.publish("setup.hotspot", {"on": True, "ssid": ssid})
    return dict(_hotspot)


def hotspot_stop() -> None:
    with _hlock:
        if not _hotspot:
            return
        _hotspot.clear()
        sh(["nmcli", "connection", "down", "id", HOTSPOT_CON], check=False, timeout=30)
        sh(["nmcli", "connection", "delete", "id", HOTSPOT_CON], check=False)
    events.publish("setup.hotspot", {"on": False})


def lan_ip() -> str:
    """This box's address on the home network (not the hotspot's or the tailnet's)."""
    for line in out(["ip", "-4", "-o", "route", "get", "1.1.1.1"], check=False).splitlines():
        m = re.search(r"\bsrc (\d+\.\d+\.\d+\.\d+)", line)
        if m and m.group(1) != HOTSPOT_IP:
            return m.group(1)
    return ""


@method("setup.phone")
def setup_phone(auto: bool = True) -> dict[str, Any]:
    """What the wizard's "use your phone" card shows. Online: the phone page's address (by IP:
    not every phone resolves .local names). Offline for a while (auto): a hotspot to join first.
    A write method: the address carries the phone token."""
    global _first_offline
    token = secrets.ensure_token()
    if not settings.get("phone.enabled"):
        return {"mode": "off"}
    ip = lan_ip()
    if ip and not _hotspot:
        _first_offline = 0
        return {"mode": "lan", "url": f"http://{ip}:{PHONE_PORT}/#t={token}"}
    if ip and _hotspot:
        # Ethernet came up while the hotspot was on: the home network wins
        hotspot_stop()
        return {"mode": "lan", "url": f"http://{ip}:{PHONE_PORT}/#t={token}"}
    if not _hotspot and auto:
        _first_offline = _first_offline or time.time()
        if time.time() - _first_offline >= OFFLINE_GRACE and wifi_device():
            try:
                hotspot_start()
            except UserError:
                return {"mode": "none"}
    if _hotspot:
        return {
            "mode": "hotspot",
            "ssid": _hotspot["ssid"],
            "password": _hotspot["password"],
            "wifi": wifi_qr(_hotspot["ssid"], _hotspot["password"]),
            "url": f"http://{HOTSPOT_IP}:{PHONE_PORT}/#t={token}",
        }
    return {"mode": "none"}


@method("setup.hotspot")
def setup_hotspot(on: bool) -> dict[str, Any]:
    if on:
        hotspot_start()
    else:
        hotspot_stop()
    return setup_phone(auto=False)
