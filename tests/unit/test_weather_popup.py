"""The weather pop-up: rain due soon from Open-Meteo's 15-minute steps (once a shower), official
warnings (once each, across their updates), quiet hours, the words it shows, and in the pop-up
service, that a camera always gets the corner while weather waits for it."""

import importlib.machinery
import importlib.util
import os
import pathlib
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from couchbox import frigate_popup as fp
from couchbox import settings
from couchbox import weather_popup as wp
from couchbox.services import weather

ROOT = pathlib.Path(__file__).resolve().parents[2]
NOW = 1_800_000_000.0  # a quarter-hour step: steps end at NOW, NOW + 900, ...
LA = ZoneInfo("America/Los_Angeles")


def steps(*mm, snow=False):
    """Open-Meteo's minutely_15 from the step before now: mm per 15 minutes."""
    times = [int(NOW) + 900 * i for i in range(len(mm))]
    return {"time": times, "precipitation": list(mm), "rain": [0.0 if snow else x for x in mm]}


# ---------------------------------------------------------------------- rain
def test_rain_starting_soon_pops_with_its_length():
    # now is in the step ending NOW + 900; rain falls in the steps ending +1800 ... +4500
    r = wp.rain_ahead(steps(0, 0, 0.4, 0.8, 1.1, 0.6, 0, 0), NOW + 60)
    assert r == {"start": NOW + 900, "end": NOW + 4500, "snow": False, "openEnded": False}
    assert wp.rain_text(r, NOW + 60) == ("Rain in about 15 minutes", "Lasting an hour")


def test_no_pop_while_dry_far_off_or_already_raining():
    assert wp.rain_ahead(steps(0, 0, 0, 0, 0), NOW + 60) is None
    assert wp.rain_ahead(steps(0, 0, 0, 0.5, 0.5), NOW + 60) is None  # starts in 29 min: later
    assert wp.rain_ahead(steps(0, 0.3, 0.5, 0), NOW + 60) == {"raining": True}
    assert wp.rain_ahead(steps(0.3, 0, 0, 0), NOW + 60) == {"raining": True}  # just stopped: same rain
    assert wp.rain_ahead(steps(0, 0, 0.1, 0, 0, 0), NOW + 60) is None  # a blip in the model


def test_a_dry_step_between_wet_ones_is_one_shower():
    r = wp.rain_ahead(steps(0, 0, 0.5, 0, 0.5, 0.5, 0, 0, 0.5), NOW + 60)
    assert (r["start"], r["end"]) == (NOW + 900, NOW + 4500)


def test_snow_and_rain_past_the_forecast():
    r = wp.rain_ahead(steps(0, 0, *[0.6] * 20, snow=True), NOW + 60)
    assert r["snow"] and r["openEnded"]
    assert wp.rain_text(r, NOW + 60) == ("Snow in about 15 minutes", "Lasting several hours")


@pytest.mark.parametrize(
    "minutes,words",
    [
        (15, "lasting 15 minutes"),
        (30, "lasting half an hour"),
        (45, "lasting 45 minutes"),
        (60, "lasting an hour"),
        (90, "lasting an hour and a half"),
        (120, "lasting 2 hours"),
        (195, "lasting 3 hours"),
    ],
)
def test_how_long_it_rains(minutes, words):
    assert wp.lasting(minutes * 60) == words


def test_lead_words():
    r = {"start": NOW + 600, "end": NOW + 4200}
    assert wp.rain_text(r, NOW)[0] == "Rain in about 10 minutes"
    assert wp.rain_text(r, NOW + 400)[0] == "Rain in a few minutes"
    assert wp.rain_text(r, NOW + 700) == ("Rain starting now", "Lasting an hour")  # waited for a camera


def test_each_shower_pops_once():
    t = wp.Tracker()
    m = steps(0, 0, 0.5, 0.5, 0.5, 0.5, 0, 0, 0, 0, 0, 0, 0, 0)
    r = t.next_rain(m, NOW + 60)
    assert r
    t.rained(r)
    assert t.next_rain(m, NOW + 360) is None  # the same forecast five minutes later
    assert t.next_rain(steps(0, 0.5, 0.5, 0), NOW + 960) is None  # it's raining
    # dry for over an hour after it ends, then a new shower: pops
    later = NOW + 5400 + 3600 + 900
    m2 = {"time": [int(later) + 900 * i for i in range(6)], "precipitation": [0, 0, 0.5, 0.5, 0, 0], "rain": [0, 0, 0.5, 0.5, 0, 0]}
    assert t.next_rain(m2, later + 60)


# ---------------------------------------------------------------------- warnings
def feature(event, vtec="", rid="urn:a", refs=(), severity="Severe", ends="2027-01-15T19:15:00-06:00", mtype="Alert"):
    return {
        "properties": {
            "id": rid,
            "event": event,
            "severity": severity,
            "status": "Actual",
            "messageType": mtype,
            "ends": ends,
            "references": [{"identifier": r} for r in refs],
            "parameters": {"VTEC": [vtec]} if vtec else {},
        }
    }


def test_warnings_carry_what_tells_their_updates_apart():
    raw = {
        "features": [
            feature("Severe Thunderstorm Warning", "/O.NEW.KPAH.SV.W.0374.261112T0016Z-261112T0115Z/", "urn:1"),
            feature("Flood Warning", "/O.CAN.KPQR.FL.W.0012.000000T0000Z-261112T0115Z/", "urn:2", refs=["urn:0"]),
        ]
    }
    a, b = weather.parse_alerts(raw)
    assert (a["key"], a["id"], a["cancelled"], a["references"]) == ("KPAH.SV.W.0374", "urn:1", False, [])
    assert a["ends"] == int(datetime.fromisoformat("2027-01-15T19:15:00-06:00").timestamp())
    assert (b["key"], b["cancelled"], b["references"]) == ("KPQR.FL.W.0012", True, ["urn:0"])


def test_only_warnings_pop_once_each_across_updates():
    t = wp.Tracker()
    now = datetime(2027, 1, 15, 18, 0, tzinfo=ZoneInfo("America/Chicago")).timestamp()
    first = weather.parse_alerts(
        {
            "features": [
                feature("Severe Thunderstorm Warning", "/O.NEW.KPAH.SV.W.0374.x/", "urn:1"),
                feature("Wind Advisory", "", "urn:9", severity="Moderate"),
                feature("Winter Storm Watch", "", "urn:8"),
                feature("Tornado Emergency", "", "urn:7", severity="Extreme"),
            ]
        }
    )
    new = t.next_warnings(first, now)
    assert [a["event"] for a in new] == ["Tornado Emergency", "Severe Thunderstorm Warning"]
    for a in new:
        t.warned_of(a, now)
    update = weather.parse_alerts(
        {
            "features": [
                feature("Severe Thunderstorm Warning", "/O.CON.KPAH.SV.W.0374.x/", "urn:3", refs=["urn:1"], mtype="Update"),
                feature("Tornado Emergency", "", "urn:5", refs=["urn:7"], severity="Extreme", mtype="Update"),
            ]
        }
    )
    assert t.next_warnings(update, now + 120) == []
    # a cancellation, or one that has ended, never pops
    gone = weather.parse_alerts(
        {
            "features": [
                feature("Flood Warning", "/O.CAN.KPQR.FL.W.0012.x/", "urn:6"),
                feature("Flood Warning", "", "urn:4", ends="2027-01-15T17:00:00-06:00"),
            ]
        }
    )
    assert t.next_warnings(gone, now) == []


def test_until_words():
    now = datetime(2027, 1, 15, 18, 0, tzinfo=LA).timestamp()
    assert wp.until_text(now + 6300, now, LA) == "Until 7:45 PM"
    assert wp.until_text(now + 6300, now, LA, clock24=True) == "Until 19:45"
    assert wp.until_text(now + 86400, now, LA) == "Until Sat 6:00 PM"
    assert wp.until_text(0, now, LA) == ""


# ---------------------------------------------------------------------- settings
@pytest.mark.parametrize(
    "window,hm,quiet",
    [
        ("22:00-07:00", (23, 30), True),
        ("22:00-07:00", (6, 59), True),
        ("22:00-07:00", (7, 0), False),
        ("22:00-07:00", (21, 59), False),
        ("09:00-17:00", (12, 0), True),
        ("09:00-17:00", (18, 0), False),
        ("", (3, 0), False),
    ],
)
def test_quiet_hours(window, hm, quiet):
    assert wp.quiet(window, datetime(2027, 1, 15, *hm)) is quiet


def test_settings_defaults_and_quiet_hours_are_checked():
    p = wp.prefs(settings.load())
    assert p == {"rain": True, "rain_quiet": "22:00-07:00", "warnings": True, "warnings_quiet": ""}
    settings.validate("weather.popup.rain_quiet", "")
    settings.validate("weather.popup.warnings_quiet", "23:00-06:30")
    with pytest.raises(settings.SettingsError):
        settings.validate("weather.popup.rain_quiet", "10pm-7am")


def test_the_weather_app_in_front():
    assert fp.is_app({"class": "couchbox-weather"}, "couchbox-weather")
    assert fp.is_app({"app": "couchbox-weather.desktop"}, "couchbox-weather")
    assert not fp.is_app({"class": "couchbox-frigate"}, "couchbox-weather")
    assert fp.is_frigate({"class": "couchbox-frigate"})


# ---------------------------------------------------------------------- the pop-up service
@pytest.fixture
def service(monkeypatch):
    pytest.importorskip("PySide6.QtCore")
    monkeypatch.setenv("COUCHBOX_MUTE", "")
    monkeypatch.setenv("QSG_RENDER_LOOP", "")
    loader = importlib.machinery.SourceFileLoader("couchbox_frigate_popup", str(ROOT / "bin/couchbox-frigate-popup"))
    spec = importlib.util.spec_from_loader("couchbox_frigate_popup", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    p = mod.Popup(demo=True)
    p.wx = dict(p.wx, rain_quiet="", warnings_quiet="")  # whatever the time the tests run
    p.shown = []
    p.present.connect(lambda js: p.shown.append(js))
    p.radar.frames = lambda *a, **kw: None  # no radar relay in tests
    p.client = lambda: type("F", (), {"live": lambda self, s: {"url": "rtsp://cam"}})()
    yield p
    os.environ.pop("COUCHBOX_MUTE", None)


def camera(rid="cam-1"):
    return {
        "type": "camera",
        "id": rid,
        "camera": "front_door",
        "label": "Front door",
        "seen": "Person",
        "kind": "person",
        "severity": "alert",
        "live": True,
        "end": 0,
        "test": False,
    }


def rain(p, now):
    return p.rain_item({"start": now + 900, "end": now + 4500, "snow": False})


def test_weather_waits_while_a_camera_shows_then_has_its_turn(service):
    import time

    p = service
    p.show(camera())
    assert p.show_weather(rain(p, time.time())) is False
    assert p.current["type"] == "camera" and [w["id"] for w in p.waiting] == [p.waiting[0]["id"]]
    p.hide("back")
    p.offer_waiting()
    assert p.current["type"] == "weather" and p.current["label"].startswith("Rain in about")
    assert p.waiting == []


def test_a_camera_over_the_weather_sends_it_back_to_wait(service):
    import time

    p = service
    now = time.time()
    p.show_weather(p.warning_item({"key": "KPAH.SV.W.0374", "event": "Severe Thunderstorm Warning", "ends": now + 3600}))
    assert p.current["weather"] == "warnings"
    p.show(camera())
    assert p.current["type"] == "camera"
    assert [w["label"] for w in p.waiting] == ["Severe Thunderstorm Warning"]
    p.hide("timeout")
    p.offer_waiting()
    assert p.current["label"] == "Severe Thunderstorm Warning" and p.current["seen"].startswith("Until ")


def test_a_warning_goes_before_rain_and_stale_rain_is_dropped(service):
    import time

    p = service
    now = time.time()
    p.show_weather(p.warning_item({"key": "K.TO.W.1", "event": "Tornado Warning", "ends": now + 3600}))
    assert p.show_weather(rain(p, now)) is False  # rain waits for the warning
    p.show_weather(p.warning_item({"key": "K.SV.W.2", "event": "Severe Thunderstorm Warning", "ends": now + 3600}))
    assert p.current["label"] == "Severe Thunderstorm Warning"  # a warning replaces a warning
    old = p.rain_item({"start": now - wp.LATE - 60, "end": now + 3600, "snow": False})
    p.waiting.append(old)
    p.hide("back")
    p.offer_waiting()
    assert p.current["weather"] == "rain" and p.current["id"] != old["id"]
    assert p.waiting == []


def test_ok_on_weather_opens_the_radar_and_back_dismisses(service, monkeypatch):
    import time

    p = service
    opened = []
    import threading

    monkeypatch.setattr(threading, "Thread", lambda target, **kw: type("T", (), {"start": lambda self: opened.append(target.__name__)})())
    p.show_weather(rain(p, time.time()))
    assert p.key("ok") == {"handled": True, "did": "opened the radar"}
    assert opened == ["open_radar"] and p.current is None
    p.show_weather(rain(p, time.time() + 1))
    assert p.key("back")["handled"] and p.current is None


def test_rain_switched_off_meanwhile_isnt_shown_after_waiting(service):
    import time

    p = service
    p.wx = dict(p.wx, rain=False)
    assert not p.still_good(rain(p, time.time()), time.time())
