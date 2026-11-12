"""The morning show: each morning a tile at the front of the home screen offers a short, silent
show about the house, made overnight. OK plays it (about a minute and a half, captions, no
sound); nothing plays by itself, and the tile goes at noon (or once the show is watched to the end).

In order, each part only when there's something for it:
  yard     yesterday at the backyard camera, sunrise to sunset in about YARD_SECONDS: stills from
           Frigate's recordings (Frigate cuts them; the TV only downloads JPEGs and flips through
           them: nothing is encoded on the box)
  night    overnight camera moments, captioned (couchbox.away's picking and captions, over the night)
  pets     the pets' best of yesterday (the same, the pets only, over yesterday's day)
  weather  the radar and today's forecast line (both fetched when the show plays)
  videos   new videos from the YouTube subscriptions of the profile the YouTube app last watched as

When: the night is from when the TV was last used in the evening (no earlier than EVENING
yesterday) until the show is made. It's made from MAKE_AT, once the TV has been idle for
IDLE (no remote press, nothing playing) and the updater isn't installing (its hours are
02:00-06:00 by default; it installs only when nobody is watching too), so it never competes
with someone watching late. Making takes a few minutes and runs off the box: Frigate decodes
the stills and cuts the clips, the assistant's model (couchbox-voice's /look) writes captions.

"While you were out" gives way: on a morning with a show, its reel leaves out the night the
show covers (covers()): back at 07:30 after a night with the TV unused since 23:00, the reel
holds 04:00 to 07:30 only (no card when that's under 20 minutes or has nothing worth showing).

Which camera is the backyard: Settings → Home → Morning show camera (home.morning_camera, a
Frigate camera name), else the outside camera (Frigate's camera groups, as couchbox.away reads
them) whose name says yard, garden or patio, the main one before its _left and _right.

Files (the TV user's):
  ~/.cache/couchbox-morning/show.json   the show, for the home screen and the player:
                                        {date, made, until (noon), night, parts, tile, cameras, seen}
  ~/.cache/couchbox-morning/yard/       the backyard's stills
  ~/.cache/couchbox-morning/*.mp4, *.jpg  the clips and a still of each
"""

import datetime
import math
import re
import time
from pathlib import Path
from typing import Any

from couchbox import away

MAKE_AT = 4  # o'clock: the show is made from then (the night up to then)
NOON = 12  # the tile goes at noon
EVENING = 21  # the night starts no earlier than this, yesterday
IDLE = 20 * 60  # the TV unused this long before the show is made
YARD_SECONDS = 20.0
YARD_FRAMES = 240  # stills of the day (12 a second)
YARD_HEIGHT = 720
YARD_MIN = 60  # fewer stills than this (no recordings): no sped-up day
NIGHT_CLIPS = 6
PET_CLIPS = 3
WEATHER_SECONDS = 12.0
VIDEOS_SECONDS = 15.0
MAX_VIDEOS = 6
NEW_VIDEOS = 30 * 3600  # published this recently: new
MIN_VIDEO = 60  # seconds: shorter ones (Shorts) are left out
DAY_PAD = 20 * 60  # the yard from a little before sunrise to a little after sunset
DAY_FALLBACK = (7, 18)  # (no town set: these hours)

YARD_WORDS = (r"back ?yard", r"garden", r"patio", r"yard", r"lawn", r"deck", r"pool")
NOT_YARD = r"front|door|drive|garage|street|porch|gate|side|road|parking"

TITLES = {
    "yard": "Yesterday, sped up",
    "night": "Overnight",
    "pets": "The pets yesterday",
    "weather": "Today",
    "videos": "New from your subscriptions",
}
GLOW = "#f59e0b"  # the tile's glow: morning


# ------------------------------------------------------------------ where things are
def cache_dir(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".cache/couchbox-morning"


def show_file(home: Path | None = None) -> Path:
    return cache_dir(home) / "show.json"


# ------------------------------------------------------------------ when
def at_hour(day: datetime.date, hour: float) -> float:
    """Unix time of day at hour (local time, the box's zone)."""
    h = int(hour)
    return datetime.datetime(day.year, day.month, day.day, h, int(round((hour - h) * 60))).timestamp()


def today(now: float) -> datetime.date:
    return datetime.date.fromtimestamp(now)


def making_time(now: float) -> bool:
    """Whether it's the time of day to make this morning's show (MAKE_AT to noon)."""
    d = today(now)
    return at_hour(d, MAKE_AT) <= now < at_hour(d, NOON)


def night(now: float, last_use: float) -> tuple[float, float]:
    """The night the show covers: from when the TV was last used (no earlier than EVENING
    yesterday) to now."""
    evening = at_hour(today(now) - datetime.timedelta(days=1), EVENING)
    start = max(evening, last_use if last_use < now else evening)
    return start, now


def sun_times(day: datetime.date, lat: float, lon: float) -> tuple[float, float] | None:
    """Sunrise and sunset on day at lat, lon (unix times; the sunrise equation, within a few
    minutes), or None when the sun doesn't rise or set that day."""
    jd_noon = day.toordinal() + 1721425.0  # the Julian day at noon UTC
    n = jd_noon - 2451545.0 + 0.0008
    j = n - lon / 360
    m = math.radians((357.5291 + 0.98560028 * j) % 360)
    c = 1.9148 * math.sin(m) + 0.02 * math.sin(2 * m) + 0.0003 * math.sin(3 * m)
    lam = math.radians((math.degrees(m) + c + 180 + 102.9372) % 360)
    transit = 2451545.0 + j + 0.0053 * math.sin(m) - 0.0069 * math.sin(2 * lam)
    dec = math.asin(math.sin(lam) * math.sin(math.radians(23.4397)))
    phi = math.radians(lat)
    cos_w = (math.sin(math.radians(-0.833)) - math.sin(phi) * math.sin(dec)) / (math.cos(phi) * math.cos(dec))
    if not -1 <= cos_w <= 1:
        return None
    w = math.degrees(math.acos(cos_w)) / 360
    unix = lambda jd: (jd - 2440587.5) * 86400  # noqa: E731
    return unix(transit - w), unix(transit + w)


def daylight(day: datetime.date, place: dict[str, Any] | None) -> tuple[float, float]:
    """The part of day the sped-up yard covers: a little before sunrise to a little after sunset."""
    sun = sun_times(day, place["lat"], place["lon"]) if place and place.get("lat") is not None else None
    if not sun:
        return at_hour(day, DAY_FALLBACK[0]), at_hour(day, DAY_FALLBACK[1])
    return sun[0] - DAY_PAD, sun[1] + DAY_PAD


def yard_times(start: float, end: float, n: int = YARD_FRAMES) -> list[float]:
    return [round(start + (end - start) * i / (n - 1), 1) for i in range(n)]


# ------------------------------------------------------------------ the backyard
def backyard(side: dict[str, bool], labels: dict[str, str], chosen: str = "") -> str | None:
    """The camera for the sped-up day: the one chosen in Settings (when Frigate has it), else
    the outside camera whose name says yard, garden or patio (the shortest name: the main one
    before its _left and _right), else an outside one that isn't the front, the drive or the
    garage, else any outside one. None without outside cameras."""
    if chosen and chosen in side:
        return chosen
    outside = [c for c, out in side.items() if out]
    if not outside:
        return None

    def name(c: str) -> str:
        return f"{c} {labels.get(c, '')}".replace("_", " ").replace("-", " ").lower()

    for words in YARD_WORDS:
        hits = [c for c in outside if re.search(rf"\b{words}", name(c))]
        if hits:
            return min(hits, key=lambda c: (len(c), outside.index(c)))
    rest = [c for c in outside if not re.search(NOT_YARD, name(c))]
    return (rest or outside)[0]


# ------------------------------------------------------------------ YouTube
_AGO = re.compile(r"(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago", re.I)
_UNIT = {"second": 1, "minute": 60, "hour": 3600, "day": 86400, "week": 7 * 86400, "month": 30 * 86400, "year": 365 * 86400}


def ago(line: str) -> int | None:
    """Seconds since "3 hours ago", "Streamed 25 minutes ago", "1 day ago"; None without one."""
    m = _AGO.search(line or "")
    return int(m.group(1)) * _UNIT[m.group(2).lower()] if m else None


def seconds_of(duration: str) -> int:
    """ "1:02:03" -> 3723; "" -> 0."""
    try:
        parts = [int(x) for x in duration.split(":")] if duration else []
    except ValueError:
        return 0
    return sum(p * 60**i for i, p in enumerate(reversed(parts)))


def new_videos(page: dict[str, Any], now: float, limit: int = MAX_VIDEOS) -> list[dict[str, Any]]:
    """The subscriptions page's new videos (published in the last NEW_VIDEOS, not started, not
    Shorts or live now), newest first: [{id, title, channel, thumb, duration, at, target}]."""
    out: dict[str, dict[str, Any]] = {}
    for shelf in page.get("shelves") or []:
        for it in shelf.get("items") or []:
            if it.get("type") != "video" or not it.get("id") or it.get("live") or (it.get("progress") or 0) > 0.02:
                continue
            lines = it.get("lines") or []
            age = next((a for a in (ago(x) for x in lines[1:] or lines) if a is not None), None)
            if age is None or age > NEW_VIDEOS or seconds_of(it.get("duration") or "") < MIN_VIDEO:
                continue
            if it["id"] not in out:
                out[it["id"]] = {
                    "id": it["id"],
                    "title": it.get("title") or "",
                    "channel": lines[0] if lines else "",
                    "thumb": it.get("thumb") or "",
                    "duration": it.get("duration") or "",
                    "at": now - age,
                    "target": f"youtube:video:{it['id']}",
                }
    return sorted(out.values(), key=lambda v: -v["at"])[:limit]


def when_published(at: float, now: float) -> str:
    """ "5 h ago", "40 min ago", "yesterday"."""
    s = max(0, now - at)
    if s < 3600:
        return f"{max(1, round(s / 60))} min ago"
    if s < 20 * 3600:
        return f"{round(s / 3600)} h ago"
    return "yesterday"


# ------------------------------------------------------------------ the show
def part_seconds(p: dict[str, Any]) -> float:
    k = p["kind"]
    if k == "yard":
        return YARD_SECONDS
    if k in ("night", "pets"):
        return away.CLIP * len(p.get("clips") or [])
    return WEATHER_SECONDS if k == "weather" else VIDEOS_SECONDS


def length_label(seconds: float) -> str:
    """ "1½ min", "2 min", "45 s"."""
    if seconds < 50:
        return f"{max(5, int(round(seconds / 5) * 5))} s"
    halves = int(seconds / 30 + 0.5)
    whole, half = divmod(halves, 2)
    return f"{whole}{'½' if half else ''} min" if whole else "½ min"


def tile(show: dict[str, Any]) -> dict[str, Any]:
    """The home row's tile: the show's picture (the yard at midday, else a clip's still), its
    day and length. OK opens show:morning (couchbox.ontv)."""
    parts = show["parts"]
    art = ""
    for p in parts:
        if p["kind"] == "yard" and p.get("frames"):
            art = p["frames"][len(p["frames"]) // 2]["file"]
            art = "" if art.startswith("demo:") else art
        elif p["kind"] in ("night", "pets") and not art:
            art = next((c["poster"] for c in p["clips"] if c.get("poster")), "")
        if art:
            break
    day = datetime.date.fromisoformat(show["date"])
    return {
        "id": "show:morning",
        "app": "show",
        "show": True,
        "name": "Morning show",
        "title": f"{day:%A}'s morning show",
        "subtitle": f"{day:%A} · {length_label(sum(part_seconds(p) for p in parts))}",
        "art": "file://" + art if art else "",
        "glow": GLOW,
        "icon": "",
        "tile": "",
        "hideable": False,
        "desktop": "couchbox-show.desktop",
        "target": "show:morning",
    }


def finish(show: dict[str, Any]) -> dict[str, Any]:
    """The parts' titles and lengths, and the tile (once the parts are in)."""
    for p in show["parts"]:
        p.setdefault("title", TITLES[p["kind"]])
        p["seconds"] = part_seconds(p)
    show["tile"] = tile(show)
    return show


def current(home: Path | None = None, now: float | None = None) -> dict[str, Any] | None:
    """This morning's show to offer, or None (none made, watched, or past noon)."""
    s = away.read_json(show_file(home))
    now = time.time() if now is None else now
    if not isinstance(s, dict) or s.get("seen") or not s.get("parts") or not s.get("until"):
        return None
    if s.get("date") != today(now).isoformat() or now >= s["until"]:
        return None
    return s


def made_today(home: Path | None = None, now: float | None = None) -> bool:
    s = away.read_json(show_file(home))
    now = time.time() if now is None else now
    return isinstance(s, dict) and s.get("date") == today(now).isoformat() and bool(s.get("made"))


def covers(home: Path | None = None, now: float | None = None) -> tuple[float, float] | None:
    """For While you were out: the night this morning's show covers (its reel leaves it out),
    or None when there's no show this morning."""
    s = away.read_json(show_file(home))
    now = time.time() if now is None else now
    if not isinstance(s, dict) or not s.get("parts") or s.get("date") != today(now).isoformat() or now >= (s.get("until") or 0):
        return None
    a, b = (s.get("night") or [0, 0])[:2]
    return (float(a), float(b)) if b > a else None


def uncovered(since: float, until: float, night: tuple[float, float]) -> float:
    """How much of an absence (since to until) lies outside the show's night."""
    a, b = night
    return max(0.0, min(until, a) - since) + max(0.0, until - max(since, b))


def mark_seen(home: Path | None = None) -> None:
    s = away.read_json(show_file(home))
    if isinstance(s, dict) and not s.get("seen"):
        s["seen"] = time.time()
        away.write_json(show_file(home), s)


def forecast(data: dict[str, Any]) -> dict[str, Any]:
    """Today's forecast line from couchbox.services.weather's data: {line, cond, icon, hi, lo, place}."""
    d, u = data["days"][0], data["units"]
    t = u["temp"][0]
    return {
        "line": d.get("summary") or d.get("cond", ""),
        "cond": d.get("cond", ""),
        "icon": d.get("icon", ""),
        "hi": f"{d['hi']}{t}",
        "lo": f"{d['lo']}{t}",
        "place": data.get("place", {}).get("name", ""),
        "alerts": [a.get("event", "") for a in data.get("alerts") or []][:2],
    }


# ------------------------------------------------------------------ made-up show (screenshots, tests)
def demo_show(now: float | None = None) -> dict[str, Any]:
    now = now or time.time()
    d = today(now)
    rise, sets = at_hour(d - datetime.timedelta(days=1), 6.9), at_hour(d - datetime.timedelta(days=1), 17.2)
    reel = away.demo_reel(now)
    clip = lambda c, t: dict(c, at=t, when=away.clock(t, False))  # noqa: E731
    night_clips = [clip(c, at_hour(d, h)) for c, h in zip(reel["clips"][:3], (0.6, 2.2, 3.4), strict=True)]
    for c in night_clips:
        c["review"] = dict(c["review"], start=c["at"] - 4, end=c["at"] + 20)
    pets = [clip(c, at_hour(d - datetime.timedelta(days=1), h)) for c, h in zip(reel["clips"][3:6], (9.5, 13.25, 16.7), strict=True)]
    for c in pets:
        c["review"] = dict(c["review"], start=c["at"] - 4, end=c["at"] + 20)
    videos = [
        ("demo0000101", "Building a tiny cabin in one weekend", "Northwood Builds", "24:12", 3.5),
        ("demo0000102", "The map that fooled sailors for 200 years", "Orbit Lab", "18:40", 6),
        ("demo0000103", "Sourdough, the lazy way", "Kitchen Table", "12:05", 9),
        ("demo0000104", "Night trains across the Alps", "Rail Diaries", "41:30", 14),
        ("demo0000105", "Why bees build hexagons", "Small Wonders", "9:58", 19),
        ("demo0000106", "We restored a 1970s arcade cabinet", "Retro Room", "33:21", 22),
    ]
    show = {
        "date": d.isoformat(),
        "made": at_hour(d, MAKE_AT) + 300,
        "until": at_hour(d, NOON),
        "night": [at_hour(d - datetime.timedelta(days=1), 23.1), at_hour(d, MAKE_AT)],
        "parts": [
            {
                "kind": "yard",
                "camera": "backyard",
                "cameraLabel": "Backyard",
                "from": rise,
                "to": sets,
                "frames": [
                    {"file": "demo:yard", "at": t, "when": away.clock(t, False)} for t in yard_times(rise, sets, int(YARD_SECONDS * 4))
                ],
            },
            {"kind": "night", "clips": night_clips},
            {"kind": "pets", "clips": pets},
            {"kind": "weather"},
            {
                "kind": "videos",
                "videos": [
                    {
                        "id": i,
                        "title": t,
                        "channel": ch,
                        "thumb": "",
                        "duration": du,
                        "at": now - h * 3600,
                        "target": f"youtube:video:{i}",
                    }
                    for i, t, ch, du, h in videos
                ],
            },
        ],
        "cameras": [{"name": "backyard", "label": "Backyard"}, {"name": "front_door", "label": "Front door"}],
        "seen": None,
    }
    return finish(show)
