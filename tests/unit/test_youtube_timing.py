"""The YouTube app's timing (yttiming): yt-dlp's messages as phases, and the kept measurements."""

from couchbox.services import yttiming as T


def test_ytdlp_messages_become_phases(monkeypatch):
    clock = iter([0.0, 0.2, 1.3, 1.5, 1.55, 1.6])
    monkeypatch.setattr(T.time, "monotonic", lambda: next(clock))
    p = T.Phases()
    p.debug("[youtube] Extracting URL: https://www.youtube.com/watch?v=x")  # no phase of its own
    p.debug("[youtube] abcdefghijk: Downloading webpage")
    p.debug("[youtube] abcdefghijk: Downloading tv samsung player API JSON")
    p.debug("[youtube] abcdefghijk: Downloading player a5c2aafe-main")
    p.debug("[youtube] [jsc:node] Solving JS challenges using node")
    p.debug("[youtube] abcdefghijk: Downloading m3u8 information")
    assert [n for _, n in p.marks] == ["webpage", "api:tv-samsung", "player-js", "js-challenge", "hls-playlist"]
    spans = p.spans(2100)
    assert spans == {"webpage": 1100, "api:tv-samsung": 200, "player-js": 50, "js-challenge": 50, "hls-playlist": 500}


def test_measurements_are_kept_for_the_focus_report():
    T.note("call", op="home", ms=320)
    last = T.recent(1)[0]
    assert last["kind"] == "call" and last["op"] == "home" and last["ms"] == 320 and "at" in last
