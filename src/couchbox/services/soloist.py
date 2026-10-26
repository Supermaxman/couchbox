"""Spotify Soloist: Spotify's own headless player (a Spotify Connect device), which plays the
music on this box. https://developer.spotify.com/documentation/soloist

Couchbox doesn't ship it: Spotify asks that its archives aren't redistributed, and each user
needs their own Soloist API key (made by a Premium account at developer.spotify.com). When the
user sets Spotify up on the TV, the box downloads the official build from Spotify's CDN into
the TV user's ~/.local/share/couchbox-spotify/soloist/. Builds expire 90 days after they're
built (the player exits with code 10), so couchbox-spotify --connect fetches a newer one when
the installed build is more than 60 days old, and again whenever the player reports it expired.

Soloist signs in through Spotify Connect: once, pick this TV in the Spotify app on a phone on
the same network. Its data directory keeps that session.

Player (below) is a client of Soloist's local WebSocket API (--ws 127.0.0.1:0; the port is in
<data>/ws.port): playback state and events, and play/pause/skip/seek/volume/shuffle/queue.
"""

import io
import json
import os
import platform
import re
import shutil
import subprocess
import tarfile
import threading
import time
from pathlib import Path

import requests

from couchbox.services.spotify import data_dir

CDN = "https://soloist-builds.spotifycdn.com/soloist_release_{arch}.tar.gz"
DOCS = "https://developer.spotify.com/documentation/soloist"
UPDATE_AFTER_DAYS = 60
EXPIRED = 10  # Soloist's exit code for an expired build


def home() -> Path:
    d = data_dir() / "soloist"
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    return d


def binary() -> Path:
    return home() / "soloist"


def state_dir() -> Path:
    d = home() / "data"
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    return d


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    d = Path(base) / "couchbox-spotify" / "soloist"
    d.mkdir(parents=True, exist_ok=True)
    return d


def key_file() -> Path:
    return data_dir() / "soloist.key"


def api_key() -> str:
    try:
        return key_file().read_text().strip()
    except OSError:
        return ""


def set_api_key(key: str) -> None:
    key = (key or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9._~+/=-]{8,512}", key):
        raise ValueError("That doesn't look like a Soloist API key.")
    tmp = key_file().with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(key + "\n")
    os.replace(tmp, key_file())


def arch() -> str:
    m = platform.machine()
    return {"aarch64": "arm64", "arm64": "arm64", "armv7l": "arm32", "x86_64": "x86_64"}.get(m, m)


def build_info():
    """{"version", "built" (epoch), "days_left"} of the installed build, or None."""
    b = binary()
    if not os.access(b, os.X_OK):
        return None
    try:
        out = subprocess.run([str(b), "--version"], capture_output=True, text=True, timeout=15).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    return parse_version(out) or {"version": out.strip()[:80], "built": os.path.getmtime(b), "days_left": None}


def parse_version(text):
    """Soloist --version prints its version and build timestamp; find both."""
    v = re.search(r"(\d+\.\d+(?:\.\d+)*(?:[-+][\w.]+)?)", text or "")
    built = None
    m = re.search(r"(20\d\d)-(\d\d)-(\d\d)[T ]?(\d\d)?:?(\d\d)?", text or "")
    if m:
        y, mo, d, hh, mm = (int(x) if x else 0 for x in m.groups())
        built = time.mktime((y, mo, d, hh, mm, 0, 0, 0, -1))
    else:
        m = re.search(r"\b(1[6-9]\d{8})\b", text or "")  # an epoch timestamp
        if m:
            built = int(m.group(1))
    if not v and not built:
        return None
    left = None if built is None else round(90 - (time.time() - built) / 86400, 1)
    return {"version": v.group(1) if v else "", "built": built, "days_left": left}


def needs_update(info=None) -> bool:
    info = info if info is not None else build_info()
    if not info:
        return True
    if info.get("days_left") is None:  # unknown build date: go by the file's age
        return time.time() - os.path.getmtime(binary()) > UPDATE_AFTER_DAYS * 86400
    return info["days_left"] < 90 - UPDATE_AFTER_DAYS


def install(session=None, url=None) -> dict:
    """Download Spotify's current build and put its `soloist` executable in place (atomically).
    Only that one file is taken from the archive."""
    url = url or CDN.format(arch=arch())
    s = session or requests
    r = s.get(url, timeout=120)
    r.raise_for_status()
    if len(r.content) > 200 * 1024 * 1024:
        raise RuntimeError("The Soloist download is unexpectedly large.")
    with tarfile.open(fileobj=io.BytesIO(r.content), mode="r:gz") as tar:
        member = next((m for m in tar.getmembers() if m.isfile() and os.path.basename(m.name) == "soloist"), None)
        if member is None:
            raise RuntimeError("The Soloist download has no soloist program in it.")
        data = tar.extractfile(member).read()
    tmp = home() / ".soloist.new"
    with open(tmp, "wb") as f:
        f.write(data)
    os.chmod(tmp, 0o755)  # noqa: S103 - a program the TV user runs
    os.replace(tmp, binary())
    return build_info() or {}


def ensure(force=False, log=print) -> dict:
    """Install or refresh the build when it's missing, old, or expired (force)."""
    info = build_info()
    if force or needs_update(info):
        try:
            log("soloist: downloading Spotify's current build")
            info = install()
            log(f"soloist: installed {info.get('version', '')} ({info.get('days_left')} days left)")
        except Exception as err:  # noqa: BLE001 - keep the old build if the download fails
            log(f"soloist: download failed: {err}")
            if not info:
                raise
    return info or {}


def command(device_name: str, ws_port: int = 0) -> list[str]:
    return [
        str(binary()),
        "--device-name",
        device_name,
        "--api-key",
        api_key(),
        "--data-dir",
        str(state_dir()),
        "--cache-dir",
        str(cache_dir()),
        "--cache-size",
        "500",
        "--ws",
        f"127.0.0.1:{ws_port}",
    ]


def ws_url():
    """ws://127.0.0.1:<port> of the running player (from its data directory), or ""."""
    try:
        addr = (state_dir() / "ws.addr").read_text().strip() or "127.0.0.1"
    except OSError:
        addr = "127.0.0.1"
    try:
        port = int((state_dir() / "ws.port").read_text().strip())
    except (OSError, ValueError):
        return ""
    if addr in ("0.0.0.0", "::"):  # noqa: S104 - reading where it listens, not binding
        addr = "127.0.0.1"
    return f"ws://{addr}:{port}"


def remove() -> None:
    """Forget the player: its program, Connect session and cache (not the API key)."""
    shutil.rmtree(home(), ignore_errors=True)
    shutil.rmtree(cache_dir(), ignore_errors=True)


# ------------------------------------------------------------------ the WebSocket client
class Player:
    """Soloist's local WebSocket API, kept connected in a thread.

    state: {"connected", "logged_in", "status" (idle|playing|paused|buffering), "item", "context",
            "position_ms", "timestamp_ms", "speed", "volume", "is_active", "shuffle", "repeat"}
    on_change(state, event_type) is called from the thread after every event."""

    def __init__(self, url_fn=ws_url, on_change=None):
        self.url_fn = url_fn
        self.on_change = on_change
        self.state = {
            "connected": False,
            "logged_in": False,
            "status": "idle",
            "item": None,
            "context": None,
            "position_ms": 0,
            "timestamp_ms": 0,
            "speed": 0.0,
            "volume": 0,
            "is_active": False,
            "shuffle": False,
            "repeat": "off",
            "queue": [],
        }
        self.ws = None
        self._stop = False
        self._lock = threading.Lock()
        self.thread = None

    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True, name="soloist-ws")
        self.thread.start()
        return self

    def stop(self):
        self._stop = True
        try:
            if self.ws:
                self.ws.close()
        except Exception:  # noqa: BLE001
            pass

    def _run(self):
        import websocket

        while not self._stop:
            url = self.url_fn()
            if not url:
                time.sleep(2)
                continue
            try:
                ws = websocket.create_connection(url, timeout=10)
            except Exception:  # noqa: BLE001 - the player is starting or restarting
                time.sleep(2)
                continue
            self.ws = ws
            ws.settimeout(None)
            self._set(connected=True)
            self.send("get_auth_state")
            try:
                while not self._stop:
                    msg = ws.recv()
                    if not msg:
                        break
                    try:
                        self.handle(json.loads(msg))
                    except ValueError:
                        continue
            except Exception:  # noqa: BLE001 - closed
                pass
            self.ws = None
            self._set(connected=False, logged_in=False, status="idle")
            time.sleep(1)

    def _set(self, event="", **kw):
        with self._lock:
            self.state.update(kw)
            st = dict(self.state)
        if self.on_change:
            try:
                self.on_change(st, event)
            except Exception:  # noqa: BLE001
                pass

    def handle(self, m):
        t = m.get("type")
        if t == "auth_state":
            logged = bool(m.get("logged_in"))
            self._set(t, logged_in=logged)
            if logged:
                self.send("get_state")
                self.send("get_queue", limit=20)
        elif t == "playback_state":
            pos = m.get("position") or {}
            opts = m.get("options") or {}
            self._set(
                t,
                status=m.get("status", "idle"),
                item=m.get("item"),
                context=m.get("context"),
                position_ms=pos.get("position_ms", 0),
                timestamp_ms=pos.get("timestamp_ms", 0),
                speed=pos.get("speed", 0.0),
                volume=m.get("volume", 0),
                is_active=bool(m.get("is_active")),
                shuffle=bool(opts.get("shuffle")),
                repeat=opts.get("repeat", "off"),
            )
        elif t == "track_changed":
            self._set(t, item=m.get("item"))
            self.send("get_queue", limit=20)
        elif t == "playback_changed":
            self._set(t, status=m.get("status", "idle"))
        elif t == "volume_changed":
            self._set(t, volume=m.get("volume", 0))
        elif t == "device_changed":
            self._set(t, is_active=bool(m.get("is_active")))
        elif t == "context_changed":
            self._set(t, context=m.get("context"))
        elif t == "options_changed":
            o = m.get("options") or {}
            self._set(t, shuffle=bool(o.get("shuffle")), repeat=o.get("repeat", "off"))
        elif t == "position_sync":
            pos = m.get("position") or {}
            self._set(t, position_ms=pos.get("position_ms", 0), timestamp_ms=pos.get("timestamp_ms", 0), speed=pos.get("speed", 0.0))
        elif t == "queue_changed":
            self._set(
                t,
                queue=[
                    {"uri": (e.get("item") or {}).get("uri", ""), "name": name_of(e.get("item")), "source": e.get("source", "")}
                    for e in m.get("upcoming") or []
                ][:20],
            )
        elif t == "error":
            self._set("error", last_error=m.get("message", ""))

    def send(self, command, **fields):
        ws = self.ws
        if not ws:
            return False
        try:
            ws.send(json.dumps({"type": "command", "command": command, **fields}))
            return True
        except Exception:  # noqa: BLE001
            return False

    # what the app and MPRIS use
    def position(self):
        s = self.state
        if not s.get("timestamp_ms"):
            return s.get("position_ms", 0) / 1000
        return (s["position_ms"] + max(0.0, time.time() * 1000 - s["timestamp_ms"]) * (s.get("speed") or 0)) / 1000

    def play(self, uri=""):
        return self.send("play", **({"uri": uri} if uri else {}))

    def pause(self):
        return self.send("pause")

    def toggle(self):
        return self.pause() if self.state.get("status") in ("playing", "buffering") else self.play()

    def next(self):
        return self.send("skip_next")

    def previous(self):
        return self.send("skip_prev")

    def seek(self, seconds):
        return self.send("seek", position_ms=int(max(0, seconds) * 1000))

    def volume(self, v):
        return self.send("set_volume", volume=int(max(0, min(100, v))))

    def shuffle(self, on):
        return self.send("set_shuffle", enabled=bool(on))

    def repeat(self, mode):
        if mode == "track":
            return self.send("set_repeat_context", enabled=False) and self.send("set_repeat_track", enabled=True)
        self.send("set_repeat_track", enabled=False)
        return self.send("set_repeat_context", enabled=mode == "context")

    def queue(self, uri):
        return self.send("add_to_queue", uri=uri)

    def activate(self):
        return self.send("activate")


def name_of(entity):
    return (((entity or {}).get("decorations") or {}).get("identity") or {}).get("name", "")


def duration_of(entity):
    return ((((entity or {}).get("decorations") or {}).get("playback") or {}).get("duration_ms") or 0) / 1000
