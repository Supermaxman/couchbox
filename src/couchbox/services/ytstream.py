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
"""

import os
import shutil
import subprocess
import sys
import threading
import time
from typing import Any

YTDLP_ZIP = "/opt/couchbox/yt-dlp/yt-dlp"
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
_module = None


class Unavailable(RuntimeError):
    """The video can't be played (private, removed, members only, yt-dlp missing...)."""


# ------------------------------------------------------------------ yt-dlp
def add_path() -> None:
    """yt-dlp's release on Python's path (without importing it: its EJS scripts are enough for
    the challenge solver)."""
    for path in (os.environ.get("COUCHBOX_YTDLP"), YTDLP_ZIP):
        if path and os.path.exists(path):
            if path not in sys.path:
                sys.path.insert(0, path)
            return


def module():
    """The yt_dlp module (imported once), or None when there isn't one."""
    global _module
    if _module is not None:
        return _module or None
    add_path()
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
    }


# The quick way, as a TV app asks: the TV and visionOS clients' /player calls only, with the TV's
# visitor data, without the watch webpage, the client configs or the /next call (the app has
# its own) that yt-dlp otherwise fetches first (~1 s of the ~1.3): ~0.2-0.5 s a video. The JS
# challenges are solved in node kept running (ytjs). yt-dlp's usual way is the fallback.
FAST_CLIENTS = ["tv_samsung", "visionos"]
_fast: dict[str, Any] = {}


def _downloader(visitor: str = ""):
    global _ydl
    m = module()
    if not m:
        raise Unavailable("YouTube needs yt-dlp: run  sudo couchbox-yt-dlp  on the box.")
    from couchbox.services import ytjs

    ytjs.register()
    base = {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True, "js_runtimes": js_runtimes()}
    if visitor:
        if visitor not in _fast:
            _fast.clear()
            args = {
                "skip": ["translated_subs"],
                "player_client": FAST_CLIENTS,
                "player_skip": ["webpage", "configs", "initial_data"],
                "visitor_data": [visitor],
            }
            _fast[visitor] = m.YoutubeDL(dict(base, extractor_args={"youtube": args}))
        return _fast[visitor]
    if _ydl is None:
        _ydl = m.YoutubeDL(dict(base, extractor_args={"youtube": {"skip": ["translated_subs"]}}))
    return _ydl


def extract(video_id: str, phases: Any = None, visitor: str = "") -> dict[str, Any]:
    """yt-dlp's information about a video (formats not chosen yet): the quick way with the TV's
    visitor data, else (or when that finds nothing to play) yt-dlp's usual way. phases
    (yttiming.Phases) hears yt-dlp's progress messages: when each step began."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    with _lock:
        if visitor:
            ydl = _downloader(visitor)
            ydl.params["logger"] = phases
            try:
                info = ydl.extract_info(url, download=False, process=False)
                if info.get("formats"):
                    return info
            except Exception:  # noqa: BLE001 - the usual way says why, if it fails too
                pass
            finally:
                ydl.params["logger"] = None
            if phases is not None:
                phases.marks.append((phases.marks[-1][0] if phases.marks else 0, "fallback"))
        ydl = _downloader()
        ydl.params["logger"] = phases
        try:
            return ydl.extract_info(url, download=False, process=False)
        except Exception as err:  # yt-dlp's DownloadError, ExtractorError, ...
            raise Unavailable(friendly(str(err))) from err
        finally:
            ydl.params["logger"] = None


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
    # (unprocessed information has no "protocol" yet: the address says)
    url = f.get("url") or ""
    return (f.get("protocol") or "").startswith("m3u8") or "/hls_" in url or ".m3u8" in url


def ready(f: dict[str, Any], now: float | None = None) -> bool:
    """Whether YouTube serves this format now. Some clients' addresses only open once the ads that
    would have played first are over (yt-dlp's "available_at"; until then they answer 403)."""
    return (f.get("available_at") or 0) <= (time.time() if now is None else now) + 1


def upscaled(f: dict[str, Any]) -> bool:
    """YouTube's "Super resolution" (AI-upscaled) copy of a format."""
    note = (f.get("format_note") or "").lower()
    return "upscaled" in note or "super resolution" in note


def pick(
    formats: list[dict[str, Any]], h264: bool = True, max_height: int = MAX_HEIGHT, now: float | None = None, superres: bool = True
) -> tuple[dict | None, dict | None]:
    """(video, audio) formats to play: the best video at max_height or less (H.264 only when
    there is H.264 and h264 is on), and when it has no sound of its own, the best stereo AAC.
    Formats that play now come first (rather than wait out ads that aren't shown), then quality,
    then plain downloads (DASH, "https") before HLS: they start faster and seek better."""
    formats = [f for f in formats if f.get("url") and (f.get("protocol") or "https") in ("https", "http", "m3u8", "m3u8_native")]
    # the short side counts: a Short's 1080x1920 is "1080p"
    videos = [f for f in formats if (f.get("vcodec") or "none") != "none" and _lines(f) <= max_height and (superres or not upscaled(f))]
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


def playable(
    info: dict[str, Any], h264: bool = True, max_height: int = MAX_HEIGHT, superres: bool = True, lead: float = 0.0
) -> dict[str, Any]:
    """What MpvVideo plays for yt-dlp's information: {url, opts, live, width, height, ...}.
    lead: formats that open within this many seconds count as ready (the caller waits for them:
    "probe" is the address to try meanwhile)."""
    formats = info.get("formats") or []
    live = info.get("live_status") in ("is_live", "post_live") or bool(info.get("is_live"))
    video, audio = pick(formats, h264, max_height, now=time.time() + lead, superres=superres)
    if video is None:
        raise Unavailable("YouTube didn't offer a format this TV can play.")
    out = {
        "protocol": "hls" if _hls(video) else "dash" if audio else "https",
        "itags": [f.get("format_id") for f in (video, audio) if f],
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
    out["wait"] = max(0, round(max((f.get("available_at") or 0) for f in (video, audio) if f) - time.time(), 1))
    if out["wait"]:
        out["probe"] = video["url"]
        out["until"] = max((f.get("available_at") or 0) for f in (video, audio) if f)
    return out


def chapters(info: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"start": float(c.get("start_time") or 0), "title": c.get("title") or ""} for c in info.get("chapters") or [] if c.get("title")]


def captions(info: dict[str, Any], want: tuple[str, ...] = ("en",)) -> list[dict[str, Any]]:
    """Captions to offer, as YouTube's TV app does: the video's own (every language), its
    automatic ones (whatever their language), and when nothing is in a wanted language, one
    translated to it by YouTube ("auto-translated"): [{lang, name, url, auto, translated}]
    (WebVTT, which mpv reads); the video's own first, the wanted languages first among them."""
    out = []

    def vtt_of(tracks):
        return next((t for t in tracks or [] if t.get("ext") == "vtt" and t.get("url")), None)

    def add(lang, vtt, auto, translated=False):
        name = vtt.get("name") or lang
        if auto and not translated and "auto" not in name.lower():
            name = f"{name} (auto-generated)"
        out.append({"lang": lang, "name": name, "url": vtt["url"], "auto": auto, "translated": translated})

    for lang, tracks in (info.get("subtitles") or {}).items():
        vtt = vtt_of(tracks)
        if vtt and lang != "live_chat":
            add(lang, vtt, False)
    autos = info.get("automatic_captions") or {}
    # yt-dlp lists YouTube's automatic captions in every language it translates them to, the
    # spoken one as "xx-orig" (ours, from /player: the spoken one only, marked "orig")
    for lang, tracks in autos.items():
        vtt = vtt_of(tracks)
        if not vtt:
            continue
        orig = lang.endswith("-orig") or vtt.get("orig")
        if orig or lang.split("-")[0] in want:
            spoken = lang.removesuffix("-orig")
            translated = (
                not orig
                and any(k.endswith("-orig") for k in autos)
                and not any(k.removesuffix("-orig").split("-")[0] == lang.split("-")[0] and k.endswith("-orig") for k in autos)
            )
            add(spoken, dict(vtt, name=(vtt.get("name") or spoken) + (" (auto-translated)" if translated else "")), True, translated)
    # nothing in a wanted language: YouTube's translation of a track that offers one (tlang)
    if not any(c["lang"].split("-")[0] in want for c in out):
        src = next((t for t in info.get("_tracks") or [] if t.get("translatable")), None)
        if src:
            name = {"en": "English"}.get(want[0], want[0])
            out.append(
                {
                    "lang": want[0],
                    "name": f"{name} (auto-translated)",
                    "url": src["url"] + "&tlang=" + want[0],
                    "auto": True,
                    "translated": True,
                }
            )
    seen, uniq = set(), []
    for c in out:
        key = (c["lang"], c["auto"], c["translated"])
        if key not in seen:
            seen.add(key)
            uniq.append(c)
    uniq.sort(key=lambda c: (c["auto"], c["lang"].split("-")[0] not in want, c["translated"], c["lang"]))  # the video's own first
    return uniq[:12]


def heights(formats: list[dict[str, Any]], h264: bool = True) -> list[int]:
    """The qualities to offer (the short side, as YouTube names them: 1080, 720...)."""
    vids = [f for f in formats if (f.get("vcodec") or "none") != "none" and f.get("url")]
    if h264 and any(_is_h264(f) for f in vids):
        vids = [f for f in vids if _is_h264(f)]
    return sorted({_lines(f) for f in vids if _lines(f) >= 144}, reverse=True)


def storyboard(formats: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The video's storyboard (the frames the bar shows while seeking): the largest of yt-dlp's
    "storyboard" formats, as {width, height, cols, rows, sheets: [{url, start, end}]} (each sheet
    a grid of cols x rows frames, in order, covering start..end seconds)."""
    best = None
    for f in formats:
        if f.get("format_note") != "storyboard" and not str(f.get("format_id", "")).startswith("sb"):
            continue
        if not f.get("fragments") or not f.get("columns") or not f.get("rows"):
            continue
        if best is None or (f.get("width") or 0) > (best.get("width") or 0):
            best = f
    if best is None:
        return None
    sheets, at = [], 0.0
    for frag in best["fragments"]:
        d = float(frag.get("duration") or 0)
        if not frag.get("url") or d <= 0:
            continue
        sheets.append({"url": frag["url"], "start": at, "end": at + d})
        at += d
    if not sheets:
        return None
    return {
        "width": int(best.get("width") or 0),
        "height": int(best.get("height") or 0),
        "cols": int(best["columns"]),
        "rows": int(best["rows"]),
        "sheets": sheets,
    }


def protocol(url: str) -> str:
    return "hls" if "m3u8" in url or "/hls_" in url else "dash" if url.startswith("edl://") else "https"


def resolve(
    video_id: str,
    h264: bool = True,
    max_height: int = MAX_HEIGHT,
    superres: bool = True,
    info: dict[str, Any] | None = None,
    lead: float = 0.0,
    visitor: str = "",
) -> dict[str, Any]:
    """Everything the player needs for a video: the stream (playable()) and what yt-dlp knows
    about it (title, channel, chapters, length, portrait for Shorts). info: yt-dlp's, from
    before (ytworker's cache); else it's asked for now."""
    from couchbox.services import yttiming

    t = time.monotonic()
    phases = yttiming.Phases()
    if info is None:
        info = extract(video_id, phases, visitor)
    took = yttiming.ms(t)
    out = playable(info, h264, max_height, superres, lead)
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
            "storyboard": storyboard(info.get("formats") or []),
            "heights": [h for h in heights(info.get("formats") or [], h264) if h <= max(max_height, MAX_HEIGHT)],
            "maxHeight": max_height,
            "took": round(time.monotonic() - t, 2),
        }
    )
    spans = phases.spans(took)
    out["timing"] = dict(spans, extract=took, protocol=out["protocol"])
    return out


# ------------------------------------------------------------------ from our own /player call
def _codecs(mime: str) -> tuple[str, str]:
    """(vcodec, acodec) of 'video/mp4; codecs="avc1.4d401f"' (as yt-dlp names them)."""
    import re

    kind = mime.split("/")[0]
    codec = (re.search(r'codecs="([^"]+)"', mime) or [None, ""])[1].split(",")[0].strip()
    return (codec, "none") if kind == "video" else ("none", codec)


def _storyboard_formats(pr: dict[str, Any], duration: float) -> list[dict[str, Any]]:
    """The player response's storyboard spec as yt-dlp's storyboard formats (for storyboard())."""
    spec = (((pr.get("storyboards") or {}).get("playerStoryboardSpecRenderer") or {}).get("spec")) or ""
    parts = spec.split("|")
    if len(parts) < 2:
        return []
    base, out = parts[0], []
    for i, level in enumerate(parts[1:]):
        f = level.split("#")
        if len(f) < 8:
            continue
        w, h, count, cols, rows, interval = (int(x or 0) for x in f[:6])
        name, sigh = f[6], f[7]
        per = cols * rows or 1
        sheets = -(-count // per) if count else 0
        step = interval / 1000 if interval else (duration / count if count else 0)
        url = base.replace("$L", str(i)).replace("$N", name) + f"&sigh={sigh}"
        frags = [{"url": url.replace("$M", str(j)), "duration": step * min(per, count - j * per)} for j in range(sheets)]
        out.append(
            {
                "format_id": f"sb{i}",
                "format_note": "storyboard",
                "width": w,
                "height": h,
                "columns": cols,
                "rows": rows,
                "fragments": frags,
                "url": frags[0]["url"] if frags else "",
                "vcodec": "none",
                "acodec": "none",
            }
        )
    return out


def hls_formats(master: str) -> list[dict[str, Any]]:
    """A live stream's HLS master playlist as yt-dlp's formats: each variant (its resolution, frame
    rate, codecs: with sound of its own or not) and each sound rendition."""
    import re

    def attrs(line: str) -> dict[str, str]:
        return {k: v.strip('"') for k, v in re.findall(r'([A-Z0-9-]+)=("[^"]*"|[^,]*)', line.split(":", 1)[1])}

    out, lines = [], [ln.strip() for ln in master.splitlines()]
    for i, ln in enumerate(lines):
        if ln.startswith("#EXT-X-MEDIA:"):
            a = attrs(ln)
            if a.get("TYPE") == "AUDIO" and a.get("URI"):
                note = ("Default, " if a.get("DEFAULT") == "YES" else "") + (a.get("NAME") or "")
                out.append(
                    {
                        "format_id": f"hls-audio-{a.get('GROUP-ID', '')}",
                        "url": a["URI"],
                        "vcodec": "none",
                        "acodec": "mp4a.40.2",
                        "protocol": "m3u8_native",
                        "format_note": note,
                        "language_preference": 10 if a.get("DEFAULT") == "YES" else -1,
                    }
                )
        elif ln.startswith("#EXT-X-STREAM-INF:") and i + 1 < len(lines) and lines[i + 1].startswith("http"):
            a = attrs(ln)
            codecs = [c.strip() for c in a.get("CODECS", "").split(",") if c.strip()]
            w, _, h = a.get("RESOLUTION", "").partition("x")
            fps = float(a.get("FRAME-RATE") or 0)
            v = next((c for c in codecs if not c.startswith("mp4a")), "none")
            muxed = any(c.startswith("mp4a") for c in codecs) and not a.get("AUDIO")
            out.append(
                {
                    "format_id": f"hls-{h or '?'}p{round(fps) or ''}",
                    "url": lines[i + 1],
                    "vcodec": v,
                    "acodec": next(c for c in codecs if c.startswith("mp4a")) if muxed else "none",
                    "width": int(w) if w.isdigit() else None,
                    "height": int(h) if h.isdigit() else None,
                    "fps": fps or None,
                    "tbr": int(a.get("BANDWIDTH") or 0) / 1000,
                    "protocol": "m3u8_native",
                }
            )
    return out


def _deciphered(raw: list[dict[str, Any]], solve: Any) -> list[dict[str, Any]]:
    """An InnerTube answer's formats as yt-dlp's, each address deciphered (its signature and
    "n", solve(n, sig) -> ({n: answer}, {sig: answer})); those it can't are left out."""
    from urllib.parse import parse_qs, parse_qsl, urlencode, urlparse, urlunparse

    pending = []
    for f in raw:
        if f.get("url"):
            url, s, sp = f["url"], "", ""
        else:
            c = parse_qs(f.get("signatureCipher") or f.get("cipher") or "")
            url, s, sp = (c.get("url") or [""])[0], (c.get("s") or [""])[0], (c.get("sp") or ["signature"])[0]
        if not url:
            continue
        n = (parse_qs(urlparse(url).query).get("n") or [""])[0]
        pending.append((f, url, s, sp, n))
    n_ans, sig_ans = solve([p[4] for p in pending if p[4]], [p[2] for p in pending if p[2]])
    formats = []
    for f, url, s, sp, n in pending:
        u = urlparse(url)
        q = parse_qsl(u.query, keep_blank_values=True)
        if n:
            if n not in n_ans:
                continue
            q = [(k, n_ans[n] if k == "n" else v) for k, v in q]
        if s:
            if s not in sig_ans:
                continue
            q.append((sp, sig_ans[s]))
        vcodec, acodec = _codecs(f.get("mimeType") or "")
        track = f.get("audioTrack") or {}
        formats.append(
            {
                "format_id": f"{f.get('itag')}" + ("-drc" if f.get("isDrc") else ""),
                "url": urlunparse(u._replace(query=urlencode(q))),
                "vcodec": vcodec,
                "acodec": acodec,
                "width": f.get("width"),
                "height": f.get("height"),
                "fps": f.get("fps"),
                "tbr": (f.get("bitrate") or 0) / 1000,
                "abr": (f.get("averageBitrate") or f.get("bitrate") or 0) / 1000 if vcodec == "none" else None,
                "audio_channels": f.get("audioChannels"),
                "format_note": f.get("qualityLabel") or "",
                "language_preference": (10 if track.get("audioIsDefault") else -1) if track else None,
            }
        )
    return formats


def from_player(pr: dict[str, Any], solve: Any, get: Any = None) -> dict[str, Any]:
    """yt-dlp's information, as extract() gives it, from an InnerTube /player response (the TV
    client, signed in: no ads, so DASH opens at once): every format's address deciphered (its
    signature and "n", solve(n, sig) -> ({n: answer}, {sig: answer})). A live stream: its HLS,
    its DASH manifest, or else its adaptive formats through ytlive's server. Unavailable when it
    has nothing to play this way."""
    status = (pr.get("playabilityStatus") or {}).get("status")
    if status != "OK":
        raise Unavailable((pr.get("playabilityStatus") or {}).get("reason") or "YouTube won't play this video here.")
    vd = pr.get("videoDetails") or {}
    sd = pr.get("streamingData") or {}
    raw = (sd.get("adaptiveFormats") or []) + (sd.get("formats") or [])
    if (vd.get("isLive") or not raw) and sd.get("hlsManifestUrl") and get is not None:
        # live: its HLS master playlist, the variants and the sound read from it (no challenges)
        r = get(sd["hlsManifestUrl"], timeout=(8, 20))
        formats = hls_formats(getattr(r, "text", "") or "")
        if not formats:
            raise Unavailable("no live variants: the usual way")
        return {
            "id": vd.get("videoId") or "",
            "title": vd.get("title") or "",
            "channel": vd.get("author") or "",
            "channel_id": vd.get("channelId") or "",
            "duration": 0.0,
            "live_status": "is_live",
            "is_live": True,
            "formats": formats,
            "subtitles": {},
            "automatic_captions": {},
        }
    if vd.get("isLive") and sd.get("dashManifestUrl"):  # live, only as DASH: the manifest, to mpv (ffmpeg reads it)
        return {
            "id": vd.get("videoId") or "",
            "title": vd.get("title") or "",
            "channel": vd.get("author") or "",
            "channel_id": vd.get("channelId") or "",
            "duration": 0.0,
            "live_status": "is_live",
            "is_live": True,
            "formats": [
                {
                    "format_id": "dash-live",
                    "url": sd["dashManifestUrl"],
                    "vcodec": "avc1",
                    "acodec": "mp4a.40.2",
                    "height": 1080,
                    "fps": 30,
                    "protocol": "https",
                }
            ],
            "subtitles": {},
            "automatic_captions": {},
        }
    live_adaptive = bool(vd.get("isLive") and raw and not sd.get("hlsManifestUrl") and not sd.get("dashManifestUrl"))
    if not live_adaptive and (vd.get("isLive") or vd.get("isLiveContent") and sd.get("hlsManifestUrl") or not raw):
        raise Unavailable("not a plain video (live): the usual way")
    formats = _deciphered(raw, solve)
    if live_adaptive:
        # live, its adaptive formats only (the TV's clients signed in): each one's segments,
        # one after another, from ytlive's server on this box (mpv reads them as one MP4)
        from couchbox.services import ytlive

        formats = [f for f in formats if not str(f["format_id"]).endswith("-drc")]
        seconds = next((float(f["targetDurationSec"]) for f in raw if f.get("targetDurationSec")), 5.0)
        local = ytlive.PROXY.group({f["format_id"]: f["url"] for f in formats}, seconds)
        for f in formats:
            f["url"] = local[f["format_id"]]
            f["protocol"] = "http"  # (to 127.0.0.1)
        return {
            "id": vd.get("videoId") or "",
            "title": vd.get("title") or "",
            "channel": vd.get("author") or "",
            "channel_id": vd.get("channelId") or "",
            "duration": 0.0,
            "live_status": "is_live",
            "is_live": True,
            "formats": formats,
            "subtitles": {},
            "automatic_captions": {},
        }
    duration = float(vd.get("lengthSeconds") or 0)
    subs: dict[str, list] = {}
    auto: dict[str, list] = {}
    tracks: list[dict[str, Any]] = []  # every track, for a translation when none is in English
    for t in ((pr.get("captions") or {}).get("playerCaptionsTracklistRenderer") or {}).get("captionTracks") or []:
        lang = t.get("languageCode") or ""
        name = "".join(r.get("text", "") for r in (t.get("name") or {}).get("runs") or []) or (t.get("name") or {}).get("simpleText", "")
        entry = {"ext": "vtt", "url": (t.get("baseUrl") or "") + "&fmt=vtt", "name": name}
        if t.get("kind") == "asr":
            entry["orig"] = True  # (the spoken language's: translations come by tlang)
        (auto if t.get("kind") == "asr" else subs).setdefault(lang, []).append(entry)
        tracks.append({"url": entry["url"], "translatable": bool(t.get("isTranslatable")), "asr": t.get("kind") == "asr"})
    return {
        "id": vd.get("videoId") or "",
        "title": vd.get("title") or "",
        "channel": vd.get("author") or "",
        "channel_id": vd.get("channelId") or "",
        "duration": duration,
        "view_count": int(vd.get("viewCount") or 0),
        "live_status": "not_live",
        "formats": formats + _storyboard_formats(pr, duration),
        "subtitles": subs,
        "automatic_captions": auto,
        "_tracks": tracks,
    }
