"""Rain radar for the Weather app (its Radar page): the last two hours of precipitation as a
loop over a map, around the town in Settings → Time.

  sources   nexrad      the lower 48 US states: the National Weather Service's NEXRAD base
                        reflectivity mosaic (about 1 km), as map tiles from the Iowa Environmental
                        Mesonet (mesonet.agron.iastate.edu, public domain, no key): a frame every
                        5 minutes; the loop takes one every 10
            rainviewer  everywhere else: RainViewer's public Weather Maps API (rainviewer.com,
                        free for personal use, no key): a frame every 10 minutes, map zoom 7 at
                        most, 100 requests a minute per address (the relay keeps under it), and
                        future ("nowcast") frames when it has them
  base map  OpenStreetMap's standard tiles with an identifying User-Agent (the QML darkens them)
  relay     127.0.0.1:<port>/<secret>/base/z/x/y and /<secret>/radar/<source>/<frame>/z/x/y: tiles
            for the QML from a cache on the box (~/.cache/couchbox-weather/tiles; radar frames
            never change, so they're kept a few hours; the map a week) or the source

Nothing is fetched ahead: the page asks for the tiles on screen, newest frame first. Demo mode
(tests, screenshots) draws a made-up map and a rain band that moves, with no network.
"""

import http.server
import math
import os
import re
import secrets
import struct
import threading
import time
import zlib
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from couchbox import __version__
from couchbox.services.maps import _Server, demo_tile

UA = f"Couchbox-Weather/{__version__} (+https://github.com/Supermaxman/couchbox)"
TIMEOUT = (6, 20)
OSM_TILES = "https://tile.openstreetmap.org"
IEM_LIST = "https://mesonet.agron.iastate.edu/json/radar.py"
IEM_TILES = "https://mesonet.agron.iastate.edu/c/tile.py/1.0.0/ridge::USCOMP-N0Q-{frame}/{z}/{x}/{y}.png"
RAINVIEWER_LIST = "https://api.rainviewer.com/public/weather-maps.json"
RAINVIEWER_HOST = "https://tilecache.rainviewer.com"
SPAN = 2 * 3600  # the loop: the last two hours
STEP = 600  # a frame every 10 minutes
FRAMES_TTL = 150  # seconds a frame list is good for
BASE_DAYS = 7
RADAR_HOURS = 6
CACHE_MB = 120

# What each source's colours mean (dBZ steps of 5 from light to heavy), for the legend. NEXRAD:
# the National Weather Service's reflectivity colours; RainViewer: its "Universal Blue" scheme
# (2), the one its public tiles still have.
SOURCES = {
    "nexrad": {
        "id": "nexrad",
        "name": "NEXRAD",
        "attribution": "Radar: NOAA NEXRAD via Iowa Environmental Mesonet · Map © OpenStreetMap contributors",
        "tile_px": 256,
        "max_zoom": 8,  # the mosaic is about 1 km a pixel: closer is just bigger
        "zoom_drop": 1,  # radar tiles one zoom out from the map's, drawn twice the size
        "legend": [
            "#04e9e7",
            "#019ff4",
            "#0300f4",
            "#02fd02",
            "#01c501",
            "#008e00",
            "#fdf802",
            "#e5bc00",
            "#fd9500",
            "#fd0000",
            "#d40000",
            "#bc0000",
            "#f800fd",
        ],
    },
    "rainviewer": {
        "id": "rainviewer",
        "name": "RainViewer",
        "attribution": "Radar: RainViewer · Map © OpenStreetMap contributors",
        "tile_px": 512,
        "max_zoom": 7,  # RainViewer's public tiles stop at 7
        "zoom_drop": 2,  # 512 px tiles two zooms out: few requests (its limit is 100 a minute)
        "legend": ["#88ddee", "#00a3e0", "#0077aa", "#005588", "#ffee00", "#ffaa00", "#ff4400", "#c10000", "#ffaaff", "#ff77ff"],
    },
}
FRAME_ID = {"nexrad": re.compile(r"\d{12}"), "rainviewer": re.compile(r"[0-9a-f]{6,40}|\d{9,11}")}


class RadarError(Exception):
    pass


def in_conus(lat, lon):
    """The lower 48 (what the NEXRAD mosaic covers)."""
    return 24 <= lat <= 50 and -125 <= lon <= -66


def pick_source(lat, lon):
    return "nexrad" if in_conus(lat, lon) else "rainviewer"


def clock(ts, clock24, tz=None):
    dt = datetime.fromtimestamp(ts, tz)
    return dt.strftime("%H:%M") if clock24 else dt.strftime("%I:%M %p").lstrip("0")


def every(frames, step=STEP):
    """Frames ({"time", ...}, oldest first) thinned to one per step, counting back from the newest."""
    out, last = [], None
    for f in reversed(frames):
        if last is None or last - f["time"] >= step - 30:
            out.append(f)
            last = f["time"]
    return out[::-1]


def parse_iem(raw, now=None, span=SPAN):
    """IEM's list of mosaic scans -> frames, oldest first: {"id": YYYYMMDDHHMI (UTC), "time"}."""
    now = now or time.time()
    frames = []
    for s in raw.get("scans") or []:
        try:
            dt = datetime.strptime(s["ts"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=UTC)
        except (KeyError, TypeError, ValueError):
            continue
        t = int(dt.timestamp())
        if now - span - 60 <= t <= now + 60:
            frames.append({"id": dt.strftime("%Y%m%d%H%M"), "time": t, "nowcast": False})
    frames.sort(key=lambda f: f["time"])
    return every(frames)


def parse_rainviewer(raw, now=None, span=SPAN):
    """RainViewer's weather-maps.json -> (tile host, frames oldest first): {"id", "time",
    "nowcast"}. The id is the last part of the frame's path (a hash, or a time in older answers)."""
    now = now or time.time()
    host = raw.get("host") or RAINVIEWER_HOST
    if not re.fullmatch(r"https://[a-z0-9.-]+\.rainviewer\.com", host):
        host = RAINVIEWER_HOST
    radar = raw.get("radar") or {}
    frames = []
    for kind in ("past", "nowcast"):
        for f in radar.get(kind) or []:
            m = re.fullmatch(r"/v2/radar/([0-9a-f]{6,40}|\d{9,11})", str(f.get("path", "")))
            if not m or not isinstance(f.get("time"), int):
                continue
            if kind == "past" and f["time"] < now - span - 60:
                continue
            frames.append({"id": m.group(1), "time": f["time"], "nowcast": kind == "nowcast"})
    frames.sort(key=lambda f: f["time"])
    return host, frames


def radar_url(source, frame, z, x, y, host=RAINVIEWER_HOST):
    if source == "nexrad":
        return IEM_TILES.format(frame=frame, z=z, x=x, y=y)
    # 512 px, colour scheme 2 (Universal Blue), smoothed, snow in the same colours as rain
    return f"{host}/v2/radar/{frame}/512/{z}/{x}/{y}/2/1_0.png"


def cache_dir():
    return Path(os.environ.get("COUCHBOX_WEATHER_CACHE") or Path.home() / ".cache/couchbox-weather") / "tiles"


def prune(limit_mb=CACHE_MB, now=None):
    """Radar frames past RADAR_HOURS and map tiles past BASE_DAYS go; then the oldest, to fit."""
    now = now or time.time()
    root = cache_dir()
    files = []
    for dirpath, _, names in os.walk(root):
        radar = Path(dirpath).relative_to(root).parts[:1] == ("radar",)
        for n in names:
            fp = os.path.join(dirpath, n)
            try:
                st = os.stat(fp)
            except OSError:
                continue
            too_old = st.st_mtime < now - (RADAR_HOURS * 3600 if radar else BASE_DAYS * 86400)
            files.append((not too_old, st.st_mtime, st.st_size, fp))
    files.sort()
    total = sum(f[2] for f in files)
    for keep, _, size, fp in files:
        if keep and total <= limit_mb * 1024 * 1024:
            break
        try:
            os.unlink(fp)
            total -= size
        except OSError:
            pass


class Bucket:
    """At most `per_minute` requests a minute: take() waits for a turn."""

    def __init__(self, per_minute):
        self.rate = per_minute / 60
        self.room = self.cap = max(1, per_minute // 6)
        self.at = time.monotonic()
        self.lock = threading.Lock()

    def take(self):
        while True:
            with self.lock:
                now = time.monotonic()
                self.room = min(self.cap, self.room + (now - self.at) * self.rate)
                self.at = now
                if self.room >= 1:
                    self.room -= 1
                    return
                wait = (1 - self.room) / self.rate
            time.sleep(wait)


class Radar:
    def __init__(self, demo=False, session=None):
        self.demo = demo
        self.http = session or requests.Session()
        self.http.headers["User-Agent"] = UA
        self.host = RAINVIEWER_HOST
        self.cache = {}  # source -> (time, frames)
        self.relay = None
        self.buckets = {"rainviewer": Bucket(90), "nexrad": Bucket(600), "base": Bucket(600)}
        self.lock = threading.Lock()

    # ------------------------------------------------------------------ frames
    def frames(self, place, clock24=False, force=False, tz=None):
        """What the page shows: the source (legend, attribution), the frames with their times
        (in tz, a zone name: Settings → Time; else the box's), the tile relay, and where to centre."""
        if not place or place.get("lat") is None:
            raise RadarError("Set your town in Settings → Time to see the radar.")
        src = pick_source(place["lat"], place["lon"])
        hit = self.cache.get(src)
        if hit and not force and time.time() - hit[0] < FRAMES_TTL:
            frames = hit[1]
        else:
            frames = self.demo_frames() if self.demo else self.fetch(src)
            self.cache[src] = (time.time(), frames)
        if not frames:
            raise RadarError("No radar pictures right now. Try again in a few minutes.")
        try:
            zone = UTC if self.demo else ZoneInfo(tz) if tz else None
        except (ValueError, KeyError):
            zone = None
        return {
            "source": SOURCES[src],
            "frames": [dict(f, label=clock(f["time"], clock24, zone)) for f in frames],
            "tiles": self.tile_base(),
            "lat": place["lat"],
            "lon": place["lon"],
            "name": place.get("name", ""),
        }

    def fetch(self, src):
        try:
            if src == "nexrad":
                now = time.time()
                fmt = lambda t: datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%dT%H:%MZ")  # noqa: E731
                r = self.http.get(
                    IEM_LIST,
                    params={
                        "operation": "list",
                        "radar": "USCOMP",
                        "product": "N0Q",
                        "start": fmt(now - SPAN - 300),
                        "end": fmt(now + 300),
                    },
                    timeout=TIMEOUT,
                )
                r.raise_for_status()
                return parse_iem(r.json(), now)
            r = self.http.get(RAINVIEWER_LIST, timeout=TIMEOUT)
            r.raise_for_status()
            self.host, frames = parse_rainviewer(r.json())
            return frames
        except (requests.RequestException, ValueError) as err:
            raise RadarError("The radar isn't answering. Check the connection.") from err

    def demo_frames(self):
        now = int(time.time()) // STEP * STEP
        return [
            {"id": datetime.fromtimestamp(t, UTC).strftime("%Y%m%d%H%M"), "time": t, "nowcast": False}
            for t in range(now - SPAN, now + 1, STEP)
        ]

    # ------------------------------------------------------------------ tiles
    def tile_base(self):
        with self.lock:
            if self.relay is None:
                self.relay = Relay(self)
        return self.relay.base

    def tile(self, kind, z, x, y, source="", frame=""):
        """PNG bytes for a map tile (kind "base") or a radar frame's tile (kind "radar")."""
        n = 2**z
        if not (0 <= y < n) or z > 19:
            raise RadarError("no such tile")
        x %= n
        if kind == "radar":
            if source not in SOURCES or not FRAME_ID[source].fullmatch(frame) or z > SOURCES[source]["max_zoom"]:
                raise RadarError("no such frame")
            if self.demo:
                return demo_radar(frame, z, x, y)
            f = cache_dir() / "radar" / source / frame / str(z) / str(x) / str(y)
            url, bucket = radar_url(source, frame, z, x, y, self.host), source
        else:
            if self.demo:
                return demo_tile(z, x, y, size=64)
            f = cache_dir() / "base" / str(z) / str(x) / str(y)
            url, bucket = f"{OSM_TILES}/{z}/{x}/{y}.png", "base"
        days = RADAR_HOURS / 24 if kind == "radar" else BASE_DAYS
        if f.exists() and f.stat().st_mtime > time.time() - days * 86400:
            return f.read_bytes()
        self.buckets[bucket].take()
        r = self.http.get(url, timeout=TIMEOUT)
        if r.status_code >= 400:
            raise RadarError(f"tile {r.status_code}")
        try:  # two requests for one tile can race: each writes its own temporary file
            f.parent.mkdir(parents=True, exist_ok=True)
            tmp = f.with_name(f"{f.name}.{secrets.token_hex(4)}.tmp")
            tmp.write_bytes(r.content)
            tmp.replace(f)
        except OSError as err:
            print(f"radar tile cache: {err}", flush=True)
        if secrets.randbelow(300) == 0:
            threading.Thread(target=prune, daemon=True).start()
        return r.content


class Relay:
    """127.0.0.1:<port>/<secret>/base/z/x/y and /<secret>/radar/<source>/<frame>/z/x/y."""

    def __init__(self, radar):
        self.secret = secrets.token_urlsafe(16)
        relay = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def do_GET(self):
                s = re.escape(relay.secret)
                m = re.fullmatch(rf"/{s}/(?:base|radar/([a-z]+)/([0-9a-f]+))/(\d+)/(-?\d+)/(\d+)(?:\?.*)?", self.path)
                if not m:
                    return self._send(404, b"")
                source, frame, z, x, y = m.groups()
                try:
                    data = radar.tile("radar" if source else "base", int(z), int(x), int(y), source or "", frame or "")
                    self._send(200, data)
                except (RadarError, requests.RequestException) as err:
                    print(f"radar tile {self.path.split('/', 2)[-1]}: {err}", flush=True)
                    self._send(502, b"")

            def _send(self, code, data):
                try:
                    self.send_response(code)
                    self.send_header("Content-Type", "image/png" if code == 200 else "text/plain")
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "max-age=3600")
                    self.end_headers()
                    self.wfile.write(data)
                except OSError:
                    pass

        self.server = _Server(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}/{self.secret}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


# ------------------------------------------------------------------ demo (tests, screenshots)
def png_rgba(width, height, rows):
    raw = b"".join(b"\x00" + r for r in rows)
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)  # noqa: E731
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 6))
        + chunk(b"IEND", b"")
    )


def demo_radar(frame, z, x, y, size=32):
    """A made-up band of showers with a heavy core, drifting east with the frames."""
    t = int(datetime.strptime(frame, "%Y%m%d%H%M").replace(tzinfo=UTC).timestamp())
    shift = 0.006 * math.sin(math.pi * (t // STEP) / 13)  # of the world's width: back and forth
    colours = [bytes.fromhex(c[1:]) for c in SOURCES["nexrad"]["legend"]]
    n = 2**z
    rows = []
    for py in range(size):
        row = bytearray()
        wy = (y + (py + 0.5) / size) / n  # 0..1 down the world
        for px in range(size):
            wx = (x + (px + 0.5) / size) / n
            d = abs((wx - 0.159 - shift) * 3 + (wy - 0.357) * 5)  # a diagonal band
            k = max(0.0, 1 - d / 0.02) * (0.6 + 0.4 * abs(((wx * 900 + wy * 700) % 2) - 1))
            if k < 0.08:
                row += b"\x00\x00\x00\x00"
            else:
                row += colours[min(len(colours) - 1, int(k * 11))] + b"\xc8"
        rows.append(bytes(row))
    return png_rgba(size, size, rows)
