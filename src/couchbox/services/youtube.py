"""YouTube for the TV app (couchbox-yt): InnerTube, the API YouTube's own apps use, as YouTube's TV
client (TVHTML5), so pages come back shaped the way YouTube's TV app ("Leanback") draws them:
shelves of tiles, the guide's tabs (Gaming, News, Music...), a watch page's rows of related videos.

    POST https://www.youtube.com/youtubei/v1/<browse | search | next | guide>  {"context": {"client": TV}, ...}
    browse   browseId FEtopics (Home), FEtopics_music / _gaming / _news / _live / _sports / _podcasts /
             _movies (the guide's tabs), UC... (a channel), or a continuation token (more shelves, more tiles)
    search   query -> shelves of results
    next     videoId -> the video's title, channel and views, and the related videos below the player
Search suggestions come from suggestqueries-clients6.youtube.com (client=youtube-lr, the TV's).

Everything comes out as plain dicts for the QML: a page is {"shelves": [shelf...], "more": token},
a shelf is {"title", "items": [item...], "more": token}, an item is a video, Short, channel,
playlist or game ({"type", "id", "title", "thumb", "lines", "badges", "duration", ...}; item()).

YouTube moves fields around, sends two shapes of the same card (the TV's tileRenderer and the
newer lockupViewModel) and adds renderers we don't know: parsing is defensive, and anything it
doesn't know is left out rather than failing the page. Ads are never shown: ad slots, in-feed
ads, mastheads and anything marked "Ad" or "Sponsored" are dropped (AD_RENDERERS, is_ad()).

Signed out ("guest"), YouTube's TV Home is only a "sign in" note; home() fills it with the top
shelves of the guide's tabs. Streams are ytstream.py (yt-dlp). --demo: Demo, made-up data.
"""

import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import requests

API = "https://www.youtube.com/youtubei/v1"
SUGGEST = "https://suggestqueries-clients6.youtube.com/complete/search"
# YouTube's TV app (Cobalt), as yt-dlp's "tv" client sends it: tv_client() takes yt-dlp's own,
# when it has one, since yt-dlp keeps the version current
TV_CLIENT = {
    "clientName": "TVHTML5",
    "clientVersion": "7.20260707.07.00",
    "userAgent": "Mozilla/5.0 (ChromiumStylePlatform) Cobalt/25.lts.30.1034943-gold (unlike Gecko), Unknown_TV_Unknown_0/Unknown (Unknown, Unknown)",
}
TIMEOUT = (8, 20)
CACHE_SECONDS = 300
# The guide (left of every page): (key, label, browseId). Search, Shorts and Settings are the app's own.
GUIDE = [
    ("search", "Search", ""),
    ("home", "Home", "FEtopics"),
    ("shorts", "Shorts", ""),
    ("music", "Music", "FEtopics_music"),
    ("subscriptions", "Subscriptions", "FEsubscriptions"),
    ("library", "Library", "FElibrary"),
    ("gaming", "Gaming", "FEtopics_gaming"),
    ("news", "News", "FEtopics_news"),
    ("podcasts", "Podcasts", "FEtopics_podcasts"),
    ("movies", "Movies & TV", "FEtopics_movies"),
    ("live", "Live", "FEtopics_live"),
    ("sports", "Sports", "FEtopics_sports"),
    ("settings", "Settings", ""),
]
# Signed out, Home is filled with the top shelves of these tabs
GUEST_HOME = ("FEtopics_music", "FEtopics_gaming", "FEtopics_news", "FEtopics_sports", "FEtopics_live", "FEtopics_podcasts")
AD_RENDERERS = {
    "adSlotRenderer",
    "inFeedAdLayoutRenderer",
    "promotedVideoRenderer",
    "promotedSparklesWebRenderer",
    "promotedSparklesTextSearchRenderer",
    "displayAdRenderer",
    "searchPyvRenderer",
    "compactPromotedVideoRenderer",
    "tvMastheadRenderer",
    "bannerPromoRenderer",
    "statementBannerRenderer",
    "brandVideoShelfRenderer",
    "brandVideoSingletonRenderer",
    "mealbarPromoRenderer",
    "adSlotAndLayoutMetadata",
}
AD_BADGES = {"ad", "sponsored", "paid promotion"}


class YouTubeError(RuntimeError):
    pass


# ------------------------------------------------------------------ small parsing helpers
def text(o: Any) -> str:
    """The text of any of YouTube's text shapes: "x", {"simpleText"}, {"runs": [...]}, {"content"}."""
    if o is None:
        return ""
    if isinstance(o, str):
        return o
    if isinstance(o, dict):
        if "simpleText" in o:
            return str(o["simpleText"])
        if "runs" in o:
            return "".join(str(r.get("text", "")) for r in o["runs"] if isinstance(r, dict))
        if "content" in o:
            return str(o["content"])
        if "text" in o:
            return text(o["text"])
    return ""


def dig(o: Any, *path, default=None):
    """o[path[0]][path[1]]... or default when any step is missing (ints index lists)."""
    for p in path:
        try:
            o = o[p]
        except (KeyError, IndexError, TypeError):
            return default
    return o


def thumb(o: Any, want: int = 640) -> str:
    """The smallest thumbnail at least `want` wide (else the largest), as an https address."""
    thumbs = dig(o, "thumbnails") or dig(o, "sources") or (o if isinstance(o, list) else [])
    thumbs = [t for t in thumbs if isinstance(t, dict) and t.get("url")]
    if not thumbs:
        return ""
    big = [t for t in thumbs if (t.get("width") or 0) >= want]
    t = min(big, key=lambda t: t.get("width") or 0) if big else max(thumbs, key=lambda t: t.get("width") or 0)
    url = t["url"]
    return "https:" + url if url.startswith("//") else url


def avatar(url: str, size: int = 176) -> str:
    """A channel picture at about `size` pixels (yt3 addresses carry their size: =s88-...)."""
    return re.sub(r"=s\d+-", f"=s{size}-", url) if url else ""


def seconds(t: str) -> int:
    """ "1:05:56" -> 3956."""
    try:
        n = 0
        for part in (t or "").strip().split(":"):
            n = n * 60 + int(part)
        return n
    except ValueError:
        return 0


def endpoint(cmd: dict | None) -> dict[str, Any]:
    """What a command opens: {"type": "video" | "short" | "channel" | "playlist" | "browse", ...}."""
    cmd = cmd or {}
    if "innertubeCommand" in cmd:
        cmd = cmd["innertubeCommand"]
    for inner in dig(cmd, "commandExecutorCommand", "commands") or []:
        e = endpoint(inner)
        if e:
            return e
    if "watchEndpoint" in cmd:
        w = cmd["watchEndpoint"]
        out = {"type": "video", "id": w.get("videoId", "")}
        if w.get("playlistId"):
            out["playlistId"] = w["playlistId"]
        if w.get("startTimeSeconds"):
            out["start"] = int(w["startTimeSeconds"])
        return out if out["id"] else {}
    if "reelWatchEndpoint" in cmd:
        vid = cmd["reelWatchEndpoint"].get("videoId", "")
        return {"type": "short", "id": vid} if vid else {}
    if "watchPlaylistEndpoint" in cmd:
        return {"type": "playlist", "id": cmd["watchPlaylistEndpoint"].get("playlistId", "")}
    if "browseEndpoint" in cmd:
        b = cmd["browseEndpoint"]
        bid = b.get("browseId", "")
        if bid.startswith("UC"):
            return {"type": "channel", "id": bid}
        if bid.startswith("VL"):
            return {"type": "playlist", "id": bid[2:]}
        out = {"type": "browse", "id": bid}
        if b.get("params"):
            out["params"] = b["params"]
        return out if bid else {}
    if "searchEndpoint" in cmd:
        return {"type": "search", "id": cmd["searchEndpoint"].get("query", "")}
    return {}


def is_ad(item: dict[str, Any]) -> bool:
    return any(b.lower() in AD_BADGES for b in item.get("badges", []))


# ------------------------------------------------------------------ cards
def item(**kw) -> dict[str, Any]:
    """A card. type: video | short | live | channel | playlist | game. lines: the grey lines under
    the title (the first is the channel); badges: "4K", "New", "CC" (drawn before the last line);
    progress: how much was watched (0-1); duration: "12:34"; live: a LIVE badge instead."""
    out = {
        "type": "video",
        "id": "",
        "title": "",
        "thumb": "",
        "lines": [],
        "badges": [],
        "duration": "",
        "progress": 0.0,
        "live": False,
    }
    out.update({k: v for k, v in kw.items() if v is not None})
    return out


def _overlays(overlays: list, out: dict) -> None:
    for o in overlays or []:
        if "thumbnailOverlayTimeStatusRenderer" in o:
            r = o["thumbnailOverlayTimeStatusRenderer"]
            t = text(r.get("text"))
            style = r.get("style", "")
            if style == "LIVE" or t.upper() == "LIVE":
                out["live"] = True
            elif style == "SHORTS":
                out["type"] = "short"
            elif t:
                out["duration"] = t
        elif "thumbnailOverlayResumePlaybackRenderer" in o:
            out["progress"] = min(1.0, (o["thumbnailOverlayResumePlaybackRenderer"].get("percentDurationWatched") or 0) / 100)
        elif "thumbnailBottomOverlayViewModel" in o:
            vm = o["thumbnailBottomOverlayViewModel"]
            for b in vm.get("badges") or []:
                bv = b.get("thumbnailBadgeViewModel") or {}
                t = bv.get("text", "")
                if "LIVE" in (bv.get("badgeStyle") or "") or t.upper() == "LIVE":
                    out["live"] = True
                elif t:
                    out["duration"] = t
            p = dig(vm, "progressBar", "thumbnailOverlayProgressBarViewModel", "startPercent")
            if p:
                out["progress"] = min(1.0, p / 100)
        elif "thumbnailOverlayBadgeViewModel" in o:
            for b in o["thumbnailOverlayBadgeViewModel"].get("thumbnailBadges") or []:
                t = dig(b, "thumbnailBadgeViewModel", "text") or ""
                if t.upper() == "LIVE":
                    out["live"] = True
                elif re.fullmatch(r"[\d:]+", t):
                    out["duration"] = t


def parse_tile(t: dict[str, Any]) -> dict[str, Any] | None:
    """The TV's tileRenderer."""
    if t.get("adSlotMetadata") or "ad" in (t.get("style") or "").lower().split("_"):
        return None
    out = item()
    header = dig(t, "header", "tileHeaderRenderer") or {}
    out["thumb"] = thumb(header.get("thumbnail"))
    _overlays(header.get("thumbnailOverlays"), out)
    meta = dig(t, "metadata", "tileMetadataRenderer") or {}
    out["title"] = text(meta.get("title"))
    for line in meta.get("lines") or []:
        parts = []
        for li in dig(line, "lineRenderer", "items") or []:
            r = li.get("lineItemRenderer") or {}
            if "badge" in r:
                label = dig(r, "badge", "metadataBadgeRenderer", "label") or ""
                if label:
                    out["badges"].append(label)
                continue
            s = text(r.get("text")).strip()
            if s:
                parts.append(s)
        s = " ".join(parts).replace(" • ", " • ").strip(" •")
        if s:
            out["lines"].append(s)
    target = endpoint(t.get("onSelectCommand"))
    kind = t.get("contentType", "")
    if kind == "TILE_CONTENT_TYPE_CHANNEL" or target.get("type") == "channel":
        out["type"] = "game" if (t.get("style") or "").endswith("_GAME") else "channel"
    elif kind == "TILE_CONTENT_TYPE_PLAYLIST" or target.get("type") == "playlist":
        out["type"] = "playlist"
    elif kind == "TILE_CONTENT_TYPE_SHORTS" or target.get("type") == "short":
        out["type"] = "short"
    if out["live"] and out["type"] == "video":
        out["type"] = "live"
    out["id"] = target.get("id") or t.get("contentId", "")
    if target.get("start"):
        out["start"] = target["start"]
    if target.get("playlistId") and out["type"] != "playlist":
        out["playlistId"] = target["playlistId"]
    if target.get("type") == "browse":
        out["type"], out["params"] = "browse", target.get("params", "")
    out["channelId"] = _menu_channel(t.get("onLongPressCommand"))
    return out if out["id"] and out["title"] else None


def _menu_channel(cmd):
    for m in dig(cmd, "showMenuCommand", "menu", "menuRenderer", "items") or []:
        e = endpoint(dig(m, "menuNavigationItemRenderer", "navigationEndpoint"))
        if e.get("type") == "channel":
            return e["id"]
    return ""


LOCKUP_TYPES = {
    "LOCKUP_CONTENT_TYPE_VIDEO": "video",
    "LOCKUP_CONTENT_TYPE_SHORT": "short",
    "LOCKUP_CONTENT_TYPE_CHANNEL": "channel",
    "LOCKUP_CONTENT_TYPE_PLAYLIST": "playlist",
    "LOCKUP_CONTENT_TYPE_PODCAST": "playlist",
    "LOCKUP_CONTENT_TYPE_ALBUM": "playlist",
}


def parse_lockup(v: dict[str, Any]) -> dict[str, Any] | None:
    """The newer lockupViewModel (search results, some shelves)."""
    out = item(type=LOCKUP_TYPES.get(v.get("contentType", ""), "video"))
    img = dig(v, "contentImage") or {}
    tvm = img.get("thumbnailViewModel") or dig(img, "collectionThumbnailViewModel", "primaryThumbnail", "thumbnailViewModel") or {}
    if tvm:
        out["thumb"] = thumb(dig(tvm, "image"))
        _overlays(tvm.get("overlays"), out)
    elif "decoratedAvatarViewModel" in img or "avatarViewModel" in img:
        av = dig(img, "decoratedAvatarViewModel", "avatar", "avatarViewModel") or img.get("avatarViewModel") or {}
        out["thumb"] = avatar(thumb(av.get("image")))
    meta = dig(v, "metadata", "lockupMetadataViewModel") or {}
    out["title"] = text(meta.get("title"))
    rows = dig(meta, "metadata", "contentMetadataViewModel", "metadataRows") or []
    delim = dig(meta, "metadata", "contentMetadataViewModel", "delimiter") or " • "
    for row in rows:
        parts = [text(p.get("text")).strip() for p in row.get("metadataParts") or []]
        parts = [p for p in parts if p]
        for b in row.get("badges") or []:
            label = dig(b, "badgeViewModel", "badgeText") or ""
            if label:
                out["badges"].append(label)
        if parts:
            out["lines"].append(delim.join(parts))
    target = endpoint(dig(v, "rendererContext", "commandContext", "onTap"))
    if target.get("type") == "short":
        out["type"] = "short"
    if out["live"] and out["type"] == "video":
        out["type"] = "live"
    out["id"] = (target.get("id") if target.get("type") != "browse" else "") or v.get("contentId", "")
    if target.get("start"):
        out["start"] = target["start"]
    if out["type"] == "channel" and target.get("type") == "channel":
        out["id"] = target["id"]
    return out if out["id"] and out["title"] else None


def parse_video_renderer(r: dict[str, Any]) -> dict[str, Any] | None:
    """The web's videoRenderer / gridVideoRenderer / compactVideoRenderer / pivotVideoRenderer
    (YouTube sometimes answers the TV with these)."""
    out = item(id=r.get("videoId", ""), title=text(r.get("title") or r.get("headline")), thumb=thumb(r.get("thumbnail")))
    _overlays(r.get("thumbnailOverlays"), out)
    if not out["duration"] and r.get("lengthText"):
        out["duration"] = text(r["lengthText"])
    owner = text(r.get("shortBylineText") or r.get("longBylineText") or r.get("ownerText"))
    if owner:
        out["lines"].append(owner)
    second = " • ".join(x for x in (text(r.get("shortViewCountText") or r.get("viewCountText")), text(r.get("publishedTimeText"))) if x)
    if second:
        out["lines"].append(second)
    for b in r.get("badges") or []:
        label = dig(b, "metadataBadgeRenderer", "label")
        if label:
            out["badges"].append(label)
    if out["live"]:
        out["type"] = "live"
    return out if out["id"] and out["title"] else None


def parse_any(x: dict[str, Any]) -> dict[str, Any] | None:
    """One card of a shelf, whatever its shape; None for ads and unknown renderers."""
    if not isinstance(x, dict) or any(k in AD_RENDERERS for k in x):
        return None
    out = None
    if "tileRenderer" in x:
        out = parse_tile(x["tileRenderer"])
    elif "lockupViewModel" in x:
        out = parse_lockup(x["lockupViewModel"])
    else:
        for k in ("videoRenderer", "gridVideoRenderer", "compactVideoRenderer", "pivotVideoRenderer"):
            if k in x:
                out = parse_video_renderer(x[k])
                break
    return None if out is None or is_ad(out) else out


# ------------------------------------------------------------------ shelves and pages
def _continuation(o: Any) -> str:
    for c in dig(o, "continuations") or []:
        tok = dig(c, "nextContinuationData", "continuation") or dig(c, "reloadContinuationData", "continuation")
        if tok:
            return tok
    return ""


def shelf_title(s: dict[str, Any]) -> tuple[str, str]:
    """(title, subtitle) of a shelfRenderer."""
    h = dig(s, "headerRenderer", "shelfHeaderRenderer") or {}
    title = text(dig(h, "avatarLockup", "avatarLockupRenderer", "title")) or text(h.get("title")) or text(s.get("title"))
    sub = text(dig(h, "avatarLockup", "avatarLockupRenderer", "subtitle")) or text(h.get("subtitle")) or text(s.get("subtitle"))
    return title.strip(), sub.strip()


def parse_items(items: list) -> list[dict[str, Any]]:
    out, seen = [], set()
    for x in items or []:
        it = parse_any(x)
        if it and (it["type"], it["id"]) not in seen:
            seen.add((it["type"], it["id"]))
            out.append(it)
    return out


def parse_shelf(s: dict[str, Any]) -> list[dict[str, Any]]:
    """A section of a page as shelves (a cluster of a channel and its uploads is several)."""
    if "shelfRenderer" in s:
        r = s["shelfRenderer"]
        content = r.get("content") or {}
        lst = content.get("horizontalListRenderer") or content.get("gridRenderer") or content.get("verticalListRenderer") or {}
        title, sub = shelf_title(r)
        items = parse_items(lst.get("items"))
        if not items:
            return []
        out = {"title": title, "subtitle": sub, "items": items, "more": _continuation(lst)}
        if r.get("tvhtml5ShelfRendererType") == "TVHTML5_SHELF_RENDERER_TYPE_GRID":
            out["grid"] = True
        return [out]
    if "clusterShelfRenderer" in s:
        shelves = []
        for c in s["clusterShelfRenderer"].get("clusters") or []:
            cr = c.get("clusterRenderer") or {}
            items = parse_items(cr.get("items"))
            if not items:
                continue
            head = cr.get("headerRenderer") or {}
            h = head.get("shelfHeaderRenderer") or {}
            title = text(dig(h, "avatarLockup", "avatarLockupRenderer", "title")) or text(h.get("title"))
            shelf = {"title": title.strip(), "subtitle": "", "items": items, "more": ""}
            b = head.get("buttonViewModel")
            if b and b.get("title"):
                # a pill above the cluster: the channel (with its picture) or a search ("Recently uploaded")
                shelf["title"] = ""
                shelf["pill"] = {
                    "title": b["title"],
                    "avatar": avatar(dig(b, "iconImage", "url") or ""),
                    "icon": (b.get("iconName") or "").lower(),
                    "target": endpoint(b.get("onTap")),
                }
            shelves.append(shelf)
        return shelves
    if "itemSectionRenderer" in s:
        out = []
        for c in s["itemSectionRenderer"].get("contents") or []:
            out += parse_shelf(c)
        return out
    if "gridRenderer" in s or "horizontalListRenderer" in s:
        lst = s.get("gridRenderer") or s.get("horizontalListRenderer")
        items = parse_items(lst.get("items"))
        return [{"title": "", "subtitle": "", "items": items, "more": _continuation(lst)}] if items else []
    return []


def section_list(resp: dict[str, Any]) -> dict[str, Any]:
    """The page's sectionListRenderer (or the continuation of one), wherever this response keeps it."""
    for path in (
        ("contents", "tvBrowseRenderer", "content", "tvSurfaceContentRenderer", "content", "sectionListRenderer"),
        ("contents", "sectionListRenderer"),
        ("continuationContents", "sectionListContinuation"),
        ("contents", "singleColumnBrowseResultsRenderer", "tabs", 0, "tabRenderer", "content", "sectionListRenderer"),
    ):
        s = dig(resp, *path)
        if isinstance(s, dict):
            return s
    return {}


def parse_page(resp: dict[str, Any]) -> dict[str, Any]:
    """A browse or search response: {"shelves", "more", "header", "nudge"}."""
    sl = section_list(resp)
    shelves, nudge = [], None
    for s in sl.get("contents") or []:
        if not isinstance(s, dict) or any(k in AD_RENDERERS for k in s):
            continue
        if "feedNudgeRenderer" in s:
            n = s["feedNudgeRenderer"]
            nudge = {"title": text(n.get("title")), "subtitle": text(n.get("subtitle"))}
            continue
        shelves += parse_shelf(s)
    out = {"shelves": shelves, "more": _continuation(sl), "nudge": nudge, "header": None}
    head = dig(resp, "contents", "tvBrowseRenderer", "content", "tvSurfaceContentRenderer", "header")
    if head:
        out["header"] = parse_header(head)
    return out


def parse_more_items(resp: dict[str, Any]) -> dict[str, Any]:
    """The continuation of a shelf: {"items", "more"}."""
    c = dig(resp, "continuationContents", "horizontalListContinuation") or dig(resp, "continuationContents", "gridContinuation") or {}
    return {"items": parse_items(c.get("items")), "more": _continuation(c)}


def parse_header(h: dict[str, Any]) -> dict[str, Any] | None:
    """A channel page's header: name, picture, subscribers and videos, description."""
    c = h.get("channelHeaderRenderer")
    if not c:
        return None
    lines = []
    for li in dig(c, "subtitle", "lineRenderer", "items") or []:
        s = text(dig(li, "lineItemRenderer", "text")).strip()
        if s and s != "•":
            lines.append(s)
    return {
        "title": text(c.get("title")),
        "avatar": avatar(thumb(c.get("avatar"), 72)),
        "banner": thumb(c.get("backgroundImage"), 1280),
        "lines": lines,
        "description": text(c.get("description")) or text(c.get("descriptionText")),
    }


def parse_watch(resp: dict[str, Any]) -> dict[str, Any]:
    """A next response: the video (title, channel, views...), the related rows and the next video."""
    results = dig(resp, "contents", "singleColumnWatchNextResults") or {}
    video = {}
    for c in dig(results, "results", "results", "contents") or []:
        for x in dig(c, "itemSectionRenderer", "contents") or []:
            vm = x.get("videoMetadataRenderer")
            if not vm:
                continue
            owner = dig(vm, "owner", "videoOwnerRenderer") or {}
            sub = dig(owner, "subscribeButton", "subscribeButtonRenderer") or {}
            video = {
                "id": vm.get("videoId", ""),
                "title": text(vm.get("title")),
                "channel": text(owner.get("title")),
                "channelId": endpoint(owner.get("navigationEndpoint")).get("id", ""),
                "avatar": avatar(thumb(owner.get("thumbnail"), 88)),
                "subscribers": text(owner.get("subscriberCountText")),
                "subscribed": bool(sub.get("subscribed")),
                "views": text(dig(vm, "viewCount", "videoViewCountRenderer", "shortViewCount"))
                or text(dig(vm, "viewCount", "videoViewCountRenderer", "viewCount")),
                "date": text(vm.get("dateText")) or text(vm.get("publishedTimeText")),
                "live": bool(dig(vm, "viewCount", "videoViewCountRenderer", "isLive")),
            }
    related = []
    for s in dig(results, "pivot", "sectionListRenderer", "contents") or []:
        for sh in parse_shelf(s):
            related += sh["items"]
    seen, rel = set(), []
    for it in related:
        if it["id"] not in seen and it["id"] != video.get("id"):
            seen.add(it["id"])
            rel.append(it)
    nxt = ""
    for s in dig(results, "autoplay", "autoplay", "sets") or []:
        e = endpoint(dig(s, "autoplayVideoRenderer", "autonavEndpointRenderer", "endpoint")) or endpoint(
            dig(s, "autoplayVideoRenderer", "autoplayEndpointRenderer", "endpoint")
        )
        if e.get("type") == "video" and s.get("mode", "NORMAL") == "NORMAL":
            nxt = e["id"]
            break
    return {"video": video, "related": rel, "next": nxt}


def parse_suggestions(body: str) -> list[str]:
    """suggestqueries' answer: ["q", [["text", 0, [...]], ...], {...}] (or JSONP around it)."""
    m = re.search(r"\[.*\]", body, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return []
    out = []
    for s in data[1] if len(data) > 1 and isinstance(data[1], list) else []:
        t = s[0] if isinstance(s, list) and s else s
        if isinstance(t, str) and t not in out:
            out.append(t)
    return out


# ------------------------------------------------------------------ the client
def tv_client() -> dict[str, str]:
    """The TV client's context: yt-dlp's (kept current with YouTube's), else ours."""
    try:
        from couchbox.services import ytstream

        m = ytstream.module()
        if m:
            from yt_dlp.extractor.youtube._base import INNERTUBE_CLIENTS

            c = INNERTUBE_CLIENTS["tv"]["INNERTUBE_CONTEXT"]["client"]
            if c.get("clientName") == "TVHTML5" and c.get("clientVersion"):
                return {k: c[k] for k in ("clientName", "clientVersion", "userAgent") if k in c}
    except Exception:
        pass
    return dict(TV_CLIENT)


class YouTube:
    """InnerTube as the TV app, signed out (a guest). The guest's visitor id is kept, so YouTube
    sees the same TV each time (as a real one is)."""

    def __init__(self, data_dir: str | None = None, hl: str = "en", gl: str = "US"):
        self.dir = data_dir or os.path.expanduser("~/.local/share/couchbox-yt")
        os.makedirs(self.dir, mode=0o700, exist_ok=True)
        self.client = dict(tv_client(), hl=hl, gl=gl)
        self.s = requests.Session()
        self.s.headers.update(
            {
                "User-Agent": self.client["userAgent"],
                "Origin": "https://www.youtube.com",
                "Referer": "https://www.youtube.com/tv",
                "X-YouTube-Client-Name": "7",
                "X-YouTube-Client-Version": self.client["clientVersion"],
            }
        )
        self.visitor = self._read("visitor.json").get("visitorData", "")
        self.cache: dict[str, tuple[float, Any]] = {}
        self.lock = threading.Lock()
        self.pool = ThreadPoolExecutor(max_workers=6)

    # ---------------------------------------------------------------- storage
    def _read(self, name):
        try:
            with open(os.path.join(self.dir, name)) as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _write(self, name, data):
        path = os.path.join(self.dir, name)
        fd = os.open(path + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)
        os.replace(path + ".tmp", path)

    # ---------------------------------------------------------------- requests
    def call(self, ep: str, body: dict[str, Any], cache: bool = True) -> dict[str, Any]:
        key = ep + json.dumps(body, sort_keys=True)
        hit = self.cache.get(key)
        if cache and hit and time.time() - hit[0] < CACHE_SECONDS:
            return hit[1]
        client = dict(self.client)
        if self.visitor:
            client["visitorData"] = self.visitor
        headers = {"X-Goog-Visitor-Id": self.visitor} if self.visitor else {}
        r = self.s.post(f"{API}/{ep}?prettyPrint=false", json={"context": {"client": client}, **body}, headers=headers, timeout=TIMEOUT)
        if r.status_code >= 400:
            raise YouTubeError(f"YouTube said {r.status_code} ({ep})")
        data = r.json()
        vd = dig(data, "responseContext", "visitorData")
        if vd and vd != self.visitor:
            self.visitor = vd
            self._write("visitor.json", {"visitorData": vd})
        with self.lock:
            if len(self.cache) > 200:
                self.cache.clear()
            self.cache[key] = (time.time(), data)
        return data

    def browse(self, browse_id: str, params: str = "") -> dict[str, Any]:
        body = {"browseId": browse_id}
        if params:
            body["params"] = params
        return parse_page(self.call("browse", body))

    def more(self, token: str) -> dict[str, Any]:
        """More of a page (shelves) or of a shelf (items), from a continuation token."""
        resp = self.call("browse", {"continuation": token})
        if dig(resp, "continuationContents", "sectionListContinuation"):
            return parse_page(resp)
        return parse_more_items(resp)

    def home(self) -> dict[str, Any]:
        page = self.browse("FEtopics")
        if page["shelves"]:
            return page
        # signed out: the note, then the top shelves of the guide's tabs
        tabs = list(self.pool.map(lambda b: self._safe_browse(b), GUEST_HOME))
        shelves, seen = [], set()
        for rnd in range(2):
            for t in tabs:
                if len(t["shelves"]) > rnd:
                    s = t["shelves"][rnd]
                    s = dict(s, items=[i for i in s["items"] if i["type"] in ("video", "live") and i["id"] not in seen])
                    seen.update(i["id"] for i in s["items"])
                    if len(s["items"]) >= 3:
                        shelves.append(s)
        return {"shelves": shelves, "more": "", "nudge": page.get("nudge"), "header": None}

    def _safe_browse(self, bid):
        try:
            return self.browse(bid)
        except Exception:
            return {"shelves": []}

    def channel(self, channel_id: str) -> dict[str, Any]:
        page = self.browse(channel_id)
        if not page["header"]:
            page["header"] = {"title": "", "avatar": "", "banner": "", "lines": [], "description": ""}
        return page

    def search(self, query: str) -> dict[str, Any]:
        page = parse_page(self.call("search", {"query": query}))
        page["query"] = query
        return page

    def suggest(self, query: str) -> list[str]:
        if not query.strip():
            return []
        r = self.s.get(
            SUGGEST,
            params={
                "client": "youtube-lr",
                "ds": "yt",
                "xhr": "t",
                "oe": "utf-8",
                "hl": self.client["hl"],
                "gl": self.client["gl"],
                "q": query,
            },
            timeout=TIMEOUT,
        )
        return parse_suggestions(r.text)[:10]

    def watch(self, video_id: str) -> dict[str, Any]:
        return parse_watch(self.call("next", {"videoId": video_id}))

    # ---------------------------------------------------------------- the guest's searches
    def searches(self) -> list[str]:
        return self._read("searches.json").get("recent", [])

    def remember_search(self, q: str) -> None:
        q = q.strip()
        if not q:
            return
        recent = [s for s in self.searches() if s.lower() != q.lower()]
        self._write("searches.json", {"recent": [q, *recent][:20]})


# ------------------------------------------------------------------ demo (made-up data, no network)
DEMO_CHANNELS = [
    ("UCdemo0000000000000orbit", "Orbit Lab", "@orbitlab", "4.2M subscribers"),
    ("UCdemo00000000000kettle", "Kettle & Crumb", "@kettlecrumb", "890K subscribers"),
    ("UCdemo000000000000trail", "Trailhead Weekly", "@trailheadweekly", "1.3M subscribers"),
    ("UCdemo000000000000pixel", "Pixel Forge", "@pixelforge", "2.7M subscribers"),
    ("UCdemo000000000000tide", "Tidewater News", "@tidewaternews", "610K subscribers"),
    ("UCdemo00000000000tempo", "Tempo Room", "@temporoom", "3.1M subscribers"),
]
DEMO_TITLES = [
    "Why Is the Sky Dark at Night?",
    "We Built a Bridge Out of Paper",
    "The Fastest Bread You Can Bake",
    "A Week on the Coastal Trail",
    "Making a Game in 48 Hours",
    "How Tides Really Work",
    "The Drummer Who Never Practiced",
    "Inside a Lighthouse Lens",
    "Sourdough Without a Starter?",
    "This Map Is Upside Down",
    "Speedrunning a Puzzle Classic",
    "The Strangest Clock in the World",
]
DEMO_AGES = ["14 hours ago", "2 days ago", "3 weeks ago", "1 month ago", "5 days ago", "7 months ago"]


class Demo(YouTube):
    """Made-up channels and videos for the screenshots (no network). Thumbnails are left out:
    the cards draw a gradient with the title instead."""

    def __init__(self):
        self.dir = ""
        self.client = dict(TV_CLIENT, hl="en", gl="US")
        self.recent = ["paper bridge", "coastal trail", "sourdough"]

    def _video(self, n, kind="video"):
        cid, name, _handle, _subs = DEMO_CHANNELS[n % len(DEMO_CHANNELS)]
        mins = 4 + (n * 7) % 50
        it = item(
            type=kind,
            id=f"demo{n:07d}",
            title=DEMO_TITLES[n % len(DEMO_TITLES)],
            lines=[name, f"{(n * 37) % 900 + 12}K views • {DEMO_AGES[n % len(DEMO_AGES)]}"],
            badges=["4K"] if n % 3 == 0 else (["New"] if n % 4 == 1 else []),
            duration="" if kind == "live" else (f"1:{mins:02d}:{(n * 13) % 60:02d}" if n % 5 == 0 else f"{mins}:{(n * 13) % 60:02d}"),
            progress=0.35 if n % 4 == 2 else 0.0,
            live=kind == "live",
            channelId=cid,
        )
        if kind == "live":
            it["lines"][1] = f"{(n * 11) % 90 + 3}K watching"
        return it

    def _shelf(self, title, start, n=8, kind="video"):
        return {"title": title, "subtitle": "", "items": [self._video(start + i, kind) for i in range(n)], "more": ""}

    def home(self):
        return {
            "shelves": [
                self._shelf("Recommended", 0),
                self._shelf("New to you", 8),
                self._shelf("Live now", 16, kind="live"),
                self._shelf("Science & engineering", 24),
            ],
            "more": "",
            "nudge": None,
            "header": None,
        }

    def browse(self, browse_id, params=""):
        label = next((g[1] for g in GUIDE if g[2] == browse_id), "Videos")
        n = sum(map(ord, browse_id)) % 20
        return {
            "shelves": [
                self._shelf(f"Top in {label}", n),
                self._shelf("Trending", n + 8),
                self._shelf(f"Live: {label}", n + 16, kind="live"),
            ],
            "more": "",
            "nudge": None,
            "header": None,
        }

    def more(self, token):
        return {"items": [], "more": ""}

    def channel(self, channel_id):
        i = next((k for k, c in enumerate(DEMO_CHANNELS) if c[0] == channel_id), 0)
        cid, name, handle, subs = DEMO_CHANNELS[i]
        return {
            "shelves": [self._shelf("Videos", i), self._shelf("Popular", i + 6), self._shelf("Shorts", i + 3, kind="short")],
            "more": "",
            "nudge": None,
            "header": {
                "title": name,
                "avatar": "",
                "banner": "",
                "lines": [handle, subs, f"{120 + i * 40} videos"],
                "description": "Experiments, explanations and the occasional disaster, every other Thursday.",
            },
        }

    def search(self, query):
        cid, name, handle, subs = DEMO_CHANNELS[0]
        first = [self._video(0), item(type="channel", id=cid, title=name, lines=[handle, subs])] + [self._video(i) for i in range(1, 8)]
        return {
            "shelves": [
                {"title": f"Search results for {query}", "subtitle": "", "items": first, "more": ""},
                self._shelf(name, 10, n=6),
                self._shelf("Previously watched", 20, n=6),
            ],
            "more": "",
            "nudge": None,
            "header": None,
            "query": query,
        }

    def suggest(self, query):
        q = query.strip().lower()
        return [q] + [f"{q} {w}" for w in ("explained", "experiment", "live", "documentary", "tutorial", "compilation")] if q else []

    def watch(self, video_id):
        n = int(video_id[4:]) if video_id.startswith("demo") and video_id[4:].isdigit() else 0
        v = self._video(n)
        cid, name, _handle, subs = DEMO_CHANNELS[n % len(DEMO_CHANNELS)]
        return {
            "video": {
                "id": v["id"],
                "title": v["title"],
                "channel": name,
                "channelId": cid,
                "avatar": "",
                "subscribers": subs,
                "subscribed": False,
                "views": v["lines"][1].split(" • ")[0],
                "date": DEMO_AGES[n % len(DEMO_AGES)].replace(" ago", " ago"),
                "live": False,
            },
            "related": [self._video(n + 1 + i) for i in range(9)],
            "next": f"demo{n + 1:07d}",
        }

    def searches(self):
        return list(self.recent)

    def remember_search(self, q):
        self.recent = [q, *[s for s in self.recent if s != q]][:20]


def demo_stream(video_id: str) -> dict[str, Any]:
    """The demo's "stream": nothing to play (the stand-in video), with chapters to draw."""
    n = int(video_id[4:]) if video_id.startswith("demo") and video_id[4:].isdigit() else 0
    names = ["Intro", "The question", "First try", "What went wrong", "Second try", "The answer", "Wrapping up"]
    return {
        "id": video_id,
        "url": "demo://" + video_id,
        "opts": "",
        "live": False,
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "vcodec": "avc1",
        "acodec": "mp4a",
        "title": DEMO_TITLES[n % len(DEMO_TITLES)],
        "channel": DEMO_CHANNELS[n % len(DEMO_CHANNELS)][1],
        "channelId": DEMO_CHANNELS[n % len(DEMO_CHANNELS)][0],
        "duration": 3600.0,
        "chapters": [{"start": i * 3600 / len(names) + (i * 97) % 200 * (1 if i else 0), "title": t} for i, t in enumerate(names)],
        "views": 0,
        "likes": 0,
        "timestamp": 0,
        "portrait": False,
        "took": 0,
    }
