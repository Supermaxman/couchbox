"""What's on this TV, across its apps: the home screen's Continue watching row and Search's
"On this TV" results. couchbox-ontv (the TV user's service) keeps the row fresh; the Search app
asks here for matches; both open what's picked in its own app.

Sources, each only while its app is on the home row (as couchboxd last wrote it, home.json):
  jellyfin        what's part-watched (Jellyfin's Resume list) and its library search, with the
                  TV's own Jellyfin sign-in: read from Jellyfin Desktop (or the Jellyfin web app)
                  over DevTools whenever it runs, and kept (~/.local/share/couchbox-ontv, mode 600)
                  for when it doesn't
  dropout, 2ndtry their Continue Watching (VHX, vhx.py) and search
  nebula          its Continue Watching and search (nebula.py)
  twitch          followed channels live now (signed in), and channel / category search (twitch.py)
  movies          search only: TMDB through Seerr or a TMDB key (movies.py)
  youtube         Couchbox's own YouTube app (couchbox-yt): the part-watched videos of its History,
                  as the profile it last watched as (its own sign-in, ~/.local/share/couchbox-yt;
                  a guest has none), OK starting each where it was left; and search: one card
                  that opens the app's search. With VacuumTube chosen instead (Settings → Apps →
                  YouTube app), search only: its history lives in VacuumTube's page.

Items are plain dicts, the same for both lists:
  {key, app, name, desktop, title, subtitle, art, fit, progress, left, live, viewers, when, target}
  fit: the art is a poster (fit it, don't crop it); left: "23 min left"; when: last watched
  (unix time; for a live stream, when it started).

Targets name the app and what its --open takes:
  dropout:play:123  dropout:series:45  nebula:play:<id>  twitch:play:live:<login>
  twitch:series:<login>  twitch:category:<name>  movies:movie:603  movies:tv:1399
  jellyfin:<item id>  youtube:search:<text>  youtube:video:<id>[@<seconds>]
  frigate:reel (the While you were out card's reel, couchbox.away)
  frigate:recording:<camera>@<start>-<end> (a camera's recording then: the morning show's moments)
  show:morning (the morning show, couchbox.show: its tile at the front of the home row)
  reels:<id> (a kept reel in the Reels app, couchbox.reels: Today at home's card)
open_target() opens one as the TV user: the streaming apps, Movies & TV and YouTube through their
control socket when they run (and KWin raises the window), else started with --open; Jellyfin,
and YouTube when VacuumTube is the YouTube app, through couchbox-voice (127.0.0.1:8790
/play/jellyfin, /search/youtube), which drives them over DevTools as the voice assistant does
(Jellyfin resumes where it was left).
"""

import datetime
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.parse
import uuid
from pathlib import Path
from typing import Any

from couchbox import apps, paths, settings

STREAMING = ("dropout", "2ndtry", "nebula", "twitch")  # app id = couchbox-streaming --site
CONTINUE_APPS = ("jellyfin", "dropout", "2ndtry", "nebula", "twitch", "youtube")
SEARCH_APPS = ("jellyfin", "dropout", "2ndtry", "nebula", "twitch", "movies", "youtube")
NAMES = {
    "jellyfin": "Jellyfin",
    "dropout": "Dropout",
    "2ndtry": "2nd Try",
    "nebula": "Nebula",
    "twitch": "Twitch",
    "movies": "Movies & TV",
    "youtube": "YouTube",
    "frigate": "Frigate",  # (opened only: the home screen's While you were out card, couchbox.away)
    "show": "Morning show",  # (opened only: its tile, couchbox.show)
    "reels": "Reels",  # (from Today at home's card, couchbox.dayreel)
}
DESKTOP = {a: f"couchbox-{a}.desktop" for a in ("jellyfin", "movies", *STREAMING)} | {"youtube": "couchbox-yt.desktop"}

# each app's colour, as its home tile's glow (shell/theme/tiles): where home.json isn't at hand
GLOW = {
    "jellyfin": "#8a5cff",
    "dropout": "#ffe23a",
    "2ndtry": "#14bdb5",
    "nebula": "#3a5bff",
    "twitch": "#9146ff",
    "movies": "#f5b301",
    "youtube": "#ff1f1f",
}

MAX_ITEMS = 20  # the row
MAX_LIVE = 6  # ... of which live Twitch channels
PER_SOURCE = 8  # search: matches per app
DONE = 0.97  # watched this much: finished, not "continue"
KEEP = {"twitch": 15 * 60}  # a source that can't be reached keeps its last items this long (live: briefly)
KEEP_DEFAULT = 6 * 3600
YOUTUBE_MAX = 4  # YouTube's History is long: its newest few, among the other apps' (by when)
FORGET = 30 * 86400  # remembered positions of items gone from every list
VOICE = "http://127.0.0.1:8790"
JELLYFIN_DEVTOOLS = 9224  # Jellyfin Desktop (couchbox-jellyfin)
WEB_DEVTOOLS = 9223  # the Chromium web apps, Jellyfin's web app among them


class NotSignedIn(Exception):
    """The app isn't signed in on this TV (said once in the service's log, not on screen)."""


# ------------------------------------------------------------------ where things are
def data_dir(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".local/share/couchbox-ontv"


def continue_file(home: Path | None = None) -> Path:
    """The row, for the home screen (written by the service, read by the home QML)."""
    return (home or Path.home()) / ".cache/couchbox-ontv/continue.json"


def write_json(path: Path, data: Any, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def home_apps() -> list[str]:
    """App ids on the home row, as couchboxd last wrote it: the TV user can't judge apps that need a
    root-only secret (Movies & TV with a TMDB key) itself."""
    data = read_json(paths.state() / "home/home.json")
    if isinstance(data, dict) and isinstance(data.get("apps"), list):
        return [a.get("app", "") for a in data["apps"]]
    return [a.id for a in apps.home_row(settings.load())]


def sources(kind: str = "continue", on_home: list[str] | None = None) -> list[str]:
    """The apps to ask, in order: those on the home row (hidden or turned-off apps are left out)."""
    on = set(home_apps() if on_home is None else on_home)
    return [a for a in (CONTINUE_APPS if kind == "continue" else SEARCH_APPS) if a in on]


# ------------------------------------------------------------------ shaping
def when_of(iso: str | None) -> float:
    """Unix time of an ISO date (Jellyfin's have 7 decimals), 0 when there's none."""
    if not iso:
        return 0.0
    s = re.sub(r"(\.\d{6})\d+", r"\1", iso.strip()).replace("Z", "+00:00")
    try:
        t = datetime.datetime.fromisoformat(s)
    except ValueError:
        return 0.0
    if t.tzinfo is None:
        t = t.replace(tzinfo=datetime.UTC)
    return t.timestamp()


def minutes_left(total_s: float, done_s: float) -> str:
    m = round(max(0.0, total_s - done_s) / 60)
    if m <= 0:
        return ""
    return f"{m // 60} h {m % 60} min left" if m >= 60 else f"{m} min left"


def ep_label(c: dict[str, Any]) -> str:
    """As the streaming app shows it (D.epLabel): "Fantasy High · E1", "S5 · E2", "Episode 3"."""
    if not c.get("episode"):
        return ""
    sn = c.get("seasonName") or ""
    if sn and not re.fullmatch(r"season\s*\d+", sn, re.I):
        return f"{sn} · E{c['episode']}"
    return f"S{c['seasonNumber']} · E{c['episode']}" if c.get("seasonNumber") else f"Episode {c['episode']}"


def item(app: str, key: str, title: str, target: str, **kw: Any) -> dict[str, Any]:
    out = {
        "key": f"{app}:{key}",
        "app": app,
        "title": title,
        "subtitle": "",
        "art": "",
        "fit": False,
        "progress": 0.0,
        "left": "",
        "live": False,
        "viewers": "",
        "when": 0.0,
        "target": target,
        "name": NAMES.get(app, app),
        "desktop": DESKTOP.get(app, ""),
    }
    out.update(kw)
    return out


def jellyfin_art(it: dict[str, Any], server: str, width: int = 560) -> tuple[str, bool]:
    """(picture URL, is a poster) for a Jellyfin item: an episode's still, a movie's backdrop or
    thumb, else the poster."""
    tags = it.get("ImageTags") or {}

    def url(item_id: str, kind: str, tag: str = "") -> str:
        q = {"maxWidth": width, "quality": 85}
        if tag:
            q["tag"] = tag
        return f"{server}/Items/{item_id}/Images/{kind}?{urllib.parse.urlencode(q)}"

    if it.get("Type") == "Episode" and tags.get("Primary"):
        return url(it["Id"], "Primary", tags["Primary"]), False
    if tags.get("Thumb"):
        return url(it["Id"], "Thumb", tags["Thumb"]), False
    if it.get("BackdropImageTags"):
        return url(it["Id"], "Backdrop/0", it["BackdropImageTags"][0]), False
    if it.get("ParentThumbItemId") and it.get("ParentThumbImageTag"):
        return url(it["ParentThumbItemId"], "Thumb", it["ParentThumbImageTag"]), False
    if it.get("ParentBackdropItemId") and it.get("ParentBackdropImageTags"):
        return url(it["ParentBackdropItemId"], "Backdrop/0", it["ParentBackdropImageTags"][0]), False
    if tags.get("Primary"):
        return url(it["Id"], "Primary", tags["Primary"]), True
    if it.get("SeriesId") and it.get("SeriesPrimaryImageTag"):
        return url(it["SeriesId"], "Primary", it["SeriesPrimaryImageTag"]), True
    return "", False


def jellyfin_item(it: dict[str, Any], server: str) -> dict[str, Any]:
    ud = it.get("UserData") or {}
    run = (it.get("RunTimeTicks") or 0) / 1e7
    pos = (ud.get("PlaybackPositionTicks") or 0) / 1e7
    progress = (ud.get("PlayedPercentage") or 0) / 100 or (pos / run if run else 0.0)
    t = it.get("Type")
    if t == "Episode":
        title = it.get("SeriesName") or it.get("Name") or ""
        num = (
            f"S{it['ParentIndexNumber']} · E{it['IndexNumber']}"
            if it.get("ParentIndexNumber") is not None and it.get("IndexNumber")
            else ""
        )
        sub = " · ".join(x for x in (num, it.get("Name") if it.get("SeriesName") else "") if x)
    elif t == "Series":
        title, sub = it.get("Name") or "", "Show"
    else:
        title, sub = it.get("Name") or "", str(it.get("ProductionYear") or "")
    art, fit = jellyfin_art(it, server)
    return item(
        "jellyfin",
        it.get("Id", ""),
        title,
        f"jellyfin:{it.get('Id', '')}",
        subtitle=sub,
        art=art,
        fit=fit,
        progress=round(min(1.0, progress), 3),
        left=minutes_left(run, pos) if pos else "",
        when=when_of(ud.get("LastPlayedDate")),
    )


def stream_item(site: str, c: dict[str, Any]) -> dict[str, Any] | None:
    """A streaming app's card (vhx.card, nebula's, twitch's) as an item, or None if it can't be opened."""
    from couchbox.services import vhx

    cid = str(c.get("id") or "")
    if not cid:
        return None
    art = c.get("landscape") or c.get("background") or ""
    if "imgix.net" in art:
        art = vhx.img(art, 560, 315)
    if c.get("live"):  # Twitch: a live stream (id live:<login>)
        return item(
            site,
            cid,
            c.get("series") or c.get("slug") or "",
            f"{site}:play:{cid}",
            subtitle=c.get("title") or "",
            art=art,
            live=True,
            viewers=c.get("viewers") or "",
            when=when_of(c.get("started")),
            category=c.get("description") or "",
        )
    kind = c.get("kind")
    if kind == "category":
        return item(
            site,
            cid,
            c.get("title") or "",
            f"{site}:category:{c.get('slug') or cid.removeprefix('cat:')}",
            subtitle=c.get("viewers") or "Category",
            art=c.get("poster") or art,
            fit=True,
        )
    if kind in ("series", "collection", "movie"):
        sub = c.get("description") if site == "twitch" else f"{c['seasons']} seasons" if c.get("seasons", 0) > 1 else ""
        return item(
            site,
            cid,
            c.get("title") or "",
            f"{site}:series:{cid}",
            subtitle=sub or "",
            art=art or c.get("square") or c.get("poster") or "",
            fit=not art,
        )
    if kind != "video":
        return None
    dur, tc = c.get("duration") or 0, c.get("timecode") or 0
    series = c.get("series") or ""
    sub = " · ".join(x for x in (ep_label(c), c.get("title") if series else "") if x)
    return item(
        site,
        cid,
        series or c.get("title") or "",
        f"{site}:play:{cid}",
        subtitle=sub,
        art=art,
        progress=round(min(1.0, c.get("progress") or 0.0), 3),
        left=minutes_left(dur, tc) if tc else "",
        position=tc,
    )


def watching(site: str, cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A streaming app's Continue Watching as row items: started and not finished (Twitch: live)."""
    out = []
    for c in cards:
        if site != "twitch" and (c.get("completed") or (c.get("progress") or 0) >= DONE):
            continue
        if site == "twitch" and not c.get("live"):
            continue
        it = stream_item(site, c)
        if it:
            out.append(it)
    return out


def movies_items(found: dict[str, Any]) -> list[dict[str, Any]]:
    """Movies & TV's search (movies.Movies.search) as items: movies and shows, best first."""
    cards = sorted(found.get("movies", []) + found.get("tv", []), key=lambda c: -(c.get("popularity") or 0))
    out = []
    for c in cards[:PER_SOURCE]:
        bits = [str(c.get("year") or ""), "Movie" if c["type"] == "movie" else "Show"]
        if c.get("score"):
            bits.append(f"★ {c['score']}")
        out.append(
            item(
                "movies",
                f"{c['type']}:{c['id']}",
                c.get("title") or "",
                f"movies:{c['type']}:{c['id']}",
                subtitle=" · ".join(b for b in bits if b),
                art=c.get("backdrop") or c.get("poster") or "",
                fit=not c.get("backdrop"),
            )
        )
    return out


def length(d: str) -> int:
    """Seconds of a card's "1:02:03" or "12:34" (0 if it has none)."""
    try:
        n = 0
        for part in d.split(":"):
            n = n * 60 + int(part)
        return n if ":" in d else 0
    except ValueError:
        return 0


def youtube_continue(page: dict[str, Any], limit: int = 12) -> list[dict[str, Any]]:
    """The part-watched videos of couchbox-yt's History page, most recent first, each opening where
    it was left (a few seconds before). YouTube gives no times, so the position the service
    remembers is how far each was watched (place())."""
    out = []
    for shelf in page.get("shelves") or []:
        for c in shelf.get("items") or []:
            p = c.get("progress") or 0.0
            key = f"youtube:{c.get('id')}"
            if c.get("type") != "video" or not c.get("id") or not 0.01 < p < DONE or any(it["key"] == key for it in out):
                continue
            total = length(c.get("duration") or "")
            at = max(0, int(total * p) - 3) if total else 0
            out.append(
                item(
                    "youtube",
                    c["id"],
                    c.get("title") or "",
                    f"youtube:video:{c['id']}" + (f"@{at}" if at else ""),
                    subtitle=(c.get("lines") or [""])[0],
                    art=c.get("thumb") or "",
                    progress=round(p, 3),
                    left=minutes_left(total, total * p) if total else "",
                    position=round(p, 2),
                )
            )
    return out[:limit]


def youtube_item(query: str) -> dict[str, Any]:
    return item(
        "youtube", "search", f"Search YouTube for “{query.strip()}”", f"youtube:search:{query.strip()}", subtitle="Opens in YouTube"
    )


# ------------------------------------------------------------------ the row's order
def place(source: str, items: list[dict[str, Any]], seen: dict[str, Any], now: float, first: bool) -> None:
    """Give every item a "when" (last watched), newest first across apps. Jellyfin says when; a
    live stream started when it did. Dropout, 2nd Try and Nebula only give their own order, so
    the service remembers each item's position: one that moved, or is new since the last look,
    was watched just now; one that sits still keeps its time. The first look at an app can't
    tell, so its items go after everything dated, in the app's order."""
    for rank, it in enumerate(items):
        pos = it.pop("position", None)
        if it["when"]:
            seen[it["key"]] = {"pos": pos, "at": it["when"], "seen": now}
            continue
        prev = seen.get(it["key"])
        if prev and prev.get("pos") == pos:
            at = prev["at"]
        elif first and not prev:
            at = -float(rank)  # undated: after the rest, in the app's order
        else:
            at = now - rank  # watched since the last look (keeps the app's order among them)
        it["when"] = at
        seen[it["key"]] = {"pos": pos, "at": at, "seen": now}
    for k in [k for k, v in seen.items() if k.startswith(source + ":") and now - v.get("seen", 0) > FORGET]:
        del seen[k]


def merge(lists: dict[str, list[dict[str, Any]]], limit: int = MAX_ITEMS) -> list[dict[str, Any]]:
    """Every app's items in one row, newest first (ties: the order of CONTINUE_APPS), at most
    MAX_LIVE live channels."""
    order = {a: i for i, a in enumerate(CONTINUE_APPS)}
    flat = [(it, order.get(src, 99), i) for src, items in lists.items() for i, it in enumerate(items)]
    flat.sort(key=lambda x: (-x[0]["when"], x[1], x[2]))
    out, live, keys = [], 0, set()
    for it, _, _ in flat:
        if it["key"] in keys:
            continue
        if it["live"]:
            if live >= MAX_LIVE:
                continue
            live += 1
        keys.add(it["key"])
        out.append(it)
        if len(out) >= limit:
            break
    return out


# ------------------------------------------------------------------ Jellyfin
JF_AUTH_JS = """() => {
  const a = window.ApiClient;
  if (!a || !a.getCurrentUserId || !a.getCurrentUserId() || !a.accessToken()) return null;
  return {server: a.serverAddress(), token: a.accessToken(), user: a.getCurrentUserId()};
}"""


class Jellyfin:
    """Jellyfin's REST API with the TV's sign-in. Only the token goes with each request, so the
    server counts it as the TV's own Jellyfin (same device and session), not a new one."""

    FIELDS = "UserData,ProductionYear,PrimaryImageAspectRatio"

    def __init__(self, auth: dict[str, str]):
        import requests

        self.server = auth["server"].rstrip("/")
        self.user = auth["user"]
        self.s = requests.Session()
        self.s.headers["Authorization"] = f'MediaBrowser Token="{auth["token"]}"'

    @staticmethod
    def auth_file() -> Path:
        return data_dir() / "jellyfin.json"

    @classmethod
    def from_tv(cls, look: bool = True) -> "Jellyfin | None":
        """With the sign-in of the Jellyfin app on this TV: read from it when it runs (kept for
        later), else the copy kept from last time. None if there's neither."""
        auth = cls.from_app() if look else None
        kept = read_json(cls.auth_file())
        if auth and auth != kept:
            write_json(cls.auth_file(), auth, 0o600)
        auth = auth or kept
        return cls(auth) if isinstance(auth, dict) and auth.get("token") and auth.get("server") and auth.get("user") else None

    @staticmethod
    def from_app() -> dict[str, str] | None:
        from couchbox.voice import cdp

        host = urllib.parse.urlsplit(settings.get("media.jellyfin.url") or "").netloc
        pages = cdp.pages(JELLYFIN_DEVTOOLS) + [p for p in cdp.pages(WEB_DEVTOOLS) if host and host in p.get("url", "")]
        for p in pages:
            try:
                got = cdp.call(p, JF_AUTH_JS, timeout=5)
            except Exception:  # noqa: BLE001 - a page that's loading, or not Jellyfin's
                continue
            if isinstance(got, dict) and got.get("token"):
                return {k: str(got[k]) for k in ("server", "token", "user")}
        return None

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        r = self.s.get(self.server + path, params=params, timeout=(5, 20))
        if r.status_code == 401:
            raise NotSignedIn("Jellyfin no longer takes the TV's sign-in: open Jellyfin and sign in")
        r.raise_for_status()
        return r.json()

    def resume(self, limit: int = 12) -> list[dict[str, Any]]:
        import requests

        q = {
            "limit": limit,
            "fields": self.FIELDS,
            "mediaTypes": "Video",
            "enableImageTypes": "Primary,Backdrop,Thumb",
            "imageTypeLimit": 1,
        }
        try:
            r = self.get("/UserItems/Resume", dict(q, userId=self.user))
        except requests.HTTPError:  # before 10.9
            r = self.get(f"/Users/{self.user}/Items/Resume", q)
        return [jellyfin_item(i, self.server) for i in r.get("Items", [])]

    def search(self, query: str, limit: int = PER_SOURCE) -> list[dict[str, Any]]:
        r = self.get(
            "/Items",
            {
                "userId": self.user,
                "searchTerm": query,
                "recursive": "true",
                "limit": limit,
                "fields": self.FIELDS,
                "includeItemTypes": "Movie,Series,Episode",
                "enableImageTypes": "Primary,Backdrop,Thumb",
                "imageTypeLimit": 1,
            },
        )
        return [jellyfin_item(i, self.server) for i in r.get("Items", [])]


# ------------------------------------------------------------------ the apps' clients
class Clients:
    """One client per streaming app, made again when the app saves a new sign-in (or signs out).
    done() after each use: the client's own saves (a refreshed token) don't count as new."""

    def __init__(self) -> None:
        self.made: dict[str, tuple[float | None, Any]] = {}

    @staticmethod
    def _mtime(site: str) -> float | None:
        try:
            return (Path.home() / f".local/share/couchbox-{site}/session.json").stat().st_mtime
        except OSError:
            return None

    def done(self, site: str) -> None:
        if site in self.made:
            self.made[site] = (self._mtime(site), self.made[site][1])

    def get(self, site: str) -> Any:
        from couchbox.services import vhx

        if site == "youtube":
            return self.youtube()
        mtime = self._mtime(site)
        if site in self.made and self.made[site][0] == mtime:
            return self.made[site][1]
        backend = vhx.SITES[site].get("backend")
        if backend == "nebula":
            from couchbox.services import nebula

            c = nebula.Nebula(site)
        elif backend == "twitch":
            from couchbox.services import twitch

            c = twitch.Twitch(site)
        else:
            c = vhx.Vhx(site)
        self.made[site] = (mtime, c)
        return c

    def youtube(self) -> Any:
        """couchbox-yt's YouTube (its own sign-in) as the profile it last watched as; NotSignedIn for
        a guest. Made once: it reads the app's files each time."""
        from couchbox.services import youtube

        if "youtube" not in self.made:  # the TV client as it's known here: no yt-dlp in this service
            self.made["youtube"] = (None, youtube.YouTube(client=youtube.TV_CLIENT))
        yt = self.made["youtube"][1]
        prof = yt.find_profile(yt.auth.last_profile())
        if not prof:
            raise NotSignedIn("YouTube: watching as a guest (nothing to continue)")
        with yt.lock:
            yt.profile = prof
            yt.cache.clear()
        return yt


def fetch_continue(source: str, clients: Clients) -> list[dict[str, Any]]:
    """One app's part of the row (NotSignedIn, or the app's own errors, when it can't)."""
    from couchbox.services import vhx

    if source == "jellyfin":
        j = Jellyfin.from_tv()
        if not j:
            raise NotSignedIn("Jellyfin: open it once on the TV, signed in, so its sign-in can be read")
        return j.resume()
    if source == "youtube":
        from couchbox import apps
        from couchbox.services import ytauth

        if not apps.youtube_native():
            raise NotSignedIn("YouTube: VacuumTube is the YouTube app (its history isn't readable here)")
        try:
            return youtube_continue(clients.get("youtube").browse("FEhistory"), limit=YOUTUBE_MAX)
        except ytauth.SignedOut:
            raise NotSignedIn("YouTube: the account was signed out; sign in again from Who's watching") from None
    c = clients.get(source)
    if source == "twitch" and not c.signed_in:
        raise NotSignedIn("Twitch: not signed in")
    try:
        return watching(source, c.watching()["items"])
    except vhx.SignInNeeded:
        raise NotSignedIn(f"{NAMES[source]}: not signed in") from None
    finally:
        clients.done(source)


def search(source: str, query: str, clients: Clients | None = None) -> list[dict[str, Any]]:
    """One app's matches for query, best first (NotSignedIn when it can't look)."""
    from couchbox.services import vhx

    q = query.strip()
    if not q:
        return []
    if source == "youtube":
        return [youtube_item(q)]
    if source == "jellyfin":
        j = Jellyfin.from_tv()
        if not j:
            raise NotSignedIn("Jellyfin: open it once on the TV, signed in")
        return j.search(q)
    if source == "movies":
        from couchbox.services import movies

        return movies_items(movies.Movies.for_app(settings.get("media.seerr.url")).search(q))
    clients = clients or Clients()
    c = clients.get(source)
    try:
        cards = c.search(q, 1)["items"]
    except vhx.SignInNeeded:
        raise NotSignedIn(f"{NAMES[source]}: not signed in") from None
    finally:
        clients.done(source)
    return [x for x in (stream_item(source, c) for c in cards) if x][:PER_SOURCE]


# ------------------------------------------------------------------ opening
def split_target(target: str) -> tuple[str, str]:
    """("dropout", "play:123") from "dropout:play:123"; ValueError for anything else."""
    app, _, rest = (target or "").partition(":")
    if app not in NAMES or not rest:
        raise ValueError(f"not something to open: {target!r}")
    if app == "jellyfin" and not re.fullmatch(r"[0-9a-fA-F-]{8,40}", rest):
        raise ValueError(f"not a Jellyfin item: {rest!r}")
    if app in STREAMING and not re.match(r"(play|series|category|search):.", rest):
        raise ValueError(f"not something {NAMES[app]} opens: {rest!r}")
    if app == "movies" and not re.fullmatch(r"(movie|tv):\d+", rest):
        raise ValueError(f"not a title: {rest!r}")
    if app == "frigate" and rest != "reel" and not re.fullmatch(r"recording:[\w-]{1,64}@\d{9,11}(\.\d+)?-\d{9,11}(\.\d+)?", rest):
        raise ValueError(f"not something Frigate opens from here: {rest!r}")
    if app == "show" and rest != "morning":
        raise ValueError(f"not a show: {rest!r}")
    if app == "reels" and not re.fullmatch(r"[a-z]{1,16}-\d{9,11}", rest):
        raise ValueError(f"not a reel: {rest!r}")
    if app == "youtube" and not (re.fullmatch(r"video:[\w-]{11}(@\d{1,6})?", rest) or re.match(r"search:.", rest)):
        raise ValueError(f"not a video or a search: {rest!r}")
    return app, rest


SITE = {"youtube": "yt"}  # control socket names that aren't the app's id
EXE = {"youtube": "couchbox-yt"}


def launch_command(app: str, rest: str, unit: str = "") -> list[str]:
    """How to start an app on rest (when it isn't running): in a unit of its own, named like
    the home screen's (app-<desktop name>@...), so couchbox-memory treats it as any app."""
    name = EXE.get(app, f"couchbox-{app}")
    exe = f"/usr/lib/couchbox/bin/{name}"
    unit = unit or f"app-{name}@ontv-{uuid.uuid4().hex[:8]}.service"
    return ["systemd-run", "--user", "--quiet", "--collect", f"--unit={unit}", "--", exe, "--open", rest]


def voice_request(app: str, rest: str) -> tuple[str, dict[str, str]]:
    """couchbox-voice's endpoint and body for Jellyfin and YouTube."""
    if app == "jellyfin":
        return "/play/jellyfin", {"id": rest}
    return "/search/youtube", {"query": rest.removeprefix("search:")}


RAISE_JS = """for (const w of workspace.windowList())
  if (w.normalWindow && (w.desktopFileName === %s || w.resourceClass === %s)) {
    w.minimized = false; w.fullScreen = true; workspace.activeWindow = w; break;
  }"""


def kwin_raise(app_id: str) -> None:
    """Bring an app's window to the front, full screen (a KWin script, as couchbox-jellyfin does)."""
    js = RAISE_JS % (json.dumps(app_id), json.dumps(app_id))
    fd, path = tempfile.mkstemp(suffix=".js")
    with os.fdopen(fd, "w") as f:
        f.write(js)
    name = f"couchbox-ontv-{os.getpid()}"
    kwin = ["gdbus", "call", "--session", "--dest", "org.kde.KWin"]
    try:
        out = subprocess.run(
            kwin + ["--object-path", "/Scripting", "--method", "org.kde.kwin.Scripting.loadScript", path, name],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
        sid = re.findall(r"\d+", out)
        if sid:
            subprocess.run(
                kwin + ["--object-path", f"/Scripting/Script{sid[-1]}", "--method", "org.kde.kwin.Script.run"],
                capture_output=True,
                timeout=5,
            )
            time.sleep(0.3)
        subprocess.run(
            kwin + ["--object-path", "/Scripting", "--method", "org.kde.kwin.Scripting.unloadScript", name], capture_output=True, timeout=5
        )
    except (OSError, subprocess.SubprocessError):
        pass
    finally:
        os.unlink(path)


def open_target(target: str) -> str:
    """Open one item in its app, as the TV user. Returns what was done (for the log)."""
    import requests

    from couchbox import appctl

    app, rest = split_target(target)
    from couchbox import apps

    if app == "jellyfin" or (app == "youtube" and not apps.youtube_native()):  # (VacuumTube: its search, over DevTools)
        path, body = voice_request(app, rest)
        r = requests.post(VOICE + path, json=body, headers={"X-Couchbox": "1"}, timeout=10)
        r.raise_for_status()
        return f"{NAMES[app]}: asked couchbox-voice ({path})"
    site = SITE.get(app, app)
    if appctl.running(site):
        appctl.call(site, {"op": "open", "target": rest}, timeout=10)
        kwin_raise(EXE.get(app, f"couchbox-{app}"))
        return f"{NAMES[app]}: opened {rest} in the running app"
    cmd = launch_command(app, rest)
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):  # no user manager (tests, a bare session)
        subprocess.Popen(cmd[cmd.index("--") + 1 :], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return f"{NAMES[app]}: started on {rest}"


# ------------------------------------------------------------------ made-up items (tests, screenshots)
def demo_continue(now: float | None = None) -> list[dict[str, Any]]:
    now = now or time.time()
    return [
        item(
            "jellyfin",
            "a1",
            "The Long Harbor",
            "jellyfin:0f3a9c2e8b7d4e10",
            subtitle="S2 · E4 · Low Tide",
            progress=0.42,
            left="31 min left",
            when=now - 3600,
        ),
        item(
            "dropout",
            "101",
            "Game Changer",
            "dropout:play:101",
            subtitle="S6 · E3 · Sam Says",
            progress=0.7,
            left="12 min left",
            when=now - 5000,
        ),
        item(
            "twitch",
            "live:northcliff",
            "Northcliff",
            "twitch:play:live:northcliff",
            subtitle="Speedrunning the lighthouse level",
            live=True,
            viewers="4.2K viewers",
            when=now - 7000,
            category="Retro",
        ),
        item(
            "nebula",
            "v9",
            "Map Men",
            "nebula:play:v9",
            subtitle="Why is this border so strange?",
            progress=0.25,
            left="9 min left",
            when=now - 86400,
        ),
        item(
            "jellyfin",
            "a2",
            "Paper Moons",
            "jellyfin:0f3a9c2e8b7d4e11",
            subtitle="2019",
            progress=0.15,
            left="1 h 32 min left",
            when=now - 2 * 86400,
        ),
        item("2ndtry", "55", "Ultimate Pie", "2ndtry:play:55", subtitle="S1 · E2", progress=0.55, left="8 min left", when=now - 3 * 86400),
        item(
            "youtube",
            "demo0000006",
            "How Tides Really Work",
            "youtube:video:demo0000006@1257",
            subtitle="Orbit Lab",
            progress=0.35,
            left="39 min left",
            when=now - 3.5 * 86400,
        ),
        item(
            "dropout",
            "102",
            "Dimension 20",
            "dropout:play:102",
            subtitle="Fantasy High · E7",
            progress=0.1,
            left="1 h 20 min left",
            when=now - 4 * 86400,
        ),
    ]


def demo_search(source: str, query: str) -> list[dict[str, Any]]:
    q = query.strip() or "harbor"
    t = q.title()
    made = {
        "jellyfin": [
            item("jellyfin", "s1", t, "jellyfin:0f3a9c2e8b7d4e20", subtitle="Show", fit=True),
            item("jellyfin", "s2", f"{t}: The Return", "jellyfin:0f3a9c2e8b7d4e21", subtitle="2021", progress=0.3),
        ],
        "dropout": [item("dropout", "7", f"Very Important {t}", "dropout:series:7", subtitle="2 seasons")],
        "nebula": [item("nebula", "v1", f"The Truth About {t}s", "nebula:play:v1", subtitle="Half as Interesting")],
        "twitch": [
            item(
                "twitch",
                "live:harborcam",
                "HarborCam",
                "twitch:play:live:harborcam",
                subtitle=f"{t} live, all day",
                live=True,
                viewers="312 viewers",
            ),
            item("twitch", "cat:Harbor", f"{t} Simulator", f"twitch:category:{t} Simulator", subtitle="1.1K viewers", fit=True),
        ],
        "movies": [
            item("movies", "movie:101", f"{t} Lights", "movies:movie:101", subtitle="2019 · Movie · ★ 7.4"),
            item("movies", "tv:201", f"{t} Street", "movies:tv:201", subtitle="2016 · Show · ★ 8.1", fit=True),
        ],
        "youtube": [youtube_item(q)],
    }
    return made.get(source, [])
