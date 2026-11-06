"""The YouTube app's extras, as VacuumTube offers them, and their settings:

* SponsorBlock (sponsor.ajay.app): the parts of a video its viewers marked (a sponsor, a
  self-promotion...); the player skips the chosen kinds and says so, with an undo.
* DeArrow (the same people): titles and pictures its viewers wrote in place of clickbait.
* Return YouTube Dislike (returnyoutubedislikeapi.com): the dislike count YouTube hides.
* Hide Shorts: Shorts left out of the pages.
* H.264 only (VacuumTube's "h264ify"): the Pi decodes H.264 in hardware; off, other codecs too.

SponsorBlock and DeArrow are asked by the first 4 hex digits of the video id's SHA-256 (their
"privacy" API): the answer holds every video with that prefix and we pick ours, so the services
never learn which video plays. Return YouTube Dislike is asked by the id. Answers are kept for
the app's life (an hour at most). The settings are one file, ~/.local/share/couchbox-yt/settings.json
(the TV's, not a profile's).
"""

import hashlib
import json
import os
import threading
import time
from typing import Any

import requests

SPONSORBLOCK = "https://sponsor.ajay.app/api"
DEARROW_THUMB = "https://dearrow-thumb.ajay.app/api/v1/getThumbnail"
RYD = "https://returnyoutubedislikeapi.com/votes"
TIMEOUT = (5, 10)
KEEP = 3600

# SponsorBlock's kinds of segment, as its site names them (the player's toast says these)
CATEGORIES = {
    "sponsor": "Sponsor",
    "selfpromo": "Self-promotion",
    "interaction": "Interaction reminder",
    "intro": "Intro",
    "outro": "Endcards and credits",
    "preview": "Preview or recap",
    "hook": "Hook",
    "filler": "Filler",
    "music_offtopic": "Non-music part",
}
# VacuumTube's defaults: SponsorBlock on, skipping sponsors only; the rest off; H.264 only
DEFAULTS: dict[str, Any] = {
    "sponsorblock": True,
    "skip": {k: k == "sponsor" for k in CATEGORIES},
    "dearrow": False,
    "dislikes": False,
    "hide_shorts": False,
    "h264": True,
    # VacuumTube's other options, its defaults
    "block_continue": False,  # no "Video paused. Continue watching?" after a long autoplay
    "remove_superres": False,  # leave out YouTube's AI-upscaled ("Super resolution") formats
    "unlock_resolution": False,  # past 1080p (VP9/AV1, with H.264 only off)
    "pause_on_blur": False,  # pause when another window comes in front
    "remaining_time": False,  # the time left instead of the length
    # the TV's refresh rate to the video's: off | film (24 and 25 fps films only) | always
    "match_rate": "film",
    "cast": True,  # the TV as a cast target for the YouTube phone app (couchbox-yt-cast, DIAL and the Lounge)
    "guide_tabs": {"music": True, "gaming": True, "news": True, "podcasts": True, "movies": True, "live": True, "sports": True},
}


class Settings:
    def __init__(self, data_dir: str):
        self.path = os.path.join(data_dir, "settings.json")
        self.lock = threading.Lock()

    def get(self) -> dict[str, Any]:
        try:
            with open(self.path) as f:
                saved = json.load(f)
        except (OSError, ValueError):
            saved = {}
        out = json.loads(json.dumps(DEFAULTS))
        for k, v in saved.items():
            if k == "skip" and isinstance(v, dict):
                out["skip"].update({c: bool(on) for c, on in v.items() if c in CATEGORIES})
            elif k == "guide_tabs" and isinstance(v, dict):
                out["guide_tabs"].update({t: bool(on) for t, on in v.items() if t in DEFAULTS["guide_tabs"]})
            elif k == "match_rate":
                out[k] = v if v in ("off", "film", "always") else DEFAULTS[k]
            elif k in DEFAULTS and isinstance(v, type(DEFAULTS[k])):
                out[k] = v
        return out

    def set(self, key: str, value: Any) -> dict[str, Any]:
        """key: a setting, or "skip.<category>"."""
        with self.lock:
            cur = self.get()
            if key.startswith("skip."):
                if key[5:] not in CATEGORIES:
                    raise ValueError(f"no SponsorBlock category {key[5:]}")
                cur["skip"][key[5:]] = bool(value)
            elif key.startswith("tab."):
                if key[4:] not in DEFAULTS["guide_tabs"]:
                    raise ValueError(f"no guide tab {key[4:]}")
                cur["guide_tabs"][key[4:]] = bool(value)
            elif key == "match_rate":
                if value not in ("off", "film", "always"):
                    raise ValueError(f"no frame rate matching {value!r}")
                cur[key] = value
            elif key in DEFAULTS and not isinstance(DEFAULTS[key], dict):
                cur[key] = type(DEFAULTS[key])(value)
            else:
                raise ValueError(f"no setting {key}")
            tmp = self.path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(cur, f, indent=1)
            os.replace(tmp, self.path)
            return cur


def prefix(video_id: str) -> str:
    return hashlib.sha256(video_id.encode()).hexdigest()[:4]


class Extras:
    def __init__(self, session: requests.Session | None = None):
        self.s = session or requests.Session()
        self.s.headers.setdefault("User-Agent", "couchbox-yt (https://github.com/Supermaxman/couchbox)")
        self.cache: dict[str, tuple[float, Any]] = {}
        self.lock = threading.Lock()

    def _get(self, key, fetch):
        with self.lock:
            hit = self.cache.get(key)
        if hit and time.time() - hit[0] < KEEP:
            return hit[1]
        value = fetch()
        with self.lock:
            if len(self.cache) > 500:
                self.cache.clear()
            self.cache[key] = (time.time(), value)
        return value

    # ------------------------------------------------------------------ SponsorBlock
    def segments(self, video_id: str) -> list[dict[str, Any]]:
        """[{category, label, start, end, action}] for the video, every category (the player picks
        which to skip; the bar shows them all). [] when there are none or the service is down."""

        def fetch():
            r = self.s.get(
                f"{SPONSORBLOCK}/skipSegments/{prefix(video_id)}",
                params={"categories": json.dumps(list(CATEGORIES)), "actionTypes": json.dumps(["skip", "mute"])},
                timeout=TIMEOUT,
            )
            if r.status_code == 404:  # nothing for this prefix
                return []
            r.raise_for_status()
            return r.json()

        try:
            data = self._get("sb:" + prefix(video_id), fetch)
        except (requests.RequestException, ValueError) as err:
            print(f"SponsorBlock: no answer ({type(err).__name__})", flush=True)
            return []
        return parse_segments(data, video_id)

    # ------------------------------------------------------------------ DeArrow
    def branding(self, video_id: str) -> dict[str, str]:
        """{title, thumb} from DeArrow for the video (either may be missing: keep YouTube's)."""

        def fetch():
            r = self.s.get(f"{SPONSORBLOCK}/branding/{prefix(video_id)}", timeout=TIMEOUT)
            if r.status_code == 404:
                return {}
            r.raise_for_status()
            return r.json()

        try:
            data = self._get("da:" + prefix(video_id), fetch)
        except (requests.RequestException, ValueError) as err:
            print(f"DeArrow: no answer ({type(err).__name__})", flush=True)
            return {}
        return parse_branding(data, video_id)

    # ------------------------------------------------------------------ Return YouTube Dislike
    def votes(self, video_id: str) -> dict[str, int]:
        """{likes, dislikes} (estimates), {} when the service doesn't know."""

        def fetch():
            r = self.s.get(RYD, params={"videoId": video_id}, timeout=TIMEOUT)
            if r.status_code in (400, 404):
                return {}
            r.raise_for_status()
            return r.json()

        try:
            data = self._get("ryd:" + video_id, fetch)
        except (requests.RequestException, ValueError) as err:
            print(f"Return YouTube Dislike: no answer ({type(err).__name__})", flush=True)
            return {}
        if not isinstance(data, dict) or "dislikes" not in data:
            return {}
        if not data.get("likes") and not data.get("dislikes") and not data.get("viewCount"):
            return {}  # a video it knows nothing about (it answers 0 and 0)
        return {"likes": int(data.get("likes") or 0), "dislikes": int(data.get("dislikes") or 0)}


def parse_segments(data: Any, video_id: str) -> list[dict[str, Any]]:
    """SponsorBlock's privacy answer (a list of videos) -> this video's segments, in order."""
    out = []
    for v in data if isinstance(data, list) else []:
        if v.get("videoID") != video_id:
            continue
        for s in v.get("segments") or []:
            seg, cat = s.get("segment") or [], s.get("category", "")
            if len(seg) != 2 or cat not in CATEGORIES or not seg[1] > seg[0]:
                continue
            out.append(
                {
                    "category": cat,
                    "label": CATEGORIES[cat],
                    "start": float(seg[0]),
                    "end": float(seg[1]),
                    "action": s.get("actionType", "skip"),
                }
            )
    return sorted(out, key=lambda s: s["start"])


def parse_branding(data: Any, video_id: str) -> dict[str, str]:
    """DeArrow's privacy answer ({id: {titles, thumbnails}}) -> {title, thumb} for this video: the
    best title that isn't the original (DeArrow's ">" marks one for auto-formatting), and a frame
    of the video as its picture when viewers chose one."""
    v = (data or {}).get(video_id) if isinstance(data, dict) else None
    if not isinstance(v, dict):
        return {}
    out: dict[str, str] = {}
    for t in v.get("titles") or []:  # DeArrow sends them best first
        if t.get("original") or (t.get("votes", 0) < 0 and not t.get("locked")):
            continue
        title = (t.get("title") or "").replace(">", "").strip()
        if title:
            out["title"] = title
            break
    for th in v.get("thumbnails") or []:
        if th.get("original") or (th.get("votes", 0) < 0 and not th.get("locked")):
            continue
        if th.get("timestamp") is not None:
            out["thumb"] = f"{DEARROW_THUMB}?videoID={video_id}&time={float(th['timestamp'])}"
            break
    return out


def hide_shorts(page: Any) -> Any:
    """A page (or a list of more cards) without Shorts: their cards, and shelves left empty."""
    if isinstance(page, dict) and "shelves" in page:
        shelves = []
        for s in page.get("shelves") or []:
            items = [i for i in s.get("items") or [] if i.get("type") != "short"]
            if items:
                s = dict(s, items=items)
                if s.get("cluster"):
                    c = s["cluster"]
                    s["cluster"] = {k: dict(c[k], items=[i for i in c[k].get("items") or [] if i.get("type") != "short"]) for k in c}
                shelves.append(s)
        return dict(page, shelves=shelves)
    if isinstance(page, dict) and "items" in page:
        return dict(page, items=[i for i in page["items"] if i.get("type") != "short"])
    return page
