"""The morning show (couchbox.show): when it's made and what night it covers, the backyard
camera, the new videos, the tile until noon, and While you were out giving way."""

import datetime
import json
from pathlib import Path

import pytest

from couchbox import away, home, ontv, settings, show

H = 3600
DAY = datetime.date(2026, 11, 12)
MORNING = show.at_hour(DAY, 4.25)  # the show is being made


# ------------------------------------------------------------------ when
def test_making_time_is_four_to_noon():
    assert not show.making_time(show.at_hour(DAY, 3.9))
    assert show.making_time(show.at_hour(DAY, 4))
    assert show.making_time(show.at_hour(DAY, 11.9))
    assert not show.making_time(show.at_hour(DAY, 12))


def test_the_night_starts_when_the_tv_was_last_used():
    yesterday = DAY - datetime.timedelta(days=1)
    # watched until 23:40: the night is from then
    assert show.night(MORNING, show.at_hour(yesterday, 23 + 40 / 60)) == (show.at_hour(yesterday, 23 + 40 / 60), MORNING)
    # last used in the afternoon (or not for days): from the evening
    assert show.night(MORNING, show.at_hour(yesterday, 15))[0] == show.at_hour(yesterday, show.EVENING)
    assert show.night(MORNING, 0)[0] == show.at_hour(yesterday, show.EVENING)


def test_sunrise_and_sunset():
    rise, sets = show.sun_times(datetime.date(2026, 6, 21), 51.48, 0.0)  # Greenwich, midsummer
    utc = lambda t: datetime.datetime.fromtimestamp(t, datetime.UTC)  # noqa: E731
    assert (utc(rise).hour, utc(rise).minute // 10) == (3, 4)  # 03:43 UTC
    assert (utc(sets).hour, utc(sets).minute // 10) == (20, 2)  # 20:21 UTC
    assert show.sun_times(datetime.date(2026, 12, 21), 80.0, 0.0) is None  # polar night
    # no town: fixed hours
    assert show.daylight(DAY, None) == (show.at_hour(DAY, 7), show.at_hour(DAY, 18))
    start, end = show.daylight(datetime.date(2026, 6, 21), {"lat": 51.48, "lon": 0.0})
    assert end - start == pytest.approx(sets - rise + 2 * show.DAY_PAD)


def test_yard_times_span_the_day():
    t = show.yard_times(1000.0, 1000.0 + 239 * 60)
    assert len(t) == show.YARD_FRAMES and t[0] == 1000.0 and t[-1] == 1000.0 + 239 * 60


# ------------------------------------------------------------------ the backyard
def test_the_backyard_camera():
    side = {"front_door": True, "backyard": True, "backyard_left": True, "garage": True, "kitchen": False}
    assert show.backyard(side, {}) == "backyard"  # the main one, not its _left
    assert show.backyard(side, {}, "backyard_left") == "backyard_left"  # chosen in Settings
    assert show.backyard(side, {}, "gone") == "backyard"  # (a camera Frigate no longer has)
    assert show.backyard({"cam1": True, "cam2": True}, {"cam2": "Garden"}) == "cam2"  # its friendly name
    assert show.backyard({"front_door": True, "driveway": True, "shed": True}, {}) == "shed"
    assert show.backyard({"front_door": True}, {}) == "front_door"
    assert show.backyard({"kitchen": False}, {}) is None


# ------------------------------------------------------------------ YouTube
def video(i, ago, duration="12:00", progress=0.0, live=False):
    return {
        "type": "video",
        "id": i,
        "title": f"Video {i}",
        "thumb": "",
        "lines": ["A channel", f"1K views • {ago}"],
        "duration": duration,
        "progress": progress,
        "live": live,
    }


def test_new_videos():
    page = {
        "shelves": [
            {"items": [video("aaaaaaaaaa1", "13 days ago"), video("aaaaaaaaaa2", "5 hours ago")]},
            {
                "items": [
                    video("aaaaaaaaaa3", "Streamed 25 minutes ago"),
                    video("aaaaaaaaaa4", "1 hour ago", duration="0:22"),
                    video("aaaaaaaaaa5", "2 hours ago", progress=0.5),
                    video("aaaaaaaaaa6", "3 hours ago", live=True),
                    video("aaaaaaaaaa2", "5 hours ago"),
                    video("aaaaaaaaaa7", "1 day ago"),
                ]
            },
        ]
    }
    got = show.new_videos(page, now=1_800_000_000)
    # newest first; old ones, Shorts, started ones and live ones left out; one of each
    assert [v["id"] for v in got] == ["aaaaaaaaaa3", "aaaaaaaaaa2", "aaaaaaaaaa7"]
    assert got[0]["target"] == "youtube:video:aaaaaaaaaa3" and got[0]["channel"] == "A channel"
    assert show.ago("2 weeks ago") == 14 * 86400 and show.ago("no age") is None
    assert show.when_published(1000, 1000 + 5 * H) == "5 h ago" and show.when_published(1000, 1000 + 25 * H) == "yesterday"


# ------------------------------------------------------------------ the tile
def test_the_tile_and_how_long():
    s = show.demo_show(now=MORNING)
    t = s["tile"]
    assert t["name"] == "Morning show" and t["target"] == "show:morning" and t["show"] is True
    assert t["subtitle"].startswith(f"{DAY:%A} · ")
    assert [p["kind"] for p in s["parts"]] == ["yard", "night", "pets", "weather", "videos"]
    assert show.length_label(92) == "1½ min" and show.length_label(75) == "1½ min" and show.length_label(30) == "30 s"


def test_offered_until_noon_or_watched(box):
    tv = box / "home/tv"
    away.write_json(show.show_file(tv), show.demo_show(now=MORNING))
    assert show.current(tv, now=MORNING)["tile"]["id"] == "show:morning"
    assert show.made_today(tv, now=MORNING)
    assert show.current(tv, now=show.at_hour(DAY, 12)) is None  # noon
    assert show.current(tv, now=show.at_hour(DAY + datetime.timedelta(days=1), 8)) is None  # yesterday's
    show.mark_seen(tv)
    assert show.current(tv, now=MORNING) is None


def test_home_json_names_the_show_file(box):
    assert home.row_json()["morning"]["file"].endswith(".cache/couchbox-morning/show.json")
    settings.update({"home.morning": False})
    assert home.row_json()["morning"] is None


def test_the_tile_opens_the_show_and_moments_open_in_frigate():
    assert ontv.split_target("show:morning") == ("show", "morning")
    assert ontv.launch_command("show", "morning", unit="u")[-3:] == ["/usr/lib/couchbox/bin/couchbox-show", "--open", "morning"]
    assert ontv.split_target("frigate:recording:back_yard@1794427223-1794427243")[0] == "frigate"
    for bad in ("show:evening", "frigate:recording:x;y@1794427223-1794427243", "frigate:recording:x@now-later"):
        with pytest.raises(ValueError):
            ontv.split_target(bad)


# ------------------------------------------------------------------ While you were out gives way
def test_while_you_were_out_leaves_the_shows_night_out(box):
    tv = box / "home/tv"
    assert show.covers(tv, now=MORNING) is None
    s = show.demo_show(now=MORNING)
    away.write_json(show.show_file(tv), s)
    night = show.covers(tv, now=show.at_hour(DAY, 7.5))
    assert night == tuple(s["night"])
    a, b = night
    # out from 23:00 (the show's night) to 07:30: only 04:00 to 07:30 is left for the reel
    assert show.uncovered(a, show.at_hour(DAY, 7.5), night) == pytest.approx(show.at_hour(DAY, 7.5) - b)
    # back at 04:10: nothing left worth a card
    assert show.uncovered(a, b + 600, night) < away.MIN_AWAY
    # away for two days: the days before the night count too
    assert show.uncovered(a - 40 * H, show.at_hour(DAY, 7.5), night) == pytest.approx(40 * H + show.at_hour(DAY, 7.5) - b)
    assert show.covers(tv, now=show.at_hour(DAY, 13)) is None  # the afternoon: no show, the whole absence


def test_the_shared_reel_clip_shape():
    c = {
        "id": "r1",
        "camera": "front_door",
        "section": "outside",
        "severity": "alert",
        "start": 1000.0,
        "end": 1020.0,
        "objects": ["person"],
        "thumb": 0,
        "file": "/x.mp4",
        "poster": "",
        "caption": "Someone at the door",
    }
    clip = away.reel_clip(c, "Front door", False)
    assert clip["what"] == "Someone at the door" and clip["review"]["id"] == "r1" and clip["cameraLabel"] == "Front door"
    json.dumps(clip)
    assert Path(show.cache_dir(Path("/h"))) == Path("/h/.cache/couchbox-morning")
