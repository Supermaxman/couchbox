"""Past reels: every reel the box makes is kept, so the Reels app (couchbox-show --reels, its own
tile on the home row) can play it again later: Today at home (couchbox.dayreel), While you were
out (couchbox.away) and the morning show's camera moments (couchbox.show).

Each reel is a folder of its own: its clips and stills (hard links to the ones the card played
when they're on the same disk, so keeping them costs nothing until the card's copies go) and
reel.json. The oldest go first once they hold more than KEEP_BYTES together.

Files (the TV user's):
  ~/.local/share/couchbox-reels/<id>/reel.json   {id, kind, since, until, made, clips} (clips:
                                                 couchbox.away.reel_clip's, files in the folder)
  ~/.local/share/couchbox-reels/<id>/*.mp4, *.jpg
"""

import datetime
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any

from couchbox import away

KEEP_BYTES = 10 * 1024**3  # about half a year of reels
TITLES = {"day": "Today at home", "away": "While you were out", "morning": "Morning show"}


def archive_dir(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".local/share/couchbox-reels"


def reel_id(kind: str, until: float) -> str:
    return f"{kind}-{int(until)}"


def _keep(src: str, d: Path) -> str:
    """src kept in d (a hard link, else a copy); its path there, or "" when it's gone."""
    if not src or not os.path.exists(src):
        return ""
    dst = d / os.path.basename(src)
    if os.path.abspath(src) == os.path.abspath(dst) or dst.exists():
        return str(dst)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)
    return str(dst)


def save(kind: str, clips: list[dict[str, Any]], since: float, until: float, home: Path | None = None) -> dict[str, Any] | None:
    """Keep a reel (its clips as the player takes them); the entry, or None without clips."""
    if not clips:
        return None
    rid = reel_id(kind, until)
    d = archive_dir(home) / rid
    d.mkdir(parents=True, exist_ok=True)
    kept = []
    for c in clips:
        f = _keep(c.get("file", ""), d)
        if f:
            kept.append(dict(c, file=f, poster=_keep(c.get("poster", ""), d)))
    if not kept:
        shutil.rmtree(d, ignore_errors=True)
        return None
    entry = {"id": rid, "kind": kind, "since": since, "until": until, "made": time.time(), "clips": kept}
    away.write_json(d / "reel.json", entry)
    prune(home)
    return entry


def all_reels(home: Path | None = None) -> list[dict[str, Any]]:
    """Every kept reel, newest first."""
    root = archive_dir(home)
    out = []
    if root.is_dir():
        for d in root.iterdir():
            r = away.read_json(d / "reel.json")
            if isinstance(r, dict) and r.get("clips"):
                out.append(r)
    return sorted(out, key=lambda r: -(r.get("until") or 0))


def get(rid: str, home: Path | None = None) -> dict[str, Any] | None:
    if not re.fullmatch(r"[\w-]{1,64}", rid or ""):
        return None
    r = away.read_json(archive_dir(home) / rid / "reel.json")
    return r if isinstance(r, dict) and r.get("clips") else None


def ids(kind: str, day: datetime.date, home: Path | None = None) -> set[str]:
    """The Frigate review items in that day's reels of a kind (so another reel can leave them out)."""
    return {
        c["review"]["id"]
        for r in all_reels(home)
        if r.get("kind") == kind and datetime.date.fromtimestamp(r["until"]) == day
        for c in r["clips"]
        if c.get("review")
    }


def _size(d: Path) -> int:
    return sum(p.stat().st_size for p in d.iterdir() if p.is_file())


def prune(home: Path | None = None, keep: int = KEEP_BYTES) -> None:
    """The oldest reels go once the archive holds more than keep."""
    root = archive_dir(home)
    total = 0
    for r in all_reels(home):
        d = root / r["id"]
        total += _size(d)
        if total > keep:
            shutil.rmtree(d, ignore_errors=True)


def hours(since: float, until: float, clock24: bool) -> str:
    """ "7 am – 3 pm", "07:00 – 15:00"; minutes only where they aren't :00."""

    def one(t: float) -> str:
        d = datetime.datetime.fromtimestamp(t)
        if clock24:
            return d.strftime("%H:%M")
        m = f":{d.minute:02d}" if d.minute else ""
        return f"{d.hour % 12 or 12}{m} {'am' if d.hour < 12 else 'pm'}"

    return f"{one(since)} – {one(until)}"


def group(r: dict[str, Any], now: float | None = None) -> str:
    """The heading a reel goes under: "This week", "Last week", "October", "October 2025"."""
    now = time.time() if now is None else now
    today = datetime.date.fromtimestamp(now)
    d = datetime.date.fromtimestamp(r["until"])
    monday = today - datetime.timedelta(days=today.weekday())
    if d >= monday:
        return "This week"
    if d >= monday - datetime.timedelta(days=7):
        return "Last week"
    return f"{d:%B}" + (f" {d.year}" if d.year != today.year else "")


def listing(r: dict[str, Any], clock24: bool, now: float | None = None) -> dict[str, Any]:
    """A reel as the Reels app lists it: {id, kind, title, day, span, art}."""
    now = time.time() if now is None else now
    until = datetime.date.fromtimestamp(r["until"])
    today = datetime.date.fromtimestamp(now)
    if until == today:
        day = "Today"
    elif until == today - datetime.timedelta(days=1):
        day = "Yesterday"
    elif (today - until).days < 7:
        day = f"{until:%A}"
    else:
        day = f"{until:%a}, {until:%b} {until.day}" + (f", {until.year}" if until.year != today.year else "")
    if r["kind"] == "away":
        span = f"{away.length(r['until'] - r['since'])} out"
    elif r["kind"] == "morning":
        span = "Overnight"
    else:
        span = hours(r["since"], r["until"], clock24)
    title = TITLES.get(r["kind"], "Reel")
    if r["kind"] == "day" and until != today:
        title = "At home"
    return {
        "id": r["id"],
        "kind": r["kind"],
        "title": title,
        "day": day,
        "span": span,
        "art": next((c["poster"] for c in r["clips"] if c.get("poster")), ""),
    }


# ------------------------------------------------------------------ made-up reels (screenshots, tests)
def demo_reels(now: float | None = None) -> list[dict[str, Any]]:
    from couchbox import dayreel

    now = now or time.time()
    base = away.demo_reel(now)["clips"]
    day = dayreel.demo_reel(now)["clips"]
    out = []
    today = datetime.date.fromtimestamp(now)
    for back in range(0, 16):
        d = today - datetime.timedelta(days=back)
        if d.weekday() < 5:
            since, until = (
                datetime.datetime(d.year, d.month, d.day, 7).timestamp(),
                datetime.datetime(d.year, d.month, d.day, 15).timestamp(),
            )
            if until < now:
                out.append(
                    {"id": reel_id("day", until), "kind": "day", "since": since, "until": until, "clips": day[back % 3 :] + day[: back % 3]}
                )
        if back % 3 == 1:
            until = datetime.datetime(d.year, d.month, d.day, 18, 40).timestamp()
            out.append({"id": reel_id("away", until), "kind": "away", "since": until - 4.2 * 3600, "until": until, "clips": base})
        if back % 2 == 0:
            until = datetime.datetime(d.year, d.month, d.day, 4, 10).timestamp()
            if until < now:
                out.append(
                    {
                        "id": reel_id("morning", until),
                        "kind": "morning",
                        "since": until - 6 * 3600,
                        "until": until,
                        "clips": base[:3] + day[:2],
                    }
                )
    return sorted(out, key=lambda r: -r["until"])
