"""What's playing, as the voice assistant reads it: "who is this guy again?", "what did I miss?",
"skip to where he tastes it". Jellyfin and YouTube (Couchbox's own app or VacuumTube).

The assistant gets the subtitles of what plays, with times: up to the current second for
questions about the story (and, for an episode, what the episodes already watched were about),
so nothing later can slip into the answer; the last few minutes for a recap; the whole video to
find a moment and jump there. With the story and the recap goes a picture of the screen
(couchbox-screenshot), for models that see pictures.

    watching.run("story" | "recent" | "find", minutes=None, query=None) -> Text (a str, .image)
"""

import base64
import os
import pwd
import re
import subprocess
import time

from couchbox import appctl, settings

from . import cdp, ytnative

TV_USER = "tv"
SCREENSHOT = "/usr/lib/couchbox/bin/couchbox-screenshot"
STORY_CHARS = 32000  # about 8k tokens of subtitles (a few seconds for the model): the latest part when there's more
FIND_CHARS = 90000  # a whole film's subtitles; longer ones are cut to the lines that match
EARLIER_CHARS = 6000  # what the episodes already watched were about
RECENT_MINUTES = 5
LINE_SECONDS = 8  # subtitles are joined into lines of about this long, each with its time
RESULT_CHARS = STORY_CHARS + EARLIER_CHARS + 2000  # (the agent's cap for this tool's text)
NO_SPOILERS = (
    "Answer only from these subtitles{earlier} and what is on screen now (below), never from what you know of it, "
    "and say nothing about what comes after {at}."
)


class Text(str):
    """A tool result with a picture of the screen (a data: URL, or None): the agent has the model
    look at it and adds what it shows."""

    image = None


# ------------------------------------------------------------------ subtitles
_TIME = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})")
_TAG = re.compile(r"<[^>]*>|\{\\[^}]*\}")  # <i>, <c.colour>, <00:00:01.300>, {\an8}


def _secs(m):
    h, mi, s, ms = m.groups()
    return round(int(h or 0) * 3600 + int(mi) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000, 3)


def parse(text):
    """Cues of a WebVTT or SRT file: [(start, end, text)], in order, each spoken line once.
    YouTube's automatic captions repeat the line before in each cue and grow word by word: kept
    as one line, from when it began."""
    raw = []  # [(start, end, [lines])]
    rows = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    cur = None
    for n, row in enumerate(rows):
        if "-->" in row:
            a, _, b = row.partition("-->")
            ma, mb = _TIME.search(a), _TIME.search(b)
            cur = (_secs(ma), _secs(mb), []) if ma and mb else None
            if cur:
                raw.append(cur)
        elif row == "":  # (a line of spaces is part of a YouTube cue)
            cur = None
        elif cur is not None and row.strip() and not (row.strip().isdigit() and n + 1 < len(rows) and "-->" in rows[n + 1]):
            cur[2].append(row)
    cues = []
    for start, end, body in raw:
        for line in body:
            line = re.sub(r"\s+", " ", _TAG.sub("", line)).strip()
            line = line.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&nbsp;", " ")
            if not line or any(line == c[2] for c in cues[-4:]):  # the line before, repeated
                continue
            if cues and line.startswith(cues[-1][2]):  # the same line, a word longer
                cues[-1] = (cues[-1][0], max(end, cues[-1][1]), line)
            elif not (cues and cues[-1][2].startswith(line)):
                cues.append((start, end, line))
    cues.sort(key=lambda c: c[0])
    return cues


def clock(s):
    s = int(max(0, s))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def lines(cues, start=0.0, until=None):
    """The cues from start to until as lines of about LINE_SECONDS, each with its time:
    ["[12:04] text text", ...]."""
    out, cur, began = [], [], None
    for s, _, t in cues:
        if s < start or (until is not None and s > until):
            continue
        if cur and s - began >= LINE_SECONDS:
            out.append(f"[{clock(began)}] {' '.join(cur)}")
            cur = []
        if not cur:
            began = s
        cur.append(t)
    if cur:
        out.append(f"[{clock(began)}] {' '.join(cur)}")
    return out


def since(cues, until, limit, step=600):
    """Lines of the cues up to until that fit in limit characters: from the start, else from the
    latest whole 10 minutes they fit from (so the start stays put from one question to the next
    and the model server's prompt cache keeps the text)."""
    start = 0.0
    while True:
        rows = lines(cues, start, until)
        if start >= until or sum(len(r) + 1 for r in rows) <= limit:
            return rows, start
        start += step


def last_chars(rows, limit):
    """The most recent rows that fit in limit characters (and whether some were left out)."""
    kept, n = [], 0
    for row in reversed(rows):
        n += len(row) + 1
        if n > limit:
            return kept[::-1], True
        kept.append(row)
    return kept[::-1], False


def matching(rows, query, limit):
    """Rows near the ones sharing words with query, when all of them don't fit."""
    words = {w[:5] for w in re.findall(r"[a-z']{3,}", (query or "").lower())}
    score = [len(words & {w[:5] for w in re.findall(r"[a-z']{3,}", r.lower())}) for r in rows]
    picked = set()
    for i in sorted(range(len(rows)), key=lambda i: -score[i]):
        if not score[i]:
            break
        picked.update(range(max(0, i - 3), min(len(rows), i + 4)))
        if sum(len(rows[j]) + 1 for j in picked) > limit:
            break
    return [rows[i] for i in sorted(picked)]


# ------------------------------------------------------------------ what's playing
class Playing:
    """What plays: app ("Jellyfin", "YouTube"), title, position, duration, paused; cues() its
    subtitles ([] when it has none), earlier() what came before (episodes already watched),
    chapters() [(start, title)]."""

    app = title = ""
    position = duration = 0.0
    paused = False

    def cues(self):
        return []

    def earlier(self):
        return ""

    def chapters(self):
        return []

    def head(self):
        return f"{self.app}: {self.title}."

    def where(self):
        return f"Now: {'paused' if self.paused else 'playing'} at {clock(self.position)} of {clock(self.duration)}."


_cache = {}  # subtitles fetched this session, by item: a question after another doesn't fetch again


def cached(key, fetch):
    if key not in _cache:
        if len(_cache) > 8:
            _cache.pop(next(iter(_cache)))
        _cache[key] = fetch()
    return _cache[key]


def http_get(url, headers=None, timeout=20):
    import requests

    r = requests.get(url, headers=headers or {}, timeout=(5, timeout))
    r.raise_for_status()
    return r


# ---- Jellyfin
JF_AUTH_JS = """() => {
  const a = window.ApiClient;
  if (!a || !a.getCurrentUserId || !a.getCurrentUserId() || !a.accessToken()) return null;
  return {server: a.serverAddress(), token: a.accessToken(), user: a.getCurrentUserId(), device: a.deviceId()};
}"""


def jellyfin_auth():
    """The TV's own Jellyfin sign-in, read from the Jellyfin app (Desktop, else the web app)."""
    import urllib.parse

    host = urllib.parse.urlsplit(settings.get("media.jellyfin.url") or "").netloc
    pages = cdp.pages(cdp.JELLYFIN_PORT) + [p for p in cdp.pages(cdp.WEB_PORT) if host and host in p.get("url", "")]
    for p in pages:
        try:
            got = cdp.call(p, JF_AUTH_JS, timeout=5)
        except Exception:  # noqa: BLE001 - a page that's loading, or not Jellyfin's
            continue
        if isinstance(got, dict) and got.get("token"):
            return got
    return None


def mpv_get(prop):
    """A property of Jellyfin Desktop's player (its socket), or None when it isn't playing."""
    from couchbox import playback

    try:
        sock = f"/run/user/{pwd.getpwnam(TV_USER).pw_uid}/mpv-jellyfin.sock"
        if not os.path.exists(sock):
            return None
        m = playback.MpvSocket(sock, timeout=2)
    except (KeyError, OSError):
        return None
    try:
        return m.get(prop)
    except (OSError, ValueError):
        return None
    finally:
        m.close()


def mpv_position():
    """Jellyfin Desktop's player's position to the second (its session reports every few)."""
    return mpv_get("time-pos")


def pick_subtitles(streams, chosen=None):
    """The subtitle stream to read: the one showing if it's text, else English (not just the
    forced lines), else any text one. None when there are only pictures (PGS) or none."""
    text = [s for s in streams if s.get("Type") == "Subtitle" and s.get("IsTextSubtitleStream")]
    showing = next((s for s in text if s.get("Index") == chosen), None)
    if showing and not showing.get("IsForced"):
        return showing
    english = [s for s in text if (s.get("Language") or "").lower() in ("eng", "en", "en-us", "en-gb")]
    full = [s for s in english if not s.get("IsForced")] or english
    return (full or [s for s in text if not s.get("IsForced")] or text or [None])[0]


class JellyfinPlaying(Playing):
    app = "Jellyfin"

    def __init__(self, api, item, play_state, position=None):
        self.api, self.item = api, item
        i = item
        ep = f"{i.get('SeriesName')} S{i.get('ParentIndexNumber')}E{i.get('IndexNumber')} " if i.get("Type") == "Episode" else ""
        self.title = f"“{ep}{i.get('Name', '')}”".replace("“ ", "“")
        self.duration = (i.get("RunTimeTicks") or 0) / 1e7
        reported = (play_state.get("PositionTicks") or 0) / 1e7
        self.position = float(position) if position is not None else reported
        self.paused = bool(play_state.get("IsPaused"))
        self.chosen = play_state.get("SubtitleStreamIndex")
        self.source = play_state.get("MediaSourceId") or i.get("Id")

    def cues(self):
        return cached(("jellyfin", self.item["Id"]), self._cues)

    def _cues(self):
        full = self.api.get(f"/Users/{self.api.user}/Items/{self.item['Id']}", {"fields": "MediaSources,MediaStreams"})
        sources = full.get("MediaSources") or [{"Id": self.item["Id"], "MediaStreams": full.get("MediaStreams") or []}]
        src = next((s for s in sources if s.get("Id") == self.source), sources[0])
        sub = pick_subtitles(src.get("MediaStreams") or [], self.chosen)
        if not sub:
            return []
        path = f"/Videos/{self.item['Id']}/{src['Id']}/Subtitles/{sub['Index']}/0/Stream.srt"
        return parse(self.api.text(path))

    def earlier(self):
        i = self.item
        if i.get("Type") != "Episode" or not i.get("SeriesId"):
            return ""
        eps = self.api.get(f"/Shows/{i['SeriesId']}/Episodes", {"userId": self.api.user, "fields": "Overview"}).get("Items") or []
        at = next((n for n, e in enumerate(eps) if e.get("Id") == i.get("Id")), len(eps))
        rows = [
            f"S{e.get('ParentIndexNumber')}E{e.get('IndexNumber')} {e.get('Name', '')}: {re.sub(r'\s+', ' ', e.get('Overview') or '').strip()}"
            for e in eps[:at]
            if (e.get("UserData") or {}).get("Played") and e.get("Overview")
        ]
        return "\n".join(last_chars(rows, EARLIER_CHARS)[0])

    def chapters(self):
        named = [c for c in self.item.get("Chapters") or [] if c.get("Name") and not re.fullmatch(r"(Chapter|Kapitel)\s*\d+", c["Name"])]
        return [((c.get("StartPositionTicks") or 0) / 1e7, c["Name"]) for c in named]


class JellyfinApi:
    def __init__(self, auth):
        import requests

        self.server, self.user, self.device = auth["server"].rstrip("/"), auth["user"], auth.get("device")
        self.s = requests.Session()
        self.s.headers["Authorization"] = f'MediaBrowser Token="{auth["token"]}"'

    def get(self, path, params=None):
        r = self.s.get(self.server + path, params=params, timeout=(5, 20))
        r.raise_for_status()
        return r.json()

    def text(self, path):
        r = self.s.get(self.server + path, timeout=(5, 60))  # an embedded track is pulled out of the file first
        r.raise_for_status()
        r.encoding = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else "utf-8"
        return r.text


def jellyfin_playing():
    auth = jellyfin_auth()
    if not auth:
        return None
    api = JellyfinApi(auth)
    sessions = api.get("/Sessions", {"deviceId": auth["device"]} if auth.get("device") else {"controllableByUserId": api.user})
    s = next((s for s in sessions if s.get("NowPlayingItem")), None)
    if not s:
        return None
    return JellyfinPlaying(api, s["NowPlayingItem"], s.get("PlayState") or {}, mpv_position())


_warming = set()


def warm():
    """Called every few seconds by the voice service: the subtitles of an episode or film that
    starts in Jellyfin are fetched in the background, so the first question about it doesn't
    wait while Jellyfin pulls them out of the file (half a minute for a film)."""
    import threading

    m = re.search(r"/videos/([0-9a-f]{32})", str(mpv_get("path") or ""), re.I)
    if not m or ("jellyfin", m.group(1)) in _cache or m.group(1) in _warming:
        return None
    _warming.add(m.group(1))

    def fetch():
        try:
            p = jellyfin_playing()
            if p:
                p.cues()
        except Exception:  # noqa: BLE001 - asked for again with the first question
            _warming.discard(m.group(1))

    threading.Thread(target=fetch, daemon=True).start()
    return m.group(1)


# ---- YouTube
YT_NOW_JS = r"""() => {
  const p = document.querySelector(".html5-video-player"), v = document.querySelector("video");
  if (!p || !p.getVideoData || !v || !v.duration) return null;
  const d = p.getVideoData();
  return {id: d.video_id, title: d.title, channel: d.author, position: v.currentTime, duration: v.duration, paused: v.paused,
          live: !!(d.isLive || (p.getVideoStats && p.getVideoStats().live))};
}"""


class YouTubePlaying(Playing):
    app = "YouTube"

    def __init__(self, vid, title, position, duration, paused, channel="", native=False):
        self.vid, self.native = vid, native
        self.title = f"“{title or 'a video'}”" + (f" by {channel}" if channel else "")
        self.position, self.duration, self.paused = float(position or 0), float(duration or 0), bool(paused)
        self._chapters = []

    def info(self):
        """{captions: [{url, lang, auto...}], chapters: [{start, title}]}: from Couchbox's app
        when it runs (it has them already), else from yt-dlp."""
        return cached(("youtube", self.vid), self._info)

    def _info(self):
        from couchbox.services import ytstream

        if self.native:
            try:
                got = ytnative.call("stream", id=self.vid)
                if got.get("captions") is not None and "error" not in got:
                    return {"captions": got.get("captions") or [], "chapters": got.get("chapters") or []}
            except (appctl.NotRunning, OSError, ValueError, RuntimeError):
                pass
        info = ytstream.extract(self.vid)
        return {"captions": ytstream.captions(info), "chapters": ytstream.chapters(info)}

    def cues(self):
        return cached(("youtube-cues", self.vid), self._cues)

    def _cues(self):
        for c in (self.info().get("captions") or [])[:3]:  # the video's own first, English first
            try:
                got = parse(http_get(c["url"]).text)
            except Exception:  # noqa: BLE001 - YouTube said 429, or the address went stale
                continue
            if got:
                return got
        return []

    def chapters(self):
        return [(float(c.get("start") or 0), c.get("title") or "") for c in self.info().get("chapters") or []]


def youtube_playing(native):
    if native:
        st = ytnative.state()
        if st.get("page") != "player" or not st.get("videoId") or st.get("live"):
            return None
        return YouTubePlaying(st["videoId"], st.get("title"), st.get("position"), st.get("duration"), st.get("paused"), native=True)
    for p in cdp.pages(cdp.YOUTUBE_PORT):
        try:
            got = cdp.call(p, YT_NOW_JS, timeout=4)
        except Exception:  # noqa: BLE001
            continue
        if got and got.get("id") and not got.get("live"):
            return YouTubePlaying(
                got["id"], got.get("title"), got.get("position"), got.get("duration"), got.get("paused"), got.get("channel")
            )
    return None


def playing():
    """What plays now, the app in front first; None when nothing readable plays."""
    from . import tools

    a = tools.app_of_window(tools.active_window())
    front = getattr(a, "id", None)
    native = tools.yt_native() and ytnative.running()
    order = ["youtube", "jellyfin"] if front != "jellyfin" else ["jellyfin", "youtube"]
    for app in order:
        try:
            if app == "jellyfin":
                p = jellyfin_playing() if settings.get("media.jellyfin.url") else None
            else:  # Couchbox's app, else VacuumTube (the tile's fallback, or opened some other way)
                p = (native and youtube_playing(True)) or youtube_playing(False)
        except Exception:  # noqa: BLE001 - one app not answering doesn't hide the other
            p = None
        if p:
            return p
    return None


# ------------------------------------------------------------------ the screen
def screen_picture(width=1024):
    """A picture of the TV screen as a data: URL (JPEG), or None."""
    try:
        uid = pwd.getpwnam(TV_USER).pw_uid
    except KeyError:
        return None
    path = f"/run/user/{uid}/couchbox-voice-screen.jpg"  # written as the TV user (KWin answers it)
    try:
        subprocess.run([SCREENSHOT, "--width", str(width), path], capture_output=True, timeout=15, check=True)
        with open(path, "rb") as f:
            data = f.read()
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    return "data:image/jpeg;base64," + base64.b64encode(data).decode() if data else None


# ------------------------------------------------------------------ the tool
def run(action, minutes=None, query=None, picture=screen_picture):
    """The tool. What changes from one question to the next (the position, the picture) comes
    last, after the subtitles: the model server's prompt cache keeps the rest."""
    t0 = time.monotonic()
    p = playing()
    if not p:
        return "Nothing is playing that I can read along with: this works with Jellyfin and YouTube videos (not live streams)."
    head = p.head()
    try:
        cues = p.cues()
    except Exception as err:  # noqa: BLE001
        cues, head = [], head + f" (Its subtitles couldn't be read: {err}.)"
    at = clock(p.position)

    if action == "find":
        if not cues:
            return f"{head} It has no subtitles to search, so I can't find moments in it."
        rows = lines(cues)
        if sum(len(r) + 1 for r in rows) > FIND_CHARS:
            rows = matching(rows, query, FIND_CHARS)
        out = [
            head,
            f"Find the moment: {query or 'the one asked for'}. Below are its subtitles, whole, with times; look for the lines where"
            " that happens (what is said then, or just before or after).",
        ] + rows
        chapters = p.chapters()
        if chapters:
            out.append("Chapters: " + "; ".join(f"[{clock(s)}] {t}" for s, t in chapters))
        out += [
            p.where(),
            f"Find: {query or 'the moment asked for'}. Jump to the line that best fits: media seek to its time in seconds, minus 3."
            " Then reply only with where you jumped and the words said there, e.g. 'Jumped to 23:10 (\u201cOh, that's good\u201d).'"
            " If nothing fits, say so and don't jump.",
        ]
        return Text("\n".join(out))

    if action == "recent":
        mins = float(minutes or RECENT_MINUTES)
        rows = lines(cues, p.position - mins * 60, p.position)
        body = [head, f"Subtitles of the last {mins:g} minutes:"] + (rows or ["(nobody spoke)" if cues else "(no subtitles)"])
        body += [
            p.where(),
            NO_SPOILERS.format(earlier="", at=at)
            + " Tell what happened in the third person (never 'you'), in three short lines, each on a line of its own,"
            " most recent last.",
        ]
    else:  # story
        body = [head]
        earlier = p.earlier()
        if earlier:
            body += ["The episodes already watched were about:", earlier]
        before = [f"[{clock(s)}] {t}" for s, t in p.chapters() if s <= p.position]
        if before:
            body.append("Chapters so far: " + "; ".join(before))
        if cues:
            rows, start = since(cues, p.position, STORY_CHARS)
            body.append(f"Its subtitles from {clock(start)}, with times:" if start else "Its subtitles from the start, with times:")
            body += rows or ["(nobody has spoken yet)"]
        else:
            body.append("It has no subtitles to read: go by the picture, or say you can't tell.")
        body += [
            p.where() + " The subtitles above go up to now.",
            NO_SPOILERS.format(earlier=", the episodes already watched" if earlier else "", at=at)
            + " 'This guy', 'she', 'them' mean who is on screen now: start from that, and if nobody like that is on screen,"
            " say who is. Name people as the subtitles do (labels like 'Scott:' show who speaks; people"
            " call each other by name), not from how they look or what you know of it, and say how they fit in so far; when"
            " it isn't clear who is on screen, give your best guess from who is speaking, with 'probably'."
            " At most three short lines.",
        ]
    out = Text("\n".join(body))
    out.image = picture() if picture else None
    out.took = round(time.monotonic() - t0, 1)
    return out
