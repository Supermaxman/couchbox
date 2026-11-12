"""While you were out: when the household comes home and picks up the remote, the home screen
offers a short, silent reel of what the cameras (Frigate) saw while they were gone. OK on the
card plays it in the Frigate app; nothing plays by itself.

Out means from when someone started a leaving Moment (couchbox.moments.left_at(): pet music,
say) or the TV went unused for QUIET (no remote press, nothing playing), until the remote is
next pressed. couchbox-away (the TV user's service) keeps track of that, and while the household
is out it looks through Frigate's review items every SWEEP: outside first (people, packages,
cars), then the pets (dogs and cats on the inside cameras, animals on their own outside). The
assistant's model, when there is one that reads pictures, looks at three frames of each
(through couchbox-voice's /look, which says no while someone is using the assistant), scores how
lively it is and writes its caption; without it, Frigate's own labels choose and caption. When
the remote is pressed again, the reel is put together (about REEL_SECONDS of CLIP-second clips,
downloaded ahead) and the card goes on the home screen; it goes when the reel has been watched
to the end, or after HOLD.

Which cameras are outside: Frigate's camera groups (a group called Outside, Outdoor, Yard...;
else one called Inside, Indoor, Downstairs...), else the ones that track cars or packages.

Files (the TV user's):
  ~/.local/share/couchbox-away/state.json   the tracker and what was already looked at
  ~/.cache/couchbox-away/reel.json          the card and the clips, for the home screen and the
                                            Frigate app: {card, clips: [{file, poster, caption,
                                            camera, at, review}], since, until, seen}
  ~/.cache/couchbox-away/*.mp4, *.jpg       the clips and a still of each
"""

import base64
import datetime
import json
import os
import re
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

QUIET = 3 * 3600  # the TV unused this long: the household is out (or asleep)
GRACE = 5 * 60  # presses this soon after starting a leaving Moment don't end the absence
EDGE = 5 * 60  # the first and last minutes of an absence: the household itself leaving, arriving
MIN_AWAY = 20 * 60  # shorter absences get no card
SWEEP = 10 * 60  # how often Frigate is looked at while the household is out
HOLD = 12 * 3600  # the card stays this long after coming home (unless the reel is watched)
REEL_SECONDS = 40
CLIP = 5.0  # seconds of each clip
MAX_CLIPS = int(REEL_SECONDS // CLIP)
PER_CAMERA = 3
APART = 120  # two picks on one camera at least this far apart
RATE_PER_SWEEP = 12  # model looks per sweep (the best-looking candidates first)
DULL = 3  # the model's liveliness under this: only to make up a reel of three

PEOPLE = {"person", "face"}
VEHICLES = {"car", "truck", "bus", "van", "motorcycle", "bicycle", "boat", "license_plate", "plate"}
PACKAGES = {"package", "amazon", "ups", "fedex", "usps", "dhl", "dpd", "gls", "an_post", "purolator", "postnl", "nzpost", "postnord"}
PETS = {"dog", "cat"}
ANIMALS = PETS | {"bird", "horse", "bear", "deer", "fox", "raccoon", "squirrel", "rabbit", "goat", "cow", "sheep"}
OUTSIDE_WORDS = r"outside|outdoors?|exterior|yard|garden|patio|porch|driveway|street|perimeter|grounds"
INSIDE_WORDS = r"inside|indoors?|interior|house|home|downstairs|upstairs|rooms?|living"

LOOK = (
    "Frames, in order, from a home security camera clip ({camera}, {where}; its detector guessed: {labels}, often wrongly at night). "
    "Write a caption of at most 9 words saying what happens, as a friendly neighbour would: "
    "'A delivery driver leaves a box', 'The dog chases a ball', 'Two cats nap on the sofa'. "
    "No names, no guesses about who it is, no times or camera names. "
    "Rate how lively it is, 0 to 10: 0 when no person, animal or vehicle is actually there (rain, snow, fog, shadows, headlights, "
    "an empty scene: the detector was wrong), 1-2 for one standing still or asleep, up to 10 for a lot going on, fun to watch. "
    'Reply with JSON only: {{"lively": 0-10, "best": the liveliest frame (1 is the first), "caption": "..."}}'
)


# ------------------------------------------------------------------ where things are
def data_dir(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".local/share/couchbox-away"


def cache_dir(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".cache/couchbox-away"


def reel_file(home: Path | None = None) -> Path:
    return cache_dir(home) / "reel.json"


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


# ------------------------------------------------------------------ out and back
class Tracker:
    """Whether the household is out. tick() is called every few seconds with what the box knows;
    it answers ("back", since, until) once when the remote is pressed after an absence, else None.

    state: {busy: the last remote press or playing (unix time), key: the last press seen,
            out: when the absence began or None, why: "left" | "quiet", left: the leaving Moment's start}"""

    def __init__(self, state: dict[str, Any] | None = None, now: float | None = None):
        st = dict(state or {})
        now = time.time() if now is None else now
        st.setdefault("busy", now)
        st.setdefault("key", 0.0)
        st.setdefault("out", None)
        st.setdefault("why", "")
        st.setdefault("left", 0.0)
        self.st = st

    def tick(self, now: float, last_key: float, playing: bool, left: float | None) -> tuple[str, float, float] | None:
        st = self.st
        pressed = last_key > st["key"] + 0.5
        if pressed:
            st["key"] = last_key
        if left and left > st["left"]:  # a leaving Moment was started (since the TV was last used): out from then
            st["left"] = left
            if st["out"] is None and left >= st["busy"] - 60:
                st["out"], st["why"] = left, "left"
        if st["out"] is not None:
            in_grace = st["why"] == "left" and last_key < st["out"] + GRACE
            if pressed and not in_grace:
                since = st["out"]
                st["out"], st["why"], st["busy"] = None, "", last_key
                return ("back", since, last_key)
            return None
        if pressed:
            gap_from = st["busy"]
            st["busy"] = max(st["busy"], last_key)
            if last_key - gap_from >= QUIET:  # an absence the service didn't see begin (it wasn't running)
                return ("back", gap_from, last_key)
            return None
        if playing:
            st["busy"] = now
        elif now - st["busy"] >= QUIET:
            st["out"], st["why"] = st["busy"], "quiet"
        return None

    @property
    def out(self) -> float | None:
        return self.st["out"]


# ------------------------------------------------------------------ the cameras
def sides(config: dict[str, Any]) -> dict[str, bool]:
    """camera -> True when it's outside: Frigate's camera groups, else what each camera tracks."""
    cams = [n for n, c in (config.get("cameras") or {}).items() if c.get("enabled", True)]
    groups = config.get("camera_groups") or {}

    def members(words: str) -> set[str]:
        out: set[str] = set()
        for name, g in groups.items():
            if re.search(rf"\b({words})\b", name.replace("_", " "), re.I):
                out.update(g.get("cameras") or [])
        return out

    outside = members(OUTSIDE_WORDS)
    if outside:
        return {c: c in outside for c in cams}
    inside = members(INSIDE_WORDS)
    if inside:
        return {c: c not in inside for c in cams}
    result = {}
    for c in cams:
        track = set(((config["cameras"][c].get("objects") or {}).get("track")) or [])
        result[c] = bool(track & (VEHICLES | PACKAGES))
    return result


def section(objects: list[str], outside: bool) -> str | None:
    """Where a review item goes in the reel: "outside" (people, packages, cars), "pets", or None."""
    objs = {o.split("-verified")[0] for o in objects}
    if outside:
        if objs & (PEOPLE | VEHICLES | PACKAGES):
            return "outside"
        return "pets" if objs & ANIMALS else None
    return "pets" if objs & PETS else None


def base_score(c: dict[str, Any]) -> float:
    """How promising an item looks from Frigate's data alone (0-10)."""
    objs = set(c["objects"])
    s = 3.0
    if objs & PACKAGES:
        s += 3
    if objs & PEOPLE:
        s += 2
    if objs & PETS:
        s += 2
    if objs & VEHICLES:
        s += 1
    if c["severity"] == "alert":
        s += 1
    dur = c["end"] - c["start"]
    if dur < 2:
        s -= 2  # a blip
    elif dur > 600:
        s -= 1  # hours of a sleeping dog
    return max(0.0, min(10.0, s))


def candidates(reviews: list[dict[str, Any]], side: dict[str, bool], since: float, until: float) -> list[dict[str, Any]]:
    """Frigate's review items (/api/review rows) of an absence, as reel candidates, oldest first."""
    out = []
    for r in reviews:
        start, end = r.get("start_time") or 0, r.get("end_time")
        if end is None or start < since + EDGE or end > until - EDGE:
            continue
        cam = r.get("camera")
        if cam not in side:
            continue
        data = r.get("data") or {}
        objects = list(
            dict.fromkeys(
                o.split("-verified")[0] for o in (data.get("objects") or []) + (data.get("sub_labels") or []) if isinstance(o, str)
            )
        )
        sec = section(objects, side[cam])
        if not sec:
            continue
        c = {
            "id": r["id"],
            "camera": cam,
            "section": sec,
            "severity": r.get("severity", "detection"),
            "start": float(start),
            "end": float(end),
            "objects": objects,
            "thumb": float(data.get("thumb_time") or 0),
        }
        c["score"] = base_score(c)
        out.append(c)
    out.sort(key=lambda c: c["start"])
    return out


def frame_times(c: dict[str, Any]) -> list[float]:
    """Three moments of an item for the model to look at."""
    s, e = c["start"], c["end"]
    if e - s < 1.5:
        return [s, s + (e - s) / 2, e]
    return [round(s + (e - s) * f, 1) for f in (0.2, 0.5, 0.8)]


def look_prompt(c: dict[str, Any], camera_label: str) -> str:
    from couchbox.services.frigate import label

    labels = ", ".join(label(o).lower() for o in c["objects"]) or "motion"
    return LOOK.format(camera=camera_label, where="outside" if c["section"] == "outside" else "inside the house", labels=labels)


def parse_look(text: str) -> dict[str, Any] | None:
    """The model's {"lively", "best", "caption"} (in a code block or with words around it)."""
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        j = json.loads(m.group(0))
    except ValueError:
        return None
    try:
        lively = max(0.0, min(10.0, float(j.get("lively"))))
    except (TypeError, ValueError):
        return None
    try:
        best = max(1, int(j.get("best", 2)))
    except (TypeError, ValueError):
        best = 2
    caption = re.sub(r"\s+", " ", str(j.get("caption") or "")).strip().strip('"').rstrip(".")
    words = caption.split(" ")
    if len(words) > 12:
        caption = " ".join(words[:12])
    return {"lively": lively, "best": best, "caption": caption[:1].upper() + caption[1:]}


VOICE = "http://127.0.0.1:8790"
FRAME = 540  # the frames' height for the model (a cat and a small dog apart at night)


def look(f: Any, c: dict[str, Any], camera_label: str, log: Any = print) -> str:
    """The model's look at one candidate (three frames through couchbox-voice's /look), written
    into c (lively, best, caption, best_t). Answers "ok" (looked, or nothing to look at: try
    counted), "busy" (someone is using the assistant), "none" (no model that sees: 404, 501,
    503), or "down" (couchbox-voice out of reach)."""
    import requests

    times, images = [], []
    for t in frame_times(c):  # (a moment Frigate kept no recording of: left out)
        try:
            images.append("data:image/jpeg;base64," + base64.b64encode(f.frame_jpeg(c["camera"], t, height=FRAME)).decode())
            times.append(t)
        except requests.HTTPError:
            pass
    if not images:
        c["tries"] = c.get("tries", 0) + 1
        return "ok"
    try:
        r = requests.post(
            f"{VOICE}/look", json={"prompt": look_prompt(c, camera_label), "images": images}, headers={"X-Couchbox": "1"}, timeout=90
        )
    except requests.RequestException as err:
        log(f"the model isn't reachable through couchbox-voice: {err}")
        return "down"
    if r.status_code == 409:  # someone is using the assistant: later
        return "busy"
    if r.status_code in (404, 501, 503):  # no model, one that reads text only, an older couchbox-voice
        log(f"no model to look at the clips ({r.status_code}): choosing by Frigate's labels")
        return "none"
    c["tries"] = c.get("tries", 0) + 1
    res = parse_look(r.json().get("text", "")) if r.ok else None
    if res:
        c.update(res, best_t=times[min(res["best"], len(times)) - 1])
    else:
        log(f"model on {c['id']}: {r.status_code} {r.text[:200]}")
    return "ok"


def fetch(f: Any, picks: list[dict[str, Any]], d: Path, log: Any = print) -> list[dict[str, Any]]:
    """Download each pick's clip (CLIP seconds, Frigate cuts it) and a still of it into d (kept
    when already there); the picks with file, poster and clipStart, those that failed left out."""
    import requests

    d.mkdir(parents=True, exist_ok=True)

    def one(c: dict[str, Any]) -> dict[str, Any] | None:
        s, e = clip_window(c)
        key = f"{c['id']}-{s:.0f}".replace("/", "_")
        clip, still = d / f"{key}.mp4", d / f"{key}.jpg"
        try:
            if not clip.exists():
                f.save_clip(c["camera"], s, e, str(clip))
            for t in (s + CLIP * 0.4, c["start"] + 1, c["thumb"]):  # (a second Frigate didn't keep: the next)
                if still.exists() or not t:
                    break
                try:
                    still.write_bytes(f.frame_jpeg(c["camera"], t, height=720))
                except requests.HTTPError:
                    pass
        except Exception as err:  # noqa: BLE001 - left out of the reel
            log(f"clip of {c['id']}: {err}")
            return None
        return dict(c, file=str(clip), poster=str(still) if still.exists() else "", clipStart=s)

    with ThreadPoolExecutor(max_workers=4) as pool:
        return [x for x in pool.map(one, picks) if x]


def reel_clip(c: dict[str, Any], label: str, clock24: bool) -> dict[str, Any]:
    """A fetched pick as the player takes it (the reel's clips, the morning show's)."""
    return {
        "file": c["file"],
        "poster": c["poster"],
        "camera": c["camera"],
        "cameraLabel": label,
        "section": c["section"],
        "at": c["start"],
        "when": clock(c["start"], clock24),
        "caption": caption(c, label, clock24),
        "what": c.get("caption") or fallback_caption(c["objects"]),
        "lively": c.get("lively"),
        "review": {k: c[k] for k in ("id", "camera", "start", "end", "severity", "objects")},
    }


def score(c: dict[str, Any]) -> float:
    """The model's liveliness when it looked, else Frigate's labels alone (counting for less)."""
    if c.get("lively") is not None:
        return c["lively"] + base_score(c) / 10  # (labels break ties)
    return c["score"] * 0.7  # not looked at: between a lively clip and a sleeping dog


def choose(cands: list[dict[str, Any]], n: int = MAX_CLIPS) -> list[dict[str, Any]]:
    """The reel: the best n (at most PER_CAMERA a camera, picks on one camera APART), outside
    first, then the pets, each in time order. When both have something, each gets a place or
    more. Dull clips (a dog standing still) only make up a reel of three; once the model has
    looked, what it didn't look at (a moment Frigate kept no pictures of) is left out."""
    if any(c.get("lively") is not None for c in cands):  # the model looked: only what it looked at
        cands = [c for c in cands if c.get("lively") is not None]
    ranked = sorted(cands, key=lambda c: (-score(c), c["start"]))
    picked: list[dict[str, Any]] = []

    def fits(c: dict[str, Any]) -> bool:
        same = [p for p in picked if p["camera"] == c["camera"]]
        return len(same) < PER_CAMERA and all(abs(p["start"] - c["start"]) >= APART for p in same)

    for sec in ("outside", "pets"):  # each section's best first, so neither is crowded out
        for c in ranked:
            if c["section"] == sec and fits(c) and not (c.get("lively") is not None and c["lively"] < DULL):
                picked.append(c)
                break
    for c in ranked:
        if len(picked) >= n:
            break
        dull = c.get("lively") is not None and c["lively"] < DULL
        empty = c.get("lively") is not None and c["lively"] < 1  # nothing there (snow, shadows): never
        if c not in picked and fits(c) and not empty and not (dull and len(picked) >= 3):
            picked.append(c)
    picked = picked[:n]
    return sorted(picked, key=lambda c: (c["section"] != "outside", c["start"]))


def clip_window(c: dict[str, Any]) -> tuple[float, float]:
    """The CLIP seconds of an item shown in the reel: around its liveliest frame (the model's
    pick, else Frigate's thumbnail), inside the item where it can be."""
    if c.get("best_t"):
        mid = c["best_t"]
    elif c.get("thumb") and c["start"] <= c["thumb"] <= c["end"]:
        mid = c["thumb"]
    else:
        mid = frame_times(c)[1]
    start = mid - CLIP * 0.4
    start = max(c["start"] - 1, min(start, c["end"] + 1 - CLIP))
    return round(start, 1), round(start + CLIP, 1)


def fallback_caption(objects: list[str]) -> str:
    """Frigate's labels as a caption: "Person", "Dog and cat", "Package"."""
    from couchbox.services.frigate import label

    names = []
    for o in objects:
        k = "package" if o in PACKAGES else o
        n = label(k).lower()
        if n and n not in names:
            names.append(n)
    if not names:
        return "Motion"
    text = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    return text[:1].upper() + text[1:]


def camera_name(name: str, friendly: str = "") -> str:
    """ "front_door" -> "Front door" (a friendly name from Frigate is kept as it is)."""
    if friendly:
        return friendly
    words = [w for w in name.replace("-", "_").split("_") if w]
    return " ".join(words)[:1].upper() + " ".join(words)[1:].lower() if words else name


def clock(t: float, clock24: bool) -> str:
    d = datetime.datetime.fromtimestamp(t)
    if clock24:
        return d.strftime("%H:%M")
    return f"{d.hour % 12 or 12}:{d.minute:02d} {'am' if d.hour < 12 else 'pm'}"


def caption(c: dict[str, Any], camera_label: str, clock24: bool) -> str:
    """ "2:14 pm · Front door · A delivery driver leaves a box"."""
    what = c.get("caption") or fallback_caption(c["objects"])
    return f"{clock(c['start'], clock24)} · {camera_label} · {what}"


def length(seconds: float) -> str:
    """How long the household was out: "45 min", "4 h", "2 days"."""
    m = seconds / 60
    if m < 60:
        return f"{max(1, round(m))} min"
    h = m / 60
    if h < 48:
        return f"{round(h)} h"
    return f"{round(h / 24)} days"


def card(since: float, until: float, clips: list[dict[str, Any]]) -> dict[str, Any]:
    """The home screen's card (a Continue watching item: couchbox.ontv's shape)."""
    n = len(clips)
    return {
        "key": "away",
        "app": "frigate",
        "name": "Frigate",
        "desktop": "couchbox-frigate.desktop",
        "title": "While you were out",
        "subtitle": f"{length(until - since)} · {n} moment{'s' if n != 1 else ''}",
        "art": next(("file://" + c["poster"] for c in clips if c.get("poster")), ""),
        "target": "frigate:reel",
        "when": until,
    }


def current(home: Path | None = None, now: float | None = None) -> dict[str, Any] | None:
    """The reel to offer, or None (none, watched, or too old)."""
    r = read_json(reel_file(home))
    now = time.time() if now is None else now
    if not isinstance(r, dict) or r.get("seen") or not r.get("clips") or now - (r.get("until") or 0) > HOLD:
        return None
    return r


def mark_seen(home: Path | None = None) -> None:
    r = read_json(reel_file(home))
    if isinstance(r, dict) and not r.get("seen"):
        r["seen"] = time.time()
        write_json(reel_file(home), r)


def clear(home: Path | None = None) -> None:
    """Forget the last reel (its card and files)."""
    d = cache_dir(home)
    if d.is_dir():
        for p in d.iterdir():
            if p.suffix in (".mp4", ".jpg", ".json", ".part"):
                p.unlink(missing_ok=True)


# ------------------------------------------------------------------ made-up reel (screenshots, tests)
def demo_reel(now: float | None = None) -> dict[str, Any]:
    now = now or time.time()
    since = now - 4.2 * 3600
    rows = [
        ("front_door", "Front door", "outside", ["person", "package"], 3.4, "A delivery driver leaves a box on the step"),
        ("driveway", "Driveway", "outside", ["car"], 2.6, "A neighbour's car turns around in the drive"),
        ("front_door", "Front door", "outside", ["person"], 1.2, "Someone drops a flyer at the door"),
        ("backyard_side_gate", "Backyard side gate by the garden path", "pets", ["dog"], 3.0, "The dog chases a squirrel along the fence"),
        ("living_room", "Living room", "pets", ["dog"], 2.2, "The dog watches the window, tail wagging"),
        ("kitchen", "Kitchen", "pets", ["cat"], 1.6, "The cat jumps onto the counter"),
        ("stairs", "Stairs", "pets", ["cat", "dog"], 0.7, "The cat and the dog race up the stairs"),
    ]
    clips = []
    for cam, name, sec, objs, ago, what in rows:
        t = now - ago * 3600
        c = {"start": t, "objects": objs, "caption": what}
        clips.append(
            {
                "file": "demo:clip",
                "poster": "",
                "camera": cam,
                "cameraLabel": name,
                "section": sec,
                "at": t,
                "when": clock(t, False),
                "caption": caption(c, name, False),
                "what": what,
                "review": {
                    "id": f"demo-away-{len(clips)}",
                    "camera": cam,
                    "start": t - 4,
                    "end": t + 20,
                    "severity": "alert" if sec == "outside" else "detection",
                    "objects": objs,
                },
            }
        )
    return {"since": since, "until": now - 60, "clips": clips, "card": card(since, now - 60, clips), "seen": None}
