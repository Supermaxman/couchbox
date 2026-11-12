"""Moments: named things the household teaches the TV by showing it once ("remember this as pet
music" while it plays), then starts with a word ("play pet music"), its tile on the home screen,
or a button on the phone page. A person always starts one; nothing starts a Moment by itself.

This module is the data (any user may import it); playing them is couchbox.voice.moments, in
the voice service (root), which every way of starting one goes through.

A Moment (the setting moments.list, edited in Settings → Moments):
  id        "pet-music": from the name, unique
  name      "Pet music": what it's called, by voice, on its tile and on the phone page
  app       youtube, jellyfin, dropout, 2ndtry, nebula, twitch
  target    what that app opens: video:<id> (YouTube), <item id> (Jellyfin), play:<id> (the
            streaming apps; Twitch's live channels are play:live:<login>)
  title     what it plays, as the app named it ("Calm piano for dogs")
  art       a picture of it for the tile (an http(s) address), or ""
  volume    5-100: the box's own sound level while it plays (under the TV's own volume, which
            can't be read or set to a number over HDMI-CEC); 100 leaves it as it is
  repeat    starts again from the beginning when it ends
  dark      the picture goes black while it plays (the sound goes on; any key brings it back)
  leaving   one the household plays when leaving the house: the box notes when it starts

What plays now and when Moments were started (the voice service writes it, anyone may read it):
/var/lib/couchbox/moments.json  {"active": {...} | null, "started": {id: unix time},
                                 "left": unix time of the last start of a leaving Moment}
left_at() is when the household last left, for the cameras' "While you were out".
"""

import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any

from couchbox import paths, settings

KEY = "moments.list"
APPS = ("youtube", "jellyfin", "dropout", "2ndtry", "nebula", "twitch")
NAMES = {"youtube": "YouTube", "jellyfin": "Jellyfin", "dropout": "Dropout", "2ndtry": "2nd Try", "nebula": "Nebula", "twitch": "Twitch"}
MAX = 24  # Moments on one box
VOLUMES = (100, 80, 60, 40, 20)  # Settings' choices (any 5-100 is kept)
_TARGET = {
    "youtube": r"video:[\w-]{11}",
    "jellyfin": r"[0-9a-fA-F-]{8,40}",
}
_STREAM_TARGET = r"play:[\w:.-]{1,120}"


class MomentError(ValueError):
    """A Moment that can't be stored; the message is for the screen."""


# ------------------------------------------------------------------ the list
def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "moment"


def clean(v: Any) -> dict[str, Any]:
    """One Moment, checked and tidied (settings.validate calls this for each)."""
    if not isinstance(v, dict):
        raise MomentError("Moment: expected its details")
    name = re.sub(r"\s+", " ", str(v.get("name", ""))).strip()
    if not name or len(name) > 40:
        raise MomentError("Moment: needs a name (up to 40 letters)")
    app = v.get("app")
    if app not in APPS:
        raise MomentError(f"Moment: {app!r} can't play Moments yet")
    target = str(v.get("target", ""))
    if not re.fullmatch(_TARGET.get(app, _STREAM_TARGET), target):
        raise MomentError(f"Moment: {NAMES[app]} can't open {target!r}")
    mid = str(v.get("id") or slug(name))
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", mid):
        raise MomentError("Moment: bad id")
    art = str(v.get("art") or "")
    if art and not re.fullmatch(r"https?://\S{4,1000}", art):
        art = ""
    try:
        volume = int(v.get("volume", 100))
    except (TypeError, ValueError):
        raise MomentError("Moment: volume is a number from 5 to 100") from None
    return {
        "id": mid,
        "name": name,
        "app": app,
        "target": target,
        "title": re.sub(r"\s+", " ", str(v.get("title") or "")).strip()[:200],
        "art": art,
        "volume": max(5, min(100, volume)),
        "repeat": bool(v.get("repeat")),
        "dark": bool(v.get("dark")),
        "leaving": bool(v.get("leaving")),
    }


def all(st: dict[str, Any] | None = None) -> list[dict[str, Any]]:  # noqa: A001 - moments.all()
    return list((st or settings.load())[KEY])


def get(mid: str, st: dict[str, Any] | None = None) -> dict[str, Any] | None:
    return next((m for m in all(st) if m["id"] == mid), None)


def words(s: str) -> str:
    """A name as it's said: "The pet music!" -> "pet music"."""
    s = re.sub(r"[^a-z0-9 ]+", " ", s.lower())
    s = re.sub(r"^(the|my|our|some) ", "", re.sub(r"\s+", " ", s).strip())
    return re.sub(r" (moment|music moment)$", "", s)


def find(name: str, st: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """The Moment a spoken name means: the same words, else the only one that contains them
    (or is contained in them: "play the pet music one")."""
    want = words(name)
    if not want:
        return None
    ms = all(st)
    for m in ms:
        if words(m["name"]) == want or m["id"] == slug(name):
            return m
    near = [m for m in ms if words(m["name"]) and (words(m["name"]) in want or want in words(m["name"]))]
    return near[0] if len(near) == 1 else None


def with_moment(ms: list[dict[str, Any]], m: dict[str, Any]) -> list[dict[str, Any]]:
    """The list with m added; a Moment of the same name is replaced (taught again)."""
    m = clean(m)
    out = [x for x in ms if words(x["name"]) != words(m["name"]) and x["id"] != m["id"]]
    taken = {x["id"] for x in out}
    base, n = m["id"], 2
    while m["id"] in taken:
        m["id"] = f"{base[:36]}-{n}"
        n += 1
    if len(out) >= MAX:
        raise MomentError(f"That's {MAX} Moments already: delete one in Settings → Moments first.")
    old = next((i for i, x in enumerate(ms) if words(x["name"]) == words(m["name"])), None)
    if old is not None:  # taught again: keeps its place
        out.insert(min(old, len(out)), m)
    else:
        out.append(m)
    return out


def describe(m: dict[str, Any]) -> str:
    """'“Calm piano for dogs” on YouTube · repeats · picture dark · volume 40%'."""
    bits = [f"“{m['title']}” on {NAMES[m['app']]}" if m.get("title") else NAMES[m["app"]]]
    if m.get("repeat"):
        bits.append("repeats")
    if m.get("dark"):
        bits.append("picture dark")
    if m.get("volume", 100) < 100:
        bits.append(f"volume {m['volume']}%")
    if m.get("leaving"):
        bits.append("marked as the one played when leaving")
    return " · ".join(bits)


# ------------------------------------------------------------------ what plays, when
def state_file() -> Path:
    return paths.state() / "moments.json"


def read_state() -> dict[str, Any]:
    try:
        st = json.loads(state_file().read_text())
    except (OSError, ValueError):
        st = {}
    if not isinstance(st, dict):
        st = {}
    st.setdefault("active", None)
    st.setdefault("started", {})
    st.setdefault("left", None)
    return st


def write_state(st: dict[str, Any]) -> None:
    p = state_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".moments.")
    with os.fdopen(fd, "w") as f:
        json.dump(st, f)
    os.chmod(tmp, 0o644)
    os.replace(tmp, p)


def note_started(st: dict[str, Any], m: dict[str, Any], now: float | None = None) -> None:
    now = time.time() if now is None else now
    st["started"][m["id"]] = now
    if m.get("leaving"):
        st["left"] = now


def left_at() -> float | None:
    """When the household last left the house: the last time a Moment marked for leaving was
    started (unix time), or None."""
    t = read_state().get("left")
    return float(t) if isinstance(t, (int, float)) else None


def active_id() -> str | None:
    a = read_state().get("active")
    return a.get("id") if isinstance(a, dict) else None


# ------------------------------------------------------------------ the home screen
def tiles(st: dict[str, Any]) -> list[dict[str, Any]]:
    """The Moments' tiles on the home row (home.json), after the apps: OK starts one."""
    out = []
    for m in all(st):
        out.append(
            {
                "id": f"moment:{m['id']}",
                "app": f"moment:{m['id']}",  # (not the app's id: home.json's apps say what's on the row)
                "moment": m["id"],
                "plays": m["app"],
                "name": m["name"],
                "title": m["title"],
                "art": m["art"],
                "icon": "",
                "tile": "",
                "glow": "",
                "hideable": False,
            }
        )
    return out
