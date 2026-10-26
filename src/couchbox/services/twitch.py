"""Twitch client for the couchbox TV app (the Dropout app's screens and player, plus live chat).

  browsing   gql.twitch.tv (the website's GraphQL, anonymous with its web Client-ID): top
             streams, categories, a category's streams, channels with their videos, search
  sign-in    the TV device flow (id.twitch.tv/oauth2/device with Twitch's TV app Client-ID):
             a code to enter at twitch.tv/activate. The app keeps checking for the whole life of
             the code (30 min), even after Back, so a code entered later still signs the TV in.
             The token is kept and refreshed. Twitch's refresh tokens are single-use and expire
             after 30 days unused, so refreshes take a lock and re-read the file (another
             process may have refreshed first), and keep_alive() (daily, couchbox-clean-caches)
             refreshes a week-old token even if nobody opens Twitch
  following  api.twitch.tv/helix/streams/followed and channels/followed (with the token)
  video      a playback access token (GQL) -> usher.ttvnw.net HLS; the best stream up to 1080p.
             Live streams go through AdFilter, a local playlist proxy that leaves out Twitch's
             stitched-in ads (segments not titled "live"), as streamlink does: during a break
             the picture holds and the app says so
  chat       IRC over WebSocket (irc-ws.chat.twitch.tv): anonymous to read, the token to send;
             Twitch emotes from the message tags, 7TV, BTTV and FrankerFaceZ by name
Everything comes out as the same "cards" as vhx.py. Ids: "live:<login>", "vod:<id>",
channels by login, categories as "cat:<name>".
"""

import fcntl
import json
import os
import random
import re
import threading
import time
import urllib.parse

import requests

from . import vhx

GQL = "https://gql.twitch.tv/gql"
WEB_CLIENT = "kimne78kx3ncx6brgo4mv6wki5h1ko"  # the website's: anonymous GraphQL and playback
TV_CLIENT = "ue6666qo983tsx6so1t0vnawi233wa"  # Twitch's TV app: device sign-in, Helix, chat
TIMEOUT = (10, 30)
SCOPES = "chat:read chat:edit user:read:follows user:read:subscriptions"

STREAM = (
    "id title viewersCount createdAt game { id name displayName } previewImageURL(width: 1280, height: 720) "
    "freeformTags { name } contentClassificationLabels { localizedName }"
)
USER = f"id login displayName description profileImageURL(width: 300) bannerImageURL offlineImageURL stream {{ {STREAM} }}"
VIDEO = (
    "id title lengthSeconds publishedAt viewCount previewThumbnailURL(width: 1280, height: 720) game { name } owner { login displayName }"
)


def kcount(n):
    n = int(n or 0)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    return f"{n / 1000:.1f}K".replace(".0K", "K") if n >= 1000 else str(n)


def live_for(iso):
    """ "5h 28m" since a stream's start (ISO time)."""
    import datetime

    try:
        t = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return ""
    m = int((datetime.datetime.now(datetime.UTC) - t).total_seconds() // 60)
    return f"{m // 60}h {m % 60}m" if m >= 60 else f"{m}m"


class Twitch:
    def __init__(self, site="twitch", skip_ads=False):
        self.site = site
        self.skip_ads = skip_ads  # Settings → Apps → Skip Twitch ads (experimental)
        self.cfg = vhx.SITES[site]
        self.dir = os.path.expanduser(f"~/.local/share/couchbox-{site}")
        os.makedirs(self.dir, mode=0o700, exist_ok=True)
        self.s = requests.Session()
        self.s.headers["User-Agent"] = vhx.UA
        self.auth = {}
        try:
            self.auth = json.load(open(self.session_file))
        except (OSError, ValueError):
            pass
        self.device = None
        self.device_state = {"state": "expired"}
        self.emotes = {}  # channel login -> {name: url}
        self.chat = None
        self.on_event = lambda name, data: None  # set by the launcher: chat messages, ad breaks
        self.ads = None

    # ------------------------------------------------------------------ session
    @property
    def session_file(self):
        return os.path.join(self.dir, "session.json")

    def _save(self):
        tmp = self.session_file + ".tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(self.auth, f)
        os.replace(tmp, self.session_file)

    @property
    def signed_in(self):
        return bool(self.auth.get("access_token"))

    def _reload(self):
        try:
            self.auth = json.load(open(self.session_file))
        except (OSError, ValueError):
            self.auth = {}

    def token(self, force=False):
        """The user's access token, refreshed when it's near expiry ("" when signed out)."""
        if not self.signed_in:
            return ""
        if (force or time.time() > self.auth.get("expires_at", 0) - 300) and self.auth.get("refresh_token"):
            with open(os.path.join(self.dir, ".lock"), "w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                mine = self.auth.get("refresh_token")
                self._reload()  # another process (the app, keep_alive) may have refreshed already
                if not self.signed_in:
                    return ""
                if self.auth.get("refresh_token") != mine and time.time() < self.auth.get("expires_at", 0) - 300:
                    return self.auth["access_token"]
                r = self.s.post(
                    "https://id.twitch.tv/oauth2/token",
                    data={"client_id": TV_CLIENT, "grant_type": "refresh_token", "refresh_token": self.auth["refresh_token"]},
                    timeout=TIMEOUT,
                )
                if r.ok:
                    j = r.json()
                    self.auth.update(
                        access_token=j["access_token"],
                        refresh_token=j.get("refresh_token", self.auth["refresh_token"]),
                        expires_at=time.time() + int(j.get("expires_in") or 3600),
                        refreshed_at=time.time(),
                    )
                    self._save()
                elif r.status_code in (400, 401):  # revoked, password changed, or 30 days unused
                    print(f"twitch: refresh refused ({r.status_code} {r.text[:120]}): signed out", flush=True)
                    self.sign_out()
                    return ""
        return self.auth.get("access_token", "")

    def keep_alive(self, every=7 * 86400):
        """Refresh a token that hasn't been refreshed for a week (Twitch drops it after 30 days unused)."""
        if self.signed_in and time.time() - self.auth.get("refreshed_at", self.auth.get("signed_in_at", 0)) > every:
            return bool(self.token(force=True))
        return self.signed_in

    def status(self):
        out = {"state": "ok", "site": self.cfg["name"], "signedIn": self.signed_in}
        if self.signed_in:
            out["user"] = self.auth.get("login", "")
        return out

    def device_start(self):
        r = self.s.post("https://id.twitch.tv/oauth2/device", data={"client_id": TV_CLIENT, "scopes": SCOPES}, timeout=TIMEOUT)
        r.raise_for_status()
        self.device = dev = r.json()
        dev["started"] = time.time()
        self.device_state = {"state": "waiting"}
        threading.Thread(target=self._wait_device, args=(dev,), daemon=True).start()
        full = f"{dev['verification_uri']}?device-code={dev['user_code']}"
        qr = os.path.join(self.dir, "activate.png")
        try:  # a QR code of the activation link, for a phone
            import subprocess

            subprocess.run(["qrencode", "-t", "PNG", "-s", "12", "-m", "2", "-o", qr, full], check=True, timeout=10)
        except Exception:
            qr = ""
        return {
            "code": dev["user_code"],
            "url": dev["verification_uri"],
            "full": full,
            "qr": qr,
            "expires": int(dev.get("expires_in") or 1800),
        }

    def _exchange(self, dev):
        """One check of a device code: "waiting", "ok" (signed in and saved) or "expired"."""
        r = self.s.post(
            "https://id.twitch.tv/oauth2/token",
            data={
                "client_id": TV_CLIENT,
                "scopes": SCOPES,
                "device_code": dev["device_code"],
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            timeout=TIMEOUT,
        )
        if r.ok:
            j = r.json()
            auth = {
                "access_token": j["access_token"],
                "refresh_token": j.get("refresh_token", ""),
                "expires_at": time.time() + int(j.get("expires_in") or 3600),
                "signed_in_at": time.time(),
            }
            v = self.s.get(
                "https://id.twitch.tv/oauth2/validate", headers={"Authorization": f"OAuth {j['access_token']}"}, timeout=TIMEOUT
            ).json()
            auth.update(login=v.get("login", ""), user_id=v.get("user_id", ""))
            self.auth = auth
            self._save()
            return {"state": "ok", "user": auth["login"]}
        msg = (r.json() or {}).get("message", "") if r.headers.get("content-type", "").startswith("application/json") else ""
        if "pending" in msg or "slow_down" in msg:
            return {"state": "waiting"}
        return {"state": "expired", "message": msg}

    def _wait_device(self, dev):
        """Checks a code until it's used or expires, whether or not the sign-in page is still open."""
        end = dev["started"] + int(dev.get("expires_in") or 1800)
        while self.device is dev and time.time() < end:
            time.sleep(max(int(dev.get("interval") or 5), 2))
            if self.device is not dev:
                return
            try:
                st = self._exchange(dev)
            except (requests.RequestException, ValueError):
                continue  # offline for a moment: keep trying until the code expires
            if st["state"] != "waiting":
                break
        else:
            st = {"state": "expired"}
        if self.device is dev:
            self.device = None
            self.device_state = st
            if st["state"] == "ok":
                self.on_event("signedIn", json.dumps({"user": st["user"]}))

    def device_poll(self):
        """ "waiting", "ok" (signed in), or "expired" (the check runs in _wait_device)."""
        return {"state": "waiting"} if self.device else self.device_state

    def sign_out(self):
        self.auth = {}
        try:
            os.remove(self.session_file)
        except OSError:
            pass

    # the shared app calls these for VHX sites; Twitch signs in with a code instead
    def import_browser(self):
        return False

    def login(self, email, password):
        raise RuntimeError("Twitch signs in with a code at twitch.tv/activate.")

    def pick_profile(self, index):
        return self.status()

    # ------------------------------------------------------------------ APIs
    def gql(self, query, variables=None):
        r = self.s.post(GQL, json={"query": query, "variables": variables or {}}, headers={"Client-ID": WEB_CLIENT}, timeout=TIMEOUT)
        r.raise_for_status()
        j = r.json()
        if j.get("errors") and not j.get("data"):
            raise RuntimeError(j["errors"][0].get("message", "Twitch error"))
        return j.get("data") or {}

    def gql_user(self, query, variables=None):
        """GraphQL as the signed-in user (the TV app's client id with its token): following."""
        tok = self.token()
        if not tok:
            raise vhx.SignInNeeded()
        r = self.s.post(
            GQL,
            json={"query": query, "variables": variables or {}},
            headers={"Client-ID": TV_CLIENT, "Authorization": f"OAuth {tok}"},
            timeout=TIMEOUT,
        )
        if r.status_code == 401:
            raise vhx.SignInNeeded()
        r.raise_for_status()
        j = r.json()
        if j.get("errors") and not j.get("data"):
            raise RuntimeError(j["errors"][0].get("message", "Twitch error"))
        return j.get("data") or {}

    def helix(self, path, params=None):
        tok = self.token()
        if not tok:
            raise vhx.SignInNeeded()
        r = self.s.get(
            "https://api.twitch.tv/helix" + path,
            params=params,
            headers={"Client-ID": TV_CLIENT, "Authorization": f"Bearer {tok}"},
            timeout=TIMEOUT,
        )
        if r.status_code == 401:
            raise vhx.SignInNeeded()
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------ cards
    @staticmethod
    def blank():
        return {
            "kind": "video",
            "id": "",
            "slug": "",
            "title": "",
            "description": "",
            "longDescription": "",
            "landscape": "",
            "poster": "",
            "square": "",
            "background": "",
            "logo": "",
            "duration": 0,
            "timecode": 0,
            "completed": False,
            "progress": 0.0,
            "series": "",
            "seasonNumber": 0,
            "seasonName": "",
            "episode": 0,
            "seasons": 0,
            "items": 0,
            "collectionId": "",
            "upNext": 0,
            "live": False,
            "viewers": "",
        }

    def stream_card(self, s, user=None):
        user = user or s.get("broadcaster") or {}
        c = self.blank()
        game = (s.get("game") or {}).get("displayName") or (s.get("game") or {}).get("name") or ""
        prev = s.get("previewImageURL") or ""
        c.update(
            id=f"live:{user.get('login', '')}",
            slug=user.get("login", ""),
            title=s.get("title") or "",
            description=game,
            longDescription=s.get("title") or "",
            landscape=prev + ("?t=%d" % (time.time() // 120) if prev else ""),
            background=prev,
            series=user.get("displayName") or user.get("login", ""),
            live=True,
            viewers=kcount(s.get("viewersCount")) + " viewers",
            square=user.get("profileImageURL") or "",
            viewerCount=int(s.get("viewersCount") or 0),
            started=s.get("createdAt") or "",
            category=game,
            tags=[t["name"] for t in s.get("freeformTags") or [] if t.get("name")],
            labels=[l["localizedName"] for l in s.get("contentClassificationLabels") or [] if l.get("localizedName")],
        )
        return c

    def video_card(self, v):
        c = self.blank()
        owner = v.get("owner") or {}
        thumb = v.get("previewThumbnailURL") or ""
        c.update(
            id=f"vod:{v.get('id')}",
            title=v.get("title") or "",
            landscape=thumb,
            background=thumb,
            description=((v.get("game") or {}).get("name") or "")
            + (f" · {kcount(v.get('viewCount'))} views" if v.get("viewCount") else ""),
            duration=int(v.get("lengthSeconds") or 0),
            series=owner.get("displayName") or "",
            collectionId=owner.get("login") or "",
        )
        return c

    def channel_card(self, u):
        c = self.blank()
        st = u.get("stream")
        c.update(
            kind="series",
            id=u.get("login", ""),
            slug=u.get("login", ""),
            title=u.get("displayName") or u.get("login", ""),
            description=(st or {}).get("title") or u.get("description") or "",
            longDescription=u.get("description") or "",
            square=u.get("profileImageURL") or "",
            landscape=u.get("bannerImageURL") or u.get("profileImageURL") or "",
            background=u.get("bannerImageURL") or u.get("offlineImageURL") or "",
            live=bool(st),
            viewers=(kcount(st.get("viewersCount")) + " viewers") if st else "",
        )
        return c

    def game_card(self, g):
        c = self.blank()
        c.update(
            kind="category",
            id=f"cat:{g.get('name')}",
            slug=g.get("name", ""),
            title=g.get("displayName") or g.get("name", ""),
            poster=g.get("boxArtURL") or "",
            viewers=kcount(g.get("viewersCount")) + " viewers" if g.get("viewersCount") else "",
        )
        return c

    # ------------------------------------------------------------------ the app's calls
    def browse(self):
        rows = []
        if self.signed_in:
            rows.append({"title": "Live Channels You Follow", "kind": "watching", "href": "following", "count": 1, "shape": "wide"})
        rows += [
            {"title": "Top Live Streams", "kind": "row", "href": "top", "count": 1, "shape": "wide"},
            {"title": "Top Categories", "kind": "row", "href": "games", "count": 1, "shape": "poster"},
        ]
        for g in ("Just Chatting", "Games + Demos", "Minecraft", "Grand Theft Auto V", "League of Legends", "Music", "Art"):
            rows.append({"title": g, "kind": "row", "href": f"cat:{g}", "count": 1, "shape": "wide"})
        return rows

    def featured(self):
        d = self.gql(
            f"query {{ streams(first: 8) {{ edges {{ node {{ {STREAM} broadcaster {{ login displayName profileImageURL(width: 150) }} }} }} }} }}"
        )
        out = []
        for e in d["streams"]["edges"]:
            c = self.stream_card(e["node"])
            # the banner: the channel's name big, the stream's title under it
            c["description"] = f"{c['description']} · {c['viewers']} · live for {live_for(c['started'])}\n{c['title']}"
            c["title"] = c["series"]
            out.append(c)
        return out

    def items(self, href, page=1, per_page=24):
        cursor = getattr(self, "_cursors", {}).get((href, page))
        after = {"after": cursor} if cursor else {}
        if href == "following":
            return self.following()
        if href == "top":
            d = self.gql(
                f"query($n: Int!, $after: Cursor) {{ streams(first: $n, after: $after) {{ edges {{ cursor node {{ {STREAM} broadcaster {{ login displayName profileImageURL(width: 150) }} }} }} pageInfo {{ hasNextPage }} }} }}",
                {"n": per_page, **after},
            )
            conn = d.get("streams") or {"edges": [], "pageInfo": {}}
            cards = [self.stream_card(e["node"]) for e in conn["edges"]]
        elif href == "games":
            d = self.gql(
                "query($n: Int!, $after: Cursor) { games(first: $n, after: $after) { edges { cursor node { id name displayName viewersCount boxArtURL(width: 285, height: 380) } } pageInfo { hasNextPage } } }",
                {"n": per_page, **after},
            )
            conn = d.get("games") or {"edges": [], "pageInfo": {}}
            cards = [self.game_card(e["node"]) for e in conn["edges"]]
        elif href.startswith("cat:"):
            d = self.gql(
                f"query($g: String!, $n: Int!, $after: Cursor) {{ game(name: $g) {{ streams(first: $n, after: $after) {{ edges {{ cursor node {{ {STREAM} broadcaster {{ login displayName profileImageURL(width: 150) }} }} }} pageInfo {{ hasNextPage }} }} }} }}",
                {"g": href[4:], "n": per_page, **after},
            )
            conn = (d.get("game") or {}).get("streams") or {"edges": [], "pageInfo": {}}
            cards = [self.stream_card(e["node"]) for e in conn["edges"]]
        else:
            return {"items": [], "more": False}
        if conn["edges"]:
            self._cursors = getattr(self, "_cursors", {})
            self._cursors[(href, page + 1)] = conn["edges"][-1].get("cursor")
        return {"items": cards, "more": bool((conn.get("pageInfo") or {}).get("hasNextPage"))}

    def following(self):
        uid = self.auth.get("user_id")
        live = self.helix("/streams/followed", {"user_id": uid, "first": 100}).get("data", [])
        if not live:
            return {"items": [], "more": False}
        logins = [s["user_login"] for s in live]
        d = self.gql(
            f"query($l: [String!]) {{ users(logins: $l) {{ login displayName profileImageURL(width: 150) stream {{ {STREAM} }} }} }}",
            {"l": logins},
        )
        cards = [self.stream_card(u["stream"], u) for u in d.get("users") or [] if u and u.get("stream")]
        return {"items": cards, "more": False}

    def watching(self, page=1):
        return self.following() if self.signed_in else {"items": [], "more": False}

    def my_list(self, page=1):
        """Following: live ones first, then the rest (channels)."""
        if not self.signed_in:
            raise vhx.SignInNeeded()
        live = self.following()["items"]
        uid = self.auth.get("user_id")
        chans = self.helix("/channels/followed", {"user_id": uid, "first": 100}).get("data", [])
        live_logins = {c["slug"] for c in live}
        rest = [c["broadcaster_login"] for c in chans if c["broadcaster_login"] not in live_logins]
        cards = list(live)
        for i in range(0, len(rest), 50):
            d = self.gql(f"query($l: [String!]) {{ users(logins: $l) {{ {USER} }} }}", {"l": rest[i : i + 50]})
            cards += [self.channel_card(u) for u in d.get("users") or [] if u]
        return {"items": cards, "more": False}

    def all_series(self):
        return self.items("games", 1, per_page=100)

    def category(self, name, page=1):
        return self.items(f"cat:{name}", page)

    def collection(self, login):
        """A channel: its live stream (if live) and its videos as "seasons"."""
        login = str(login)
        d = self.gql(f"query($l: String!) {{ user(login: $l) {{ {USER} followers {{ totalCount }} }} }}", {"l": login})
        u = d.get("user")
        if not u:
            raise RuntimeError("No such channel.")
        c = self.channel_card(u)
        c["kind"] = "series"
        c["trailer"] = ""
        c["seasons"] = 0
        bits = [f"{kcount((u.get('followers') or {}).get('totalCount'))} followers"]
        if u.get("stream"):
            bits.insert(0, "LIVE · " + kcount(u["stream"].get("viewersCount")) + " viewers · " + live_for(u["stream"].get("createdAt")))
        c["meta"] = "  ·  ".join(bits)
        tabs = []
        if u.get("stream"):
            tabs.append({"id": f"live|{login}", "name": "Live Now", "number": 0, "count": 1})
        for t, name in (("ARCHIVE", "Past Broadcasts"), ("HIGHLIGHT", "Highlights"), ("UPLOAD", "Videos")):
            tabs.append({"id": f"{t}|{login}", "name": name, "number": 0, "count": 0})
        c["seasonList"] = tabs
        c["profile"] = u.get("profileImageURL") or ""
        return c

    def collection_items(self, cid, page=1):
        kind, _, login = str(cid).partition("|")
        if kind == "live":
            d = self.gql(
                f"query($l: String!) {{ user(login: $l) {{ login displayName profileImageURL(width: 150) stream {{ {STREAM} }} }} }}",
                {"l": login},
            )
            u = d.get("user") or {}
            return {"items": [self.stream_card(u["stream"], u)] if u.get("stream") else [], "more": False}
        d = self.gql(
            f"query($l: String!, $t: BroadcastType) {{ user(login: $l) {{ videos(first: 40, type: $t, sort: TIME) {{ edges {{ node {{ {VIDEO} }} }} }} }} }}",
            {"l": login, "t": kind},
        )
        vids = ((d.get("user") or {}).get("videos") or {}).get("edges", [])
        return {"items": [self.video_card(e["node"]) for e in vids], "more": False}

    def stream_info(self, login):
        """Now: viewers, start time, title, category (the player refreshes these)."""
        d = self.gql(f"query($l: String!) {{ user(login: $l) {{ stream {{ {STREAM} }} }} }}", {"l": str(login)})
        st = (d.get("user") or {}).get("stream")
        if not st:
            return {"live": False}
        g = st.get("game") or {}
        return {
            "live": True,
            "viewers": kcount(st.get("viewersCount")) + " viewers",
            "viewerCount": int(st.get("viewersCount") or 0),
            "started": st.get("createdAt") or "",
            "title": st.get("title") or "",
            "category": g.get("displayName") or g.get("name") or "",
            "tags": [t["name"] for t in st.get("freeformTags") or [] if t.get("name")],
        }

    def search(self, q, page=1):
        d = self.gql(
            f"""query($q: String!) {{ searchFor(userQuery: $q, platform: "web") {{
            channels {{ edges {{ item {{ ... on User {{ {USER} }} }} }} }}
            games {{ edges {{ item {{ ... on Game {{ id name displayName viewersCount boxArtURL(width: 285, height: 380) }} }} }} }} }} }}""",
            {"q": q},
        )
        sf = d.get("searchFor") or {}
        users = [e["item"] for e in (sf.get("channels") or {}).get("edges", []) if e.get("item")]
        cards = [self.stream_card(u["stream"], u) for u in users if u.get("stream")]
        cards += [self.channel_card(u) for u in users if not u.get("stream")]
        cards += [self.game_card(e["item"]) for e in (sf.get("games") or {}).get("edges", []) if e.get("item")]
        return {"items": cards, "more": False}

    # ------------------------------------------------------------------ playback
    def _pick(self, url, text, path):
        """Write a master playlist with only the best stream up to 1080p (the source can be
        1440p, which this box would decode in software)."""
        lines = text.splitlines()
        absu = lambda u: urllib.parse.urljoin(url, u)
        head, variants, i = [], [], 0
        while i < len(lines):
            ln = lines[i]
            if ln.startswith("#EXT-X-STREAM-INF"):
                h = int((re.search(r"RESOLUTION=\d+x(\d+)", ln) or [0, 0])[1])
                bw = int((re.search(r"[,:]BANDWIDTH=(\d+)", ln) or [0, 0])[1])
                fps = float((re.search(r"FRAME-RATE=([\d.]+)", ln) or [0, 0])[1])
                if h:  # not audio_only
                    variants.append((ln, absu(lines[i + 1]), h, fps, bw, (re.search(r'VIDEO="([^"]+)"', ln) or [0, ""])[1]))
                i += 2
                continue
            if not ln.startswith("#EXT-X-MEDIA") and not ln.startswith("#EXT-X-STREAM-INF"):
                head.append(ln)
            i += 1
        ok = [v for v in variants if v[2] <= 1080] or variants
        best = max(ok, key=lambda v: (v[2], v[3], v[4]))
        media = f'#EXT-X-MEDIA:TYPE=VIDEO,GROUP-ID="{best[5]}",NAME="{best[5]}",AUTOSELECT=YES,DEFAULT=YES'
        with open(path, "w") as f:
            f.write("\n".join(head + [media, best[0], best[1]]) + "\n")
        return best

    def playback(self, vid):
        vid = str(vid)
        kind, _, key = vid.partition(":")
        params = {"platform": "web", "playerBackend": "mediaplayer", "playerType": "site"}
        path = os.path.join(self.dir, "playing.m3u8")
        c = self.blank()
        if kind == "live":
            d = self.gql(
                f"""query($l: String!, $p: PlaybackAccessTokenParams!) {{
                streamPlaybackAccessToken(channelName: $l, params: $p) {{ value signature }}
                user(login: $l) {{ id login displayName profileImageURL(width: 150) stream {{ {STREAM} }} }} }}""",
                {"l": key, "p": params},
            )
            u = d.get("user") or {}
            if not u.get("stream"):
                raise RuntimeError(f"{u.get('displayName') or key} isn't live right now.")
            tok = d["streamPlaybackAccessToken"]
            c = self.stream_card(u["stream"], u)
            url = f"https://usher.ttvnw.net/api/channel/hls/{key}.m3u8"
            q = {
                "sig": tok["signature"],
                "token": tok["value"],
                "allow_source": "true",
                "allow_audio_only": "true",
                "fast_bwe": "true",
                "p": random.randint(1, 999999),
                "player_backend": "mediaplayer",
                "supported_codecs": "h265,h264",
                "platform": "web",
                "playlist_include_framerate": "true",
            }
            c["chat"] = key
            c["channelId"] = u.get("id")
        else:
            d = self.gql(
                f"""query($v: ID!, $p: PlaybackAccessTokenParams!) {{
                videoPlaybackAccessToken(id: $v, params: $p) {{ value signature }}
                video(id: $v) {{ {VIDEO} }} }}""",
                {"v": key, "p": params},
            )
            tok = d["videoPlaybackAccessToken"]
            c = self.video_card(d.get("video") or {"id": key})
            c["vodChat"] = vid  # chat replayed along with the video
            url = f"https://usher.ttvnw.net/vod/{key}.m3u8"
            q = {
                "sig": tok["signature"],
                "token": tok["value"],
                "allow_source": "true",
                "allow_audio_only": "true",
                "p": random.randint(1, 999999),
                "player_backend": "mediaplayer",
                "supported_codecs": "h265,h264",
                "platform": "web",
                "playlist_include_framerate": "true",
            }
            c["chat"] = ""
        r = self.s.get(url, params=q, timeout=TIMEOUT)
        if r.status_code == 403:
            raise RuntimeError("Twitch won't play this one here (subscriber-only or region).")
        r.raise_for_status()
        best = self._pick(r.url, r.text, path)
        c["url"] = path
        if kind == "live" and self.skip_ads:  # the stream's own playlist, without the ads
            if not self.ads:
                self.ads = AdFilter(self)
            c["url"] = self.ads.serve(best[1])
        c["start"] = 0
        c["subtitles"] = []
        c["next"] = None
        return c

    def video(self, vid):
        return self.playback(vid)

    def _user_id(self, login):
        return (self.gql("query($l: String!) { user(login: $l) { id } }", {"l": str(login)}).get("user") or {}).get("id")

    def watchlist(self, op, kind, cid):
        """Follow (op "add") or unfollow a channel."""
        uid = self._user_id(cid)
        if op == "add":
            d = self.gql_user(
                "mutation($t: ID!) { followUser(input: {targetID: $t, disableNotifications: false}) { follow { followedAt } error { code } } }",
                {"t": uid},
            )
            err = ((d.get("followUser") or {}).get("error") or {}).get("code")
            if err:
                raise RuntimeError(f"Twitch said {err}.")
        else:
            self.gql_user("mutation($t: ID!) { unfollowUser(input: {targetID: $t}) { follow { followedAt } } }", {"t": uid})
        return {"ok": True}

    def on_watchlist(self, cid):
        if not self.signed_in:
            return False
        uid = self._user_id(cid)
        d = self.gql_user("query($t: ID!) { user(id: $t) { self { follower { followedAt } } } }", {"t": uid})
        return bool(((d.get("user") or {}).get("self") or {}).get("follower"))

    # ------------------------------------------------------------------ chat replay (videos)
    def vod_comments(self, vid, offset, login=""):
        """Chat as it was, from offset (seconds) on: [{t (seconds), name, color, parts}]."""
        key = str(vid).split(":")[-1]
        d = self.gql(
            """query($id: ID!, $o: Int) { video(id: $id) { owner { id login }
            comments(contentOffsetSeconds: $o) { edges { node { contentOffsetSeconds commenter { displayName login }
            message { userColor fragments { text emote { emoteID } } } } } } } }""",
            {"id": key, "o": int(offset)},
        )
        v = d.get("video") or {}
        owner = v.get("owner") or {}
        emotes = {}
        try:
            emotes = self.channel_emotes(owner.get("login") or login, owner.get("id"))
        except Exception:
            pass
        helper = Chat(self, owner.get("login") or login, emotes)
        out = []
        for e in (v.get("comments") or {}).get("edges") or []:
            n = e.get("node") or {}
            parts = []
            for f in (n.get("message") or {}).get("fragments") or []:
                if f.get("emote"):
                    parts.append(
                        {"e": f"https://static-cdn.jtvnw.net/emoticons/v2/{f['emote']['emoteID']}/default/dark/2.0", "n": f.get("text", "")}
                    )
                elif f.get("text"):
                    parts += helper.parts(f["text"], {})
            com = n.get("commenter") or {}
            out.append(
                {
                    "t": int(n.get("contentOffsetSeconds") or 0),
                    "name": com.get("displayName") or com.get("login") or "",
                    "color": (n.get("message") or {}).get("userColor") or "",
                    "parts": parts,
                }
            )
        return {"items": out}

    def event(self, *a, **kw):
        pass

    # ------------------------------------------------------------------ emotes
    def channel_emotes(self, login, channel_id):
        """{name: image url} from 7TV, BTTV and FrankerFaceZ: the channel's and the global sets."""
        if login in self.emotes:
            return self.emotes[login]
        out = {}

        def get(url):
            try:
                r = self.s.get(url, timeout=TIMEOUT)
                return r.json() if r.ok else None
            except (requests.RequestException, ValueError):
                return None

        for j in (
            get("https://api.betterttv.net/3/cached/frankerfacez/emotes/global"),
            get(f"https://api.betterttv.net/3/cached/frankerfacez/users/twitch/{channel_id}"),
        ):
            for e in j or []:
                imgs = e.get("animated") or e.get("images") or {}
                url = imgs.get("2x") or imgs.get("1x")
                if url:
                    out[e["code"]] = url
        g = get("https://api.betterttv.net/3/cached/emotes/global") or []
        ch = get(f"https://api.betterttv.net/3/cached/users/twitch/{channel_id}") or {}
        for e in g + ch.get("channelEmotes", []) + ch.get("sharedEmotes", []):
            out[e["code"]] = f"https://cdn.betterttv.net/emote/{e['id']}/2x.webp"
        sets = [
            get("https://7tv.io/v3/emote-sets/global") or {},
            ((get(f"https://7tv.io/v3/users/twitch/{channel_id}") or {}).get("emote_set") or {}),
        ]
        for st in sets:
            for e in st.get("emotes") or []:
                host = ((e.get("data") or {}).get("host") or {}).get("url")
                if host:
                    out[e["name"]] = f"https:{host}/2x.webp"
        self.emotes[login] = out
        return out

    # ------------------------------------------------------------------ chat
    def chat_join(self, login, channel_id=""):
        self.chat_part()
        emotes = {}
        try:
            emotes = self.channel_emotes(
                login, channel_id or self.gql("query($l: String!) { user(login: $l) { id } }", {"l": login})["user"]["id"]
            )
        except Exception:
            pass
        self.chat = Chat(self, login, emotes)
        self.chat.start()
        return {"ok": True, "canSend": self.signed_in, "emotes": len(emotes)}

    def chat_part(self):
        if self.chat:
            self.chat.stop()
            self.chat = None
        return {"ok": True}

    def chat_send(self, text):
        if not self.signed_in:
            raise vhx.SignInNeeded()
        if not self.chat:
            raise RuntimeError("Chat isn't connected.")
        self.chat.send(text)
        return {"ok": True}


class Chat(threading.Thread):
    """One channel's chat: messages go to the app as "chat" events: {name, color, parts, mod},
    parts being [{"t": text} | {"e": image url, "n": name}]."""

    def __init__(self, tw, login, emotes):
        super().__init__(daemon=True)
        self.tw = tw
        self.login = login
        self.emotes = emotes
        self.ws = None
        self.running = True
        self.lock = threading.Lock()

    def stop(self):
        self.running = False
        try:
            self.ws and self.ws.close()
        except Exception:
            pass

    def raw(self, line):
        with self.lock:
            self.ws.send(line)

    def send(self, text):
        text = text.replace("\n", " ").strip()
        if text:
            self.raw(f"PRIVMSG #{self.login} :{text}")
            # Twitch doesn't echo our own messages: show it as sent
            me = self.tw.auth.get("login", "you")
            self.tw.on_event("chat", json.dumps({"name": me, "color": "#bf94ff", "parts": self.parts(text, {}), "self": True}))

    def parts(self, text, tags):
        twitch = {}  # start -> (end, url) from the emotes tag
        for spec in (tags.get("emotes") or "").split("/"):
            if ":" not in spec:
                continue
            eid, ranges = spec.split(":", 1)
            for rg in ranges.split(","):
                a, _, b = rg.partition("-")
                if a.isdigit() and b.isdigit():
                    twitch[int(a)] = (int(b), f"https://static-cdn.jtvnw.net/emoticons/v2/{eid}/default/dark/2.0")
        out, i, buf = [], 0, ""
        while i < len(text):
            if i in twitch:
                end, url = twitch[i]
                if buf:
                    out.append({"t": buf})
                    buf = ""
                out.append({"e": url, "n": text[i : end + 1]})
                i = end + 1
                continue
            buf += text[i]
            i += 1
        if buf:
            out.append({"t": buf})
        # third-party emotes: whole words
        final = []
        for p in out:
            if "e" in p:
                final.append(p)
                continue
            words = re.split(r"(\s+)", p["t"])
            acc = ""
            for w in words:
                if w in self.emotes:
                    if acc:
                        final.append({"t": acc})
                        acc = ""
                    final.append({"e": self.emotes[w], "n": w})
                else:
                    acc += w
            if acc:
                final.append({"t": acc})
        return final

    def run(self):
        import websocket

        backoff = 1
        while self.running:
            try:
                self.ws = websocket.create_connection("wss://irc-ws.chat.twitch.tv:443", timeout=30)
                self.raw("CAP REQ :twitch.tv/tags twitch.tv/commands")
                tok = self.tw.token()
                if tok:
                    self.raw(f"PASS oauth:{tok}")
                    self.raw(f"NICK {self.tw.auth.get('login')}")
                else:
                    self.raw(f"NICK justinfan{random.randint(10000, 99999)}")
                self.raw(f"JOIN #{self.login}")
                self.tw.on_event("chatState", json.dumps({"state": "connected", "canSend": bool(tok)}))
                backoff = 1
                while self.running:
                    try:
                        data = self.ws.recv()
                    except websocket.WebSocketTimeoutException:
                        self.raw("PING :tmi.twitch.tv")
                        continue
                    if not data:
                        break
                    for line in data.split("\r\n"):
                        self.handle(line)
            except Exception as err:
                if self.running:
                    self.tw.on_event("chatState", json.dumps({"state": "reconnecting", "error": str(err)[:100]}))
            finally:
                try:
                    self.ws and self.ws.close()
                except Exception:
                    pass
            if self.running:
                time.sleep(backoff)
                backoff = min(30, backoff * 2)

    def handle(self, line):
        if not line:
            return
        if line.startswith("PING"):
            self.raw("PONG :tmi.twitch.tv")
            return
        tags = {}
        if line.startswith("@"):
            raw, line = line[1:].split(" ", 1)
            for kv in raw.split(";"):
                k, _, v = kv.partition("=")
                tags[k] = v.replace("\\s", " ")
        m = re.match(r":(\w+)!\S+ PRIVMSG #\w+ :(.*)", line)
        if m:
            text = m.group(2)
            if text.startswith("\x01ACTION ") and text.endswith("\x01"):
                text = text[8:-1]
            badges = tags.get("badges", "")
            self.tw.on_event(
                "chat",
                json.dumps(
                    {
                        "name": tags.get("display-name") or m.group(1),
                        "color": tags.get("color") or "",
                        "parts": self.parts(text, tags),
                        "mod": "moderator" in badges or "broadcaster" in badges,
                        "sub": "subscriber" in badges,
                    }
                ),
            )
        elif " NOTICE " in line or " USERNOTICE " in line:
            msg = tags.get("system-msg") or (line.split(" :", 1)[1] if " :" in line else "")
            if msg:
                self.tw.on_event("chat", json.dumps({"name": "", "color": "", "parts": [{"t": msg}], "notice": True}))


class AdFilter:
    """A local HTTP server for live media playlists, leaving out Twitch's stitched-in ad
    segments. Live segments get their own sequence numbers (consecutive across an ad break),
    so the player neither skips nor repeats. A break shows as no new segments: the player
    holds its last picture, and the app is told ("ads" events) to say why."""

    def __init__(self, tw):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        self.tw = tw
        self.upstream = ""
        self.gen = 0
        self.seq = {}  # (generation, upstream sequence) -> our sequence
        self.next = 0
        self.in_ads = False
        self.lock = threading.Lock()
        filt = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                try:
                    body = filt.playlist(int(self.path.strip("/").split(".")[0] or 0))
                except Exception as err:
                    self.send_error(502, str(err)[:100])
                    return
                data = body.encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def serve(self, url):
        with self.lock:
            self.gen += 1
            self.upstream = url
            self.in_ads = False
        return f"http://127.0.0.1:{self.server.server_address[1]}/{self.gen}.m3u8"

    def set_ads(self, on):
        if on != self.in_ads:
            self.in_ads = on
            self.tw.on_event("ads", json.dumps({"on": on}))

    def playlist(self, gen):
        # the first answer waits (up to 90 s) for a live segment: a pre-roll is all ads
        for _ in range(45):
            text = self.tw.s.get(self.upstream, timeout=TIMEOUT).text
            out, live = self.filter(gen, text)
            if live or gen != self.gen or self.next:
                return out
            time.sleep(2)
        return out

    def filter(self, gen, text):
        head, segs, pending = [], [], []
        seq = 0
        last_is_ad = False
        cur_map = ""  # ads have their own init segment: each segment keeps the one it follows
        for ln in text.splitlines():
            if ln.startswith("#EXT-X-MEDIA-SEQUENCE:"):
                seq = int(ln.split(":", 1)[1])
            elif ln.startswith(("#EXT-X-TWITCH", "#EXT-X-DATERANGE")):
                continue  # Twitch's own notes, and ad markers
            elif ln.startswith("#EXT-X-MAP"):
                cur_map = ln
            elif ln.startswith(("#EXTM3U", "#EXT-X-VERSION", "#EXT-X-TARGETDURATION")):
                if ln not in head:
                    head.append(ln)
            elif ln.startswith("#"):
                pending.append(ln)
            elif ln.strip():
                inf = next((p for p in pending if p.startswith("#EXTINF")), "")
                title = inf.split(",", 1)[1] if "," in inf else ""
                last_is_ad = bool(title) and not title.startswith("live")
                if not last_is_ad:
                    segs.append((seq, pending, ln, cur_map))
                pending = []
                seq += 1
        with self.lock:
            for s_, *_ in segs:
                if (gen, s_) not in self.seq:
                    self.seq[(gen, s_)] = self.next
                    self.next += 1
            if len(self.seq) > 4000:
                for k in sorted(self.seq)[:2000]:
                    del self.seq[k]
            first = self.seq[(gen, segs[0][0])] if segs else self.next
        self.set_ads(last_is_ad)  # the newest segment is an ad: a break
        out = [h for h in head if not h.startswith("#EXT-X-MEDIA-SEQUENCE")]
        if not any(h.startswith("#EXT-X-TARGETDURATION") for h in out):
            out.append("#EXT-X-TARGETDURATION:6")
        out.insert(1, f"#EXT-X-MEDIA-SEQUENCE:{first}")
        last_map = ""
        for _, tags, uri, m in segs:
            if m and m != last_map:
                out.append(m)
                last_map = m
            out += tags + [uri]
        return "\n".join(out) + "\n", len(segs)
