"""Frigate (the NVR) for the couchbox TV app: cameras, live view, alerts and recordings.

  sign-in    Frigate's own login (POST /api/login): a cookie (frigate_token, a JWT that lasts
             Frigate's auth.session_length, a week by default). The user name and password are
             kept with it (~/.local/share/couchbox-frigate/session.json, mode 600) so the TV
             signs in again by itself when the token runs out; Sign out forgets both
  relay      a small HTTP server on 127.0.0.1 behind a random path, which the QML (images) and
             mpv (video) use instead of Frigate itself, so neither needs the cookie:
               <relay>/f/<path>               any GET on Frigate (snapshots, review thumbnails,
                                              recordings as HLS from /vod/...), cookie added
               <relay>/live/<stream>.mp4      live video: Frigate's go2rtc MSE websocket
                                              (/live/mse/api/ws?src=<stream>, the one live route
                                              behind its login), unwrapped into one fMP4 stream
  data       /api/config (cameras, camera groups), /api/review (alerts and detections),
             /api/reviews/viewed, /api/review/activity/motion (the timeline's motion),
             /api/<camera>/recordings/<time>/snapshot.jpg (the timeline's picture under the cursor)

Demo mode (tests, screenshots) answers with made-up cameras and alerts and no server.
"""

import http.server
import json
import os
import secrets
import socketserver
import threading
import time
import urllib.parse

import requests

TIMEOUT = (8, 30)
COOKIE = "frigate_token"
# what mpv/ffmpeg can take from go2rtc's MSE stream: H.264 (cameras send PCMA audio, which MSE
# can't carry, so the stream is video only unless go2rtc transcodes audio to AAC)
MSE_CODECS = "avc1.640029,avc1.64002A,avc1.640033,hvc1.1.6.L153.B0,mp4a.40.2,mp4a.40.5"


class SignInNeeded(Exception):
    pass


def label(name):
    """front_door -> Front Door"""
    return " ".join(w.capitalize() for w in name.replace("-", "_").split("_") if w)


# What the app has an icon for (ui/frigate/icons); other labels share one.
KINDS = {"person", "car", "motorcycle", "bicycle", "dog", "cat", "bird", "horse", "package", "face", "license_plate"}
ALIASES = {
    "truck": "car",
    "bus": "car",
    "van": "car",
    "motorbike": "motorcycle",
    "plate": "license_plate",
    **dict.fromkeys(
        ("amazon", "ups", "fedex", "usps", "dhl", "dpd", "gls", "an_post", "purolator", "postnl", "nzpost", "postnord"), "package"
    ),
}


def kind(name):
    """A Frigate label -> its icon: person, car (also trucks, buses), package (also the delivery
    companies' logos Frigate+ finds), ..., or object."""
    k = ALIASES.get(name, name)
    return k if k in KINDS else "object"


class Frigate:
    def __init__(self, url="", demo=False):
        self.demo = demo
        self.dir = os.path.expanduser("~/.local/share/couchbox-frigate")
        if not demo:
            os.makedirs(self.dir, mode=0o700, exist_ok=True)
        self.auth = {}
        if not demo:
            try:
                self.auth = json.load(open(self.session_file))
            except (OSError, ValueError):
                pass
        self.url = (url or "").rstrip("/")
        if self.auth.get("url") and self.auth["url"] != self.url:
            self.auth = {}  # the server changed in Settings: that sign-in was for another one
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "couchbox-frigate"
        self.lock = threading.Lock()
        self.relay = None
        self.labels = {}  # camera -> its friendly name (from config())

    # ------------------------------------------------------------------ session
    @property
    def session_file(self):
        return os.path.join(self.dir, "session.json")

    def _save(self):
        tmp = self.session_file + ".tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(self.auth, f)
        os.replace(tmp, self.session_file)

    @property
    def signed_in(self):
        return self.demo or bool(self.auth.get("token"))

    def status(self):
        return {
            "configured": bool(self.url) or self.demo,
            "url": self.url or ("https://frigate.example" if self.demo else ""),
            "signedIn": self.signed_in,
            "user": "demo" if self.demo else self.auth.get("user", ""),
        }

    def login(self, user, password):
        if self.demo:
            return self.status()
        if not self.url:
            raise RuntimeError("Set the Frigate server in Settings → Apps first.")
        try:
            r = self.s.post(f"{self.url}/api/login", json={"user": user, "password": password}, timeout=TIMEOUT)
        except requests.RequestException as err:
            raise RuntimeError(f"Can't reach Frigate at {self.url}.") from err
        token = r.cookies.get(COOKIE) or self.s.cookies.get(COOKIE)
        if r.status_code in (400, 401) or (r.ok and not token):
            raise RuntimeError("That user name and password didn't work.")
        if r.status_code == 429:
            raise RuntimeError("Too many tries: Frigate wants a minute's rest.")
        if not r.ok:
            raise RuntimeError(f"Frigate said {r.status_code}.")
        self.auth = {"url": self.url, "user": user, "password": password, "token": token, "t": time.time()}
        self._save()
        return self.status()

    def sign_out(self):
        self.auth = {}
        try:
            os.remove(self.session_file)
        except OSError:
            pass

    def _relogin(self, used):
        """The token ran out: sign in again with the kept password (once per token)."""
        with self.lock:
            if self.auth.get("token") != used:
                return True  # another thread already did
            if not self.auth.get("password"):
                return False
            try:
                self.login(self.auth["user"], self.auth["password"])
                return True
            except RuntimeError:
                return False

    def request(self, method, path, stream=False, **kw):
        """A request to Frigate with the cookie; signs in again once on 401."""
        if not self.url:
            raise SignInNeeded("Set the Frigate server in Settings → Apps.")
        if not self.auth.get("token"):
            raise SignInNeeded("Sign in to Frigate.")
        for attempt in (1, 2):
            token = self.auth["token"]
            r = self.s.request(
                method, f"{self.url}{path}", cookies={COOKIE: token}, stream=stream, timeout=kw.pop("timeout", TIMEOUT), **kw
            )
            if r.status_code != 401:
                return r
            r.close()
            if attempt == 2 or not self._relogin(token):
                self.sign_out()
                raise SignInNeeded("Frigate signed the TV out: sign in again.")
        raise SignInNeeded("Sign in to Frigate.")  # not reached

    def get_json(self, path, **params):
        r = self.request("GET", path, params=params or None)
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------ data
    def config(self):
        """Cameras and camera groups, in Frigate's order."""
        c = DEMO_CONFIG if self.demo else self.get_json("/api/config")
        cams = []
        for name, cam in (c.get("cameras") or {}).items():
            if not cam.get("enabled", True) or not (cam.get("ui") or {}).get("dashboard", True):
                continue
            streams = (cam.get("live") or {}).get("streams") or {}
            stream = next(iter(streams.values()), "") or (cam.get("live") or {}).get("stream_name") or name
            det = cam.get("detect") or {}
            cams.append(
                {
                    "name": name,
                    "label": (cam.get("friendly_name") or label(name)),
                    "stream": stream,
                    "order": (cam.get("ui") or {}).get("order", 0),
                    "aspect": round((det.get("width") or 16) / (det.get("height") or 9), 3),
                }
            )
        cams.sort(key=lambda x: (x["order"], x["name"]))
        self.labels = {x["name"]: x["label"] for x in cams}
        known = {x["name"] for x in cams}
        groups = [{"name": "All cameras", "icon": "", "cameras": [x["name"] for x in cams]}]
        for name, g in sorted((c.get("camera_groups") or {}).items(), key=lambda kv: (kv[1].get("order", 0), kv[0])):
            members = [x for x in (g.get("cameras") or []) if x in known]
            if members:
                groups.append({"name": label(name) if name.islower() else name, "icon": g.get("icon", ""), "cameras": members})
        return {"cameras": cams, "groups": groups}

    def _review_item(self, r):
        start, end = r.get("start_time") or 0, r.get("end_time")
        data = r.get("data") or {}
        objects = list(dict.fromkeys((data.get("sub_labels") or []) + (data.get("objects") or []) + (data.get("audio") or [])))
        seen = list(dict.fromkeys(o.split("-verified")[0] for o in data.get("objects") or []))
        kinds = [{"kind": kind(o), "label": label(o)} for o in seen]
        kinds += [{"kind": "audio", "label": label(a)} for a in dict.fromkeys(data.get("audio") or [])]
        thumb = r.get("thumb_path") or ""
        if "/clips/" in thumb:
            thumb = "/clips/" + thumb.split("/clips/", 1)[1]
        return {
            "id": r["id"],
            "camera": r["camera"],
            "cameraLabel": self.labels.get(r["camera"]) or label(r["camera"]),
            "severity": r.get("severity", "detection"),
            "start": start,
            "end": end or 0,
            "live": end is None,
            "objects": [label(o) for o in objects],
            "kinds": kinds or [{"kind": "motion", "label": "Motion"}],
            "names": [n for n in data.get("sub_labels") or [] if isinstance(n, str)],
            "zones": [label(z) for z in data.get("zones") or []],
            "reviewed": bool(r.get("has_been_reviewed")),
            "thumb": thumb and self.relay_url("f" + thumb),
        }

    def reviews(self, severity="alert", cameras=None, limit=40, hours=0, unreviewed=False):
        if self.demo:
            items = [x for x in demo_reviews() if x["severity"] == severity or severity == "all"]
        else:
            params = {"limit": limit}
            if severity != "all":
                params["severity"] = severity
            if cameras:
                params["cameras"] = ",".join(cameras)
            if hours:
                params["after"] = int(time.time() - hours * 3600)
            if unreviewed:
                params["reviewed"] = 0
            items = self.get_json("/api/review", **params)
        out = [self._review_item(r) for r in items]
        if cameras:
            out = [x for x in out if x["camera"] in cameras]
        if unreviewed:
            out = [x for x in out if not x["reviewed"]]
        return {"items": out[:limit]}

    def active(self):
        """Cameras with something going on right now (a review item that hasn't ended), and what."""
        items = [x for x in self.reviews("all", limit=50, hours=1)["items"] if x["live"]]
        kinds = {}
        for x in items:
            for k in x["kinds"]:
                if k["kind"] not in kinds.setdefault(x["camera"], []):
                    kinds[x["camera"]].append(k["kind"])
        return {"cameras": sorted(kinds), "kinds": kinds}

    def timeline(self, cameras, hours=24):
        """The last `hours` of these cameras for the timeline: every alert and detection, and
        each camera's motion in 5-minute steps (0..1 of its busiest step)."""
        end = time.time()
        start = end - hours * 3600
        items = self.reviews("all", cameras, limit=1000, hours=hours)["items"]
        motion = {}
        for cam in cameras:
            if self.demo:
                rows = demo_motion(cam, start, end)
            else:
                try:
                    rows = self.get_json("/api/review/activity/motion", cameras=cam, after=int(start), before=int(end), scale=300)
                except requests.RequestException:
                    rows = []
            peak = max((r.get("motion") or 0 for r in rows), default=0) or 1
            motion[cam] = [[r["start_time"], round(min(1, (r.get("motion") or 0) / peak), 3)] for r in rows if r.get("motion")]
        return {"start": start, "end": end, "step": 300, "items": items, "motion": motion}

    def mark_viewed(self, ids):
        if self.demo or not ids:
            return {"ok": True}
        try:
            self.request("POST", "/api/reviews/viewed", json={"ids": list(ids)}).close()
        except (requests.RequestException, SignInNeeded):
            pass  # a viewer account may not be allowed to: not worth bothering anyone
        return {"ok": True}

    def recording(self, camera, start, end, pad=3):
        """HLS of the recording around a review item (through the relay)."""
        end = end or time.time()
        path = f"vod/{camera}/start/{int(start - pad)}/end/{int(end + pad)}/index.m3u8"
        return {"url": "demo:recording" if self.demo else self.relay_url("f/" + path)}

    def frame(self, camera, t, height=540):
        """The recorded picture at time t (the timeline's preview)."""
        return self.relay_url(f"f/api/{camera}/recordings/{t:.1f}/snapshot.jpg?height={height}")

    def live(self, stream):
        return {"url": "demo:live" if self.demo else self.relay_url(f"live/{urllib.parse.quote(stream)}.mp4")}

    def snapshot(self, camera, height=360):
        return self.relay_url(f"f/api/{camera}/latest.webp?h={height}")

    # ------------------------------------------------------------------ relay
    def relay_url(self, rest):
        if self.demo:
            return ""
        if self.relay is None:
            self.relay = Relay(self)
        return f"{self.relay.base}/{rest}"

    def ws_url(self, stream):
        u = urllib.parse.urlsplit(self.url)
        scheme = "wss" if u.scheme == "https" else "ws"
        return f"{scheme}://{u.netloc}{u.path}/live/mse/api/ws?src={urllib.parse.quote(stream)}"

    def open_live(self, stream):
        """The websocket for a camera's live stream, with the MSE request sent ("video/mp4; ..."
        comes back first, then the fMP4 init segment and fragments as binary messages)."""
        import websocket

        if not self.auth.get("token"):
            raise SignInNeeded("Sign in to Frigate.")
        for attempt in (1, 2):
            token = self.auth["token"]
            try:
                ws = websocket.create_connection(self.ws_url(stream), cookie=f"{COOKIE}={token}", timeout=15)
            except websocket.WebSocketBadStatusException as err:
                if getattr(err, "status_code", 0) == 401 and attempt == 1 and self._relogin(token):
                    continue
                raise
            ws.send(json.dumps({"type": "mse", "value": MSE_CODECS}))
            return ws
        raise SignInNeeded("Sign in to Frigate.")


def pump_mse(ws, write, stop=lambda: False):
    """Copy a go2rtc MSE websocket to write(bytes) until it closes or write fails. Text
    messages (the codec line, errors) are skipped; returns the number of bytes written."""
    import websocket

    sent = 0
    while not stop():
        try:
            op, data = ws.recv_data()
        except websocket.WebSocketTimeoutException:
            continue
        except (websocket.WebSocketConnectionClosedException, OSError):
            break
        if op == websocket.ABNF.OPCODE_BINARY:
            write(data)
            sent += len(data)
        elif op == websocket.ABNF.OPCODE_TEXT:
            try:
                msg = json.loads(data)
            except ValueError:
                continue
            if msg.get("type") == "error":
                raise RuntimeError(msg.get("value") or "go2rtc error")
        elif op == websocket.ABNF.OPCODE_CLOSE:
            break
    return sent


class _Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        """A picture or video the app stopped loading hangs up mid-request: not worth a traceback."""
        import sys

        if not isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError)):
            super().handle_error(request, client_address)


class Relay:
    """127.0.0.1:<port>/<secret>/... -> Frigate with the cookie (see the module docstring)."""

    def __init__(self, frigate):
        self.f = frigate
        self.secret = secrets.token_urlsafe(16)
        relay = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def do_GET(self):
                prefix = f"/{relay.secret}/"
                if not self.path.startswith(prefix):
                    self.send_error(404)
                    return
                rest = self.path[len(prefix) :]
                try:
                    if rest.startswith("live/"):
                        relay.live(self, urllib.parse.unquote(rest[5:].split("?")[0].removesuffix(".mp4")))
                    elif rest.startswith("f/"):
                        relay.proxy(self, "/" + rest[2:])
                    else:
                        self.send_error(404)
                except SignInNeeded:
                    self._fail(401)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                except Exception as err:  # noqa: BLE001 - a broken camera mustn't take the relay down
                    print(f"frigate relay: {rest[:60]}: {err}", flush=True)
                    self._fail(502)

            def _fail(self, code):
                try:
                    self.send_response(code)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                except OSError:
                    pass

        self.server = _Server(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}/{self.secret}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def proxy(self, h, path):
        r = self.f.request("GET", path, stream=True)
        with r:
            h.send_response(r.status_code)
            for k in ("Content-Type", "Content-Length", "Cache-Control"):
                if k in r.headers:
                    h.send_header(k, r.headers[k])
            if "Content-Length" not in r.headers:
                h.send_header("Transfer-Encoding", "chunked")
            h.end_headers()
            for chunk in r.iter_content(64 * 1024):
                if "Content-Length" in r.headers:
                    h.wfile.write(chunk)
                else:
                    h.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk))
            if "Content-Length" not in r.headers:
                h.wfile.write(b"0\r\n\r\n")

    def live(self, h, stream):
        ws = self.f.open_live(stream)
        try:
            h.close_connection = True
            h.send_response(200)
            h.send_header("Content-Type", "video/mp4")
            h.send_header("Cache-Control", "no-store")
            h.send_header("Connection", "close")
            h.end_headers()
            pump_mse(ws, lambda b: (h.wfile.write(b), h.wfile.flush()))
        finally:
            try:
                ws.close()
            except Exception:  # noqa: BLE001
                pass

    def close(self):
        self.server.shutdown()


# ------------------------------------------------------------------ demo data (tests, screenshots)
DEMO_CONFIG = {
    "cameras": {
        n: {
            "enabled": True,
            "friendly_name": "Backyard Side Gate by the Garden Path" if n == "backyard_side_gate" else None,
            "detect": {
                "width": 2560 if n in ("front_door", "driveway", "backyard_side_gate") else 640,
                "height": 1440 if n in ("front_door", "driveway", "backyard_side_gate") else 360,
            },
            "live": {"streams": {"Main": f"{n}_main"}},
        }
        for n in (
            "front_door",
            "driveway",
            "backyard_side_gate",
            "garage",
            "living_room",
            "kitchen",
            "dining_room",
            "stairs",
            "upstairs_hallway",
        )
    },
    "camera_groups": {
        "Outside": {"order": 3, "icon": "LuTrees", "cameras": ["front_door", "driveway", "backyard_side_gate", "garage"]},
        "Downstairs": {"order": 1, "icon": "LuHome", "cameras": ["living_room", "kitchen", "dining_room"]},
        "Upstairs": {"order": 2, "icon": "LuBed", "cameras": ["stairs", "upstairs_hallway"]},
        "Front": {"order": 4, "icon": "LuDoorOpen", "cameras": ["front_door", "driveway"]},
    },
}


def demo_reviews():
    now = time.time()
    rows = [
        ("front_door", "alert", ["person", "dog"], [], 120, 18, False, True),
        ("driveway", "alert", ["car", "person", "bicycle"], [], 1500, 42, False, False),
        ("backyard_side_gate", "alert", ["person"], ["speech"], 5400, 25, True, False),
        ("front_door", "alert", ["package"], [], 9000, 12, True, False),
        ("driveway", "alert", ["motorcycle"], [], 30000, 20, True, False),
        ("garage", "detection", ["person"], [], 600, 30, False, False),
        ("living_room", "detection", ["dog"], [], 2000, 64, False, False),
        ("kitchen", "detection", [], ["speech"], 4000, 20, True, False),
        ("stairs", "detection", ["cat"], [], 7000, 8, True, False),
        ("backyard_side_gate", "detection", ["bird"], [], 20000, 15, True, False),
        ("driveway", "detection", ["license_plate", "car"], [], 50000, 9, True, False),
    ]
    return [
        {
            "id": f"demo-{i}",
            "camera": cam,
            "severity": sev,
            "start_time": now - ago,
            "end_time": None if live else now - ago + dur,
            "thumb_path": "",
            "has_been_reviewed": seen,
            "data": {"objects": objs, "zones": [], "audio": audio, "sub_labels": []},
        }
        for i, (cam, sev, objs, audio, ago, dur, seen, live) in enumerate(rows)
    ]


def demo_motion(camera, start, end):
    """Made-up motion: a busy morning and evening, a camera-dependent wobble."""
    import math

    seed = sum(map(ord, camera))
    rows, t = [], start - start % 300
    while t < end:
        hour = time.localtime(t).tm_hour
        busy = 1.0 if hour in (7, 8, 17, 18, 19) else 0.35 if 9 <= hour <= 22 else 0.05
        rows.append({"start_time": t, "motion": max(0.0, busy * (0.6 + 0.4 * math.sin(t / 900 + seed)))})
        t += 300
    return rows
