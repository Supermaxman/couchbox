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
