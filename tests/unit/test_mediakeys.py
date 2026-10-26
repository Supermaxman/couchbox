"""The remote's media keys go to whatever is playing (couchbox.mediakeys), and couchbox-input
hands them over (data/input key maps, media: targets)."""

import importlib.machinery
import importlib.util
import pathlib
import tomllib

import pytest

from couchbox import mediakeys as mk

ROOT = pathlib.Path(__file__).resolve().parents[2]

# the players on the box when this was reported: YouTube's page left its media session at
# "playing" over a paused video (Chromium's rate 0), Spotify paused in its background service
YOUTUBE = {
    "name": "org.mpris.MediaPlayer2.chromium.instance3",
    "identity": "VacuumTube",
    "status": "Playing",
    "rate": 0.0,
    "unit": "app-flatpak-rocks.shy.VacuumTube-248885842.scope",
    "desktop": "",
    "changed": 0.0,
}
SPOTIFY = {
    "name": "org.mpris.MediaPlayer2.couchbox_spotify",
    "identity": "Spotify",
    "status": "Paused",
    "rate": 1.0,
    "unit": "couchbox-spotify-connect.service",
    "desktop": "couchbox-spotify",
    "changed": 0.0,
}
JELLYFIN = {
    "name": "org.mpris.MediaPlayer2.jellyfin",
    "identity": "Jellyfin",
    "status": "Paused",
    "rate": 1.0,
    "unit": "app-jellyfin-123.scope",
    "desktop": "",
    "changed": 0.0,
}

WEATHER_WINDOW = {"app": "couchbox-weather", "unit": "app-couchbox\\x2dweather@1.service"}
SPOTIFY_WINDOW = {"app": "couchbox-spotify", "unit": "app-couchbox\\x2dspotify@2.service"}
YOUTUBE_WINDOW = {"app": "rocks.shy.VacuumTube", "unit": YOUTUBE["unit"]}
HOME = {"class": "plasmashell", "shell": True}


def p(base, **kw):
    return dict(base, **kw)


def test_a_playing_claim_at_rate_zero_is_paused():
    assert mk.effective(YOUTUBE) == ("Paused", True)
    assert mk.effective(p(YOUTUBE, rate=1.0)) == ("Playing", False)
    assert mk.effective(SPOTIFY) == ("Paused", False)
    assert mk.effective({"status": ""}) == ("Stopped", False)


def test_the_reported_case_spotify_not_a_stale_youtube():
    # Weather in front, Spotify playing: Play/Pause pauses Spotify
    who, why = mk.choose([YOUTUBE, p(SPOTIFY, status="Playing", changed=100.0)], WEATHER_WINDOW)
    assert who["identity"] == "Spotify" and why == "playing in the background"
    # Spotify paused, nothing else known: it's Spotify that plays again, not the stale YouTube
    who, _ = mk.choose([YOUTUBE, SPOTIFY], WEATHER_WINDOW)
    assert who["identity"] == "Spotify"
    # the Spotify app in front (its window isn't the player's service): Spotify
    who, why = mk.choose([p(YOUTUBE, rate=1.0, changed=200.0), p(SPOTIFY, changed=100.0)], SPOTIFY_WINDOW)
    assert who["identity"] == "Spotify" and why == "the app in front"


def test_the_app_in_front_wins_when_it_has_something_loaded():
    who, why = mk.choose([YOUTUBE, p(SPOTIFY, status="Playing", changed=100.0)], YOUTUBE_WINDOW)
    assert who["identity"] == "VacuumTube" and why == "the app in front"
    # nothing loaded in the app in front: what's playing elsewhere
    who, why = mk.choose([p(YOUTUBE, status="Stopped"), p(SPOTIFY, status="Playing")], YOUTUBE_WINDOW)
    assert who["identity"] == "Spotify" and why == "playing in the background"


def test_otherwise_what_was_paused_last():
    who, why = mk.choose([p(JELLYFIN, changed=300.0), p(SPOTIFY, changed=100.0)], HOME)
    assert who["identity"] == "Jellyfin" and why == "paused last"
    who, _ = mk.choose([p(JELLYFIN, changed=100.0), p(SPOTIFY, changed=300.0)], HOME)
    assert who["identity"] == "Spotify"


def test_playing_beats_paused_and_the_latest_start_wins():
    players = [p(JELLYFIN, changed=500.0), p(SPOTIFY, status="Playing", changed=100.0), p(YOUTUBE, rate=1.0, changed=200.0)]
    who, _ = mk.choose(players, HOME)
    assert who["identity"] == "VacuumTube"


def test_nothing_loaded_anywhere():
    assert mk.choose([], HOME) == (None, "nothing is playing or paused")
    assert mk.choose([p(SPOTIFY, status="Stopped")], SPOTIFY_WINDOW)[0] is None


def test_play_pause_says_which_so_a_stale_player_still_obeys():
    assert mk.method_for("playpause", YOUTUBE) == ("Play", ())  # it claims Playing, but is paused
    assert mk.method_for("playpause", p(YOUTUBE, rate=1.0)) == ("Pause", ())
    assert mk.method_for("playpause", SPOTIFY) == ("Play", ())
    assert mk.method_for("stop", SPOTIFY) == ("Pause", ())
    assert mk.method_for("rewind", SPOTIFY) == ("Seek", (-10_000_000,))
    assert mk.method_for("forward", SPOTIFY) == ("Seek", (10_000_000,))
    assert mk.method_for("next", SPOTIFY) == ("Next", ())
    with pytest.raises(ValueError):
        mk.method_for("eject", SPOTIFY)


def test_units_from_cgroups():
    assert (
        mk.unit_of("0::/user.slice/user-1001.slice/user@1001.service/app.slice/couchbox-spotify-connect.service")
        == "couchbox-spotify-connect.service"
    )
    assert (
        mk.unit_of("0::/user.slice/user-1001.slice/user@1001.service/app.slice/app-flatpak-rocks.shy.VacuumTube-1.scope")
        == "app-flatpak-rocks.shy.VacuumTube-1.scope"
    )
    # shared by unrelated processes: never a match
    assert mk.unit_of("0::/user.slice/user-1000.slice/session-430.scope") == ""
    assert mk.unit_of("0::/user.slice/user-1001.slice/user@1001.service/init.scope") == ""
    assert mk.unit_of("0::/user.slice/user-1001.slice/user@1001.service") == ""
    assert not mk.belongs(SPOTIFY, {"app": "", "unit": ""})
    assert not mk.belongs(SPOTIFY, dict(SPOTIFY_WINDOW, **{"shell": True}))


def test_key_maps_send_media_keys_to_couchbox_mediakeys():
    m = tomllib.loads((ROOT / "data/input/default.toml").read_text())
    fire = m["device"]["fire-remote"]["map"]
    assert fire["KEY_PLAYPAUSE"] == "media:playpause"
    assert fire["KEY_REWIND"] == "media:rewind" and fire["KEY_FASTFORWARD"] == "media:forward"
    for sec in m["device"].values():
        for dst in sec.get("map", {}).values():
            if dst.startswith("media:"):
                assert dst.split(":", 1)[1] in mk.ACTIONS


def test_couchbox_input_reads_media_targets(tmp_path, monkeypatch):
    pytest.importorskip("evdev")
    loader = importlib.machinery.SourceFileLoader("couchbox_input", str(ROOT / "bin/couchbox-input"))
    spec = importlib.util.spec_from_loader("couchbox_input", loader)
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setenv("COUCHBOX_INPUT_CONFIG", str(ROOT / "data/input/default.toml"))
    loader.exec_module(mod)
    assert mod.MEDIA_ACTIONS == mk.ACTIONS
    sections = dict((name, km) for name, _, km in mod.load_sections(str(ROOT / "data/input/default.toml")))
    keymap = sections["fire-remote"][0]
    e = mod.e
    assert keymap[e.KEY_PLAYPAUSE] == ("media", "playpause", e.KEY_PLAYPAUSE)
    assert keymap[e.KEY_REWIND] == ("media", "rewind", e.KEY_REWIND)
    bad = tmp_path / "bad.toml"
    bad.write_text('[device.x]\nmatch = { vendor = "0171" }\n[device.x.map]\nKEY_PLAYPAUSE = "media:eject"\n')
    with pytest.raises(SystemExit):
        mod.load_sections(str(bad))


def test_couchbox_input_passes_the_key_on_only_when_nothing_was_done(monkeypatch):
    pytest.importorskip("evdev")
    from couchbox import appctl

    loader = importlib.machinery.SourceFileLoader("couchbox_input", str(ROOT / "bin/couchbox-input"))
    spec = importlib.util.spec_from_loader("couchbox_input", loader)
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setenv("COUCHBOX_INPUT_CONFIG", str(ROOT / "data/input/default.toml"))
    loader.exec_module(mod)

    def answer(reply):
        def call(site, req, timeout=30):
            assert site == "mediakeys" and req == {"op": "key", "action": "playpause"}
            if isinstance(reply, Exception):
                raise reply
            return reply

        return call

    monkeypatch.setattr(appctl, "call", answer({"player": "org.mpris.MediaPlayer2.couchbox_spotify", "did": "Pause"}))
    assert mod.media_key("playpause")["pass"] is False
    monkeypatch.setattr(appctl, "call", answer({"player": None, "why": "nothing is playing or paused"}))
    assert mod.media_key("playpause")["pass"] is True
    monkeypatch.setattr(appctl, "call", answer(appctl.NotRunning("mediakeys")))
    assert mod.media_key("playpause")["pass"] is True
    # slow to answer: it may still have done it, so the key doesn't go on too
    monkeypatch.setattr(appctl, "call", answer(TimeoutError("timed out")))
    assert mod.media_key("playpause")["pass"] is False
