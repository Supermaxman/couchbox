"""Playable streams for the YouTube app (couchbox-yt), through yt-dlp used as a library.

YouTube changes how its players get their stream addresses every few weeks (the signature and
"n" challenges in its player JavaScript, which clients work without proof-of-origin tokens), and
yt-dlp follows those changes within days. So rather than our own copy of that, this asks yt-dlp
for a video's formats and picks one the Pi plays well:

  * H.264 (avc1) up to 1080p60, as VacuumTube's "h264ify" did: the Pi 5 has no decoder for VP9 or
    AV1, and H.264 in software is far cheaper. AAC audio, stereo first (no Opus: webm is off too).
  * adaptive video and audio are separate addresses: mpv gets them joined into one EDL "file"
    (edl://...;!new_stream;...), which it opens as one video with both tracks.
  * live streams: the HLS playlists of that video and of the sound (an external audio track).
  * formats that play right away first: some clients' addresses only open once the ads that would
    have come first are over (yt-dlp's "available_at"); the visionOS client's HLS doesn't wait.

Where yt-dlp comes from, newest first: $COUCHBOX_YTDLP, /opt/couchbox/yt-dlp/yt-dlp (the official
release, a zip Python imports; couchbox-yt-dlp keeps it current), then any yt_dlp module Python
already has (Ubuntu's python3-yt-dlp, often months old). Since late 2025 yt-dlp needs a JavaScript
runtime for YouTube's challenges (its "EJS" scripts, bundled in the release zip): deno, node, bun
or QuickJS, found on the PATH or in /opt/couchbox. Without one yt-dlp still plays through a
client that needs no JavaScript (visionOS: HLS only), so videos start, with fewer formats.

Proof-of-origin (PO) tokens: when YouTube says "Sign in to confirm you're not a bot", the web
clients still play if they bring a PO token. The bgutil provider makes them (BotGuard, run by
node): its yt-dlp plugin (bgutil-ytdlp-pot-provider.zip, on sys.path) asks the provider's HTTP
server (couchbox-yt-pot.service, 127.0.0.1:4416; the app starts it), else runs the provider's
script itself (slower: a node process per token). couchbox-yt-dlp installs both, pinned. Without
them yt-dlp works as before. A bot check is retried once with clients that use PO tokens
(RETRY_CLIENTS); each video's client and whether it carried a PO token are logged (never the token).
"""

import os
import shutil
import subprocess
import sys
import threading
import time
from typing import Any

YTDLP_ZIP = "/opt/couchbox/yt-dlp/yt-dlp"
POT_PLUGIN = "/opt/couchbox/yt-dlp/bgutil-ytdlp-pot-provider.zip"  # couchbox-yt-dlp
POT_SERVER_HOME = "/opt/couchbox/yt-dlp/bgutil/server"
POT_URL = "http://127.0.0.1:4416"
# after a bot check: clients whose streams carry a PO token from the provider, then the TV's
RETRY_CLIENTS = ["mweb", "tv"]
# JavaScript runtimes yt-dlp can use, in yt-dlp's order of preference: (yt-dlp's name, programs)
RUNTIMES = (
    ("deno", ("/opt/couchbox/deno/deno", "deno")),
    ("node", ("/opt/couchbox/node/bin/node", "node", "nodejs")),
    ("bun", ("/opt/couchbox/bun/bun", "bun")),
    ("quickjs", ("qjs",)),
)
MAX_HEIGHT = 1080
_lock = threading.Lock()  # one extraction at a time: a YoutubeDL isn't made for threads
_ydl = None
_ydl_retry = None
_module = None


class Unavailable(RuntimeError):
    """The video can't be played (private, removed, members only, yt-dlp missing...)."""


# ------------------------------------------------------------------ yt-dlp
def module():
    """The yt_dlp module (imported once), or None when there isn't one."""
    global _module
    if _module is not None:
        return _module or None
    for path in (os.environ.get("COUCHBOX_YTDLP"), YTDLP_ZIP):
        if path and os.path.exists(path) and path not in sys.path:
            sys.path.insert(0, path)
            break
    plugin = os.environ.get("COUCHBOX_YT_POT_PLUGIN", POT_PLUGIN)
    if os.path.exists(plugin) and plugin not in sys.path:  # yt-dlp finds yt_dlp_plugins on sys.path
        sys.path.insert(0, plugin)
    try:
        import yt_dlp

        _module = yt_dlp
    except ImportError:
        _module = False
    return _module or None


def js_runtimes() -> dict[str, dict[str, str]]:
    """{runtime: {"path": ...}} for each JavaScript runtime this box has, for yt-dlp."""
    found = {}
    for name, programs in RUNTIMES:
        for p in programs:
            path = (p if os.access(p, os.X_OK) else None) if os.path.isabs(p) else shutil.which(p)
            if path:
                found[name] = {"path": path}
                break
    return found


def about() -> dict[str, Any]:
    """What plays the videos, for the Settings page and the report: yt-dlp's version and where it
    came from, and the JavaScript runtime."""
    m = module()
    rts = js_runtimes()
    js = ""
    for name, cfg in rts.items():
        try:
            out = subprocess.run([cfg["path"], "--version"], capture_output=True, text=True, timeout=5).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            out = ""
        js = f"{name} {out.splitlines()[0] if out else ''}".strip()
        break
    return {
        "ytdlp": m.version.__version__ if m else "",
        "ytdlpPath": os.path.dirname(os.path.dirname(m.__file__)) if m else "",
        "js": js,
        "pot": {"http": "bgutil HTTP server (running)", "script": "bgutil script (the HTTP server isn't running)", "none": "none"}[
            pot_mode()
        ],
    }


def pot_mode(timeout: float = 0.3) -> str:
    """Where PO tokens come from: "http" (the provider's server answers), "script" (the plugin can
    run the provider itself) or "none"."""
    if not os.path.exists(os.environ.get("COUCHBOX_YT_POT_PLUGIN", POT_PLUGIN)):
        return "none"
    import urllib.request

    try:
        with urllib.request.urlopen(f"{POT_URL}/ping", timeout=timeout) as r:  # noqa: S310 (localhost)
            if r.status == 200:
                return "http"
    except OSError:
        pass
    home = os.environ.get("COUCHBOX_YT_POT_HOME", POT_SERVER_HOME)
    return "script" if os.path.exists(os.path.join(home, "build", "generate_once.js")) and "node" in js_runtimes() else "none"


def _options(clients: list[str] | None = None) -> dict[str, Any]:
    args: dict[str, Any] = {
        "youtube": {"skip": ["translated_subs"]},
        # the provider's plugin: its server first, else its script (both from couchbox-yt-dlp)
        "youtubepot-bgutilhttp": {"base_url": [POT_URL]},
        "youtubepot-bgutilscript": {"server_home": [os.environ.get("COUCHBOX_YT_POT_HOME", POT_SERVER_HOME)]},
    }
    if clients:
        args["youtube"]["player_client"] = clients
    return {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "js_runtimes": js_runtimes(),
        "extractor_args": args,
    }


def _downloader(retry: bool = False):
    """A YoutubeDL kept for the app's life (its caches: the player's JavaScript, PO tokens): the
    usual one, or the one for a retry after a bot check (RETRY_CLIENTS)."""
    global _ydl, _ydl_retry
    m = module()
    if not m:
        raise Unavailable("YouTube needs yt-dlp: run  sudo couchbox-yt-dlp  on the box.")
    if retry:
        if _ydl_retry is None:
            _ydl_retry = m.YoutubeDL(_options(RETRY_CLIENTS))
        return _ydl_retry
    if _ydl is None:
        _ydl = m.YoutubeDL(_options())
    return _ydl


def is_bot_check(msg: str) -> bool:
    return "not a bot" in msg.lower()


def extract(video_id: str) -> dict[str, Any]:
    """yt-dlp's information about a video (formats not chosen yet). A bot check is tried once
    more with the clients that bring PO tokens; then the TV says so in plain words."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    with _lock:
        try:
            info = _downloader().extract_info(url, download=False, process=False)
            info["_couchbox_retry"] = False
            return info
        except Exception as err:  # yt-dlp's DownloadError, ExtractorError, ...
            if not is_bot_check(str(err)):
                raise Unavailable(friendly(str(err))) from err
            print(f"yt {video_id}: bot check; trying again with {', '.join(RETRY_CLIENTS)} (PO tokens: {pot_mode()})", flush=True)
        try:
            info = _downloader(retry=True).extract_info(url, download=False, process=False)
            info["_couchbox_retry"] = True
            return info
        except Exception as err:
            raise Unavailable(friendly(str(err))) from err


def served_by(*urls: str) -> dict[str, Any]:
    """Which YouTube client a stream's addresses came from (their c=...), and whether they carry
    a PO token (pot=...): for the log; the token itself is never kept."""
    from urllib.parse import parse_qs, urlparse

    clients, pot = [], False
    for u in urls:
        parts = urlparse(u)
        q = parse_qs(parts.query)
        path = parts.path.split("/")  # HLS addresses keep their parameters in the path: .../c/IOS/...
        for k in ("c", "pot"):
            if k not in q and k in path[:-1]:
                q[k] = [path[path.index(k) + 1]]
        c = (q.get("c") or [""])[0]
        if c and c not in clients:
            clients.append(c)
        pot = pot or bool(q.get("pot"))
    if not clients and any("/api/manifest/" in u for u in urls):
        clients = ["HLS"]  # an HLS manifest's addresses don't name their client (visionOS's, mostly)
    return {"client": "+".join(clients) or "?", "pot": pot}


# yt-dlp's errors as the TV says them (the first that matches)
FRIENDLY = (
    ("not a bot", "YouTube wants this TV to prove it isn't a bot right now. Try again in a few minutes."),
    ("Private video", "This video is private."),
    ("members-only", "This video is for the channel's members."),
    ("confirm your age", "This video is age-restricted."),
    ("not available in your country", "This video isn't available here."),
    ("Video unavailable", "This video isn't available."),
    ("live event will begin", "This live stream hasn't started yet."),
)


def friendly(msg: str) -> str:
    """What yt-dlp said, for the TV: a known reason in plain words, else its first line."""
    for needle, said in FRIENDLY:
        if needle.lower() in msg.lower():
            return said
    msg = msg.replace("ERROR: ", "")
    msg = msg.split("] ", 1)[-1] if msg.startswith("[") else msg
    return msg.split("\n")[0].split(" Use --cookies")[0][:200]


# ------------------------------------------------------------------ choosing formats
def _is_h264(f):
    return (f.get("vcodec") or "").startswith(("avc1", "h264"))


def _video_only(f):
    return (f.get("vcodec") or "none") != "none" and (f.get("acodec") or "none") == "none"


def _lines(f):
    h, w = f.get("height") or 0, f.get("width") or 0
    return min(h, w) if h and w else h


def _hls(f):
    return (f.get("protocol") or "").startswith("m3u8")


def ready(f: dict[str, Any], now: float | None = None) -> bool:
    """Whether YouTube serves this format now. Some clients' addresses only open once the ads that
    would have played first are over (yt-dlp's "available_at"; until then they answer 403)."""
    return (f.get("available_at") or 0) <= (time.time() if now is None else now) + 1


def pick(
    formats: list[dict[str, Any]], h264: bool = True, max_height: int = MAX_HEIGHT, now: float | None = None
) -> tuple[dict | None, dict | None]:
    """(video, audio) formats to play: the best video at max_height or less (H.264 only when
    there is H.264 and h264 is on), and when it has no sound of its own, the best stereo AAC.
    Formats that play now come first (rather than wait out ads that aren't shown), then quality,
    then plain downloads (DASH, "https") before HLS: they start faster and seek better."""
    formats = [f for f in formats if f.get("url") and (f.get("protocol") or "https") in ("https", "http", "m3u8", "m3u8_native")]
    # the short side counts: a Short's 1080x1920 is "1080p"
    videos = [f for f in formats if (f.get("vcodec") or "none") != "none" and _lines(f) <= max_height]
    if h264 and any(_is_h264(f) for f in videos):
        videos = [f for f in videos if _is_h264(f)]
    if not videos:
        return None, None

    def vkey(f):
        return (ready(f, now), _lines(f), f.get("fps") or 0, not _hls(f), (f.get("acodec") or "none") != "none", f.get("tbr") or 0)

    video = max(videos, key=vkey)
    if not _video_only(video):
        return video, None
    # sound only (an HLS rendition's codec is unknown: None, unlike "none")
    audios = [f for f in formats if f.get("vcodec") == "none" and f.get("acodec") != "none"]
    if not audios:
        return video, None
    same = [f for f in audios if _hls(f) == _hls(video)]
    audios = same or audios

    def akey(f):
        codec = f.get("acodec") or ""
        return (
            ready(f, now),
            codec.startswith("mp4a") or (_hls(f) and not codec),  # HLS audio renditions don't say (AAC)
            0 < (f.get("audio_channels") or 2) <= 2,
            "drc" not in (f.get("format_id") or ""),  # dynamic range compressed: the quiet copy
            (f.get("language_preference") or 0) >= 0,  # not a dubbed track
            "high" in (f.get("format_note") or "").lower(),  # HLS: "Default, high" over "Default, low"
            f.get("abr") or f.get("tbr") or 0,
        )

    return video, max(audios, key=akey)


def edl(*urls: str) -> str:
    """One mpv "file" from separate streams: edl://%len%url;!new_stream;%len%url."""
    parts = []
    for i, u in enumerate(urls):
        if i:
            parts.append("!new_stream")
        parts.append(f"%{len(u.encode())}%{u}")
    return "edl://" + ";".join(parts)


def playable(info: dict[str, Any], h264: bool = True, max_height: int = MAX_HEIGHT) -> dict[str, Any]:
    """What MpvVideo plays for yt-dlp's information: {url, opts, live, width, height, ...}."""
    formats = info.get("formats") or []
    live = info.get("live_status") in ("is_live", "post_live") or bool(info.get("is_live"))
    video, audio = pick(formats, h264, max_height)
    if video is None:
        raise Unavailable("YouTube didn't offer a format this TV can play.")
    out = {
        "live": live,
        "width": video.get("width") or 0,
        "height": video.get("height") or 0,
        "fps": video.get("fps") or 0,
        "vcodec": (video.get("vcodec") or "").split(".")[0],
        "acodec": ((audio or video).get("acodec") or "").split(".")[0],
        "opts": "",
    }
    if audio and live:
        # a live stream's video and sound playlists: the sound as an external track (an EDL is a
        # finite timeline; the master playlist made mpv open every variant first, ~20 s)
        out["url"] = video["url"]
        out["opts"] = f"audio-file=%{len(audio['url'].encode())}%{audio['url']}"
    elif audio:
        out["url"] = edl(video["url"], audio["url"])
    else:
        out["url"] = video["url"]
    # nothing that plays now: wait until it does (the player says so meanwhile)
    out["wait"] = max(0, round(max((f.get("available_at") or 0) for f in (video, audio) if f) - time.time()))
    return out


def chapters(info: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"start": float(c.get("start_time") or 0), "title": c.get("title") or ""} for c in info.get("chapters") or [] if c.get("title")]


def captions(info: dict[str, Any], want: tuple[str, ...] = ("en",)) -> list[dict[str, Any]]:
    """Captions to offer: the video's own (its languages, the wanted ones first), then YouTube's
    automatic ones in the wanted languages: [{lang, name, url, auto}] (WebVTT, which mpv reads)."""
    out = []

    def add(subs, auto):
        for lang, tracks in (subs or {}).items():
            if auto and lang.split("-")[0] not in want:
                continue
            vtt = next((t for t in tracks if t.get("ext") == "vtt" and t.get("url")), None)
            if vtt and lang != "live_chat":
                name = vtt.get("name") or lang
                out.append(
                    {
                        "lang": lang,
                        "name": f"{name} (auto-generated)" if auto and "auto" not in name.lower() else name,
                        "url": vtt["url"],
                        "auto": auto,
                    }
                )

    add(info.get("subtitles"), False)
    add(info.get("automatic_captions"), True)
    out.sort(key=lambda c: (c["auto"], c["lang"].split("-")[0] not in want, c["lang"]))
    return out[:12]


def heights(formats: list[dict[str, Any]], h264: bool = True) -> list[int]:
    """The qualities to offer (the short side, as YouTube names them: 1080, 720...)."""
    vids = [f for f in formats if (f.get("vcodec") or "none") != "none" and f.get("url")]
    if h264 and any(_is_h264(f) for f in vids):
        vids = [f for f in vids if _is_h264(f)]
    return sorted({_lines(f) for f in vids if _lines(f) >= 144}, reverse=True)


def resolve(video_id: str, h264: bool = True, max_height: int = MAX_HEIGHT) -> dict[str, Any]:
    """Everything the player needs for a video: the stream (playable()) and what yt-dlp knows
    about it (title, channel, chapters, length, portrait for Shorts)."""
    t = time.monotonic()
    info = extract(video_id)
    out = playable(info, h264, max_height)
    video, audio = pick(info.get("formats") or [], h264, max_height)
    by = served_by(*[f.get("url") or "" for f in (video, audio) if f])
    # which client and PO-token path served it (never a token or an address)
    mode = pot_mode() if by["pot"] else "-"
    print(
        f"yt {video_id}: client={by['client']} pot={'yes' if by['pot'] else 'no'} provider={mode}"
        f"{' retry' if info.get('_couchbox_retry') else ''} {out['height']}p {out['vcodec']}",
        flush=True,
    )
    out.update(
        {
            "id": info.get("id") or video_id,
            "title": info.get("title") or "",
            "channel": info.get("channel") or info.get("uploader") or "",
            "channelId": info.get("channel_id") or "",
            "duration": float(info.get("duration") or 0),
            "chapters": chapters(info),
            "views": info.get("view_count") or 0,
            "likes": info.get("like_count") or 0,
            "timestamp": info.get("timestamp") or info.get("release_timestamp") or 0,
            "portrait": bool(out["height"] and out["width"] and out["height"] > out["width"]),
            "captions": captions(info),
            "heights": [h for h in heights(info.get("formats") or [], h264) if h <= MAX_HEIGHT],
            "maxHeight": max_height,
            "took": round(time.monotonic() - t, 2),
            "client": by["client"],
            "pot": by["pot"],
        }
    )
    return out
