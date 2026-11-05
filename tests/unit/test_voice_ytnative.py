"""The voice tools with YouTube in Couchbox's own app: everything goes through its control socket
(faked here with the app's made-up pages, youtube.Demo)."""

import pytest

from couchbox import appctl
from couchbox.services import youtube
from couchbox.voice import tools, ytnative


class App:
    """couchbox-yt's control socket: state, screen, open, and its back-end calls."""

    def __init__(self, signed_in=True):
        self.yt = youtube.Demo("demo1:" if signed_in else "")
        self.st = {"page": "home", "section": "home", "profile": "Robin Vale" if signed_in else "guest"}
        self.opened, self.calls, self.up = [], [], True

    def __call__(self, site, req, timeout=30):
        assert site == "yt"
        if not self.up:
            raise appctl.NotRunning(site)
        op = req["op"]
        if op == "ping":
            return {"ok": True}
        if op == "state":
            return dict(self.st)
        if op == "screen":
            return dict(self.st, shown={"op": "home", "page": self.yt.home()})
        if op == "open":
            self.opened.append(req["target"])
            return {"ok": True}
        if op == "media":
            return {"ok": True}
        assert op == "call"
        fn, a = req["fn"], req["args"]
        self.calls.append(fn)
        return {
            "home": lambda: self.yt.home(),
            "search": lambda: self.yt.search(a["q"]),
            "browse": lambda: self.yt.browse(a["id"], a.get("params", "")),
            "channel": lambda: self.yt.channel(a["id"]),
            "subscriptions": lambda: self.yt.subscriptions(),
        }[fn]()


@pytest.fixture
def app(monkeypatch):
    a = App()
    monkeypatch.setattr(appctl, "call", a)
    monkeypatch.setattr(tools, "raise_window", lambda *x: None)
    return a


def test_search_shows_it_and_lists_the_results(app):
    out = tools.youtube("search", query="tides")
    assert app.opened == ["search:tides"]
    first = out.splitlines()[0]
    assert first.startswith("video demo") and " | " in first and "views" in first


def test_play_open_and_home(app):
    assert tools.youtube("play", id="abcdefghijk") == "Playing video abcdefghijk."
    tools.youtube("open", id="UCdemo0000000000000orbit")
    tools.youtube("open", id="PLabc12345678")
    tools.youtube("home")
    assert app.opened == ["video:abcdefghijk", "channel:UCdemo0000000000000orbit", "playlist:PLabc12345678", "home"]
    assert ytnative.browse_id("PLabc12345678") == ytnative.browse_id("VLPLabc12345678") == "VLPLabc12345678"


def test_resume_plays_the_latest_unfinished_match_from_the_history(app):
    out = tools.youtube("resume", query="kettle crumb")
    assert app.opened and app.opened[-1].startswith("video:demo")
    assert "Kettle & Crumb" in out
    assert tools.youtube("resume", query="no such thing") == "Nothing from no such thing in the recent YouTube history."


def test_latest_and_channels_use_the_subscriptions(app):
    out = tools.youtube("latest", query="Orbit Lab, Nobody Here")
    assert out.startswith("Orbit Lab (newest first):") and "on screen now" in out and "Nobody Here: not a subscribed channel" in out
    assert app.opened == ["channel:UCdemo0000000000000orbit"]
    assert tools.youtube("channels", query="tempo") == "channel UCdemo00000000000tempo | Tempo Room"


def test_a_guest_is_told_to_sign_in(monkeypatch):
    a = App(signed_in=False)
    monkeypatch.setattr(appctl, "call", a)
    monkeypatch.setattr(tools, "raise_window", lambda *x: None)
    assert tools.youtube("history") == ytnative.NOT_SIGNED_IN
    assert "video demo" in tools.youtube("home")


def test_list_says_whats_on_screen(app):
    out = tools.youtube("list")
    assert out.startswith("YouTube in front, on its home page.") and "video demo" in out
    app.st = {"page": "player", "title": "How Tides Really Work", "paused": True, "position": 65, "duration": 600, "profile": "x"}
    assert tools.youtube("list") == "YouTube in front: “How Tides Really Work” paused at 1:05 of 10:00."


def test_not_running_starts_the_app_on_the_target(app, monkeypatch):
    started = []
    app.up = False

    def launch(target=""):
        started.append(target)
        app.up = True

    monkeypatch.setattr(ytnative, "launch", launch)
    monkeypatch.setattr(ytnative.time, "sleep", lambda s: None)
    assert tools.youtube("play", id="abcdefghijk") == "Playing video abcdefghijk."
    assert started == ["video:abcdefghijk"] and app.opened == []


def test_launch_runs_in_an_app_unit_as_the_tv_user(monkeypatch):
    monkeypatch.setattr(ytnative.os, "geteuid", lambda: 0)
    cmd = ytnative.launch_command("search:x", unit="app-couchbox-yt@t.service")
    assert cmd[:5] == ["systemd-run", "--user", "-M", "tv@", "--quiet"]
    assert cmd[-3:] == [ytnative.EXE, "--open", "search:x"]
    assert "--unit=app-couchbox-yt@t.service" in cmd


def test_media_and_screen_note_follow_the_native_app(app, monkeypatch):
    monkeypatch.setattr(tools, "active_window", lambda: {"class": "couchbox-yt", "app": "couchbox-yt"})
    app.st = {"page": "player", "title": "Inside a Lighthouse Lens", "paused": False, "position": 5, "duration": 300}
    monkeypatch.setattr(tools.time, "sleep", lambda s: None)
    assert tools.media("pause") == "“Inside a Lighthouse Lens”: playing at 0:05 of 5:00"
    assert tools.screen_summary() == "Screen: YouTube in front: “Inside a Lighthouse Lens” playing at 0:05 of 5:00."
    app.st = {"page": "search", "section": "search", "query": "bread"}
    assert tools.typing_target() == ("youtube", None)
    assert tools.enter_text("sourdough") == "searched" and app.opened[-1] == "search:sourdough"
