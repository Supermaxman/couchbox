"""The Weather app's rain radar (services/radar.py): which source covers a place, the frame lists
from IEM and RainViewer, tile URLs, the relay and its cache, and the demo frames."""

import os
import time
import urllib.request
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from couchbox.services import radar


class Resp:
    def __init__(self, body=None, status=200, content=b"PNG"):
        self.body, self.status_code, self.content = body, status, content

    def json(self):
        return self.body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise radar.requests.HTTPError(str(self.status_code))


class FakeHttp:
    def __init__(self, answers):
        self.answers, self.calls, self.headers = answers, [], {}

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        for prefix, resp in self.answers.items():
            if url.startswith(prefix):
                return resp
        raise AssertionError(f"unexpected {url}")


@pytest.fixture(autouse=True)
def cache(tmp_path, monkeypatch):
    monkeypatch.setenv("COUCHBOX_WEATHER_CACHE", str(tmp_path / "cache"))
    return tmp_path / "cache" / "tiles"


def iso(t):
    return datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%dT%H:%MZ")


def test_the_lower_48_get_nexrad_and_everywhere_else_rainviewer():
    assert radar.pick_source(45.6, -122.7) == "nexrad"  # Portland
    assert radar.pick_source(25.8, -80.2) == "nexrad"  # Miami
    assert radar.pick_source(61.2, -149.9) == "rainviewer"  # Anchorage
    assert radar.pick_source(21.3, -157.9) == "rainviewer"  # Honolulu
    assert radar.pick_source(52.5, 13.4) == "rainviewer"  # Berlin
    assert radar.pick_source(53.5, -113.5) == "rainviewer"  # Edmonton
    assert radar.pick_source(19.4, -99.1) == "rainviewer"  # Mexico City
    assert radar.pick_source(49.3, -123.1) == "nexrad"  # Vancouver, BC: US radars reach over the border


def test_iem_scans_become_a_frame_every_ten_minutes_for_two_hours():
    now = 1_800_000_000 // 300 * 300
    scans = [{"ts": iso(t)} for t in range(now - 3 * 3600, now + 1, 300)] + [{"ts": "garbage"}, {}]
    frames = radar.parse_iem({"scans": scans}, now=now)
    times = [f["time"] for f in frames]
    assert times[-1] == now and times[0] == now - 2 * 3600
    assert all(b - a == 600 for a, b in zip(times, times[1:], strict=False))
    assert len(frames) == 13
    assert frames[-1]["id"] == datetime.fromtimestamp(now, UTC).strftime("%Y%m%d%H%M")
    assert not any(f["nowcast"] for f in frames)


def test_iem_gaps_keep_the_newest_and_step_back_from_it():
    now = 1_800_000_000 // 300 * 300
    ts = [now, now - 300, now - 900, now - 1200, now - 1500, now - 2100]
    frames = radar.parse_iem({"scans": [{"ts": iso(t)} for t in ts]}, now=now)
    assert [f["time"] for f in frames] == [now - 2100, now - 1500, now - 900, now]


def test_rainviewer_frames_hashes_nowcast_and_a_safe_host():
    now = 1_793_022_623
    raw = {
        "host": "https://tilecache.rainviewer.com",
        "radar": {
            "past": [
                {"time": now - 3 * 3600, "path": "/v2/radar/aaaaaa000000"},  # older than the loop
                {"time": now - 600, "path": "/v2/radar/5ca4b7993d19"},
                {"time": now - 1200, "path": "/v2/radar/1793021400"},  # a time, as it used to be
                {"time": now - 300, "path": "/../../etc/passwd"},
            ],
            "nowcast": [{"time": now + 600, "path": "/v2/radar/f2a9c46de729"}],
        },
    }
    host, frames = radar.parse_rainviewer(raw, now=now)
    assert host == "https://tilecache.rainviewer.com"
    assert [f["id"] for f in frames] == ["1793021400", "5ca4b7993d19", "f2a9c46de729"]
    assert [f["nowcast"] for f in frames] == [False, False, True]
    assert radar.parse_rainviewer(dict(raw, host="https://evil.example.com"), now=now)[0] == radar.RAINVIEWER_HOST


def test_tile_urls():
    assert radar.radar_url("nexrad", "202610261310", 7, 20, 44) == (
        "https://mesonet.agron.iastate.edu/c/tile.py/1.0.0/ridge::USCOMP-N0Q-202610261310/7/20/44.png"
    )
    assert radar.radar_url("rainviewer", "5ca4b7993d19", 5, 4, 11) == (
        "https://tilecache.rainviewer.com/v2/radar/5ca4b7993d19/512/5/4/11/2/1_0.png"
    )
    for s in radar.SOURCES.values():
        assert s["legend"] and s["attribution"] and s["tile_px"] in (256, 512)
    assert radar.SOURCES["rainviewer"]["max_zoom"] == 7  # RainViewer's public tiles stop there


def test_frames_need_a_town_and_say_where_they_come_from(monkeypatch):
    r = radar.Radar(demo=True)
    with pytest.raises(radar.RadarError):
        r.frames(None)
    d = r.frames({"name": "Lakeside", "lat": 45.6, "lon": -122.7}, clock24=True)
    assert d["source"]["id"] == "nexrad" and d["name"] == "Lakeside"
    assert len(d["frames"]) == 13 and d["frames"][-1]["label"].count(":") == 1
    assert d["tiles"].startswith("http://127.0.0.1:")


def test_frame_lists_are_cached_and_errors_are_plain(monkeypatch):
    now = time.time() // 300 * 300
    http = FakeHttp({radar.IEM_LIST: Resp({"scans": [{"ts": iso(now - 600)}, {"ts": iso(now)}]})})
    r = radar.Radar(session=http)
    place = {"name": "X", "lat": 40.0, "lon": -100.0}
    assert len(r.frames(place)["frames"]) == 2
    one = r.frames(place, tz="America/Chicago")["frames"][-1]
    assert one["label"] == datetime.fromtimestamp(one["time"], ZoneInfo("America/Chicago")).strftime("%I:%M %p").lstrip("0")
    assert r.frames(place, tz="Not/AZone")["frames"]  # a bad zone: the box's own
    assert len(http.calls) == 1
    assert http.calls[0][1]["radar"] == "USCOMP" and http.calls[0][1]["product"] == "N0Q"
    r2 = radar.Radar(session=FakeHttp({radar.IEM_LIST: Resp(status=503)}))
    with pytest.raises(radar.RadarError, match="isn't answering"):
        r2.frames(place)
    r3 = radar.Radar(session=FakeHttp({radar.IEM_LIST: Resp({"scans": []})}))
    with pytest.raises(radar.RadarError, match="No radar"):
        r3.frames(place)


def test_tiles_are_checked_cached_and_relayed(cache):
    http = FakeHttp({"https://mesonet": Resp(content=b"\x89PNG radar"), radar.OSM_TILES: Resp(content=b"\x89PNG map")})
    r = radar.Radar(session=http)
    assert r.tile("radar", 7, 20, 44, "nexrad", "202610261310") == b"\x89PNG radar"
    assert r.tile("radar", 7, 20, 44, "nexrad", "202610261310") == b"\x89PNG radar"
    assert len(http.calls) == 1  # the second came from the cache
    assert (cache / "radar/nexrad/202610261310/7/20/44").exists()
    assert r.tile("base", 8, -1, 90) == b"\x89PNG map"
    assert http.calls[-1][0] == f"{radar.OSM_TILES}/8/255/90.png"  # x wraps around the world
    for bad in [
        ("radar", 9, 1, 1, "nexrad", "202610261310"),
        ("radar", 3, 1, 1, "nexrad", "../x"),
        ("radar", 3, 1, 1, "other", "1"),
        ("base", 3, 1, 8),
    ]:
        with pytest.raises(radar.RadarError):
            r.tile(*bad)

    base = r.tile_base()
    with urllib.request.urlopen(f"{base}/radar/nexrad/202610261310/7/20/44") as resp:
        assert resp.read() == b"\x89PNG radar" and resp.headers["Content-Type"] == "image/png"
    for path in ("/radar/nexrad/zz/7/20/44", "/../base/1/1/1"):
        with pytest.raises(urllib.request.HTTPError):
            urllib.request.urlopen(base + path)
    with pytest.raises(urllib.request.HTTPError):  # the secret is part of the address
        urllib.request.urlopen(base.rsplit("/", 1)[0] + "/wrong/base/1/1/1")


def test_prune_drops_old_radar_frames_first(cache):
    old_radar = cache / "radar/nexrad/202001010000/7/1/1"
    new_radar = cache / "radar/nexrad/202610261310/7/1/1"
    week_base = cache / "base/7/1/1"
    for f in (old_radar, new_radar, week_base):
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x" * 100)
    two_days = time.time() - 2 * 86400
    os.utime(old_radar, (two_days, two_days))
    os.utime(week_base, (two_days, two_days))
    radar.prune()
    assert not old_radar.exists() and new_radar.exists() and week_base.exists()
    radar.prune(limit_mb=0)
    assert not new_radar.exists() and not week_base.exists()


def test_the_bucket_spaces_out_requests(monkeypatch):
    slept = []
    clock = [0.0]
    monkeypatch.setattr(radar.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(radar.time, "sleep", lambda s: slept.append(s) or clock.__setitem__(0, clock[0] + s))
    b = radar.Bucket(60)  # one a second, 10 at once
    for _ in range(12):
        b.take()
    assert sum(slept) == pytest.approx(2.0)


def test_demo_tiles_are_pngs():
    r = radar.Radar(demo=True)
    frame = r.demo_frames()[-1]["id"]
    assert r.tile("radar", 8, 40, 91, "nexrad", frame)[:4] == b"\x89PNG"
    assert r.tile("base", 8, 40, 91)[:4] == b"\x89PNG"
