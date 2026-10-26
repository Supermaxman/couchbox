"""Spotify's voice tool (it follows the home row and goes through the background service) and
the phone page's sign-in routes (Spotify sends the phone back there over Tailscale's https)."""

import importlib.machinery
import importlib.util
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from couchbox import appctl, settings
from couchbox.voice import tools

REPO = Path(__file__).resolve().parents[2]


def names():
    return {t["function"]["name"] for t in tools.schemas()}


def test_spotify_tool_follows_its_tile_and_its_service(monkeypatch):
    assert "spotify" in names()
    settings.update({"home.hidden": ["spotify"]})
    assert "spotify" not in names()
    settings.update({"home.hidden": []})

    def not_running(site, req, **k):
        raise appctl.NotRunning(site)

    monkeypatch.setattr(tools.appctl, "call", not_running)
    assert tools.run_tool("spotify", {"action": "play", "query": "jazz"}).startswith("Spotify isn't set up")
    sent = []
    monkeypatch.setattr(tools.appctl, "call", lambda site, req, **k: sent.append((site, req)) or {"result": "Playing Jazz."})
    assert tools.run_tool("spotify", {"action": "make_playlist", "name": "Mix", "songs": ["A - B"] * 80}) == "Playing Jazz."
    site, req = sent[-1]
    assert site == "spotify-connect" and req["op"] == "voice" and len(req["songs"]) == 60


@pytest.fixture
def phone():
    pytest.importorskip("evdev")
    loader = importlib.machinery.SourceFileLoader("phone", str(REPO / "bin/couchbox-phone"))
    spec = importlib.util.spec_from_loader("phone", loader)
    m = importlib.util.module_from_spec(spec)
    loader.exec_module(m)
    srv = m.Server(("::1", 0), m.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://[::1]:{srv.server_address[1]}"
    srv.shutdown()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def get(url):
    try:
        r = urllib.request.build_opener(NoRedirect).open(url, timeout=5)
        return r.status, dict(r.headers), r.read().decode()
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers), err.read().decode()


def test_phone_page_signs_in_through_the_app_or_its_service(phone, monkeypatch):
    calls = []

    def call(site, req, **k):
        calls.append((site, req))
        if site == "spotify":
            raise appctl.NotRunning(site)  # the app is closed: its service answers
        if req["fn"] == "login_url":
            return {"url": "https://accounts.spotify.com/authorize?client_id=x"}
        return {"user": "Max", "signedIn": True} if req["args"].get("state") == "good" else {"error": "That sign-in doesn't match this TV."}

    monkeypatch.setattr(appctl, "call", call)
    code, headers, _ = get(phone + "/spotify/login")
    assert code == 302 and headers["Location"].startswith("https://accounts.spotify.com/authorize")
    code, _, body = get(phone + "/spotify/callback?code=abc&state=good")
    assert code == 200 and "Signed in to Spotify as Max" in body
    assert calls[-1] == ("spotify-connect", {"op": "call", "fn": "login_finish", "args": {"code": "abc", "state": "good"}})
    code, _, body = get(phone + "/spotify/callback?code=abc&state=bad")
    assert code == 400 and "doesn&#x27;t match" in body
