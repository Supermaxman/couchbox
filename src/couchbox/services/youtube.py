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
    """YouTube refused or failed (args: the message, and the HTTP status when there is one)."""


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
                if dig(r, "icon", "iconType") == "AUDIO":
                    out["music"] = True  # a music video: a note before its length
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
    for o in header.get("thumbnailOverlays") or []:  # posters and wormholes keep their text on the picture
        if not meta.get("title") and "tileMetadataRenderer" in o:
            meta = o["tileMetadataRenderer"]
    if not meta.get("title"):  # a carousel's (Movies & TV's hero row): wherever the tile keeps it
        rest = {k: v for k, v in t.items() if k != "onLongPressCommand"}
        meta = next((m for m in _find(rest, "tileMetadataRenderer") if isinstance(m, dict) and m.get("title")), meta)
    out["title"] = text(meta.get("title")) or text(dig(t, "onLongPressCommand", "showMenuCommand", "title"))
    out["shape"] = tile_shape(t.get("style") or "", header.get("thumbnail"))
    for line in meta.get("lines") or []:
        parts = []
        for li in dig(line, "lineRenderer", "items") or []:
            r = li.get("lineItemRenderer") or {}
            if "badge" in r:
                b = dig(r, "badge", "metadataBadgeRenderer") or {}
                label = b.get("label") or ""
                if label.strip().lower() in ("continue watching", "resume"):
                    continue  # the red bar says so: YouTube's TV app shows the card's usual lines
                if label:
                    out["badges"].append(label)
                    if b.get("style") == "BADGE_STYLE_TYPE_YPC":  # paid (Try now, Buy, Rent): green
                        out.setdefault("pay", []).append(label)
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
    fb = menu_feedback(t.get("onLongPressCommand"))
    if fb:
        out["feedback"] = fb
    wl = menu_watch_later(t.get("onLongPressCommand"))
    if wl:
        out["laterEdit"] = wl
    out["lines"] = split_channel(out["lines"])
    return out if out["id"] and out["title"] else None


def split_channel(lines: list[str]) -> list[str]:
    """A video's channel on its own line: some shelves (music videos) send "LISA • 74M views •
    13 days ago" as one line, where the TV app shows the channel, then the views and age."""
    if len(lines) == 1 and lines[0].count(" • ") >= 2 and re.search(r"\b(views?|watching)\b", lines[0]):
        chan, rest = lines[0].split(" • ", 1)
        return [chan, rest]
    return lines


def tile_shape(style: str, thumbnail: Any) -> str:
    """How a card is drawn: "wide" (16:9, most), "poster" (2:3 movie art), "square" (albums,
    podcasts), "hero" (a large wide card) or "round"."""
    if style.endswith("_SQUARE"):
        return "square"
    if style.endswith("_HERO"):
        return "hero"
    t = (dig(thumbnail, "thumbnails") or [{}])[-1]
    w, h = t.get("width") or 16, t.get("height") or 9
    if h > w * 1.2:
        return "poster"
    if 0.85 < w / h < 1.2:
        return "square"
    return "wide"


# a card's menu (hold OK): its feedback options, by the menu item's icon or, failing that, its words
FEEDBACK_KINDS = (
    ("remove_history", ("DELETE",), ("watch history",)),
    ("no_channel", ("REMOVE",), ("recommend channel",)),
    ("not_interested", ("NOT_INTERESTED",), ("not interested",)),
)


def outline(o: Any, depth: int = 0) -> Any:
    """An answer's shape for a probe: its keys (and lists' first items), the leaves' types only."""
    if depth > 7:
        return "..."
    if isinstance(o, dict):
        return {k: outline(v, depth + 1) for k, v in o.items() if k not in ("trackingParams", "clickTrackingParams")}
    if isinstance(o, list):
        return [outline(o[0], depth + 1), len(o)] if o else []
    return type(o).__name__


def menu_entries(cmd: Any) -> list[dict[str, Any]]:
    """A card's menu, whatever renderer each entry is (menuServiceItemRenderer,
    menuNavigationItemRenderer, the TV's newer ones): [{label, icon, entry}] (entry: its body)."""
    out = []
    for menu in _find(cmd or {}, "menuRenderer"):
        for m in (menu or {}).get("items") or [] if isinstance(menu, dict) else []:
            inner = next(iter(m.values()), None) if isinstance(m, dict) and m else None
            if isinstance(inner, dict):
                out.append(
                    {"label": text(inner.get("text") or inner.get("title")), "icon": dig(inner, "icon", "iconType") or "", "entry": inner}
                )
    return out


def menu_watch_later(cmd: Any) -> dict[str, Any] | None:
    """The menu's own Save to Watch later: its playlistEditEndpoint (playlistId WL, its actions
    and params as the TV sends them), for browse/edit_playlist."""
    for e in menu_entries(cmd):
        for ep in _find(e["entry"], "playlistEditEndpoint"):
            if isinstance(ep, dict) and ep.get("playlistId") == "WL":
                return {k: ep[k] for k in ("playlistId", "actions", "params") if k in ep}
    return None


def menu_feedback(cmd: Any) -> list[dict[str, str]]:
    """The feedback options of a card's menu (Not interested, Don't recommend channel, Remove from
    watch history): [{kind, label, token}] (its feedback token, for the feedback endpoint)."""
    out: list[dict[str, str]] = []
    for e in menu_entries(cmd):
        m = e["entry"]
        tok = next((f.get("feedbackToken") for f in _find(m, "feedbackEndpoint") if isinstance(f, dict)), "")
        if not tok:
            continue
        label, icon = e["label"], e["icon"]
        kind = next((k for k, icons, words in FEEDBACK_KINDS if icon in icons), "") or next(
            (k for k, _i, words in FEEDBACK_KINDS if any(w in label.lower() for w in words)), ""
        )
        if kind and not any(o["kind"] == kind for o in out):
            out.append({"kind": kind, "label": label, "token": tok})
    return out


def _menu_channel(cmd):
    """The channel a card's menu goes to (Go to channel), whatever its entry's renderer."""
    for e in menu_entries(cmd):
        for b in _find(e["entry"], "browseEndpoint"):
            bid = (b or {}).get("browseId", "") if isinstance(b, dict) else ""
            if bid.startswith("UC"):
                return bid
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
    out["lines"] = split_channel(out["lines"])
    if v.get("contentType") == "LOCKUP_CONTENT_TYPE_TV_NETWORK":
        out["type"], out["shape"] = "browse", "round"
    target = endpoint(dig(v, "rendererContext", "commandContext", "onTap"))
    if out["type"] == "browse":
        out["id"], out["params"] = target.get("id", ""), target.get("params", "")
    if target.get("type") == "short":
        out["type"] = "short"
    if out["live"] and out["type"] == "video":
        out["type"] = "live"
    if out["type"] != "browse":
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
        kind = r.get("tvhtml5ShelfRendererType") or ""
        if kind == "TVHTML5_SHELF_RENDERER_TYPE_GRID":
            out["grid"] = True
        elif kind in (
            "TVHTML5_SHELF_RENDERER_TYPE_EXPANSION_SHELF",
            "TVHTML5_SHELF_RENDERER_TYPE_WORMHOLES",
            "TVHTML5_SHELF_RENDERER_TYPE_CAROUSEL",
        ):
            out["hero"] = True  # Movies & TV: the focused title large above the row (signed in: its carousel)
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
        # a channel in search results: its pill over one large card, and "Recently uploaded" over a
        # list beside it: one row, as the TV app lays it out
        if (
            len(shelves) == 2
            and all(s.get("pill") for s in shelves)
            and shelves[0]["pill"]["target"].get("type") == "channel"
            and len(shelves[0]["items"]) == 1
        ):
            hero, lst = shelves
            return [
                {"title": "", "subtitle": "", "items": hero["items"] + lst["items"], "more": "", "cluster": {"hero": hero, "list": lst}}
            ]
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
    more = _continuation(sl)
    surface = dig(resp, "contents", "tvBrowseRenderer", "content", "tvSurfaceContentRenderer") or {}
    if not sl:
        content = parse_content(surface.get("content") or dig(resp, "continuationContents") or {})
        shelves, more = content["shelves"], content["more"] or more
    if not shelves and not nudge:
        shelves = harvest(resp)  # a shape we don't know yet: whatever cards it has
    out = {"shelves": shelves, "more": more, "nudge": nudge, "header": None}
    if surface.get("header"):
        out["header"] = parse_header(surface["header"])
    return out


def parse_content(c: dict[str, Any]) -> dict[str, Any]:
    """A tab's or surface's content: a section list, or a grid (History, Watch later, a playlist)."""
    if "tvSurfaceContentRenderer" in c:
        c = c["tvSurfaceContentRenderer"].get("content") or {}
    if "twoColumnRenderer" in c:  # a playlist (Watch later, Liked videos...): its name, then its videos
        two = c["twoColumnRenderer"]
        title = text(dig(two, "leftColumn", "entityMetadataRenderer", "title"))
        out = parse_content(two.get("rightColumn") or {})
        if out["shelves"] and not out["shelves"][0]["title"]:
            out["shelves"][0]["title"] = title
        return out
    if "sectionListRenderer" in c or "sectionListContinuation" in c:
        sl = c.get("sectionListRenderer") or c.get("sectionListContinuation")
        return parse_page({"contents": {"sectionListRenderer": sl}})
    for key in ("gridRenderer", "gridContinuation", "playlistVideoListRenderer", "verticalListRenderer", "horizontalListRenderer"):
        if key in c:
            g = c[key]
            items = parse_items(g.get("items") or g.get("contents"))
            more = _continuation(g) or next(
                (
                    dig(x, "continuationItemRenderer", "continuationEndpoint", "continuationCommand", "token")
                    for x in g.get("contents") or []
                    if "continuationItemRenderer" in x
                ),
                "",
            )
            title = text(dig(g, "header", "gridHeaderRenderer", "title"))
            shelf = {"title": title, "subtitle": "", "items": items, "more": more or "", "grid": True}
            return {"shelves": [shelf] if items else [], "more": ""}
    return {"shelves": [], "more": ""}


def harvest(resp: Any, depth: int = 0) -> list[dict[str, Any]]:
    """Every list of cards anywhere in a response, as untitled shelves: so a page YouTube has
    reshaped still shows its videos rather than nothing."""
    out: list[dict[str, Any]] = []
    if depth > 40:
        return out
    if isinstance(resp, list):
        if any(isinstance(x, dict) and ("tileRenderer" in x or "lockupViewModel" in x) for x in resp):
            items = parse_items(resp)
            return [{"title": "", "subtitle": "", "items": items, "more": "", "grid": True}] if items else []
        for x in resp:
            out += harvest(x, depth + 1)
    elif isinstance(resp, dict):
        for k, v in resp.items():
            if k in AD_RENDERERS or k in ("frameworkUpdates", "responseContext", "onLongPressCommand", "menu"):
                continue
            out += harvest(v, depth + 1)
    return out


def parse_more_items(resp: dict[str, Any]) -> dict[str, Any]:
    """The continuation of a shelf: {"items", "more"}."""
    cc = resp.get("continuationContents") or {}
    c = cc.get("horizontalListContinuation") or cc.get("gridContinuation") or cc.get("playlistVideoListContinuation") or {}
    return {"items": parse_items(c.get("items") or c.get("contents")), "more": _continuation(c)}


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
                "handle": (dig(owner, "navigationEndpoint", "browseEndpoint", "canonicalBaseUrl") or "").lstrip("/")
                if "/@" in (dig(owner, "navigationEndpoint", "browseEndpoint", "canonicalBaseUrl") or "")
                else "",
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
    video.update(engagement(resp))
    if not video.get("channelId") and video.get("subscribeChannel"):
        video["channelId"] = video["subscribeChannel"]
    start = dig(resp, "currentVideoEndpoint", "watchEndpoint", "startTimeSeconds")
    count = dig(results, "autoplay", "autoplay", "countDownSecs")
    return {
        "video": video,
        "related": rel,
        "next": nxt,
        "start": int(start or 0),
        "details": description(resp),
        "chapters": chapter_markers(resp),
        "countdown": int(count) if count else 5,
    }


def description(resp: dict[str, Any]) -> dict[str, Any]:
    """The Description panel: the factoids (likes, views, date), the text, YouTube's summary, the
    comments' count and first comment, and the comments' continuation."""
    out: dict[str, Any] = {"facts": [], "text": "", "summary": "", "comments": "", "teaser": None, "commentsToken": ""}
    for h in _find(resp, "videoDescriptionHeaderRenderer"):
        for f in h.get("factoid") or []:
            fr = f.get("factoidRenderer") or {}
            if fr:
                value, label = text(fr.get("value")), text(fr.get("label"))
                if re.fullmatch(r"\d{4}", value) and re.search(r"[A-Za-z]", label):
                    value, label = label, value  # the date: "May 14" large over "2023", as the TV app has it
                out["facts"].append({"value": value, "label": label})
        break
    for b in _find(resp, "expandableVideoDescriptionBodyRenderer"):
        out["text"] = text(b.get("descriptionBodyText")) or text(b.get("attributedDescriptionBodyText"))
        break
    for m in _find(resp, "expandableMetadataRenderer"):
        out["summary"] = text(dig(m, "header", "collapsedTitle"))
        break
    for c in _find(resp, "commentsEntryPointRenderer"):
        out["comments"] = text(c.get("commentCount"))
        out["teaser"] = {
            "author": text(c.get("authorText")),
            "text": text(c.get("contentText")),
            "photo": avatar(thumb(c.get("authorThumbnail"), 88)),
        }
        break
    for p in resp.get("engagementPanels") or []:
        e = p.get("engagementPanelSectionListRenderer") or {}
        if e.get("panelIdentifier") == "comment-item-section":
            content = e.get("content") or {}
            cmd = next(iter(_find(content, "continuationCommand")), {}) or {}
            out["commentsToken"] = cmd.get("token") or next(
                (_continuation({"continuations": c}) for c in _find(content, "continuations")), ""
            )
            if not out["comments"]:
                out["comments"] = text(dig(e, "header", "engagementPanelTitleHeaderRenderer", "contextualInfo"))
    return out


def chapter_markers(resp: dict[str, Any]) -> list[dict[str, Any]]:
    """The chapters with their pictures (the seek strip, the Description panel)."""
    for m in _find(resp.get("frameworkUpdates") or {}, "macroMarkersListEntity"):
        ml = m.get("markersList") or {}
        if ml.get("markerType") != "MARKER_TYPE_CHAPTERS":
            continue
        return [
            {"title": text(k.get("title")), "start": int(k.get("startMillis") or 0) / 1000, "thumb": thumb(k.get("thumbnailDetails"), 320)}
            for k in ml.get("markers") or []
        ]
    return []


def _token_in(o: Any) -> str:
    """The first continuation token in o (a continuationCommand's, or an older continuation's)."""
    for c in _find(o, "continuationCommand"):
        if isinstance(c, dict) and c.get("token"):
            return c["token"]
    for k in ("nextContinuationData", "reloadContinuationData"):
        for c in _find(o, k):
            if isinstance(c, dict) and c.get("continuation"):
                return c["continuation"]
    return ""


def _comment(c: dict[str, Any]) -> dict[str, Any]:
    return {
        "author": text(c.get("authorText")),
        "photo": avatar(thumb(c.get("authorThumbnail"), 88)),
        "text": text(c.get("contentText")),
        "time": text(c.get("publishedTimeText")),
        "likes": text(c.get("voteCount")),
        "replies": int(c.get("replyCount") or 0),
        "pinned": "pinnedCommentBadge" in c,
    }


def parse_comments(resp: dict[str, Any]) -> dict[str, Any]:
    """A page of comments (a next continuation): [{author, photo, text, time, likes, replies,
    pinned, repliesToken}], more. A thread's repliesToken opens its replies (a page of comments
    like this one, its own more for their next page)."""
    items, more = [], ""
    threads = [t for t in _find(resp, "commentThreadRenderer") if isinstance(t, dict)]
    if threads:
        for t in threads:
            c = next((x for x in _find(t.get("comment") or {k: v for k, v in t.items() if k != "replies"}, "commentRenderer")), None)
            if not isinstance(c, dict):
                continue
            it = _comment(c)
            tok = _token_in(t.get("replies") or {})
            if tok:
                it["repliesToken"] = tok
            items.append(it)

        def outside(o):  # the page's own continuation, not one inside a thread (its replies)
            if isinstance(o, dict):
                for k, v in o.items():
                    if k == "commentThreadRenderer":
                        continue
                    if k == "continuationItemRenderer":
                        yield v
                    else:
                        yield from outside(v)
            elif isinstance(o, list):
                for v in o:
                    yield from outside(v)

        conts = list(outside(resp))
    else:  # a thread's replies (or comments without threads)
        items = [_comment(c) for c in _find(resp, "commentRenderer") if isinstance(c, dict)]
        conts = list(_find(resp, "continuationItemRenderer"))
    for x in conts:
        more = (
            dig(x, "continuationEndpoint", "continuationCommand", "token")
            or dig(x, "button", "buttonRenderer", "command", "continuationCommand", "token")
            or more
        )
    if not more:
        more = next(
            (t for cs in _find(resp.get("continuationContents") or {}, "continuations") if (t := _continuation({"continuations": cs}))), ""
        )
    return {"items": items, "more": more}


def parse_short_sequence(resp: dict[str, Any]) -> dict[str, Any]:
    """reel/reel_watch_sequence: the Shorts to play next: [{id, thumb, color}], more."""
    out = []
    for e in resp.get("entries") or []:
        r = dig(e, "command", "reelWatchEndpoint") or next(_find(e, "reelWatchEndpoint"), None) or {}
        if r.get("videoId"):
            pal = dig(r, "thumbnail", "darkColorPalette", "section1Color")
            out.append(
                {
                    "type": "short",
                    "id": r["videoId"],
                    "thumb": thumb(r.get("thumbnail"), 360),
                    "color": f"#{pal:06x}" if isinstance(pal, int) else "",
                }
            )
    return {"items": out, "more": resp.get("continuation") or ""}


def parse_short(resp: dict[str, Any]) -> dict[str, Any]:
    """reel/reel_item_watch: a Short's title, channel and Subscribe (the right of the Shorts player)."""
    h = next(iter(_find(resp, "reelPlayerHeaderRenderer")), {}) or {}
    sub = next((b for b in _find(resp.get("overlay") or resp, "subscribeButtonRenderer") if isinstance(b, dict) and "subscribed" in b), {})
    out = {
        "title": text(h.get("reelTitleText")),
        "handle": text(h.get("channelTitleText")),
        "avatar": avatar(thumb(h.get("channelThumbnail"), 88)),
        "channelId": endpoint(h.get("channelNavigationEndpoint")).get("id", ""),
        "subscribed": bool(sub.get("subscribed")),
        "age": text(h.get("timestampText")),
    }
    out.update({k: v for k, v in engagement(resp).items() if k in ("like", "likes")})
    return out


def _find(o: Any, key: str, depth: int = 0):
    """Every value of `key` anywhere in o (depth first)."""
    if depth > 30:
        return
    if isinstance(o, dict):
        for k, v in o.items():
            if k == key:
                yield v
            yield from _find(v, key, depth + 1)
    elif isinstance(o, list):
        for x in o:
            yield from _find(x, key, depth + 1)


NOTIFY = {"NOTIFICATIONS_ACTIVE": "all", "NOTIFICATIONS_NONE": "personalized", "NOTIFICATIONS_OFF": "none"}
LIKES = {"LIKE": "like", "DISLIKE": "dislike"}


def engagement(resp: dict[str, Any]) -> dict[str, Any]:
    """The signed-in parts of a watch page: like status and count, subscribed, the notification
    levels (each with the params that set it)."""
    out: dict[str, Any] = {"like": "none", "likes": 0, "subscribed": False, "notify": "", "notifyOptions": []}
    for lb in _find(resp.get("transportControls") or resp, "likeButtonRenderer"):
        out["like"] = LIKES.get(lb.get("likeStatus", ""), "none")
        out["likes"] = int(lb.get("likeCount") or 0)
        break
    for e in _find(resp.get("frameworkUpdates") or {}, "likeStatusEntity"):
        out["like"] = LIKES.get(e.get("likeStatus", ""), out["like"])
    subs = [b for b in _find(resp, "subscribeButtonRenderer") if isinstance(b, dict)]
    if subs:
        out["subscribed"] = any(bool(b.get("subscribed")) for b in subs)
        out["subscribeChannel"] = next((b.get("channelId") for b in subs if b.get("channelId")), "")
    for e in _find(resp.get("frameworkUpdates") or {}, "subscriptionStateEntity"):
        out["subscribed"] = bool(e.get("subscribed")) or out["subscribed"]
    for t in _find(resp, "subscriptionNotificationToggleButtonRenderer"):
        states = t.get("states") or []
        cur = t.get("currentStateId")
        opts = []
        for st in states:
            icon = dig(st, "state", "buttonRenderer", "icon", "iconType") or ""
            menu = dig(st, "inlineMenuButton", "buttonRenderer") or {}
            params = dig(menu, "serviceEndpoint", "modifyChannelNotificationPreferenceEndpoint", "params") or ""
            level = NOTIFY.get(icon, "")
            if level and params:
                opts.append({"level": level, "label": text(menu.get("text")) or level.title(), "params": params})
                if st.get("stateId") == cur:
                    out["notify"] = level
        if opts:
            out["notifyOptions"] = opts
            break
    return out


def parse_save_options(resp: dict[str, Any]) -> list[dict[str, Any]]:
    """playlist/get_add_to_playlist: [{id, title, saved}] (Watch later first)."""
    out = []
    for r in _find(resp, "playlistAddToOptionRenderer"):
        pid = r.get("playlistId", "")
        if pid:
            out.append({"id": pid, "title": text(r.get("title")), "saved": r.get("containsSelectedVideos") in ("ALL", "SOME")})
    out.sort(key=lambda p: p["id"] != "WL")
    return out


def parse_accounts(resp: dict[str, Any]) -> list[dict[str, Any]]:
    """account/accounts_list: the channels one Google account can watch as: [{name, handle, photo,
    email, pageId (a brand account's), main (the account's own)}]."""
    out = []
    for a in _find(resp, "accountItem"):
        if not isinstance(a, dict) or a.get("isDisabled"):
            continue
        tokens = dig(a, "serviceEndpoint", "selectActiveIdentityEndpoint", "supportedTokens") or []
        page = next((dig(t, "pageIdToken", "pageId") for t in tokens if dig(t, "pageIdToken", "pageId")), "")
        byline = text(a.get("accountByline"))
        handle = text(a.get("channelHandle"))
        # a Premium membership: the TV's account item says so with shouldShowPremiumLogo and its
        # "unlimitedStatus" line ("YouTube Premium"), shown under the name on Who's watching
        membership = " ".join(text(s) for s in (a.get("unlimitedStatus") or []) if text(s)).strip()
        premium = bool(a.get("shouldShowPremiumLogo")) or any(
            "premium" in str(v).lower() for v in (membership, byline, a.get("badges"), a.get("membershipBadge"), a.get("isPremium")) if v
        )
        out.append(
            {
                "name": text(a.get("accountName")),
                "handle": handle if handle.startswith("@") else "",
                "photo": avatar(thumb(a.get("accountPhoto"), 88), 352),
                "email": byline if "@" in byline and not byline.startswith("@") else "",
                "pageId": page,
                "main": not page,
                "premium": premium,
                "membership": membership or ("YouTube Premium" if premium else ""),
            }
        )
    if out and not any(c["main"] for c in out):
        out[0]["main"] = True
    return out


def parse_subscriptions(resp: dict[str, Any]) -> dict[str, Any]:
    """FEsubscriptions on the TV: the channels down the side (All first, then the most relevant,
    then A-Z) and the page of the selected one: {"channels": [...], "page": {...}}."""
    nav = next(_find(resp, "tvSecondaryNavRenderer"), None)
    if not nav:
        return {"channels": [], "page": parse_page(resp)}
    channels, page = [], None
    label = ""  # a tab that's only a heading ("A-Z"): a label over the channels after it
    for sec in nav.get("sections") or []:
        sr = sec.get("tvSecondaryNavSectionRenderer") or {}
        title = text(sr.get("title"))
        for t in sr.get("tabs") or []:
            tr = t.get("tabRenderer") or {}
            e = endpoint(tr.get("endpoint"))
            ch = {
                "title": text(tr.get("title")),
                "thumb": avatar(thumb(tr.get("thumbnail"), 88)),
                "id": e.get("id", ""),
                "params": e.get("params", ""),
                "section": "",
                "new": "NEW" in json.dumps(tr.get("presentationStyle") or tr.get("badge") or ""),
            }
            if not ch["title"]:
                continue
            if channels and not ch["id"].startswith("UC") and not ch["thumb"]:  # "A-Z": a heading, not a row
                label = ch["title"]
                continue
            if label:
                ch["section"], label = label, ""
            elif title and not any(c["section"] == title for c in channels):
                ch["section"] = title
            if not channels:
                ch["all"] = True  # the first: All (YouTube gives it an address too)
            channels.append(ch)
            if tr.get("selected") and tr.get("content") and page is None:
                page = parse_content(tr["content"])
    page = page or {"shelves": [], "more": ""}
    page.update({"nudge": None, "header": None})
    return {"channels": channels, "page": page}


def tracking(resp: dict[str, Any]) -> dict[str, str]:
    """A player response's reporting addresses (history, resume, watch time)."""
    t = resp.get("playbackTracking") or {}
    return {
        "playback": dig(t, "videostatsPlaybackUrl", "baseUrl") or "",
        "watchtime": dig(t, "videostatsWatchtimeUrl", "baseUrl") or "",
    }


def is_premium(resp: Any) -> bool:
    """YouTube marks a Premium member's pages with its Premium logo (on the TV: an icon or badge
    named YOUTUBE_PREMIUM..., or its "Premium" wordmark)."""
    if not resp:
        return False
    s = json.dumps(resp)
    return "YOUTUBE_PREMIUM" in s or "YOUTUBE_LOGO_PREMIUM" in s or "PREMIUM_LOGO" in s


def premium_hints(o: Any, path: str = "", out: list | None = None, depth: int = 0) -> list[str]:
    """Where an answer says "premium" (keys and short texts; at most 12): for finding how the TV
    marks a Premium account (the box check's premiumProbe). No tokens: those are long."""
    out = [] if out is None else out
    if len(out) >= 12 or depth > 40:
        return out
    if isinstance(o, dict):
        for k, v in o.items():
            if "premium" in k.lower() and not isinstance(v, (dict, list)):
                out.append(f"{path}.{k} = {str(v)[:60]}")
            premium_hints(v, f"{path}.{k}", out, depth + 1)
    elif isinstance(o, list):
        for i, v in enumerate(o[:50]):
            premium_hints(v, f"{path}[{i}]", out, depth + 1)
    elif isinstance(o, str) and "premium" in o.lower() and len(o) < 80:
        out.append(f"{path} = {o}")
    return out


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
    """InnerTube as the TV app, as a guest or as a profile (a signed-in account and one of its
    channels: ytauth). The guest's visitor id is kept, so YouTube sees the same TV each time (as a
    real one is)."""

    def __init__(self, data_dir: str | None = None, hl: str = "en", gl: str = "US", client: dict[str, str] | None = None):
        from couchbox.services import ytauth

        self.dir = data_dir or os.path.expanduser("~/.local/share/couchbox-yt")
        os.makedirs(self.dir, mode=0o700, exist_ok=True)
        self.client = dict(client or tv_client(), hl=hl, gl=gl)
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
        self.on_event = lambda name, data: None
        self.auth = ytauth.Auth(self.dir, session=requests.Session(), on_event=lambda n, d: self.on_event(n, d))
        self.auth.channels_for = self.accounts_list
        self.profile: dict[str, Any] = {}  # {} : the guest
        self.sessions: dict[str, dict[str, Any]] = {}  # playback reports in progress, by cpn

    def set_client(self, client: dict[str, str]) -> None:
        """The TV client's context as yt-dlp keeps it current (from ytworker: no yt-dlp here)."""
        if not client.get("clientVersion"):
            return
        self.client.update({k: client[k] for k in ("clientName", "clientVersion", "userAgent") if k in client})
        self.s.headers.update({"User-Agent": self.client["userAgent"], "X-YouTube-Client-Version": self.client["clientVersion"]})

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

    # ---------------------------------------------------------------- who's watching
    def profiles(self) -> dict[str, Any]:
        return {"profiles": self.auth.profiles(), "last": self.auth.last_profile(), "current": self.profile.get("id", "")}

    def find_profile(self, pid: str) -> dict[str, Any] | None:
        """A profile on this TV by its id ("ACCOUNT:PAGE"; a bare ACCOUNT is its own channel)."""
        if not pid or pid == "guest":
            return None
        if ":" not in pid:
            pid += ":"
        return next((p for p in self.auth.profiles() if p["id"] == pid), None)

    def use(self, pid: str) -> dict[str, Any]:
        """Watch as this profile ("" or "guest": signed out)."""
        prof = self.find_profile(pid)
        if pid and pid != "guest" and not prof:
            raise YouTubeError("That profile isn't on this TV any more.")
        with self.lock:
            self.profile = prof or {}
            self.cache.clear()
        self.auth.set_last_profile(self.profile.get("id", "") or "guest")
        return {"profile": self.profile or None}

    def refresh_channels(self) -> None:
        """Brand accounts come and go, names and pictures change: read every account's channels again."""
        from couchbox.services import ytauth

        for a in self.auth.accounts():
            try:
                chans = self.accounts_list(self.auth.token(a["id"]))
                self.auth.save_channels(a["id"], chans)
                prof = self.profile
                if prof and prof.get("account") == a["id"]:  # the one watching now: its Premium at once
                    now = self.find_profile(prof["id"]) or {}
                    prof["premium"] = bool(prof.get("premium") or now.get("premium"))
                    prof["membership"] = now.get("membership", "")
            except ytauth.SignedOut:
                self.on_event("signedOut", {"account": a["id"], "name": a.get("name", "")})
            except Exception:
                pass

    def accounts_list(self, token: str) -> list[dict[str, Any]]:
        body = {"accountReadMask": {"returnOwner": True, "returnBrandAccounts": True, "returnPersonaAccounts": False}}
        return parse_accounts(self._post("account/accounts_list", body, token=token))

    # ---------------------------------------------------------------- requests
    def _post(self, ep: str, body: dict[str, Any], token: str = "", page: str = "", as_client: dict | None = None) -> dict[str, Any]:
        client = dict(self.client, **{k: v for k, v in (as_client or {}).items() if k != "clientNameId"})
        if self.visitor:
            client["visitorData"] = self.visitor
        context: dict[str, Any] = {"client": client}
        if page:
            context["user"] = {"onBehalfOfUser": page}  # a brand account of the signed-in Google account
        headers = {"X-Goog-Visitor-Id": self.visitor} if self.visitor else {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if as_client:  # another client's: its own name (number), version and user agent in the headers
            headers.update({"X-YouTube-Client-Version": client.get("clientVersion", "")})
            if client.get("userAgent"):
                headers["User-Agent"] = client["userAgent"]
            if as_client.get("clientNameId"):
                headers["X-YouTube-Client-Name"] = as_client["clientNameId"]
        r = self.s.post(f"{API}/{ep}?prettyPrint=false", json={"context": context, **body}, headers=headers, timeout=TIMEOUT)
        if r.status_code >= 400:
            try:  # YouTube's reason, for the log (its error message: no tokens in it)
                why = (r.json().get("error") or {}).get("message") or ""
            except ValueError:
                why = ""
            print(f"yt {ep}: {r.status_code} {str(why)[:200]}", flush=True)
            raise YouTubeError(f"YouTube said {r.status_code} ({ep})", r.status_code)
        data = r.json()
        vd = dig(data, "responseContext", "visitorData")
        if vd and vd != self.visitor and not token:
            self.visitor = vd
            self._write("visitor.json", {"visitorData": vd})
        return data

    def call(self, ep: str, body: dict[str, Any], cache: bool = True, as_client: dict | None = None) -> dict[str, Any]:
        prof = self.profile
        key = prof.get("id", "") + ep + json.dumps(body, sort_keys=True) + json.dumps(as_client or {})
        hit = self.cache.get(key)
        if cache and hit and time.time() - hit[0] < CACHE_SECONDS:
            return hit[1]
        if prof:
            token = self.auth.token(prof["account"])
            try:
                data = self._post(ep, body, token, prof.get("pageId", ""), as_client)
            except YouTubeError as err:
                if err.args[1:] != (401,):
                    raise
                self.auth.expire(prof["account"])  # refused: renew it once
                data = self._post(ep, body, self.auth.token(prof["account"]), prof.get("pageId", ""), as_client)
            if ep == "browse" and not prof.get("premium") and is_premium(data):
                prof["premium"] = True
                self.auth.set_premium(prof["account"], True)
        else:
            data = self._post(ep, body, as_client=as_client)
        if cache:  # (only what may be read back: a watch page's or a player's answer is kept by no one)
            with self.lock:
                if len(self.cache) > 120:
                    self.cache.clear()
                self.cache[key] = (time.time(), data)
        return data

    def changed(self) -> None:
        """Something was liked, saved or subscribed to: pages show it next time."""
        with self.lock:
            self.cache.clear()

    def need_profile(self, what: str) -> None:
        if not self.profile:
            raise YouTubeError(f"Sign in to {what}.")

    # ---------------------------------------------------------------- pages
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
        if page["shelves"] or self.profile:
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

    def channel(self, channel_id: str, params: str = "") -> dict[str, Any]:
        body = {"browseId": channel_id}
        if params:
            body["params"] = params
        resp = self.call("browse", body)
        page = parse_page(resp)
        if not page["header"]:
            page["header"] = {"title": "", "avatar": "", "banner": "", "lines": [], "description": ""}
        if not page["header"].get("description"):  # the TV's header has none: the channel's metadata's
            md = next(_find(resp, "channelMetadataRenderer"), None) or {}
            desc = md.get("description") if isinstance(md, dict) else ""
            if not desc:
                desc = next(
                    (d for d in _find(resp.get("metadata") or resp.get("microformat") or {}, "description") if isinstance(d, str)), ""
                )
            page["header"]["description"] = " ".join(str(desc or "").split())[:300]
        return page

    def subscriptions(self) -> dict[str, Any]:
        self.need_profile("see your subscriptions")
        return parse_subscriptions(self.call("browse", {"browseId": "FEsubscriptions"}))

    def library(self) -> dict[str, Any]:
        self.need_profile("see your library")
        page = self.browse("FElibrary")
        # the tiles are the app's own (History, Watch later...): leave out a shelf of the same
        page["shelves"] = [s for s in page["shelves"] if not all(i["type"] == "browse" for i in s["items"])]
        page["tiles"] = [{"title": t, "id": b, "colors": c} for t, b, c in LIBRARY_TILES]
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

    def signature_timestamp(self) -> int:
        """The current player JS's signatureTimestamp (its version, as /player wants it), kept an hour."""
        if getattr(self, "_sts", (0, 0))[0] > time.time():
            return self._sts[1]
        sts = 0
        try:
            js = self.s.get("https://www.youtube.com/iframe_api", timeout=TIMEOUT).text
            ver = re.search(r"player\\?/([0-9a-fA-F]{8})\\?/", js)
            if ver:
                base = self.s.get(f"https://www.youtube.com/s/player/{ver.group(1)}/player_ias.vflset/en_US/base.js", timeout=TIMEOUT).text
                m = re.search(r"(?:signatureTimestamp|sts)\s*:\s*(\d{5})", base)
                sts = int(m.group(1)) if m else 0
        except requests.RequestException:
            pass
        self._sts = (time.time() + 3600, sts)
        return sts

    # ---------------------------------------------------------------- the box check's cleanup
    def history_today(self, newest: int = 0) -> list[dict[str, Any]]:
        """History's entries watched today, as YouTube's TV app lists them, with each one's "Remove
        from watch history" (its feedback token, from the entry's own menu): [{id, title, shelf,
        token, label}] (token "" when the entry carries no such option). A History without days
        (one grid): its `newest` first entries instead."""
        self.need_profile("see your history")
        resp = self.call("browse", {"browseId": "FEhistory"}, cache=False)
        out = []

        def labels(o):
            return " ".join(text(v) for k, v in o.items() if k in ("text", "title", "label") and isinstance(v, (dict, str)))

        def removal(tile):
            for f in _find(tile, "feedbackEndpoint"):
                tok = (f or {}).get("feedbackToken")
                if tok:
                    return tok
            return ""

        def menu_label(tile):
            for item in _find(tile, "menuServiceItemRenderer"):
                if (json.dumps(item).find("feedbackEndpoint")) >= 0:
                    return text(item.get("text"))
            return ""

        def entry(tile, where):
            t = parse_tile(tile)
            if t and t.get("type") in ("video", "live", "short"):
                out.append({"id": t["id"], "title": t["title"], "shelf": where, "token": removal(tile), "label": menu_label(tile)})

        shelves = list(_find(resp, "shelfRenderer"))
        titles = [text(dig(s, "headerRenderer", "shelfHeaderRenderer", "title") or s.get("title")).strip() for s in shelves]
        if any(t.lower() in ("today", "yesterday") for t in titles):
            for shelf, title in zip(shelves, titles, strict=True):
                if title.lower() == "today":
                    for tile in _find(shelf, "tileRenderer"):
                        entry(tile, title)
        else:
            for tile in list(_find(resp, "tileRenderer"))[:newest]:
                entry(tile, f"the {newest} newest")
        return out

    def remove_from_history(self, token: str) -> bool:
        resp = self.call("feedback", {"feedbackTokens": [token]}, cache=False)
        self.changed()
        return bool(dig(resp, "feedbackResponses", 0, "isProcessed"))

    def edit_playlist(self, edit: dict[str, Any], add: bool = True) -> dict[str, Any]:
        """A menu's own playlist edit (its Save to Watch later), sent as the TV app sends it; add
        False: the same, taking the video out again."""
        self.need_profile("save videos")
        body = {k: edit[k] for k in ("playlistId", "actions", "params") if k in edit}
        if not add:
            body["actions"] = [
                {"action": "ACTION_REMOVE_VIDEO_BY_VIDEO_ID", "removedVideoId": a.get("addedVideoId", "")}
                for a in body.get("actions") or []
            ]
        self.call("browse/edit_playlist", body, cache=False)
        self.changed()
        return {"saved": add}

    def menu_probe(self) -> dict[str, Any]:
        """The first Home video's menu as this profile gets it, for wiring the card menu: each
        entry's renderer, words, icon and the endpoints in it (their names, never tokens)."""
        resp = self.call("browse", {"browseId": "FEwhat_to_watch"}, cache=False)
        lines = None  # a part-watched card's lines as YouTube sends them (each item: text or badge)
        for t in _find(resp, "tileRenderer"):
            if isinstance(t, dict) and lines is None and "thumbnailOverlayResumePlaybackRenderer" in json.dumps(t.get("header") or {}):
                meta = dig(t, "metadata", "tileMetadataRenderer") or {}
                lines = [
                    [
                        {"text": text((li.get("lineItemRenderer") or {}).get("text"))[:60]}
                        if "text" in (li.get("lineItemRenderer") or {})
                        else {
                            "badge": dig(li, "lineItemRenderer", "badge", "metadataBadgeRenderer", "label") or "",
                            "style": dig(li, "lineItemRenderer", "badge", "metadataBadgeRenderer", "style") or "",
                        }
                        for li in dig(line, "lineRenderer", "items") or []
                    ]
                    for line in meta.get("lines") or []
                ]
        for t in _find(resp, "tileRenderer"):
            if isinstance(t, dict) and t.get("contentType") == "TILE_CONTENT_TYPE_VIDEO":
                cmd = t.get("onLongPressCommand") or {}
                entries = []
                for e in menu_entries(cmd):
                    found = sorted(
                        {k for k in json.dumps(e["entry"]).replace('"', " ").split() if k.endswith("Endpoint") or k.endswith("Command")}
                    )
                    entries.append({"label": e["label"], "icon": e["icon"], "keys": sorted(e["entry"]), "endpoints": found})
                return {"top": sorted(cmd), "menu": sorted(cmd.get("showMenuCommand") or {}), "entries": entries, "partWatchedLines": lines}
        return {"entries": [], "note": "no video tile on Home"}

    def feedback(self, token: str) -> dict[str, Any]:
        """A card menu's Not interested, Don't recommend channel or Remove from watch history."""
        self.need_profile("tell YouTube what you'd rather not see")
        return {"ok": self.remove_from_history(token)}

    def create_playlist(self, title: str, video_id: str) -> dict[str, Any]:
        """A new private playlist with this video in it."""
        self.need_profile("make playlists")
        resp = self.call(
            "playlist/create", {"title": title, "videoIds": [video_id] if video_id else [], "privacyStatus": "PRIVATE"}, cache=False
        )
        self.changed()
        return {"id": resp.get("playlistId", ""), "title": title}

    def page_probe(self, browse_id: str) -> dict[str, Any]:
        """A page's outline as this profile gets it, for finding what isn't shown: the surface's
        own keys, and each section's renderers, shelf type, title, first items' kinds and how
        many shelves it gave (0: dropped). Names only: no tokens, no addresses."""
        resp = self.call("browse", {"browseId": browse_id}, cache=False)
        surface = dig(resp, "contents", "tvBrowseRenderer", "content", "tvSurfaceContentRenderer") or {}
        out = {
            "surface": sorted(surface),
            "header": sorted(surface.get("header") or {}),
            "sections": [],
            "headerOutline": outline(surface.get("header") or resp.get("header") or {}),
            "metadata": sorted(resp.get("metadata") or {}),
        }
        for s in section_list(resp).get("contents") or []:
            if not isinstance(s, dict):
                continue
            r = s.get("shelfRenderer") or {}
            lst = r.get("content") or {}
            lst = next(iter(lst.values()), {}) if isinstance(lst, dict) and lst else {}
            items = (lst.get("items") or []) if isinstance(lst, dict) else []
            first = items[0] if items and isinstance(items[0], dict) else {}
            inner = next(iter(first.values()), {}) if first else {}
            out["sections"].append(
                {
                    "keys": sorted(s),
                    "type": r.get("tvhtml5ShelfRendererType", ""),
                    "title": shelf_title(r)[0] if r else "",
                    "list": sorted(r.get("content") or {}) if r else [],
                    "items": [next(iter(i), "") for i in items[:3] if isinstance(i, dict)],
                    "first": {k: inner.get(k) for k in ("style", "contentType") if isinstance(inner, dict) and k in inner},
                    "outline": outline(inner) if not parse_shelf(s) else None,  # a dropped one's first item: its shape
                    "kept": 0 if any(k in AD_RENDERERS for k in s) else len(parse_shelf(s)),
                }
            )
        return out

    def premium_probe(self) -> dict[str, Any]:
        """How this profile's answers mark Premium (where they say "premium"): its accounts list
        and a Home and History page."""
        self.need_profile("look")
        token = self.auth.token(self.profile["account"])
        acc = self._post(
            "account/accounts_list",
            {"accountReadMask": {"returnOwner": True, "returnBrandAccounts": True, "returnPersonaAccounts": False}},
            token=token,
        )
        out = {"detected": bool(self.profile.get("premium")), "accounts_list": premium_hints(acc)}
        for name, bid in (("home", "FEtopics"), ("library", "FElibrary"), ("history", "FEhistory")):
            try:
                out[name] = premium_hints(self.call("browse", {"browseId": bid}, cache=False))
            except YouTubeError as err:
                out[name] = [f"({err.args[0]})"]
        return out

    def player_probe(self, video_id: str, clients: dict[str, dict] | None = None) -> dict[str, Any]:
        """player_one as the app's own client and as each of clients (yt-dlp's: name -> context)."""
        out = {"app": self.player_one(video_id)}
        for name, c in (clients or {}).items():
            try:
                out[name] = self.player_one(video_id, c)
            except YouTubeError as err:
                out[name] = {"error": str(err.args[0])}
        return out

    def player_one(self, video_id: str, as_client: dict | None = None) -> dict[str, Any]:
        """What YouTube's /player says to this TV for a video, as the profile watching (its sign-in):
        whether it plans ads (the gap before DASH opens), and its formats (ciphered or not). For
        measuring: no addresses or tokens in the answer."""
        body = {"videoId": video_id, "racyCheckOk": True, "contentCheckOk": True}
        sts = self.signature_timestamp()
        if sts:  # the player JS version the answer must suit (without it: "The page needs to be reloaded")
            body["playbackContext"] = {"contentPlaybackContext": {"signatureTimestamp": sts, "html5Preference": "HTML5_PREF_WANTS"}}
        resp = self.call("player", body, cache=False, as_client=as_client)
        sd = resp.get("streamingData") or {}
        fmts = sd.get("adaptiveFormats") or []
        h264 = [f for f in fmts if "avc1" in (f.get("mimeType") or "")]
        return {
            "signedIn": bool(self.profile),
            "premium": bool(self.profile.get("premium")) if self.profile else False,
            "client": (as_client or self.client).get("clientName", "") + " " + (as_client or self.client).get("clientVersion", ""),
            "sts": sts,
            "playability": dig(resp, "playabilityStatus", "status") or "",
            "reason": dig(resp, "playabilityStatus", "reason") or "",
            "adPlacements": len(resp.get("adPlacements") or []),
            "playerAds": len(resp.get("playerAds") or []),
            "adaptiveFormats": len(fmts),
            "h264": sorted({f.get("itag") for f in h264}),
            "ciphered": sum(1 for f in fmts if "signatureCipher" in f or "cipher" in f),
            "plainUrls": sum(1 for f in fmts if "url" in f),
            "hls": bool(sd.get("hlsManifestUrl")),
            "serverAbr": bool(sd.get("serverAbrStreamingUrl")),
            "expiresInSeconds": sd.get("expiresInSeconds"),
        }

    def watch(self, video_id: str) -> dict[str, Any]:
        out = parse_watch(self.call("next", {"videoId": video_id}, cache=False))
        out["signedIn"] = bool(self.profile)
        return out

    def comments(self, token: str) -> dict[str, Any]:
        return parse_comments(self.call("next", {"continuation": token}))

    def shorts(self, params: str = "", token: str = "") -> dict[str, Any]:
        """The Shorts to play: a sequence (the guide's Shorts, or after one), then its continuation."""
        body = {"continuation": token} if token else {"sequenceParams": params or SHORTS_PARAMS}
        return parse_short_sequence(self.call("reel/reel_watch_sequence", body, cache=False))

    def short(self, video_id: str) -> dict[str, Any]:
        return parse_short(self.call("reel/reel_item_watch", {"playerRequest": {"videoId": video_id}, "params": "CAUwAg%3D%3D"}))

    # ---------------------------------------------------------------- actions (signed in)
    def like(self, video_id: str, status: str) -> dict[str, Any]:
        """status: like | dislike | none."""
        self.need_profile({"like": "like videos", "dislike": "dislike videos"}.get(status, "rate videos"))
        ep = {"like": "like/like", "dislike": "like/dislike"}.get(status, "like/removelike")
        self.call(ep, {"target": {"videoId": video_id}}, cache=False)
        self.changed()
        return {"like": status}

    def subscribe(self, channel_id: str, on: bool) -> dict[str, Any]:
        self.need_profile("subscribe")
        self.call("subscription/subscribe" if on else "subscription/unsubscribe", {"channelIds": [channel_id]}, cache=False)
        self.changed()
        return {"subscribed": on}

    def notify(self, params: str, level: str) -> dict[str, Any]:
        self.need_profile("choose notifications")
        self.call("notification/modify_channel_preference", {"params": params}, cache=False)
        return {"notify": level}

    def save_options(self, video_id: str) -> dict[str, Any]:
        self.need_profile("save videos")
        out = parse_save_options(self.call("playlist/get_add_to_playlist", {"videoIds": [video_id]}, cache=False))
        if not any(p["id"] == "WL" for p in out):
            out.insert(0, {"id": "WL", "title": "Watch later", "saved": False})
        return {"playlists": out}

    def save(self, video_id: str, playlist_id: str, add: bool) -> dict[str, Any]:
        self.need_profile("save videos")
        action = (
            {"action": "ACTION_ADD_VIDEO", "addedVideoId": video_id}
            if add
            else {"action": "ACTION_REMOVE_VIDEO_BY_VIDEO_ID", "removedVideoId": video_id}
        )
        self.call("browse/edit_playlist", {"playlistId": playlist_id, "actions": [action]}, cache=False)
        self.changed()
        return {"saved": add}

    # ---------------------------------------------------------------- history and resume
    def report(self, video_id: str, cpn: str, event: str, position: float, duration: float) -> dict[str, Any]:
        """Tell YouTube what's watched, as its TV player does, so History, "resume where you left
        off" and recommendations follow on every device. event: start (the player's reporting
        addresses are fetched), progress (every few seconds), pause, end. Guests report nothing."""
        if not self.profile:
            return {"ok": False}
        sess = self.sessions.get(cpn)
        if event == "start" or sess is None:
            resp = self.call("player", {"videoId": video_id, "racyCheckOk": True, "contentCheckOk": True}, cache=False)
            sess = {"urls": tracking(resp), "last": position, "t0": time.time(), "started": False}
            self.sessions = {k: v for k, v in self.sessions.items() if time.time() - v["t0"] < 6 * 3600}
            self.sessions[cpn] = sess
        token = self.auth.token(self.profile["account"])
        base = {"ver": "2", "cpn": cpn, "cmt": f"{position:.3f}", "len": f"{duration:.3f}"}
        if not sess["started"] and sess["urls"]["playback"]:
            self._ping(sess["urls"]["playback"], base, token)  # into History
            sess["started"] = True
        if event != "start" and sess["urls"]["watchtime"]:
            q = dict(
                base,
                st=f"{min(sess['last'], position):.3f}",
                et=f"{position:.3f}",
                rt=f"{time.time() - sess['t0']:.3f}",
                state="paused" if event in ("pause", "end") else "playing",
            )
            if event == "end":
                q["final"] = "1"
            self._ping(sess["urls"]["watchtime"], q, token)  # the resume point and watch time
        sess["last"] = position
        return {"ok": True}

    def _ping(self, url: str, query: dict[str, str], token: str) -> None:
        try:
            self.s.get(url, params=query, headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT)
        except requests.RequestException:
            pass  # the next report tries again

    # ---------------------------------------------------------------- the guest's searches
    def searches(self) -> list[str]:
        return self._read("searches.json").get("recent", [])

    def remember_search(self, q: str) -> None:
        q = q.strip()
        if not q:
            return
        recent = [s for s in self.searches() if s.lower() != q.lower()]
        self._write("searches.json", {"recent": [q, *recent][:20]})


# The guide's Shorts: YouTube's TV app asks for this sequence (reelWatchEndpoint.params)
SHORTS_PARAMS = "CA8%3D"
# Library's tiles (as YouTube's TV app has them): title, what they open, their two colours
LIBRARY_TILES = [
    ("History", "FEhistory", ["#3b0ca3", "#7a3fe0"]),
    ("Watch later", "VLWL", ["#005f7f", "#0098c7"]),
    ("Playlists", "FEplaylist_aggregation", ["#00785a", "#005040"]),
    ("Music", "VLLM", ["#8a2a00", "#e8520a"]),
    ("Movies & TV", "FEstorefront", ["#7a5600", "#d6a10a"]),
    ("Podcasts", "FEtopics_podcasts", ["#6a0f6a", "#b0209a"]),
]


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


DEMO_PROFILES = [
    {"id": "demo1:", "account": "demo1", "pageId": "", "name": "Robin Vale", "handle": "@robinvale", "photo": "", "premium": True},
    {
        "id": "demo1:brand1",
        "account": "demo1",
        "pageId": "brand1",
        "name": "Juniper Hollow",
        "handle": "@juniperhollow",
        "photo": "",
        "premium": True,
    },
    {"id": "demo2:", "account": "demo2", "pageId": "", "name": "Kit Marlow", "handle": "@kitmarlow", "photo": "", "premium": True},
]


class Demo(YouTube):
    """Made-up profiles, channels and videos for the screenshots (no network). Thumbnails are left
    out: the cards draw a gradient with the title instead. Signed in as the first profile unless
    told otherwise (use())."""

    def __init__(self, profile: str = "demo1:"):
        self.dir = ""
        self.client = dict(TV_CLIENT, hl="en", gl="US")
        self.recent = ["paper bridge", "coastal trail", "sourdough"]
        self.profile = next((dict(p) for p in DEMO_PROFILES if p["id"] == profile), {})
        self.state = {"likes": {}, "subs": {DEMO_CHANNELS[0][0]: "personalized"}, "saved": {"WL": set()}}
        self.on_event = lambda name, data: None
        self.code_state = "idle"

    def profiles(self):
        return {
            "profiles": [dict(p) for p in DEMO_PROFILES],
            "last": self.profile.get("id", "guest"),
            "current": self.profile.get("id", ""),
        }

    def use(self, pid):
        self.profile = next((dict(p) for p in DEMO_PROFILES if p["id"] == pid), {})
        return {"profile": self.profile or None}

    def refresh_channels(self):
        pass

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
            progress=(0.35 if n % 4 == 2 else 0.0) if self.profile else 0.0,
            live=kind == "live",
            channelId=cid,
        )
        if self.profile:  # the menu's feedback options (made up: the demo's feedback does nothing)
            it["feedback"] = [
                {"kind": "not_interested", "label": "Not interested", "token": "demo"},
                {"kind": "no_channel", "label": "Don't recommend channel", "token": "demo"},
            ]
        if kind == "live":
            it["lines"][1] = f"{(n * 11) % 90 + 3}K watching"
        return it

    def _shelf(self, title, start, n=8, kind="video", subtitle=""):
        return {"title": title, "subtitle": subtitle, "items": [self._video(start + i, kind) for i in range(n)], "more": ""}

    def home(self):
        if not self.profile:
            return {
                "shelves": [self._shelf("Trending", 4), self._shelf("Live now", 16, kind="live")],
                "more": "",
                "nudge": {"title": "Make YouTube your own", "subtitle": "Sign in to see the latest videos tailored to your interests."},
                "header": None,
            }
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
        if browse_id in ("FEhistory", "VLWL", "FEplaylist_aggregation", "VLLM"):
            title = {"FEhistory": "History", "VLWL": "Watch later", "FEplaylist_aggregation": "Playlists", "VLLM": "Liked music"}[browse_id]
            shelf = self._shelf(title, 3, n=11)
            shelf["grid"] = True
            if browse_id == "FEhistory":
                for it in shelf["items"]:
                    it.setdefault("feedback", []).insert(
                        0, {"kind": "remove_history", "label": "Remove from watch history", "token": "demo"}
                    )
            return {"shelves": [shelf], "more": "", "nudge": None, "header": None}
        label = next((g[1] for g in GUIDE if g[2] == browse_id), "Videos")
        n = sum(map(ord, browse_id)) % 20
        if browse_id == "FEtopics_movies":
            films = self._shelf("Top selling", 30, n=8)
            for k, it in enumerate(films["items"]):
                it.update(
                    shape="poster",
                    badges=["Buy", "PG-13" if k % 2 else "PG"],
                    lines=[f"Drama • {2020 + k}", "A made-up film for the screenshots, about a lighthouse keeper and a very long winter."],
                )
            films["hero"] = True
            nets = {
                "title": "Channels",
                "subtitle": "",
                "more": "",
                "items": [
                    item(type="browse", id=f"FEdemo{k}", title=t, shape="round")
                    for k, t in enumerate(["Harbor TV", "Northwind", "Atlas Films", "Juniper+"])
                ],
            }
            return {"shelves": [films, nets, self._shelf("Free with ads", 40)], "more": "", "nudge": None, "header": None}
        if browse_id == "FEtopics_music":
            albums = self._shelf("Albums for you", 50, n=8)
            for it in albums["items"]:
                it.update(shape="square", duration="")
            clips = self._shelf("Music videos", 44)
            for it in clips["items"]:
                it["music"] = True
            return {"shelves": [clips, albums], "more": "", "nudge": None, "header": None}
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

    def channel(self, channel_id, params=""):
        i = next((k for k, c in enumerate(DEMO_CHANNELS) if c[0] == channel_id), 0)
        cid, name, handle, subs = DEMO_CHANNELS[i]
        return {
            "shelves": [
                self._shelf("Videos", i),
                self._shelf("Popular", i + 6),
                {
                    "title": "Channels",
                    "subtitle": "",
                    "more": "",
                    "items": [item(type="channel", id=c, title=t, lines=[h, s]) for c, t, h, s in DEMO_CHANNELS if c != cid],
                },
                self._shelf("Shorts", i + 3, kind="short"),
            ],
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

    def subscriptions(self):
        self.need_profile("see your subscriptions")
        chans = [{"title": "All", "thumb": "", "id": "", "params": "", "section": "", "new": False}]
        for k, (cid, name, _h, _s) in enumerate(DEMO_CHANNELS):
            chans.append({"title": name, "thumb": "", "id": cid, "params": "", "section": "A-Z" if k == 3 else "", "new": k % 2 == 0})
        grid = self._shelf("", 12, n=9)
        grid["grid"] = True
        return {"channels": chans, "page": {"shelves": [self._shelf("Most relevant", 2), grid], "more": "", "nudge": None, "header": None}}

    def library(self):
        self.need_profile("see your library")
        return {
            "shelves": [
                self._shelf("History", 1),
                self._shelf("Watch later", 6, subtitle="Videos you've added"),
                self._shelf("Liked videos", 9),
            ],
            "more": "",
            "nudge": None,
            "header": None,
            "tiles": [{"title": t, "id": b, "colors": c} for t, b, c in LIBRARY_TILES],
        }

    def search(self, query):
        cid, name, handle, subs = DEMO_CHANNELS[0]
        first = [self._video(0), item(type="channel", id=cid, title=name, lines=[handle, subs])] + [self._video(i) for i in range(1, 8)]
        hero = {
            "title": "",
            "subtitle": "",
            "items": [self._video(10)],
            "more": "",
            "pill": {"title": name, "avatar": "", "icon": "", "target": {"type": "channel", "id": cid}},
        }
        recent = self._shelf("", 11, n=6)
        recent["pill"] = {
            "title": "Recently uploaded",
            "avatar": "",
            "icon": "search",
            "target": {"type": "search", "id": f"{name} videos"},
        }
        cluster = {
            "title": "",
            "subtitle": "",
            "items": hero["items"] + recent["items"],
            "more": "",
            "cluster": {"hero": hero, "list": recent},
        }
        return {
            "shelves": [
                {"title": f"Search results for {query}", "subtitle": "", "items": first, "more": ""},
                cluster,
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
        cid, name, handle, subs = DEMO_CHANNELS[n % len(DEMO_CHANNELS)]
        level = self.state["subs"].get(cid, "")
        return {
            "video": {
                "id": v["id"],
                "title": v["title"],
                "channel": name,
                "channelId": cid,
                "handle": handle,
                "avatar": "",
                "subscribers": subs,
                "subscribed": bool(level) and bool(self.profile),
                "views": v["lines"][1].split(" • ")[0],
                "date": DEMO_AGES[n % len(DEMO_AGES)],
                "live": False,
                "like": self.state["likes"].get(video_id, "none") if self.profile else "none",
                "likes": 1200 + n,
                "notify": level if self.profile else "",
                "notifyOptions": [
                    {"level": "all", "label": "All", "params": "all"},
                    {"level": "personalized", "label": "Personalized", "params": "personalized"},
                    {"level": "none", "label": "None", "params": "none"},
                ],
            },
            "related": [self._video(n + 1 + i) for i in range(9)],
            "next": f"demo{n + 1:07d}",
            "start": 0,
            "signedIn": bool(self.profile),
            "details": {
                "facts": [
                    {"value": f"{1 + n % 9}.{n % 10}K", "label": "Likes"},
                    {"value": f"{(n * 37) % 900 + 12},{n % 1000:03d}", "label": "Views"},
                    {"value": "Nov 2", "label": "2026"},
                ],
                "text": "We tried it so you don't have to. Notes, sources and the full parts list are on our site.\n\n0:00 Intro\n8:34 The question",
                "summary": "A made-up summary for the screenshots: the team tries, fails, and tries again, and explains what changed.",
                "comments": "1.2K",
                "teaser": {"author": "@quietviewer", "text": "The part where it finally works made my week.", "photo": ""},
                "commentsToken": "demo-comments",
            },
            "chapters": []
            if n % 10 == 9  # ...9: no chapters (demo_stream)
            else [
                {"title": t, "start": i * 514.0, "thumb": ""}
                for i, t in enumerate(["Intro", "The question", "First try", "What went wrong", "Second try", "The answer", "Wrapping up"])
            ],
            "countdown": 5,
        }

    def comments(self, token):
        names = ["@quietviewer", "@marlin.k", "@sundaybaker", "@trailmix", "@orbitfan", "@notabot"]
        texts = [
            "The part where it finally works made my week.",
            "I've watched this three times now.",
            "Can you do one about clocks next?",
            "Love how honest the failures are.",
            "The diagram at 12:40 explained it better than my teacher did.",
            "First!",
        ]
        return {
            "items": [
                {
                    "author": a,
                    "photo": "",
                    "text": t,
                    "time": f"{k + 1} days ago",
                    "likes": f"{(k + 3) * 41}",
                    "replies": 0 if token.startswith("demo-replies") else k % 3,
                    "pinned": k == 0 and not token.startswith("demo-replies"),
                    **({"repliesToken": f"demo-replies-{k}"} if k % 3 and not token.startswith("demo-replies") else {}),
                }
                for k, (a, t) in enumerate(zip(names, texts, strict=True))
                if not token.startswith("demo-replies") or k < 3
            ],
            "more": "",
        }

    def shorts(self, params="", token=""):
        if token:
            return {"items": [], "more": ""}
        return {
            "items": [
                {"type": "short", "id": f"demo{100 + k:07d}", "thumb": "", "color": c}
                for k, c in enumerate(["#3b2f29", "#1f3340", "#3a2440", "#20382a"])
            ],
            "more": "",
        }

    def short(self, video_id):
        n = int(video_id[4:]) if video_id[4:].isdigit() else 0
        cid, name, handle, _subs = DEMO_CHANNELS[n % len(DEMO_CHANNELS)]
        return {
            "title": DEMO_TITLES[n % len(DEMO_TITLES)] + " #shorts",
            "handle": handle,
            "avatar": "",
            "channelId": cid,
            "subscribed": cid in self.state["subs"],
            "age": "2 days ago",
            "like": "none",
            "likes": 1200,
        }

    def like(self, video_id, status):
        self.need_profile("rate videos")
        self.state["likes"][video_id] = status
        return {"like": status}

    def subscribe(self, channel_id, on):
        self.need_profile("subscribe")
        if on:
            self.state["subs"][channel_id] = "personalized"
        else:
            self.state["subs"].pop(channel_id, None)
        return {"subscribed": on}

    def notify(self, params, level):
        self.need_profile("choose notifications")
        return {"notify": level}

    def save_options(self, video_id):
        self.need_profile("save videos")
        names = [("WL", "Watch later"), ("PLdemo1", "Road trip"), ("PLdemo2", "Bread experiments"), ("PLdemo3", "Watch with the kids")]
        return {"playlists": [{"id": k, "title": t, "saved": video_id in self.state["saved"].get(k, set())} for k, t in names]}

    def save(self, video_id, playlist_id, add):
        self.need_profile("save videos")
        got = self.state["saved"].setdefault(playlist_id, set())
        (got.add if add else got.discard)(video_id)
        return {"saved": add}

    def feedback(self, token):
        self.need_profile("tell YouTube what you'd rather not see")
        return {"ok": True}

    def edit_playlist(self, edit, add=True):
        return self.save(((edit.get("actions") or [{}])[0]).get("addedVideoId", ""), "WL", add)

    def create_playlist(self, title, video_id):
        self.need_profile("make playlists")
        self.state["saved"].setdefault("PLdemonew", set()).add(video_id)
        return {"id": "PLdemonew", "title": title}

    def report(self, video_id, cpn, event, position, duration):
        return {"ok": bool(self.profile)}

    def searches(self):
        return list(self.recent)

    def remember_search(self, q):
        self.recent = [q, *[s for s in self.recent if s != q]][:20]


def demo_stream(video_id: str) -> dict[str, Any]:
    """The demo's "stream": nothing to play (the stand-in video), with chapters to draw. A "demobot..."
    video gets YouTube's bot check, as a guest's can (screenshots)."""
    if video_id.startswith("demobot"):
        from couchbox.services import ytstream

        raise ytstream.Unavailable(ytstream.friendly("Sign in to confirm you’re not a bot"))
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
        # ...9: a video without chapters (the bar shows the storyboard's frame instead; none in the demo)
        "chapters": []
        if n % 10 == 9
        else [{"start": i * 3600 / len(names) + (i * 97) % 200 * (1 if i else 0), "title": t} for i, t in enumerate(names)],
        "storyboard": None,
        "captions": [
            {"lang": "en", "name": "English", "url": "demo://captions/en", "auto": False},
            {"lang": "en", "name": "English (auto-generated)", "url": "demo://captions/en-auto", "auto": True},
        ],
        "heights": [1080, 720, 480, 360, 240, 144],
        "maxHeight": 1080,
        "views": 0,
        "likes": 0,
        "timestamp": 0,
        "portrait": n >= 100,
        "took": 0,
    }
