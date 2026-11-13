"""couchbox-memory finds every app started from the home screen (its own systemd unit), not
just YouTube, Jellyfin and the web apps, so an idle Twitch or Settings gets closed too."""

import importlib.machinery
import importlib.util
import os
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
    assert mem.app_name("couchbox-yt") == "YouTube"  # the YouTube tile


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


def test_the_home_screen_reloads_after_an_update_only_when_no_one_would_notice(mem, monkeypatch, tmp_path):
    flag = tmp_path / "home-stale"
    flag.touch()
    monkeypatch.setattr(mem, "HOME_STALE", str(flag))
    restarted = []
    import couchbox.home

    monkeypatch.setattr(couchbox.home, "restart_plasmashell", lambda: restarted.append(1))
    m = mem.Memory.__new__(mem.Memory)
    m.uid, m.log = TV, lambda *_: None
    home = {"window": {"shell": True}, "players": []}
    state = {"st": home}
    monkeypatch.setattr(mem, "media_state", lambda uid: state["st"])
    m.reload_home({}, quiet=60)  # the remote was used a minute ago
    m.reload_home({"YouTube": {"playing": True}}, quiet=3600)  # something plays
    state["st"] = {"window": {"shell": False, "unit": TWITCH}, "players": []}
    m.reload_home({}, quiet=3600)  # an app is in front
    state["st"] = {"window": {"shell": True}, "players": [{"effective": "Playing"}]}
    m.reload_home({}, quiet=3600)  # Spotify plays on the home screen
    assert not restarted and flag.exists()
    state["st"] = home
    m.reload_home({}, quiet=3600)
    assert restarted == [1] and not flag.exists()


def test_restart_finds_the_apps_units(tmp_path, monkeypatch):
    """The home tile's Restart (couchbox.apps.app_units): the user's processes in the app's units."""
    from couchbox import apps

    me = os.geteuid()
    for pid, unit in ((10, TWITCH), (11, TWITCH), (12, "app-couchbox\\x2dyt@ontv-1.service"), (13, "session.scope")):
        d = tmp_path / str(pid)
        d.mkdir()
        (d / "cgroup").write_text(f"0::/user.slice/user-{me}.slice/user@{me}.service/app.slice/{unit}\n")
    twitch = apps.App(id="twitch", name="Twitch", desktop="couchbox-twitch.desktop")
    assert apps.app_units(twitch, {}, proc=str(tmp_path)) == [TWITCH]
    yt = apps.App(id="youtube", name="YouTube", desktop="couchbox-yt.desktop")
    monkeypatch.setattr(apps, "youtube_native", lambda s=None: True)
    assert apps.app_units(yt, {}, proc=str(tmp_path)) == ["app-couchbox\\x2dyt@ontv-1.service"]
