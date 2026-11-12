"""The phone page: pairing by typed code (for phones that can't scan, like an iPhone home-screen
app), and key taps slow enough that apps don't drop characters."""

import importlib.machinery
import importlib.util
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from couchbox import secrets

REPO = Path(__file__).resolve().parents[2]
pytest.importorskip("evdev")


@pytest.fixture
def phone():
    loader = importlib.machinery.SourceFileLoader("phone", str(REPO / "bin/couchbox-phone"))
    spec = importlib.util.spec_from_loader("phone", loader)
    m = importlib.util.module_from_spec(spec)
    loader.exec_module(m)
    return m


@pytest.fixture
def server(phone):
    srv = phone.Server(("::1", 0), phone.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield phone, f"http://[::1]:{srv.server_address[1]}"
    srv.shutdown()


def post(url, body, token=""):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json", "X-Couchbox-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as err:
        return err.code, json.load(err)


def test_page_offers_a_code_when_it_has_no_token(server):
    _, base = server
    page = urllib.request.urlopen(base + "/", timeout=5).read().decode()
    assert 'id="pair"' in page and "/pair" in page


def test_typed_code_pairs_the_phone(server):
    _, base = server
    token = secrets.ensure_token()
    assert post(base + "/key", {"key": "up"})[0] == 401
    status, res = post(base + "/pair", {"code": secrets.pair_code(token).lower()})
    assert status == 200 and res["token"] == token


def test_wrong_codes_are_limited(server):
    phone, base = server
    token = secrets.ensure_token()
    for _ in range(phone.PAIR_TRIES):
        assert post(base + "/pair", {"code": "AAAA-AAAA"})[0] == 403
    # even the right code waits out the minute: guessing can't go faster than 5 a minute
    assert post(base + "/pair", {"code": secrets.pair_code(token)})[0] == 429


class FakeKeyboard:
    def __init__(self):
        self.log = []

    def write(self, kind, key, value):
        self.log.append((key, value))

    def syn(self):
        self.log.append("syn")


def test_taps_hold_each_key_and_shift_separately(phone, monkeypatch):
    kb = FakeKeyboard()
    sleeps = []
    monkeypatch.setattr(phone, "ui", lambda: kb)
    monkeypatch.setattr(phone.time, "sleep", sleeps.append)
    e = phone.e
    phone.tap(e.KEY_A, shift=True)
    # Shift goes down in its own frame, the key is held, then released before Shift
    assert kb.log == [(e.KEY_LEFTSHIFT, 1), "syn", (e.KEY_A, 1), "syn", (e.KEY_A, 0), "syn", (e.KEY_LEFTSHIFT, 0), "syn"]
    assert sum(sleeps) >= 0.04
    kb.log.clear()
    sleeps.clear()
    phone.tap(e.KEY_L)
    phone.tap(e.KEY_L)  # double letters: a gap between the release and the next press
    assert kb.log == [(e.KEY_L, 1), "syn", (e.KEY_L, 0), "syn"] * 2
    assert sleeps == [phone.HOLD, phone.GAP] * 2 and phone.GAP >= 0.02


# ------------------------------------------------------------------ Send to TV


def send(url, data, token="", ctype="application/json"):
    req = urllib.request.Request(url, data, {"Content-Type": ctype, "X-Couchbox-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as err:
        return err.code, json.load(err)


@pytest.fixture
def opened(server, monkeypatch):
    """Links the page sends, opened nowhere: [text]."""
    phone, base = server
    got = []

    def open_link(text):
        got.append(text)
        if "fail" in text:
            return phone.links.Result(False, "YouTube didn't start on the TV.", "youtube")
        try:
            phone.links.parse(text)
        except phone.links.BadLink as err:
            return phone.links.Result(False, str(err))
        return phone.links.Result(True, "Playing on the TV: “A video” by Someone", "youtube")

    monkeypatch.setattr(phone.links, "open_link", open_link)
    return phone, base, got


def test_the_page_has_send_to_tv_and_the_shortcut_steps(server):
    _, base = server
    page = urllib.request.urlopen(base + "/", timeout=5).read().decode()
    assert 'id="sendtv"' in page and 'fetch("/send"' in page
    assert "Get Contents of URL" in page and "X-Couchbox-Token" in page and "Shortcut Input" in page


def test_only_paired_phones_send(opened):
    _, base, got = opened
    token = secrets.ensure_token()
    assert send(base + "/send", b'{"url": "https://youtu.be/dQw4w9WgXcQ"}')[0] == 401
    assert send(base + "/send", b'{"url": "https://youtu.be/dQw4w9WgXcQ"}', token="wrong")[0] == 401
    assert got == []
    status, res = send(base + "/send", b'{"url": "https://youtu.be/dQw4w9WgXcQ"}', token=token)
    assert status == 200 and res == {"ok": True, "result": "Playing on the TV: “A video” by Someone"}
    assert got == ["https://youtu.be/dQw4w9WgXcQ"]


def test_send_takes_json_only(opened):
    # a form or text/plain post is what another web page could make a browser send without asking
    _, base, got = opened
    token = secrets.ensure_token()
    assert send(base + "/send", b"url=https://example.com", token=token, ctype="application/x-www-form-urlencoded")[0] == 415
    assert send(base + "/send", b'{"url": "https://example.com"}', token=token, ctype="text/plain")[0] == 415
    assert send(base + "/send", b"{nope", token=token)[0] == 400
    assert send(base + "/send", b'{"url": 42}', token=token)[0] == 400
    assert send(base + "/send", b'["https://example.com"]', token=token)[0] == 400
    assert send(base + "/send", b'{"url": "x" }'.replace(b"x", b"x" * 20000), token=token)[0] == 413
    assert got == []
    # Android shares text; a Shortcut may hand over a list
    assert send(base + "/send", b'{"text": "Look https://example.com/a"}', token=token)[0] == 200
    assert send(base + "/send", b'{"url": ["https://example.com/b"]}', token=token)[0] == 200
    assert got == ["Look https://example.com/a", "https://example.com/b"]


def test_send_says_what_went_wrong(opened):
    _, base, _ = opened
    token = secrets.ensure_token()
    status, res = send(base + "/send", b'{"url": "javascript:alert(1)"}', token=token)
    assert status == 400 and not res["ok"] and "link" in res["result"]
    status, res = send(base + "/send", b'{"url": "https://youtu.be/fail"}', token=token)
    assert status == 502 and res == {"ok": False, "result": "YouTube didn't start on the TV."}


def test_sending_is_rate_limited(opened):
    phone, base, got = opened
    token = secrets.ensure_token()
    for i in range(phone.SEND_LIMIT):
        assert send(base + "/send", b'{"url": "https://example.com/%d"}' % i, token=token)[0] == 200
    status, res = send(base + "/send", b'{"url": "https://example.com/more"}', token=token)
    assert status == 429 and "minute" in res["result"]
    assert len(got) == phone.SEND_LIMIT


def test_one_link_opens_at_a_time(opened):
    phone, base, _ = opened
    token = secrets.ensure_token()
    with phone._opening:
        status, res = send(base + "/send", b'{"url": "https://example.com/"}', token=token)
    assert status == 429 and "still opening" in res["result"]


def test_moments_list_and_start_through_the_voice_service(server, monkeypatch):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from couchbox import settings

    phone, base = server
    asked = []

    class Voice(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            asked.append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"]))), self.headers.get("X-Couchbox")))
            out = json.dumps({"ok": True, "result": "Playing Pet music."}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

    voice = ThreadingHTTPServer(("127.0.0.1", 0), Voice)
    threading.Thread(target=voice.serve_forever, daemon=True).start()
    monkeypatch.setattr(phone, "VOICE", f"http://127.0.0.1:{voice.server_address[1]}")
    settings.update({"moments.list": [{"name": "Pet music", "app": "youtube", "target": "video:dQw4w9WgXcQ", "title": "Calm"}]})
    assert post(base + "/moments", {})[0] == 401
    token = secrets.ensure_token()
    assert post(base + "/moments", {}, token) == (
        200,
        {"moments": [{"id": "pet-music", "name": "Pet music", "plays": "YouTube"}], "active": None},
    )
    assert post(base + "/moments/start", {"id": "pet-music"}, token) == (200, {"ok": True, "result": "Playing Pet music."})
    assert asked == [("/moments/start", {"id": "pet-music"}, "1")]
    page = urllib.request.urlopen(base + "/", timeout=5).read().decode()
    assert 'id="momentscard"' in page
    voice.shutdown()
