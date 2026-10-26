"""Twitch sign-in: the device code keeps working after Back, refreshes survive another process
rotating the (single-use) refresh token, keep_alive refreshes a week-old sign-in, and a token
that doesn't expire (Twitch's TV app: expires_in 0, refresh needs a secret) is kept."""

import json
import os
import time

import pytest

from couchbox.services import twitch


class Resp:
    def __init__(self, status, body):
        self.status_code, self.body = status, body
        self.ok = status < 400
        self.headers = {"content-type": "application/json"}
        self.text = json.dumps(body)

    def json(self):
        return self.body

    def raise_for_status(self):
        assert self.ok


class FakeSession:
    """Answers id.twitch.tv like Twitch: device codes pending until `authorized`, refresh tokens single-use."""

    def __init__(self):
        self.headers = {}
        self.authorized = False
        self.valid_refresh = {"r1"}
        self.n = 1
        self.posts = []
        self.live = {"a1"}  # access tokens Twitch still takes
        self.expires_in = 14400  # 0: the TV app's tokens, which don't expire
        self.secret_needed = False

    def post(self, url, data=None, timeout=None):
        self.posts.append(data.get("grant_type", "device"))
        if url.endswith("/device"):
            return Resp(
                200,
                {
                    "device_code": "D",
                    "user_code": "ABCD",
                    "verification_uri": "https://www.twitch.tv/activate",
                    "expires_in": 1800,
                    "interval": 0,
                },
            )
        if data["grant_type"] == "refresh_token":
            if self.secret_needed:
                return Resp(400, {"status": 400, "message": "missing client secret"})
            if data["refresh_token"] not in self.valid_refresh:
                return Resp(400, {"status": 400, "message": "Invalid refresh token"})
            self.valid_refresh.discard(data["refresh_token"])
            self.n += 1
            self.valid_refresh.add(f"r{self.n}")
            self.live.add(f"a{self.n}")
            return Resp(200, {"access_token": f"a{self.n}", "refresh_token": f"r{self.n}", "expires_in": self.expires_in})
        if not self.authorized:
            return Resp(400, {"status": 400, "message": "authorization_pending"})
        return Resp(200, {"access_token": "a1", "refresh_token": "r1", "expires_in": self.expires_in})

    def get(self, url, headers=None, timeout=None):
        self.posts.append("validate")
        if headers["Authorization"].split()[-1] not in self.live:
            return Resp(401, {"status": 401, "message": "invalid access token"})
        return Resp(200, {"login": "viewer", "user_id": "42", "expires_in": self.expires_in})


@pytest.fixture
def tw(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    real_sleep = time.sleep
    monkeypatch.setattr(twitch.time, "sleep", lambda s: real_sleep(0.01))
    fake = FakeSession()
    monkeypatch.setattr(twitch.requests, "Session", lambda: fake)
    return fake


def wait_for(cond, secs=3):
    end = time.time() + secs
    while time.time() < end and not cond():
        time.sleep(0.01)
    return cond()


def test_code_entered_after_back_still_signs_in(tw):
    t = twitch.Twitch()
    events = []
    t.on_event = lambda name, data: events.append((name, json.loads(data)))
    t.device_start()
    assert t.device_poll() == {"state": "waiting"}
    # the sign-in page is gone (Back): nothing calls device_poll any more; the code is entered now
    tw.authorized = True
    assert wait_for(lambda: t.signed_in)
    assert wait_for(lambda: events)
    assert events == [("signedIn", {"user": "viewer"})]
    assert json.load(open(t.session_file))["refresh_token"] == "r1"
    assert t.device_poll()["state"] == "ok"


def test_new_code_replaces_the_old_wait(tw):
    t = twitch.Twitch()
    t.device_start()
    first = t.device
    t.device_start()
    assert t.device is not first
    tw.authorized = True
    assert wait_for(lambda: t.signed_in)


def signed_in(tw, expires_in=-10):
    t = twitch.Twitch()
    t.auth = {"access_token": "a1", "refresh_token": "r1", "expires_at": time.time() + expires_in, "login": "viewer"}
    t._save()
    return t


def test_refresh_rotates_and_saves(tw):
    t = signed_in(tw)
    assert t.token() == "a2"
    assert json.load(open(t.session_file))["refresh_token"] == "r2"


def test_stale_process_adopts_the_other_refresh_instead_of_signing_out(tw):
    app = signed_in(tw)
    other = twitch.Twitch()  # e.g. keep_alive, loaded the same file
    assert other.token() == "a2"  # used r1; Twitch now refuses r1
    assert app.token() == "a2"  # app still holds r1 in memory: re-reads the file, no second refresh
    assert app.signed_in and tw.posts.count("refresh_token") == 1


def test_refused_refresh_signs_out(tw):
    t = signed_in(tw)
    tw.valid_refresh.clear()  # revoked on twitch.tv, or 30 days unused
    tw.live.clear()
    assert t.token() == ""
    assert not t.signed_in


def test_keep_alive_refreshes_only_a_week_old_sign_in(tw):
    t = signed_in(tw, expires_in=3600)
    t.auth["refreshed_at"] = time.time() - 3600
    t._save()
    assert t.keep_alive() and tw.posts.count("refresh_token") == 0
    t.auth["refreshed_at"] = time.time() - 8 * 86400
    t._save()
    assert t.keep_alive() and tw.posts.count("refresh_token") == 1
    assert json.load(open(t.session_file))["refresh_token"] == "r2"


def test_a_token_that_never_expires_is_never_refreshed(tw):
    tw.expires_in, tw.secret_needed, tw.authorized = 0, True, True
    t = twitch.Twitch()
    t.device_start()
    assert wait_for(lambda: t.signed_in and os.path.exists(t.session_file))
    assert json.load(open(t.session_file))["expires_at"] == 0
    assert t.token() == "a1" and "refresh_token" not in tw.posts


def test_refresh_refused_for_a_secret_keeps_a_working_token(tw):
    # sessions saved before the fix said "expires in an hour"; Twitch then refuses the refresh
    tw.expires_in, tw.secret_needed = 0, True
    t = signed_in(tw)
    assert t.token() == "a1" and t.signed_in
    assert json.load(open(t.session_file))["expires_at"] == 0
    assert t.token() == "a1" and tw.posts.count("refresh_token") == 1


def test_keep_alive_checks_a_token_that_never_expires(tw):
    tw.expires_in, tw.secret_needed = 0, True
    t = signed_in(tw)
    t.auth.update(expires_at=0, refreshed_at=time.time() - 8 * 86400)
    t._save()
    assert t.keep_alive() and tw.posts == ["validate"]
    t.auth["refreshed_at"] = time.time() - 8 * 86400
    tw.live.clear()  # revoked on twitch.tv
    assert not t.keep_alive() and not t.signed_in
