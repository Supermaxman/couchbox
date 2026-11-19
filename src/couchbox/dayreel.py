"""Today at home: on weekdays, a short, silent reel of the pets and the people at home during the
day (Settings → Home: 7 am to 3 pm by default), offered on the home screen from soon after the
day ends until the next morning. OK on the card plays it in the Reels app; nothing plays by
itself, and the card goes once it's been watched to the end.

What goes in: the inside cameras' people and pets, and animals on the outside ones (a dog in the
yard), and what Frigate's sound detection heard (a bark, a meow, laughter: audio.listen in its
config) even off camera; deliveries, cars and passers-by are While you were out's.
couchbox-morning makes it once the day is over (DONE after it): Frigate's review items of the
day, LOOKS of them looked at by the assistant's model (couchbox-voice's /look, as couchbox.away
does), the most promising of every hour and every camera, so a quiet morning gets its look too;
the model scores how sweet or fun each is and writes its caption. The best CLIPS (the best of
each hour first, then the best of the rest) are cut by Frigate, CLIP seconds each, and kept in
the reels archive (couchbox.reels), where the Reels app finds it later too.

While you were out gives way: on a weekday with Today at home on, its reel leaves out the pets
during those hours.

Files (the TV user's):
  ~/.cache/couchbox-reels/today.json   the card: {date, made, id, card, until, seen}
                                       (id and card None when the day had nothing worth showing)
"""

import datetime
import time
from collections import Counter
from pathlib import Path
from typing import Any

from couchbox import away, reels

CLIPS = 24  # about three minutes
CLIP = 8.0  # seconds of each clip
LOOKS = 90  # the model's looks (5-6 s each), spread over the hours and the cameras
PER_CAMERA = 6
GOOD = 5  # the model's score an hour's best needs to get a place of its own
DONE = away.EDGE  # made this long after the day ends (the last review items close)
MORNING = 4  # o'clock: the card goes the next morning (when the morning show is made)

LOOK = (
    "Frames, in order, from a home camera clip ({camera}, {where}; its detector guessed: {labels}, sometimes wrongly). "
    "Write a caption of at most 9 words saying what happens, warmly, as family would: "
    "'The dog brings his toy to the sofa', 'Someone dances in the kitchen', 'Two cats nap in the sun'. "
    "No names, no guesses about who it is, no times or camera names. "
    "Rate how sweet or fun it is to watch, 0 to 10: 0 when no person or animal is actually there (shadows, light, an empty room: "
    "the detector was wrong), 1-2 for someone just walking through or working at a desk, higher for pets playing, cuddling or "
    "being silly and people playing with them, dancing or laughing, 10 for a moment the family would love to see. "
    'Reply with JSON only: {{"lively": 0-10, "best": the best frame (1 is the first), "caption": "..."}}'
)


# ------------------------------------------------------------------ where things are
def card_file(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".cache/couchbox-reels/today.json"


# ------------------------------------------------------------------ when
def at_hour(day: datetime.date, hour: int) -> float:
    """Unix time of day at hour (local time; 24 is midnight at its end)."""
    return (datetime.datetime.combine(day, datetime.time()) + datetime.timedelta(hours=hour)).timestamp()


def window(day: datetime.date, s: dict[str, Any]) -> tuple[float, float] | None:
    """The hours the reel covers that day (a weekday), or None (a weekend, or turned off)."""
    if not s["home.day"] or day.weekday() >= 5 or s["home.day_to"] <= s["home.day_from"]:
        return None
    return at_hour(day, s["home.day_from"]), at_hour(day, s["home.day_to"])


def making_time(now: float, s: dict[str, Any]) -> tuple[float, float] | None:
    """Today's hours when it's time to make their reel (the day over, before midnight)."""
    w = window(datetime.date.fromtimestamp(now), s)
    return w if w and now >= w[1] + DONE else None


def made_today(home: Path | None = None, now: float | None = None) -> bool:
    c = away.read_json(card_file(home))
    now = time.time() if now is None else now
    return isinstance(c, dict) and c.get("date") == datetime.date.fromtimestamp(now).isoformat()


# ------------------------------------------------------------------ what goes in
def section(objects: list[str], outside: bool, sounds: list[str] = ()) -> str | None:
    """ "home" for the people and pets inside (seen, or heard: a bark, laughter) and animals
    outside (a bark in the yard too); None for the rest."""
    objs = {o.split("-verified")[0] for o in objects}
    heard = set(sounds)
    if outside:
        return "home" if objs & away.ANIMALS or heard & away.PET_SOUNDS else None
    return "home" if objs & (away.PEOPLE | away.PETS) or heard & (away.PET_SOUNDS | away.FUN_SOUNDS) else None


def candidates(rows: list[dict[str, Any]], side: dict[str, bool], start: float, end: float) -> list[dict[str, Any]]:
    """Frigate's review items within the hours, as reel candidates."""
    return away.candidates(rows, side, start - away.EDGE, end + away.EDGE, section_of=section)


def look_prompt(c: dict[str, Any], camera_label: str, outside: bool) -> str:
    return LOOK.format(camera=camera_label, where="outside" if outside else "inside the house", labels=away.guesses(c))


def hour_of(c: dict[str, Any]) -> int:
    return datetime.datetime.fromtimestamp(c["start"]).hour


def to_look(cands: list[dict[str, Any]], n: int = LOOKS) -> list[dict[str, Any]]:
    """The n candidates the model looks at, in turn from every hour: each hour's most promising
    (a bark or laughter first, then Frigate's labels, then the longer), a camera looked at less
    and a moment not already looked at on that camera ahead of the rest."""
    slots: dict[int, list[dict[str, Any]]] = {}
    for c in cands:
        slots.setdefault(hour_of(c), []).append(c)
    out: list[dict[str, Any]] = []
    used: Counter[str] = Counter()

    def promise(c: dict[str, Any]) -> tuple[float, float]:
        near = any(o["camera"] == c["camera"] and abs(o["start"] - c["start"]) < away.APART for o in out)
        return (c["score"] - 0.75 * used[c["camera"]] - (3 if near else 0), min(c["end"] - c["start"], 300))

    while len(out) < n and any(slots.values()):
        for h in sorted(slots):
            if not slots[h] or len(out) >= n:
                continue
            best = max(slots[h], key=promise)
            slots[h].remove(best)
            out.append(best)
            used[best["camera"]] += 1
    return out


def choose(cands: list[dict[str, Any]], n: int = CLIPS) -> list[dict[str, Any]]:
    """The reel, in time order: each hour's best (when the model liked it, GOOD or more), then
    the best of the rest; at most PER_CAMERA a camera, picks on one camera away.APART. Once the
    model has looked, only what it looked at; nothing it saw nobody in, and dull moments only to
    make up a reel of three."""
    if any(c.get("lively") is not None for c in cands):
        cands = [c for c in cands if c.get("lively") is not None]
    ranked = sorted(cands, key=lambda c: (-away.score(c), c["start"]))
    picked: list[dict[str, Any]] = []

    def fits(c: dict[str, Any]) -> bool:
        same = [p for p in picked if p["camera"] == c["camera"]]
        return len(same) < PER_CAMERA and all(abs(p["start"] - c["start"]) >= away.APART for p in same)

    def lively(c: dict[str, Any]) -> float:
        return c["lively"] if c.get("lively") is not None else c["score"]

    for h in sorted({hour_of(c) for c in ranked}):
        for c in ranked:
            if len(picked) < n and hour_of(c) == h and lively(c) >= GOOD and fits(c):
                picked.append(c)
                break
    for c in ranked:
        if len(picked) >= n:
            break
        if c in picked or not fits(c) or lively(c) < 1 or (lively(c) < away.DULL and len(picked) >= 3):
            continue
        picked.append(c)
    return sorted(picked, key=lambda c: c["start"])


# ------------------------------------------------------------------ the card
def card(entry: dict[str, Any], clock24: bool) -> dict[str, Any]:
    """The home screen's card (a Continue watching item: couchbox.ontv's shape)."""
    n = len(entry["clips"])
    return {
        "key": "day",
        "app": "reels",
        "name": "Reels",
        "desktop": "couchbox-reels.desktop",
        "title": "Today at home",
        "subtitle": f"{reels.hours(entry['since'], entry['until'], clock24)} · {n} moment{'s' if n != 1 else ''}",
        "art": next(("file://" + c["poster"] for c in entry["clips"] if c.get("poster")), ""),
        "target": f"reels:{entry['id']}",
        "when": entry["until"],
    }


def offer(entry: dict[str, Any] | None, clock24: bool, now: float | None = None, home: Path | None = None) -> None:
    """Put the card on the home screen (until the next morning), or note the day had none."""
    now = time.time() if now is None else now
    day = datetime.date.fromtimestamp(now)
    until = at_hour(day + datetime.timedelta(days=1), MORNING)
    away.write_json(
        card_file(home),
        {
            "date": day.isoformat(),
            "made": now,
            "id": entry["id"] if entry else None,
            "card": card(entry, clock24) if entry else None,
            "until": until,
            "seen": None,
        },
    )


def current(home: Path | None = None, now: float | None = None) -> dict[str, Any] | None:
    """The card to offer, or None (none, watched, or the next morning)."""
    c = away.read_json(card_file(home))
    now = time.time() if now is None else now
    if not isinstance(c, dict) or not c.get("card") or c.get("seen") or now >= (c.get("until") or 0):
        return None
    return c


def mark_seen(rid: str, home: Path | None = None) -> None:
    """The reel rid was watched to the end: when it's the card's, the card goes."""
    c = away.read_json(card_file(home))
    if isinstance(c, dict) and c.get("id") == rid and not c.get("seen"):
        c["seen"] = time.time()
        away.write_json(card_file(home), c)


def clear(home: Path | None = None) -> None:
    card_file(home).unlink(missing_ok=True)


# ------------------------------------------------------------------ made-up reel (screenshots, tests)
def demo_reel(now: float | None = None) -> dict[str, Any]:
    now = now or time.time()
    day = datetime.date.fromtimestamp(now)
    rows = [
        ("living_room", "Living room", ["dog", "person"], 7.6, "The dog brings his toy to the sofa"),
        ("kitchen", "Kitchen", ["person"], 9.2, "Someone dances while making coffee"),
        ("living_room", "Living room", ["cat"], 10.5, "The cat stretches out in a sunbeam"),
        ("backyard", "Backyard", ["dog"], 11.4, "The dog zooms around the yard"),
        ("hallway", "Hallway", ["dog", "cat"], 12.3, "The cat ambushes the dog in the hall"),
        ("kitchen", "Kitchen", ["person", "cat"], 13.1, "Someone shares a bite with the cat"),
        ("living_room", "Living room", ["dog", "cat"], 14.4, "The dog and the cat nap together"),
    ]
    clips = []
    for cam, name, objs, h, what in rows:
        t = at_hour(day, int(h)) + (h % 1) * 3600
        c = {"start": t, "objects": objs, "caption": what}
        clips.append(
            {
                "file": "demo:clip",
                "poster": "",
                "camera": cam,
                "cameraLabel": name,
                "section": "home",
                "at": t,
                "when": away.clock(t, False),
                "caption": away.caption(c, name, False),
                "what": what,
                "review": {
                    "id": f"demo-day-{len(clips)}",
                    "camera": cam,
                    "start": t - 4,
                    "end": t + 20,
                    "severity": "detection",
                    "objects": objs,
                },
            }
        )
    since, until = at_hour(day, 7), at_hour(day, 15)
    entry = {"id": reels.reel_id("day", until), "kind": "day", "since": since, "until": until, "made": until + 300, "clips": clips}
    return entry
