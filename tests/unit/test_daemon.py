import asyncio
import os
import threading
import time

import pytest

from couchbox import ipc, settings
from couchbox.daemon import api, server


@pytest.fixture
def daemon(box, runner):
    loop = asyncio.new_event_loop()
    task = loop.create_task(server.serve())

    def run():
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(task)
        except asyncio.CancelledError:
            pass
        rest = asyncio.all_tasks(loop)  # connections still being served (event streams)
        for x in rest:
            x.cancel()
        loop.run_until_complete(asyncio.gather(*rest, return_exceptions=True))
        loop.close()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    from couchbox import paths

    for _ in range(100):
        if paths.socket_path().exists():
            break
        time.sleep(0.02)
    yield runner
    loop.call_soon_threadsafe(task.cancel)
    t.join(5)


def test_ping_and_settings_roundtrip(daemon):
    assert ipc.call("ping")["version"]
    r = ipc.call("settings.set", changes={"voice.mode": "dictation"})
    assert r["changed"] == {"voice.mode": "dictation"}
    assert ipc.call("settings.get", keys=["voice.mode"]) == {"voice.mode": "dictation"}
    # the voice service restarts to pick it up
    assert daemon.ran("systemctl", "try-restart", "couchbox-voice.service")


def test_errors_are_readable(daemon):
    with pytest.raises(ipc.IpcError, match="must be one of"):
        ipc.call("settings.set", changes={"voice.mode": "loud"})
    with pytest.raises(ipc.IpcError, match="No such method"):
        ipc.call("nope")
    with pytest.raises(ipc.IpcError, match="Bad parameters"):
        ipc.call("settings.set", wrong=1)


def test_secrets_are_write_only(daemon):
    ipc.call("secrets.set", name="voice.llm.api_key", value="sk-secret-value")
    assert ipc.call("secrets.status")["voice.llm.api_key"] is True
    assert "sk-secret" not in str(ipc.call("settings.export"))
    assert not any(n.startswith("secrets.get") for n in api.METHODS)


def test_home_methods(daemon):
    ipc.call("home.move", app="twitch", index=0)
    assert ipc.call("settings.get", keys=["home.layout"])["home.layout"][0] == "twitch"
    ipc.call("home.hide", app="nebula")
    ipc.call("home.rename", app="youtube", name="Tube")
    ipc.call("home.add_web", name="News", url="https://news.example")
    listed = {a["id"]: a for a in ipc.call("apps.list")}
    assert listed["nebula"]["hidden"] and listed["youtube"]["display_name"] == "Tube" and listed["web-news"]["on_home"]
    with pytest.raises(ipc.IpcError, match="always stays"):
        ipc.call("home.hide", app="settings")
    ipc.call("home.remove_web", app="web-news")
    ipc.call("home.reset")
    assert settings.changed() == {}


def test_events_stream(daemon):
    got = []

    def listen():
        for ev in ipc.subscribe(["settings"]):
            got.append(ev)
            return

    t = threading.Thread(target=listen, daemon=True)
    t.start()
    time.sleep(0.2)
    ipc.call("settings.set", changes={"apps.twitch.chat": "side"})
    t.join(3)
    assert got and got[0]["topic"] == "settings.changed" and got[0]["data"] == {"apps.twitch.chat": "side"}


def test_wifi_password_never_on_a_command_line(daemon, box):
    daemon.answers[("nmcli", "--wait")] = (0, "")
    ipc.call("network.wifi_connect", ssid="Home Net", password="hunter2hunter2")
    assert not any("hunter2hunter2" in " ".join(c) for c in daemon.calls)
    kf = box / "etc/NetworkManager/system-connections/couchbox-Home_Net.nmconnection"
    assert "psk=hunter2hunter2" in kf.read_text() and oct(kf.stat().st_mode)[-3:] == "600"
    with pytest.raises(ipc.IpcError, match="8 to 63"):
        ipc.call("network.wifi_connect", ssid="x", password="short")
    with pytest.raises(ipc.IpcError, match="control characters"):
        ipc.call("network.wifi_connect", ssid="x", password="abcdefgh\n[evil]")


def test_wifi_scan_parses_nmcli(daemon):
    daemon.answers[("nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY,FREQ")] = (
        0,
        " :Neighbour:40:WPA2:2437 MHz\n*:Home\\:5G:80:WPA2:5180 MHz\n :Home\\:5G:30:WPA2:2412 MHz\n :Cafe:70::2462 MHz\n",
    )
    nets = ipc.call("network.wifi_scan")
    assert nets[0] == {"ssid": "Home:5G", "signal": 80, "secure": True, "connected": True, "band": "5 GHz"}
    assert {n["ssid"] for n in nets} == {"Home:5G", "Neighbour", "Cafe"}
    assert next(n for n in nets if n["ssid"] == "Cafe")["secure"] is False


def test_write_permission_rules(monkeypatch):
    import grp

    monkeypatch.setattr(os, "getuid", lambda: 4242)
    assert server.allowed_to_write(0, 0)
    assert server.allowed_to_write(4242, 4242)  # the daemon's own user (tests)
    monkeypatch.setattr(grp, "getgrnam", lambda n: (_ for _ in ()).throw(KeyError(n)))
    assert not server.allowed_to_write(1234, 1234)


def test_phone_pairing_needs_write_access():
    assert api.METHODS["phone.pairing"].write is True
    for name in ("settings.set", "secrets.set", "network.wifi_connect", "encryption.encrypt", "updates.install", "system.reboot"):
        assert api.METHODS[name].write, name
    for name in ("settings.get", "secrets.status", "updates.status", "encryption.status"):
        assert not api.METHODS[name].write, name
