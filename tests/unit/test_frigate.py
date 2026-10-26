"""The Frigate app's back end against a fake Frigate: sign-in (and signing in again when the
token runs out), cameras and groups, review items, the relay, and the MSE stream unwrapping."""

import http.server
import json
import threading
import urllib.request

import pytest

from couchbox.services import frigate


class FakeFrigate:
    def __init__(self):
        self.tokens = set()
        self.logins = 0
        self.viewed = []
        fake = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _authed(self):
                c = self.headers.get("Cookie", "")
                return any(f"frigate_token={t}" in c for t in fake.tokens)

            def _send(self, code, body=b"", ctype="application/json", headers=()):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                for k, v in headers:
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                if self.path == "/api/login":
                    if body == {"user": "tv", "password": "pw"}:
                        fake.logins += 1
                        tok = f"tok{fake.logins}"
                        fake.tokens.add(tok)
                        return self._send(200, b"{}", headers=[("Set-Cookie", f"frigate_token={tok}; Path=/")])
                    return self._send(401, b'{"message":"bad"}')
                if not self._authed():
                    return self._send(401)
                if self.path == "/api/reviews/viewed":
                    fake.viewed += body["ids"]
                    return self._send(200, b"{}")
                self._send(404)

            def do_GET(self):
                if not self._authed():
                    return self._send(401)
                if self.path == "/api/config":
                    return self._send(200, json.dumps(frigate.DEMO_CONFIG).encode())
                if self.path.startswith("/api/review"):
                    return self._send(200, json.dumps(frigate.demo_reviews()).encode())
                if self.path.startswith("/api/garage/latest.webp"):
                    return self._send(200, b"RIFFwebp", "image/webp")
                if self.path.startswith("/vod/"):
                    return self._send(200, b"#EXTM3U\nseg-1.m4s\n", "application/vnd.apple.mpegurl")
                self._send(404)

        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    s = FakeFrigate()
    yield s
    s.srv.shutdown()


def test_sign_in_keeps_the_session_private(server, tmp_path):
    f = frigate.Frigate(server.url)
    assert not f.status()["signedIn"]
    with pytest.raises(RuntimeError, match="didn't work"):
        f.login("tv", "wrong")
    st = f.login("tv", "pw")
    assert st == {"configured": True, "url": server.url, "signedIn": True, "user": "tv"}
    p = tmp_path / ".local/share/couchbox-frigate/session.json"
    assert p.stat().st_mode & 0o777 == 0o600
    assert frigate.Frigate(server.url).status()["signedIn"]  # remembered
    assert not frigate.Frigate("http://other.example").status()["signedIn"]  # for that server only


def test_expired_token_signs_in_again(server):
    f = frigate.Frigate(server.url)
    f.login("tv", "pw")
    server.tokens.clear()  # Frigate's token ran out
    assert [c["name"] for c in f.config()["cameras"]][:2] == ["backyard", "dining_room"]
    assert server.logins == 2


def test_signed_out_when_the_password_stops_working(server):
    f = frigate.Frigate(server.url)
    f.login("tv", "pw")
    server.tokens.clear()
    f.auth["password"] = "changed"
    with pytest.raises(frigate.SignInNeeded):
        f.config()
    assert not f.signed_in


def test_groups_and_reviews(server):
    f = frigate.Frigate(server.url)
    f.login("tv", "pw")
    c = f.config()
    assert [g["name"] for g in c["groups"]] == ["All cameras", "Downstairs", "Upstairs", "Outside", "Front"]
    assert c["groups"][4]["cameras"] == ["front_door", "driveway"]
    assert next(x for x in c["cameras"] if x["name"] == "front_door")["label"] == "Front Door"
    alerts = f.reviews("alert", cameras=["front_door"])["items"]
    assert alerts and all(x["camera"] == "front_door" and x["severity"] == "alert" for x in alerts)
    assert alerts[0]["objects"] == ["Person", "Dog"] and alerts[0]["live"]
    assert f.active()["cameras"] == ["front_door"]
    f.mark_viewed(["a", "b"])
    assert server.viewed == ["a", "b"]


def test_relay_adds_the_sign_in(server):
    f = frigate.Frigate(server.url)
    f.login("tv", "pw")
    assert urllib.request.urlopen(f.snapshot("garage")).read() == b"RIFFwebp"
    pl = urllib.request.urlopen(f.recording("garage", 1000, 1010)["url"]).read()
    assert pl.startswith(b"#EXTM3U")
    assert "/vod/garage/start/997/end/1013/index.m3u8" in f.recording("garage", 1000, 1010)["url"]
    bad = f.relay.base.rsplit("/", 1)[0] + "/wrong-secret/f/api/config"
    with pytest.raises(urllib.error.HTTPError):
        urllib.request.urlopen(bad)


class FakeWS:
    def __init__(self, frames):
        self.frames = list(frames)

    def recv_data(self):
        import websocket

        if not self.frames:
            raise websocket.WebSocketConnectionClosedException()
        return self.frames.pop(0)


def test_mse_stream_is_unwrapped():
    import websocket

    T, B = websocket.ABNF.OPCODE_TEXT, websocket.ABNF.OPCODE_BINARY
    out = []
    ws = FakeWS([(T, b'{"type":"mse","value":"video/mp4; codecs=\\"avc1.640029\\""}'), (B, b"ftypmoov"), (B, b"moofmdat")])
    assert frigate.pump_mse(ws, out.append) == 16
    assert b"".join(out) == b"ftypmoovmoofmdat"
    with pytest.raises(RuntimeError, match="no stream"):
        frigate.pump_mse(FakeWS([(T, b'{"type":"error","value":"no stream"}')]), out.append)


def test_demo_needs_no_server():
    f = frigate.Frigate("", demo=True)
    assert f.status()["signedIn"]
    assert len(f.config()["groups"]) == 5
    assert f.reviews("detection")["items"]
