"""couchbox-memory finds every app started from the home screen (its own systemd unit), not
just YouTube, Jellyfin and the web apps, so an idle Twitch or Settings gets closed too."""

import importlib.machinery
import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TV = 1001
TWITCH = "app-couchbox\\x2dtwitch@db52c8d1757a4d5794a379a9126e172f.service"


def load():
    loader = importlib.machinery.SourceFileLoader("couchbox_memory", str(REPO / "bin/couchbox-memory"))
    spec = importlib.util.spec_from_loader("couchbox_memory", loader)
    m = importlib.util.module_from_spec(spec)
    loader.exec_module(m)
    return m


@pytest.fixture
def mem():
    return load()


def test_which_units_are_apps(mem):
    assert mem.unit_app(TWITCH) == "couchbox-twitch"
    assert mem.unit_app("app-flatpak-org.example.Player-123.scope") == "org.example.Player"
    assert mem.unit_app("app-org.kde.kdeconnect.daemon@autostart.service") == ""
    assert mem.unit_app("app-geoclue\\x2ddemo\\x2dagent@autostart.service") == ""
    assert mem.unit_app("app-org.kde.plasma.bigscreen.inputhandler@62e3.service") == ""
    assert mem.unit_app("couchbox-spotify-connect.service") == ""
    assert mem.app_name("couchbox-twitch") == "Twitch" and mem.app_name("org.example.Player") == "Player"


def test_launched_apps_leave_out_those_already_watched(mem, monkeypatch):
    units = {10: TWITCH, 11: TWITCH, 20: "app-couchbox\\x2djellyfin@aa.service", 30: "plasma-plasmashell.service"}
    monkeypatch.setattr(mem, "unit_of", lambda pid: units.get(pid, ""))
    plist = [(10, 1, "python3", TV), (11, 10, "python3", TV), (20, 1, "jellyfin-deskto", TV), (30, 1, "plasmashell", TV)]
    out = mem.launched_apps(TV, plist, covered={20})
    assert out == {TWITCH: ("couchbox-twitch", 10, [10, 11])}


def test_a_paused_app_in_the_background_is_idle_and_a_playing_one_is_not(mem, monkeypatch):
    monkeypatch.setattr(mem, "probe", lambda: {})
    monkeypatch.setattr(mem, "unit_of", lambda pid: TWITCH)
    plist = [(10, 1, "python3", TV)]
    monkeypatch.setattr(mem, "front_and_players", lambda uid: ("plasma-plasmashell.service", {TWITCH: False}))
    apps, groups = mem.open_apps(TV, plist)
    assert apps["app:" + TWITCH] == {"name": "Twitch", "focus": False, "playing": False}
    assert groups["app:" + TWITCH] == (10, [10])
    monkeypatch.setattr(mem, "front_and_players", lambda uid: (TWITCH, {TWITCH: True}))
    apps, _ = mem.open_apps(TV, plist)
    assert apps["app:" + TWITCH]["focus"] and apps["app:" + TWITCH]["playing"]


def test_nothing_is_closed_blind_when_mediakeys_cannot_be_asked(mem, monkeypatch):
    monkeypatch.setattr(mem, "probe", lambda: {})
    monkeypatch.setattr(mem, "unit_of", lambda pid: TWITCH)
    monkeypatch.setattr(mem, "front_and_players", lambda uid: None)
    apps, _ = mem.open_apps(TV, [(10, 1, "python3", TV)])
    assert apps["app:" + TWITCH]["playing"]
