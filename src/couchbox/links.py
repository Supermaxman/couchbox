"""Links sent to the TV: "Send to TV" on the phone page, the iPhone Shortcut (couchbox-phone's
POST /send) and the voice assistant's "open this address". What app a link belongs to, and
opening it there.

  parse(text)        -> Link: the first http(s) address in text, checked and tidied, and where
                        it goes. No network, so real-world link shapes are easy to test
  open_link(text)    -> Result: opens it on the TV and says what happened, for the phone

Where links go:
  YouTube     watch, youtu.be, shorts, live, embed (also m., music. and youtube-nocookie), with
              t= / start= timestamps and playlists; playlist pages, channels (/channel/UC..,
              /@handle, /c/, /user/), searches. Played in the YouTube app: Couchbox's own
              through its control socket (a video in a playlist plays on its own there), or
              VacuumTube (the tile's fallback) through its command router, as the voice tools do
  Twitch      twitch.tv/<channel> (live, else the channel's page), /videos/<id>, clips
              (clips.twitch.tv/<slug>, twitch.tv/<channel>/clip/<slug>), player.twitch.tv
  Nebula      nebula.tv/videos/<slug>, nebula.tv/<channel>
  Dropout,    <site>/<series>[/season:N][/videos/<slug>], <site>/videos/<slug>. VHX ids are
  2nd Try     numbers, so slugs are looked up through the app's own search
  Jellyfin    an item's page (#/details?id=...) on the server in Settings → Apps, or any
              Jellyfin web address that names its server (serverId=, a phone may know the
              server by another name): played in Jellyfin from where it was left
  anything    else opens in the Search app's web view. Never the box itself (localhost,
  else        127.x, link-local): the TV apps' DevTools ports are there

Addresses are never handed to a shell, only to DevTools calls (as JSON) and the apps' control
sockets (couchbox.appctl).
"""

import ipaddress
import re
import socket
import urllib.parse
from dataclasses import dataclass

MAX_LEN = 4096  # of the text a link is taken from


class BadLink(ValueError):
    """A link that can't be sent; the message is for the person who sent it."""


class OpenFailed(RuntimeError):
    """The link is fine but the TV couldn't open it; the message says why."""


@dataclass(frozen=True)
class Link:
    app: str  # youtube, twitch, nebula, dropout, 2ndtry, jellyfin, web
    kind: str  # what id is: video, playlist, channel, handle, search, live, vod, clip, series, item, page, home
    id: str = ""
    url: str = ""  # the tidied address
    start: int = 0  # seconds into the video (YouTube timestamps)
    playlist: str = ""  # YouTube: the playlist a video plays in


@dataclass(frozen=True)
class Result:
    ok: bool
    message: str
    app: str = ""


# ------------------------------------------------------------------ the address

_URL_IN_TEXT = re.compile(r"https?://[^\s<>\"]+", re.I)
_BARE = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}(?::\d{1,5})?(?:[/?#]\S*)?", re.I)
_TRAIL = ".,;:!?)]}>'\"”’»"  # punctuation after a link in a sentence
_SAFE = "/%:@!$&'()*+,;=-._~"
_HOST = re.compile(r"[a-z0-9_]([a-z0-9_.-]*[a-z0-9_])?")


def normalise(text):
    """The first http(s) address in text (a share often comes as "Title https://..."), tidied:
    lower-case scheme and host, no user name or password, other characters %-escaped. Text
    that is only an address without https:// gets it. BadLink if there's no usable address."""
    if not isinstance(text, str):
        raise BadLink("That isn't a link.")
    t = text.strip()
    if not t:
        raise BadLink("Paste a link first.")
    if len(t) > MAX_LEN:
        raise BadLink("That link is too long.")
    m = _URL_IN_TEXT.search(t)
    if m:
        url = m.group(0)
    elif _BARE.fullmatch(t):
        url = "https://" + t
    else:
        raise BadLink("That isn't a link. It should start with https://")
    while url[-1] in _TRAIL:  # a closing bracket stays when it closes one in the link (wiki/Foo_(bar))
        if url[-1] == ")" and url.count("(") >= url.count(")"):
            break
        url = url[:-1]
    if any(ord(c) < 32 or ord(c) == 127 for c in url):
        raise BadLink("That link has control characters in it.")
    try:
        u = urllib.parse.urlsplit(url)
        port = u.port
    except ValueError:
        raise BadLink("That link isn't valid.") from None
    scheme = u.scheme.lower()
    if scheme not in ("http", "https"):
        raise BadLink("Only http and https links can be sent.")
    if u.username is not None or u.password is not None:
        raise BadLink("Links with a user name or password in them aren't sent.")
    host = u.hostname or ""
    if not host.isascii():
        try:
            host = host.encode("idna").decode("ascii")
        except UnicodeError:
            raise BadLink("That link's site name isn't valid.") from None
    host = host.lower().rstrip(".")
    if ":" in host:
        try:
            ipaddress.IPv6Address(host)
        except ValueError:
            raise BadLink("That link's site name isn't valid.") from None
        netloc = f"[{host}]"
    elif _HOST.fullmatch(host):
        netloc = host
    else:
        raise BadLink("That link has no site in it." if not host else "That link's site name isn't valid.")
    if port is not None:
        netloc += f":{port}"
    path = urllib.parse.quote(u.path or "/", safe=_SAFE)
    query = urllib.parse.quote(u.query, safe=_SAFE + "?")
    fragment = urllib.parse.quote(u.fragment, safe=_SAFE + "?#")
    return urllib.parse.urlunsplit((scheme, netloc, path, query, fragment))


def seconds(t):
    """A timestamp in seconds: 90, 90s, 1m30s, 1h2m3s, 1:30, 1:02:03; 0 if it isn't one."""
    t = (t or "").strip().lower()
    if re.fullmatch(r"\d{1,6}s?", t):
        return int(t.rstrip("s"))
    m = re.fullmatch(r"(?:(\d{1,3})h)?(?:(\d{1,4})m)?(?:(\d{1,6})s)?", t)
    if t and m:
        h, mi, s = (int(x or 0) for x in m.groups())
        return h * 3600 + mi * 60 + s
    m = re.fullmatch(r"(?:(\d{1,3}):)?(\d{1,3}):(\d{2})", t)
    if m:
        h, mi, s = (int(x or 0) for x in m.groups())
        return h * 3600 + mi * 60 + s
    return 0


def clock(s):
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


# ------------------------------------------------------------------ where it goes

YOUTUBE_HOSTS = {"youtube.com", "music.youtube.com", "youtu.be", "youtube-nocookie.com"}
TWITCH_HOSTS = {"twitch.tv", "clips.twitch.tv", "player.twitch.tv"}
NEBULA_HOSTS = {"nebula.tv", "nebula.app"}

YT_VIDEO = re.compile(r"[A-Za-z0-9_-]{11}")
YT_LIST = re.compile(r"[A-Za-z0-9_-]{2,80}")
YT_CHANNEL = re.compile(r"UC[A-Za-z0-9_-]{22}")
YT_NAME = re.compile(r"[\w.-]{1,100}")
TW_LOGIN = re.compile(r"[a-z0-9_]{1,25}")
TW_VOD = re.compile(r"\d{1,15}")
TW_CLIP = re.compile(r"[A-Za-z0-9_-]{1,100}")
SLUG = re.compile(r"[a-z0-9][a-z0-9_-]{0,150}")
JF_ID = re.compile(r"[0-9a-f]{32}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

# first parts of an address that are the site's own pages, not a channel or series
TW_PAGES = {
    "directory", "videos", "settings", "subscriptions", "inventory", "wallet", "drops", "search", "downloads", "jobs",
    "turbo", "prime", "p", "friends", "messages", "login", "signup", "store", "popout", "moderator", "u", "payments",
    "bits", "broadcast", "products", "team", "collections", "event", "embed", "following", "activate", "user",
}  # fmt: skip
NEBULA_PAGES = {
    "login", "join", "signup", "settings", "account", "search", "explore", "library", "podcasts", "classes",
    "featured", "videos", "terms", "privacy", "faq", "help", "gift", "jobs", "about", "myshows", "beta", "guest-pass",
}  # fmt: skip
VHX_PAGES = {
    "browse", "login", "signin", "signup", "join", "checkout", "account", "settings", "help", "search", "library",
    "watchlist", "my-list", "customers", "purchase", "gift", "gifts", "buy", "subscribe", "support", "terms",
    "privacy", "faq", "videos",
}  # fmt: skip


def _vhx_hosts():
    """{host: site} of the VHX apps (Dropout, 2nd Try), from their settings in vhx.py."""
    from couchbox.services import vhx

    out = {}
    for site, cfg in vhx.SITES.items():
        if not cfg.get("backend"):
            out[cfg["domain"]] = out["watch." + cfg["domain"]] = site
    return out


def parse(text, jellyfin=""):
    """Where a link goes: a Link, or BadLink. jellyfin is the server address from Settings."""
    url = normalise(text)
    u = urllib.parse.urlsplit(url)
    host = u.hostname or ""
    site = re.sub(r"^(www|m)\.", "", host)
    q = urllib.parse.parse_qs(u.query)
    parts = [urllib.parse.unquote(p) for p in u.path.split("/") if p]
    jf = _jellyfin(url, u, jellyfin)
    if jf:
        return jf
    if site in YOUTUBE_HOSTS:
        return _youtube(url, site, parts, q, u.fragment)
    if site in TWITCH_HOSTS:
        return _twitch(url, site, parts, q)
    if site in NEBULA_HOSTS:
        return _nebula(url, parts)
    vhx_site = _vhx_hosts().get(site)
    if vhx_site:
        return _vhx(vhx_site, url, parts)
    _not_this_box(host)
    return Link("web", "page", url=url)


def _first(q, key):
    return (q.get(key) or [""])[0]


def _youtube(url, site, parts, q, fragment):
    start = seconds(_first(q, "t") or _first(q, "start") or _first(q, "time_continue") or _first(urllib.parse.parse_qs(fragment), "t"))
    plist = _first(q, "list") if YT_LIST.fullmatch(_first(q, "list")) else ""
    head = parts[0] if parts else ""
    if head == "embed" and parts[1:2] == ["videoseries"] and plist:
        return Link("youtube", "playlist", plist, url)
    if site == "youtu.be" or head in ("watch", "shorts", "live", "embed", "v", "e"):
        vid = head if site == "youtu.be" else _first(q, "v") if head == "watch" else parts[1] if len(parts) > 1 else ""
        if not YT_VIDEO.fullmatch(vid):
            raise BadLink("That YouTube link has no video in it.")
        return Link("youtube", "video", vid, url, start, plist)
    if head == "playlist" and plist:
        return Link("youtube", "playlist", plist, url)
    if head == "channel" and len(parts) > 1 and YT_CHANNEL.fullmatch(parts[1]):
        return Link("youtube", "channel", parts[1], url)
    if head.startswith("@") and YT_NAME.fullmatch(head[1:]):
        return Link("youtube", "handle", head, url)
    if head in ("c", "user") and len(parts) > 1 and YT_NAME.fullmatch(parts[1]):
        return Link("youtube", "handle", f"{head}/{parts[1]}", url)
    if head == "results" and _first(q, "search_query").strip():
        return Link("youtube", "search", _first(q, "search_query").strip()[:200], url)
    return Link("youtube", "home", url=url)


def _twitch(url, site, parts, q):
    head = parts[0].lower() if parts else ""
    if site == "clips.twitch.tv":
        slug = _first(q, "clip") if head == "embed" else parts[0] if parts else ""
        if not TW_CLIP.fullmatch(slug):
            raise BadLink("That Twitch link has no clip in it.")
        return Link("twitch", "clip", slug, url)
    if site == "player.twitch.tv":
        vod, login = _first(q, "video").lstrip("v"), _first(q, "channel").lower()
        if TW_VOD.fullmatch(vod):
            return Link("twitch", "vod", vod, url)
        if TW_LOGIN.fullmatch(login):
            return Link("twitch", "live", login, url)
        raise BadLink("That Twitch player link has no channel or video in it.")
    if head == "videos" and len(parts) > 1:
        if not TW_VOD.fullmatch(parts[1]):
            raise BadLink("That Twitch link has no video in it.")
        return Link("twitch", "vod", parts[1], url)
    if not head or head in TW_PAGES:
        return Link("twitch", "home", url=url)
    if not TW_LOGIN.fullmatch(head):
        raise BadLink("That Twitch link isn't a channel, video or clip.")
    if len(parts) > 2 and parts[1] == "clip" and TW_CLIP.fullmatch(parts[2]):
        return Link("twitch", "clip", parts[2], url)
    if len(parts) > 2 and parts[1] in ("v", "video", "videos") and TW_VOD.fullmatch(parts[2]):
        return Link("twitch", "vod", parts[2], url)
    if len(parts) > 1:  # /<channel>/videos, /about, /schedule...: the channel's page
        return Link("twitch", "channel", head, url)
    return Link("twitch", "live", head, url)


def _nebula(url, parts):
    head = parts[0].lower() if parts else ""
    if head == "videos" and len(parts) > 1:
        if not SLUG.fullmatch(parts[1].lower()):
            raise BadLink("That Nebula link has no video in it.")
        return Link("nebula", "video", parts[1].lower(), url)
    if not head or head in NEBULA_PAGES:
        return Link("nebula", "home", url=url)
    if not SLUG.fullmatch(head):
        raise BadLink("That Nebula link isn't a video or a channel.")
    return Link("nebula", "series", head, url)


def _vhx(site, url, parts):
    low = [p.lower() for p in parts]
    if "videos" in low[:-1]:  # /videos/<slug>, /<series>/season:N/videos/<slug>
        slug = low[low.index("videos") + 1]
        if not SLUG.fullmatch(slug):
            raise BadLink("That link has no video in it.")
        return Link(site, "video", slug, url)
    head = low[0] if low else ""
    if not head or head in VHX_PAGES:
        return Link(site, "home", url=url)
    if not SLUG.fullmatch(head):
        raise BadLink("That link isn't a video or a series.")
    return Link(site, "series", head, url)


def _port(u):
    try:
        return u.port or (443 if u.scheme == "https" else 80)
    except ValueError:
        return None


def _jellyfin(url, u, server):
    """An item on the Jellyfin server (or any Jellyfin page that names its server), else None."""
    if not server:
        return None
    s = urllib.parse.urlsplit(server if "://" in server else "http://" + server)
    same = (u.hostname or "") == (s.hostname or "").lower().rstrip(".") and _port(u) == _port(s)
    path, _, query = urllib.parse.unquote(u.fragment).lstrip("!").lstrip("/").partition("?")
    fq = {k.lower(): v for k, v in urllib.parse.parse_qs(query).items()}
    item = _first(fq, "id").lower()
    if path.lower() in ("details", "item", "itemdetails", "itemdetails.html") and JF_ID.fullmatch(item):
        if same or ("/web" in u.path and "serverid" in fq):
            return Link("jellyfin", "item", item.replace("-", ""), url)
    return Link("jellyfin", "home", url=url) if same else None


def _not_this_box(host):
    """BadLink for addresses of the box itself: localhost, 127.x (also written 127.1 or as one
    number, which browsers take too), ::1, link-local and unspecified addresses."""
    if host == "localhost" or host.endswith(".localhost"):
        raise BadLink("Links to the TV box itself aren't opened.")
    ip = None
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        if re.fullmatch(r"(0x[0-9a-f]+|\d+)(\.(0x[0-9a-f]+|\d+)){0,3}", host):
            try:
                ip = ipaddress.ip_address(socket.inet_aton(host))
            except OSError:
                pass
    if ip is not None:
        ip = getattr(ip, "ipv4_mapped", None) or ip
        if ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_multicast:
            raise BadLink("Links to the TV box itself aren't opened.")


# ------------------------------------------------------------------ opening it on the TV


def open_link(text):
    """Open a link in its app on the TV (starting the app if needed). Returns a Result whose
    message is for the phone: "Playing on the TV: ...", or what went wrong."""
    from couchbox import settings

    try:
        link = parse(text, settings.get("media.jellyfin.url"))
    except BadLink as err:
        return Result(False, str(err))
    try:
        opener = {"youtube": _open_youtube, "jellyfin": _open_jellyfin, "web": _open_web}.get(link.app, _open_streaming)
        return Result(True, opener(link), link.app)
    except (BadLink, OpenFailed) as err:
        return Result(False, str(err), link.app)
    except Exception as err:  # the apps' errors: the phone shows them
        return Result(False, f"The TV couldn't open it: {err}", link.app)


def _app(app_id):
    """The app on the home row (renamed as the household named it); OpenFailed if it's hidden."""
    from couchbox import apps, settings

    a = next((a for a in apps.home_row(settings.load()) if a.id == app_id), None)
    if not a:
        known = apps.get(app_id)
        raise OpenFailed(f"{known.name if known else app_id} isn't on the TV's home screen, so it can't open this link.")
    return a


def _open_youtube_native(link):
    from couchbox.voice import tools, ytnative

    def show(target):
        if not ytnative.show(target, tools.raise_youtube):
            raise OpenFailed("YouTube didn't start on the TV.")

    if link.kind == "video":
        show(f"video:{link.id}" + (f"@{link.start}" if link.start else ""))
        return f"Playing on the TV: {tools.yt_title(link.id)}" + (f", from {clock(link.start)}" if link.start else "")
    if link.kind == "playlist":
        show(f"playlist:{link.id}")
        return "The playlist is on the TV."
    if link.kind == "handle":
        cid = youtube_channel_id(link.id)
        if not cid:
            show(f"search:{link.id.split('/')[-1]}")
            return f"Searched YouTube on the TV for {link.id.split('/')[-1]}."
        link = Link("youtube", "channel", cid, link.url)
    if link.kind == "channel":
        show(f"channel:{link.id}")
        return "The channel is on the TV."
    if link.kind == "search":
        show(f"search:{link.id}")
        return f"Searched YouTube on the TV for {link.id}."
    show("home")
    return "YouTube is open on the TV."


def _open_youtube(link):
    from couchbox import apps
    from couchbox.voice import cdp, tools

    _app("youtube")
    if apps.youtube_native():
        return _open_youtube_native(link)
    page = tools.youtube_page()
    if not page:
        raise OpenFailed("YouTube didn't start on the TV.")
    run = lambda cmd: cdp.call(page, tools.YT_JS, cmd, False, timeout=30)
    if link.kind == "video":
        ep = {"videoId": link.id}
        if link.start:
            ep["startTimeSeconds"] = link.start
        if link.playlist:
            ep["playlistId"] = link.playlist
        run({"watchEndpoint": ep})
        return f"Playing on the TV: {tools.yt_title(link.id)}" + (f", from {clock(link.start)}" if link.start else "")
    if link.kind == "playlist":
        run({"browseEndpoint": {"browseId": "VL" + link.id}})
        return "The playlist is on the TV."
    if link.kind == "handle":
        cid = youtube_channel_id(link.id)
        if not cid:
            run({"searchEndpoint": {"query": link.id.split("/")[-1]}})
            return f"Searched YouTube on the TV for {link.id.split('/')[-1]}."
        link = Link("youtube", "channel", cid, link.url)
    if link.kind == "channel":
        run({"browseEndpoint": {"browseId": link.id}})
        return "The channel is on the TV."
    if link.kind == "search":
        run({"searchEndpoint": {"query": link.id}})
        return f"Searched YouTube on the TV for {link.id}."
    run({"browseEndpoint": {"browseId": "FEwhat_to_watch"}})
    return "YouTube is open on the TV."


def youtube_channel_id(path):
    """The UC... id of a channel's /@handle (or /c/, /user/) address, from its page; "" if it
    can't be found (the caller searches instead)."""
    import requests

    try:
        r = requests.get(
            "https://www.youtube.com/" + urllib.parse.quote(path, safe="/@"),
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en"},
            cookies={"SOCS": "CAI"},  # past the cookie choice page
        )
        m = re.search(r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{22})"', r.text) or re.search(
            r'"(?:externalId|browseId)":"(UC[\w-]{22})"', r.text
        )
        return m.group(1) if m else ""
    except requests.RequestException:
        return ""


def _open_jellyfin(link):
    from couchbox.voice import tools

    a = _app("jellyfin")
    if link.kind != "item":
        tools.open_app(a.name)
        return "Jellyfin is open on the TV."
    out = tools.jellyfin("play", id=link.id)
    if not out.startswith("playing "):  # "playing episode <id> | Show S1E2 Name (2020) · resume at..."
        raise OpenFailed(out)
    title = out.split(" | ", 1)[-1].split(" · ")[0]
    return f"Playing on the TV: {title}"


def _open_web(link):
    from couchbox import appctl
    from couchbox.voice import streaming, tools

    a = _app("search")
    streaming.ensure("search", start=lambda: tools.open_app(a.name, wait=False))
    appctl.call("search", {"op": "open", "target": "url:" + link.url})
    tools.raise_window(a.desktop, a.name)
    return f"Opened on the TV: {urllib.parse.urlsplit(link.url).hostname}"


def _open_streaming(link):
    """Twitch, Nebula, Dropout and 2nd Try: the app's control socket (couchbox-streaming)."""
    from couchbox import appctl
    from couchbox.voice import streaming, tools

    site, a = link.app, _app(link.app)
    streaming.ensure(site, start=lambda: tools.open_app(a.name, wait=False))
    call = lambda fn, **args: streaming.call(site, fn, **args)

    def show(target):
        appctl.call(site, {"op": "open", "target": target})
        tools.raise_window(a.desktop, a.name)

    def search(words, what):
        show(f"search:{words}")
        return f"Couldn't find that {what} in {a.name}; searched it for “{words}” on the TV."

    if link.kind == "home":
        show("home")
        return f"{a.name} is open on the TV."
    if site == "twitch":
        if link.kind == "live":
            info = call("streamInfo", login=link.id)
            if not info.get("live"):
                show(f"series:{link.id}")
                return f"{link.id} isn't live. Their channel is on the TV."
            show(f"play:live:{link.id}")
            return f"Playing on the TV: {link.id}, live" + (f": {info['title']}" if info.get("title") else "")
        if link.kind == "channel":
            show(f"series:{link.id}")
            return f"{link.id}'s channel is on the TV."
        show(f"play:{link.kind}:{link.id}")  # vod:<id>, clip:<slug>
        return f"Playing the Twitch {'clip' if link.kind == 'clip' else 'video'} on the TV."
    words = link.id.replace("-", " ").replace("_", " ")
    if site == "nebula":  # Nebula's ids are its slugs
        try:
            title = call("video" if link.kind == "video" else "collection", id=link.id).get("title")
        except RuntimeError:
            return search(words, link.kind if link.kind == "video" else "channel")
        show(f"play:{link.id}" if link.kind == "video" else f"series:{link.id}")
        return f"Playing on the TV: {title}" if link.kind == "video" else f"{title or 'The channel'} is on the TV."
    # VHX (Dropout, 2nd Try): numeric ids, found by slug through the app's search
    found = call("search", q=words).get("items", [])
    if link.kind == "series":
        found += call("allSeries").get("items", [])
    hit = next(
        (
            c
            for c in found
            if str(c.get("slug", "")).rstrip("/").rsplit("/", 1)[-1] == link.id and (c.get("kind") == "video") == (link.kind == "video")
        ),
        None,
    )
    if not hit:
        return search(words, "video" if link.kind == "video" else "series")
    if link.kind == "video":
        show(f"play:{hit['id']}")
        return f"Playing on the TV: {hit.get('title') or words}"
    show(f"series:{hit['id']}")
    return f"{hit.get('title') or 'The series'} is on the TV."
