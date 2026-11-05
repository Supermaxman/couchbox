"""Playback settings (couchbox.playback): the TV mode for a frame rate, the refresh-rate Follower
that switches and switches back, the night filter, passthrough codecs from the TV's ELD, and the
settings' wiring."""

import json

import pytest

from couchbox import playback, settings
from couchbox.daemon import apply

G, C = "\x1b[01;32m", "\x1b[0;0m"
# kscreen-doctor -o on the Pi (Plasma 6), colours and all; HDMI-A-2 has nothing plugged in
KSCREEN = f"""{G}Output: {C}1 HDMI-A-1 6b1f53c3-0000
\t{G}enabled{C}
\t{G}connected{C}
\t{G}priority 1{C}
\t\x1b[01;33mHDMI{C}
\t\x1b[01;34mModes: {C} 1:{G}1920x1080@60.00*{C}! 2:1920x1080@59.94 3:1920x1080@50.00 4:1920x1080@30.00 5:1920x1080@29.97 \
6:1920x1080@25.00 7:1920x1080@24.00 8:1920x1080@23.98 9:1280x720@60.00 10:1280x720@50.00 11:3840x2160@30.00 12:3840x2160@24.00
\t\x1b[01;33mCustom modes:{C} None
\t\x1b[01;33mGeometry: {C}0,0 1280x720
\t\x1b[01;33mScale: {C}1.5
{G}Output: {C}2 HDMI-A-2 1d2e3f40-0000
\t\x1b[01;31mdisabled{C}
\t\x1b[01;31mdisconnected{C}
\t\x1b[01;34mModes: {C}
"""


def tv(current="1"):
    o = playback.parse_outputs(KSCREEN)[0]
    o.current = current
    return o


def test_kscreen_doctor_output_is_read():
    a, b = playback.parse_outputs(KSCREEN)
    assert (a.name, a.enabled, a.connected, a.current) == ("HDMI-A-1", True, True, "1")
    assert len(a.modes) == 12 and a.mode("8") == playback.Mode("8", 1920, 1080, 23.98)
    assert (b.name, b.enabled, b.connected, b.modes) == ("HDMI-A-2", False, False, [])


@pytest.mark.parametrize(
    "fps,rate",
    [
        (23.976, 23.98),  # films
        (23.976023976, 23.98),
        (24.0, 24.0),
        (25.0, 50.0),  # PAL: 50 rather than 25 (menus, flicker)
        (50.0, 50.0),
        (29.97, 59.94),  # NTSC TV
        (59.94, 59.94),
        (30.0, 60.0),
        (60.0, 60.0),
    ],
)
def test_mode_for_a_frame_rate(fps, rate):
    m = playback.pick_mode(fps, tv())
    assert (m.width, m.height, m.rate) == (1920, 1080, rate)


def test_no_mode_fits_odd_frame_rates():
    assert playback.pick_mode(12.0, tv()) is None
    assert playback.pick_mode(15.0, tv()) is None
    assert playback.pick_mode(48.0, tv()) is None
    assert playback.pick_mode(0, tv()) is None


def test_close_rate_when_the_tv_has_no_exact_one():
    o = tv()
    o.modes = [m for m in o.modes if m.rate != 23.98]
    assert playback.pick_mode(23.976, o).rate == 24.0


def test_mode_keeps_the_current_resolution():
    assert str(playback.pick_mode(23.976, tv(current="11"))) == "3840x2160@24"
    assert str(playback.pick_mode(25, tv(current="9"))) == "1280x720@50"


def test_settings_mode_is_the_nearest_rate():
    assert playback.spec_mode(tv(), "1920x1080@60").id == "1"  # 60.00, not 59.94
    assert playback.spec_mode(tv(), "1280x720@60").id == "9"
    assert playback.spec_mode(tv(), "2560x1440@60") is None


def test_set_rate_switches_only_when_needed(runner):
    runner.answers[("kscreen-doctor", "-o")] = (0, KSCREEN)
    assert playback.set_rate(23.976) == ["HDMI-A-1"]
    assert runner.ran("kscreen-doctor", "output.HDMI-A-1.mode.8")
    assert not runner.ran("kscreen-doctor", "output.HDMI-A-2.mode.8")  # nothing on that port
    runner.calls.clear()
    assert playback.set_rate(None) == []  # already 1920x1080@60
    assert runner.calls == [["kscreen-doctor", "-o"]]
    assert playback.set_rate(30.0) == []  # 60 Hz suits 30 fps: no switch
    assert not runner.ran("kscreen-doctor", "output.HDMI-A-1.mode.1")


def test_set_rate_puts_settings_mode_back(runner):
    runner.answers[("kscreen-doctor", "-o")] = (
        0,
        KSCREEN.replace("1:\x1b[01;32m1920x1080@60.00*", "1:1920x1080@60.00").replace("8:1920x1080@23.98", "8:1920x1080@23.98*"),
    )
    settings.update({"display.mode": "1920x1080@60"})
    assert playback.set_rate(None) == []
    assert runner.ran("kscreen-doctor", "output.HDMI-A-1.mode.1")


# ------------------------------------------------------------------ the Follower


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def follow(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    calls = []

    def switch(fps):
        calls.append(fps)
        return ["HDMI-A-1"] if fps and abs(fps - 30) > 0.1 and abs(fps - 60) > 0.1 else []

    clock = Clock()

    def make(pid=100, who="a", front=lambda: True):
        return playback.Follower(pid=pid, who=who, switch=switch, clock=clock, front=front)

    make.calls, make.clock = calls, clock
    return make


def playing(path="film.mkv", fps=23.976, duration=6000.0, container=None, paused=False):
    return {
        "path": path,
        "idle": False,
        "eof": False,
        "paused": paused,
        "duration": duration,
        "container_fps": container if container is not None else fps,
        "est_fps": fps,
    }


STOPPED = {"path": None, "idle": True, "eof": False, "paused": False, "duration": None, "container_fps": None, "est_fps": None}


def run(fol, snap, seconds, passive=False, shown=True):
    for _ in range(seconds):
        fol.clock.t += 1
        fol.step(snap, passive=passive, shown=shown)


def test_a_film_switches_once_its_frame_rate_holds(follow):
    f = follow()
    run(f, playing(), 1)
    assert follow.calls == []  # the declared rate has to read the same twice
    run(f, playing(), 30)
    assert follow.calls == [pytest.approx(23.976)]  # once
    assert playback.owner() == {"pid": 100, "who": "a", "fps": pytest.approx(23.976)}


def test_the_container_rate_is_used_only_when_it_agrees(follow):
    f = follow()
    run(f, playing(fps=23.98, container=90000.0), 5)
    assert follow.calls == [pytest.approx(23.98)]


def test_an_unsteady_frame_rate_waits_then_gives_up(follow):
    f = follow()
    for i in range(40):
        follow.clock.t += 1
        f.step(playing(fps=24.0 if i % 2 else 30.0))
    assert follow.calls == []


@pytest.mark.parametrize("snap", [playing(duration=None), playing(duration=0), playing(duration=95.0)], ids=["live", "live0", "clip"])
def test_live_streams_and_clips_leave_the_tv_be(follow, snap):
    f = follow()
    run(f, snap, 10)
    assert follow.calls == []


def test_back_to_settings_mode_only_after_a_few_seconds_stopped(follow):
    f = follow()
    run(f, playing(), 5)
    run(f, STOPPED, int(playback.RESTORE_AFTER) - 2)
    assert follow.calls == [pytest.approx(23.976)]
    run(f, STOPPED, 3)
    assert follow.calls == [pytest.approx(23.976), None]
    assert playback.owner() is None
    run(f, STOPPED, 30)
    assert len(follow.calls) == 2  # once


def test_next_episode_doesnt_switch_twice(follow):
    f = follow()
    run(f, playing("ep1"), 5)
    run(f, STOPPED, 3)  # the next one starts within RESTORE_AFTER
    run(f, playing("ep2"), 10)
    assert follow.calls == [pytest.approx(23.976), pytest.approx(23.976)]  # the 2nd finds the TV there already: no kscreen switch


def test_eof_counts_as_stopped(follow):
    f = follow()
    run(f, playing(), 5)
    run(f, dict(playing(), eof=True), 12)
    assert follow.calls[-1] is None


def test_a_live_stream_after_a_film_goes_back_at_once(follow):
    f = follow()
    run(f, playing(), 5)
    run(f, playing("twitch", fps=60.0, duration=None), 5)
    assert follow.calls == [pytest.approx(23.976), None]


def test_turning_it_off_puts_the_mode_back(follow):
    f = follow()
    run(f, playing(), 5)
    f.set_enabled(False)
    assert follow.calls[-1] is None
    run(f, playing(), 10)
    assert len(follow.calls) == 2
    f.set_enabled(True)  # the playing film is looked at again
    run(f, playing(), 5)
    assert follow.calls[-1] == pytest.approx(23.976)


def test_a_camera_popup_doesnt_take_the_tv_from_a_film(follow):
    film, popup = follow(100, "jellyfin"), follow(200, "popup")
    run(film, playing(), 5)
    run(popup, playing("camera", fps=15.0, duration=None), 5, passive=True)
    assert follow.calls == [pytest.approx(23.976)]
    assert playback.owner()["who"] == "jellyfin"


def test_twitch_after_a_paused_film_takes_the_tv_and_the_film_takes_it_back(follow):
    film, twitch = follow(100, "jellyfin"), follow(200, "twitch")
    run(film, playing(), 5)
    run(film, playing(paused=True), 2)
    run(twitch, playing("live", fps=60.0, duration=None), 5)
    assert follow.calls == [pytest.approx(23.976), None]
    run(film, playing(paused=True), 3)
    run(film, playing(), 1)  # resumed
    assert follow.calls[-1] == pytest.approx(23.976) and playback.owner()["who"] == "jellyfin"


def test_only_the_owner_puts_the_mode_back_when_closing(follow):
    film, other = follow(100, "a"), follow(100, "b")
    run(film, playing(), 5)
    other.close()
    assert follow.calls == [pytest.approx(23.976)]
    film.close()
    assert follow.calls[-1] is None and playback.owner() is None


def test_the_guard_puts_the_mode_back_when_the_app_is_gone(follow, monkeypatch):
    run(follow(), playing(), 5)
    restored = []
    monkeypatch.setattr(playback, "restore", lambda: restored.append(True))
    monkeypatch.setattr(playback, "alive", lambda pid: False)
    monkeypatch.setattr(playback, "live_settings", lambda: dict(playback.LIVE))
    playback.watch(999)  # someone else's app
    assert restored == []
    playback.watch(100)
    assert restored == [True]


def test_snapshot_reads_mpv_properties():
    props = {"path": "x", "idle-active": False, "estimated-vf-fps": 23.9}

    def get(name):
        if name == "duration":
            raise RuntimeError("unavailable")
        return props.get(name)

    s = playback.snapshot(get)
    assert s["path"] == "x" and s["est_fps"] == 23.9 and s["duration"] is None and s["idle"] is False


# ------------------------------------------------------------------ night mode and passthrough


def test_night_filter():
    assert playback.night_filter(False) == ""
    f = playback.night_filter(True)
    assert f.startswith("@couchbox-night:lavfi=[") and f.endswith("]")
    assert "acompressor=" in f and "alimiter=" in f and "level=0" in f  # no auto-levelling
    assert "," in f.split("[", 1)[1]  # the graph's comma is inside lavfi's brackets


SAMSUNG_ELD = """monitor_present\t\t1
eld_valid\t\t1
monitor_name\t\tSAMSUNG
connection_type\t\tHDMI
sad_count\t\t4
sad0_coding_type\t[0x1] LPCM
sad0_channels\t\t2
sad0_rates\t\t[0xe0] 32000 44100 48000
sad1_coding_type\t[0x2] AC-3
sad1_channels\t\t6
sad2_coding_type\t[0xa] E-AC-3/DD+ (Dolby Digital Plus)
sad2_channels\t\t8
sad3_coding_type\t[0x6] AAC-LC
"""


def test_passthrough_codecs_come_from_the_tvs_eld(box):
    assert playback.eld_codecs(SAMSUNG_ELD) == ["ac3", "eac3"]
    assert playback.eld_codecs(SAMSUNG_ELD + "sad4_coding_type\t[0x7] DTS\n") == ["ac3", "eac3", "dts"]
    assert playback.tv_codecs() == []
    empty = box / "proc/asound/card0/eld#0.0"
    empty.parent.mkdir(parents=True)
    empty.write_text("monitor_present\t\t0\neld_valid\t\t0\nmonitor_name\t\t\n")
    tv_port = box / "proc/asound/card1/eld#0.0"
    tv_port.parent.mkdir(parents=True)
    tv_port.write_text(SAMSUNG_ELD)
    assert playback.tv_codecs() == ["ac3", "eac3"]
    assert playback.tv_codecs("0") == []


def test_spdif_follows_passthrough_and_night_mode():
    assert playback.spdif("off", False, ["ac3", "eac3"]) == ""
    assert playback.spdif("on", False, ["ac3", "eac3"]) == "ac3,eac3"
    assert playback.spdif("on", True, ["ac3", "eac3"]) == ""  # the night filter needs decoded sound
    assert playback.spdif("on", False, []) == ""


def test_jellyfin_conf():
    s = dict(playback.LIVE)
    assert playback.jellyfin_conf(s, ["ac3"]) == {"af": "", "passthrough": []}
    s["audio.passthrough"] = "on"
    assert playback.jellyfin_conf(s, ["ac3", "eac3"]) == {"af": "", "passthrough": ["ac3", "eac3"]}
    s["audio.night_mode"] = True
    assert playback.jellyfin_conf(s, ["ac3"]) == {"af": playback.night_filter(True), "passthrough": []}


def test_codecs_command_for_couchbox_audio(box, capsys):
    port = box / "proc/asound/card1/eld#0.0"
    port.parent.mkdir(parents=True)
    port.write_text(SAMSUNG_ELD)
    playback.main(["codecs", "--pipewire", "--card", "1"])
    assert capsys.readouterr().out.strip() == "AC3 EAC3"


# ------------------------------------------------------------------ settings


def test_settings_and_their_environment():
    sch = settings.schema()["settings"]
    for key, default in (("video.match_rate", False), ("audio.night_mode", False), ("audio.passthrough", "off")):
        assert sch[key]["default"] == default and sch[key]["page"] == "display"
    assert sch["audio.passthrough"]["values"] == ["off", "on"]
    env = settings.env()
    assert (env["COUCHBOX_VIDEO_MATCH_RATE"], env["COUCHBOX_AUDIO_NIGHT_MODE"], env["COUCHBOX_AUDIO_PASSTHROUGH"]) == ("0", "0", "off")
    assert playback.live_settings() == playback.LIVE


def test_live_settings_follow_changes():
    settings.update({"audio.night_mode": True, "audio.passthrough": "on"})
    assert playback.live_settings()["audio.night_mode"] is True
    assert set(playback.LIVE) <= set(settings.schema()["settings"])


def test_passthrough_change_rewrites_the_hdmi_sink(runner):
    s = settings.load()
    apply.apply({"audio.passthrough": "on"}, s)
    assert runner.ran(f"{apply.TOOLS}/couchbox-audio")
    runner.calls.clear()
    apply.apply({"audio.night_mode": True, "video.match_rate": False}, s)  # live in the players: nothing to run
    assert runner.calls == []


def test_owner_file_is_in_the_runtime_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    playback.claim(5, "x", 24.0)
    assert json.loads((tmp_path / "couchbox-rate.json").read_text())["pid"] == 5
    playback.release()
    assert playback.owner() is None


def jittery(i, declared):
    """HLS with software H.264 on the Pi: the measured rate wanders by a few %."""
    return playing("https://cdn.example/ep.m3u8?token=x", fps=23.976 * (1.04 if i % 2 else 0.97), container=declared)


def test_a_declared_rate_wins_over_a_jittery_measurement(follow, capsys):
    f = follow()
    for i in range(4):
        follow.clock.t += 1
        f.step(jittery(i, 23.976023976))
    assert follow.calls == [pytest.approx(23.976, rel=1e-4)]
    log = capsys.readouterr().err
    assert "HLS https" in log and "declared 23.97" in log and "match 23.976 fps (declared rate)" in log
    assert "cdn.example" not in log and "token" not in log  # no addresses in the journal


def test_without_a_declared_rate_a_jittery_measurement_never_switches(follow, capsys):
    f = follow()
    for i in range(40):
        follow.clock.t += 1
        f.step(jittery(i, 0.0))  # nothing declared
    assert follow.calls == []
    assert "Settings mode (no frame rate to go by in 30 s)" in capsys.readouterr().err


@pytest.mark.parametrize("declared", [90000.0, 1000.0, 15.0, -1.0])
def test_a_declared_rate_outside_tv_rates_is_ignored(follow, declared):
    f = follow()
    run(f, playing(fps=25.0, container=declared), 5)
    assert follow.calls == [pytest.approx(25.0)]  # the steady measurement decides


def test_every_decision_is_logged_once_with_its_reason(follow, capsys):
    f = follow()
    run(f, playing("/run/user/1000/nebula.m3u8", duration=95.0), 10)
    run(f, playing("https://x/live.m3u8", fps=60.0, duration=None), 10)
    log = capsys.readouterr().err.splitlines()
    assert len(log) == 2
    assert "HLS file" in log[0] and "duration 95 s" in log[0] and "a clip" in log[0]
    assert "live: no duration" in log[1]


def test_path_kind():
    assert playback.path_kind("https://a/b/master.m3u8?x=1") == "HLS https"
    assert playback.path_kind("/tmp/list.m3u8") == "HLS file"
    assert playback.path_kind("http://127.0.0.1:5000/vod.mp4") == "http"
    assert playback.path_kind(None) == "file"


# ------------------------------------------------------------------ paused out of sight


def test_a_paused_video_whose_page_closed_gives_the_tv_back_and_takes_it_again(follow, capsys):
    f = follow()
    run(f, playing(), 5)
    run(f, playing(paused=True), int(playback.AWAY_AFTER) - 1, shown=False)  # Back: player page gone, video paused
    assert follow.calls == [pytest.approx(23.976)]
    run(f, playing(paused=True), 2, shown=False)
    assert follow.calls[-1] is None and playback.owner() is None
    assert "paused and its player isn't shown" in capsys.readouterr().err
    run(f, playing(paused=True), 20, shown=False)
    assert len(follow.calls) == 2  # once
    run(f, playing(), 1)  # played again
    assert follow.calls[-1] == pytest.approx(23.976) and playback.owner()["who"] == "a"


def test_a_paused_video_behind_another_app_gives_the_tv_back(follow):
    front = [True]
    f = follow(front=lambda: front[0])
    run(f, playing(), 5)
    run(f, playing(paused=True), 30)  # paused in front: keeps the mode
    assert follow.calls == [pytest.approx(23.976)]
    front[0] = False  # the home screen came up
    run(f, playing(paused=True), int(playback.AWAY_AFTER) + 1)
    assert follow.calls[-1] is None
    front[0] = True
    run(f, playing(), 1)
    assert follow.calls[-1] == pytest.approx(23.976)


def test_away_needs_to_last(follow):
    front = [False]
    f = follow(front=lambda: front[0])
    run(f, playing(), 5)
    run(f, playing(paused=True), 5)
    front[0] = True  # back in front within AWAY_AFTER
    run(f, playing(paused=True), 3)
    front[0] = False
    run(f, playing(paused=True), 5)
    assert follow.calls == [pytest.approx(23.976)]


def test_unknown_front_or_playing_out_of_sight_keeps_the_mode(follow):
    f = follow(front=lambda: None)  # couchbox-mediakeys can't be asked: never guess
    run(f, playing(), 5)
    run(f, playing(paused=True), 30)
    g = follow(200, "b", front=lambda: False)
    run(g, playing("other"), 5)
    run(g, playing("other"), 30, shown=False)  # still playing (its sound is on): not "away"
    assert None not in follow.calls


def test_app_in_front(monkeypatch):
    from couchbox import appctl, mediakeys

    window = {}
    monkeypatch.setattr(appctl, "call", lambda site, req, timeout=30: {"window": window, "players": []})
    monkeypatch.setattr(mediakeys, "read_cgroup", lambda pid: f"0::/user.slice/app.slice/app-couchbox\\x2dstreaming-{pid}.scope")
    assert playback.app_in_front(42) is None  # no window known
    window.update(pid=42, unit="")
    assert playback.app_in_front(42) is True
    window.update(pid=7, unit=mediakeys.unit_of("0::/user.slice/app.slice/app-couchbox\\x2dstreaming-42.scope"))
    assert playback.app_in_front(42) is True  # another process of the same app
    window.update({"pid": 7, "unit": "plasma-plasmashell.service", "shell": True})  # the home screen
    assert playback.app_in_front(42) is False

    def down(*a, **k):
        raise appctl.NotRunning("mediakeys")

    monkeypatch.setattr(appctl, "call", down)
    assert playback.app_in_front(42) is None
