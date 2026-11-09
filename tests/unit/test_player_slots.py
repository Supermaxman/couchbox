"""Every MpvVideo function the QML calls (video.x(...), Y.video.x(...)) is one QML can call: a Slot
of couchbox.player.MpvVideo (the stop() that lost its decorator stopped no video in any app)."""

import re
from pathlib import Path

import pytest

UI = Path(__file__).resolve().parents[2] / "ui"


def called():
    names = set()
    for f in UI.rglob("*.qml"):
        if "stubs" in f.parts:
            continue
        names |= set(re.findall(r"\bvideo\.([a-zA-Z]+)\(", f.read_text()))
    return names


def test_qml_calls_only_slots():
    player = pytest.importorskip("couchbox.player")
    mo = player.MpvVideo.staticMetaObject
    slots = {bytes(mo.method(i).name()).decode() for i in range(mo.methodCount())}
    missing = sorted(n for n in called() if n not in slots)
    assert not missing, f"called from QML but not Slots: {missing}"


def test_the_stub_has_them_too():
    stub = (UI / "stubs/CouchPlayer/MpvVideo.qml").read_text()
    missing = sorted(n for n in called() if not re.search(rf"function {n}\(", stub))
    assert not missing, f"missing from the QML stub (screenshots): {missing}"


def test_a_new_file_is_covered_until_its_own_first_picture():
    """hasFrame: false from a new file's load until a render after mpv has its picture, so the apps
    cover the item meanwhile (it still holds the file before's last picture)."""
    import types

    player = pytest.importorskip("couchbox.player")
    emitted = []
    v = types.SimpleNamespace(_has_frame=True, _await_frame="", hasFrameChanged=types.SimpleNamespace(emit=lambda: emitted.append(1)))
    player.MpvVideo._new_file(v)  # loadfile: waiting for mpv's playback-restart
    assert (v._has_frame, v._await_frame, len(emitted)) == (False, "restart", 1)
    player.MpvVideo._on_prop(v, "frame", True)  # (a stray report before then: still covered)
    assert not v._has_frame
    v._await_frame = ""  # (the render after playback-restart drew it, and says so)
    player.MpvVideo._on_prop(v, "frame", True)
    assert v._has_frame and len(emitted) == 2
    player.MpvVideo._new_file(v, "")  # stop(): nothing shown, nothing awaited
    assert (v._has_frame, v._await_frame) == (False, "")


def test_a_preloaded_video_plays_with_sound_after_the_warm_up():
    """warmUp()'s clip is opened muted and stays loaded 2.5 s; a card preloaded meanwhile used to
    take that mute for the viewer's, and its video played silent. Only toggleMute is the viewer's."""
    import types

    player = pytest.importorskip("couchbox.player")

    class FakeMpv(dict):
        mute = True  # warmUp's clip is loaded: mute=yes for that file
        pause = True

        def command(self, *a):
            pass

    v = types.SimpleNamespace(
        mpv=FakeMpv(), _preloaded=None, _ended=True, _paused=True, _pos=0.0, _loads=0, _muted=False, PRELOAD_CACHE="10MiB",
        _rate=types.SimpleNamespace(suspend=lambda on: None), _error="", endedChanged=types.SimpleNamespace(emit=lambda: None),
        frameReady=types.SimpleNamespace(emit=lambda: None), _new_file=lambda *a: None,
    )  # fmt: skip
    player.MpvVideo.preload(v, "https://v/1", 0.0, "")
    v._play_preloaded = lambda start: player.MpvVideo._play_preloaded(v, start)
    player.MpvVideo._play_preloaded(v, 0.0)
    assert v.mpv.mute is False and v.mpv.pause is False
    v._muted = True  # the viewer turned the sound off (M): a preloaded video keeps it off
    player.MpvVideo.preload(v, "https://v/2", 0.0, "")
    player.MpvVideo._play_preloaded(v, 0.0)
    assert v.mpv.mute is True
