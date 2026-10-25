"""VHX (Vimeo OTT) client for the couchbox TV apps: Dropout now, 2nd Try later (same platform,
different site settings).

Signing in: the website's session cookies (copied from the TV's browser if it's signed in,
else email + password as on the website's login form, then "Who's watching?"). With the
session, the site's pages carry an API token (a JWT) for api.vhx.tv / api.vhx.com, which is
what the website itself uses. The session is kept in ~/.local/share/couchbox-<site>/session.json
(mode 600); the password is never stored.

Everything is normalised into "cards" (dicts) for the QML: series, seasons, collections,
videos, with images, durations and watch progress.
"""

import base64
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import time
import urllib.parse

import requests

# Each site's VHX ids (from its pages: site_id, product, the featured hub) and its look.
SITES = {
    "dropout": {
        "name": "Dropout",
        "site_id": 36348,
        "product_id": 28599,
        "web": "https://watch.dropout.tv",
        "featured_hub": 1221449,
        "domain": "dropout.tv",
        "all_series": 243176,
        "accent": "#feea3b",
        "accent_ink": "#000000",
        "bg": "#000000",
        "logo_text": ":DROPOUT",
        "logo": "",
    },
    "2ndtry": {
        "name": "2nd Try",
        "site_id": 215596,
        "product_id": 188682,
        "web": "https://watch.2ndtry.tv",
        "featured_hub": 1398824,
        "domain": "2ndtry.tv",
        "all_series": 0,
        "accent": "#0cadad",
        "accent_ink": "#ffffff",
        "bg": "#0b0a12",
        "logo_text": "2nd try",
        "logo": "https://vhx.imgix.net/thetryguys/assets/d947c82e-2eb4-4504-a525-ce387ece5647.png",
    },
    # not VHX: its own API (nebula.py); same screens
    "nebula": {
        "name": "Nebula",
        "backend": "nebula",
        "domain": "nebula.tv",
        "accent": "#ffffff",
        "accent_ink": "#131619",
        "bg": "#131619",
        "logo_text": "nebula",
        "logo": "",
        "nav": ["Home", "Channels", "Watch Later", "Search"],
        "series_shape": "square",
        "no_list_button": True,
    },
    # its own API (twitch.py), live chat
    "twitch": {
        "name": "Twitch",
        "backend": "twitch",
        "domain": "twitch.tv",
        "accent": "#9146ff",
        "accent_ink": "#ffffff",
        "bg": "#0e0e10",
        "logo_text": "twitch",
        "logo": "",
        "nav": ["Home", "Browse", "Following", "Search"],
        "series_shape": "poster",
        "signin": "device",
        "list_label": ["Follow", "Following"],
        "list_toast": ["Following {}.", "Unfollowed {}."],
    },
}

API_TV = "https://api.vhx.tv"
API_COM = "https://api.vhx.com"
UA = "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36"
TIMEOUT = (10, 30)


class SignInNeeded(Exception):
    pass


def img(src, w=None, h=None):
    """An imgix image URL at the size the TV shows it."""
    if not src:
        return ""
    base = src.split("?", 1)[0]
    q = {"auto": "format,compress", "q": 80}
    if w and h:
        q.update(w=w, h=h, fit="crop")
    elif w:
        q["w"] = w
    return base + "?" + urllib.parse.urlencode(q)


def secs(d):
    if isinstance(d, dict):
        return int(d.get("seconds") or 0)
    return int(d or 0)


def num(*values):
    """The first usable episode/season number: 3, or 8.5 (2nd Try has half episodes); else 0."""
    for v in values:
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if f:
            return int(f) if f.is_integer() else f
    return 0


def card(it):
    """A VHX item (api.vhx.tv style, or api.vhx.com v2 {entity, entity_type, play_state}) as a card."""
    e = it.get("entity", it)
    kind = it.get("entity_type") or e.get("type") or "video"
    if kind == "category":
        kind = "collection"
    adds = e.get("additional_images") or {}
    thumbs = e.get("thumbnails") or {}

    def pick(*names):
        for n in names:
            v = adds.get("aspect_ratio_" + n) or thumbs.get(n)
            if isinstance(v, dict) and v.get("source"):
                return v["source"]
        return ""

    t = e.get("thumbnail")
    thumb = t.get("source") if isinstance(t, dict) else ""
    md = e.get("metadata") or {}
    season = md.get("season") if isinstance(md.get("season"), dict) else {}
    series = md.get("series") if isinstance(md.get("series"), dict) else {}
    ps = it.get("play_state") or ((e.get("_embedded") or {}).get("play_state")) or {}
    dur = secs(e.get("duration"))
    tc = int(ps.get("timecode") or 0) if ps else 0
    done = bool(ps.get("completed")) if ps else False
    cc = e.get("canonical_collection") or {}
    return {
        "kind": kind,
        "id": int(e.get("id") or it.get("entity_id") or 0),
        "title": e.get("title") or e.get("name") or "",
        "description": e.get("short_description") or e.get("description") or "",
        "longDescription": e.get("description") or e.get("short_description") or "",
        "landscape": pick("16_9") or thumb or pick("16_9_background"),
        "poster": pick("2_3", "2_3_featured"),
        "square": pick("1_1"),
        "background": pick("16_9_background") or pick("16_9") or thumb,
        "logo": pick("12_5_logo"),
        "duration": dur,
        "timecode": tc,
        "completed": done,
        "progress": (1.0 if done else min(1.0, tc / dur)) if dur and (tc or done) else 0.0,
        "series": md.get("series_name") or series.get("name") or "",
        "seasonNumber": num(md.get("season_number"), season.get("number"), e.get("season_number")),
        "seasonName": md.get("season_name") or season.get("name") or "",
        "episode": num(md.get("episode_number"), season.get("episode_number"), e.get("episode_number")),
        "seasons": int(e.get("seasons_count") or 0),
        "items": int(e.get("items_count") or e.get("episodes_count") or 0),
        "collectionId": int(e.get("canonical_collection_id") or cc.get("id") or 0),
        "slug": e.get("slug") or e.get("url") or "",
        "upNext": int(e.get("up_next_offset_seconds") or 0),
    }


def browser_cookies(domain):
    """The TV browser's (Chromium Flatpak) cookies for a domain: a headless copy of its profile
    is started and asked over DevTools (cookies are encrypted on disk)."""
    prof = os.path.expanduser("~/.var/app/org.chromium.Chromium/config/chromium")
    if not os.path.isdir(os.path.join(prof, "Default")):
        return []
    tmp = tempfile.mkdtemp(prefix="couchbox-cookies-", dir=os.path.expanduser("~/.cache"))
    proc = None
    try:
        shutil.copytree(
            os.path.join(prof, "Default"),
            os.path.join(tmp, "Default"),
            ignore=shutil.ignore_patterns("Cache", "Code Cache", "GPUCache", "Service Worker", "IndexedDB"),
        )
        shutil.copy(os.path.join(prof, "Local State"), tmp)
        port = 9239
        proc = subprocess.Popen(
            [
                "flatpak",
                "run",
                "--command=chromium",
                f"--filesystem={tmp}",
                "org.chromium.Chromium",
                "--headless",
                "--mute-audio",
                "--password-store=basic",
                f"--user-data-dir={tmp}",
                f"--remote-debugging-port={port}",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        ws_url = None
        for _ in range(40):
            time.sleep(0.5)
            try:
                pages = requests.get(f"http://127.0.0.1:{port}/json", timeout=2).json()
                ws_url = next(p["webSocketDebuggerUrl"] for p in pages if p.get("type") == "page")
                break
            except Exception:
                continue
        if not ws_url:
            return []
        import websocket

        ws = websocket.create_connection(ws_url, timeout=10, suppress_origin=True)
        ws.send(json.dumps({"id": 1, "method": "Storage.getCookies", "params": {}}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == 1:
                break
        ws.close()
        return [c for c in msg.get("result", {}).get("cookies", []) if c["domain"].endswith(domain)]
    finally:
        if proc:
            proc.terminate()
            try:
                proc.wait(5)
            except subprocess.TimeoutExpired:
                proc.kill()
        shutil.rmtree(tmp, ignore_errors=True)


class Vhx:
    def __init__(self, site="dropout"):
        self.site = site
        self.cfg = SITES[site]
        self.dir = os.path.expanduser(f"~/.local/share/couchbox-{site}")
        os.makedirs(self.dir, mode=0o700, exist_ok=True)
        self.s = requests.Session()
        self.s.headers["User-Agent"] = UA
        self.token = ""
        self.token_exp = 0
        self.user = {}
        self.profile = 0
        self.device_id = ""
        self._load()

    # ------------------------------------------------------------------ session
    @property
    def session_file(self):
        return os.path.join(self.dir, "session.json")

    def _load(self):
        try:
            data = json.load(open(self.session_file))
        except (OSError, ValueError):
            data = {}
        for c in data.get("cookies", []):
            self.s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
        self.profile = int(data.get("profile", 0))
        self.device_id = data.get("device_id") or secrets.token_hex(16)

    def _save(self):
        cookies = [{"name": c.name, "value": c.value, "domain": c.domain, "path": c.path} for c in self.s.cookies]
        tmp = self.session_file + ".tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump({"cookies": cookies, "profile": self.profile, "device_id": self.device_id}, f)
        os.replace(tmp, self.session_file)

    HTML = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}  # else 406

    def _page(self, path):
        return self.s.get(self.cfg["web"] + path, headers=self.HTML, timeout=TIMEOUT)

    def refresh(self):
        """Read the API token and user from a site page. Returns "ok", "profile" (pick one)
        or "signin" (no session)."""
        r = self._page("/browse")
        if "/login" in r.url or "/signup" in r.url or "sign_in" in r.url:
            return "signin"
        if "/profile/pick" in r.url:
            self._pick_page = r.text
            return "profile"
        m = re.search(r'window\.TOKEN\s*=\s*"([^"]+)"', r.text) or re.search(r'(?s)VHX\.config\s*=\s*{.*?token:\s*"([^"]+)"', r.text)
        u = re.search(r"window\._current_user\s*=\s*(\{.*?\});", r.text)
        user = {}
        if u:
            try:
                user = json.loads(u.group(1)) or {}
            except ValueError:
                user = {}
        if not m or not user.get("id"):  # signed out: the site still hands out a token
            return "signin"
        self.token = m.group(1)
        try:
            payload = json.loads(base64.urlsafe_b64decode(self.token.split(".")[1] + "=="))
            self.token_exp = int(payload.get("exp") or 0)
        except (ValueError, IndexError):
            self.token_exp = time.time() + 3600
        self.user = user
        self._save()
        return "ok"

    def status(self):
        """{"state": "ok" | "profile" | "signin", ...}"""
        st = self.refresh()
        out = {"state": st, "site": self.cfg["name"]}
        if st == "ok":
            out["user"] = self.user.get("name") or self.user.get("email", "")
        elif st == "profile":
            out["profiles"] = self.profiles()
        return out

    def _pick_token(self):
        t = getattr(self, "_pick_page", "") or self._page("/profile/pick").text
        tok = re.search(r'window\.TOKEN\s*=\s*"([^"]+)"', t)
        uid = re.search(r'"user_id":(\d+)', t)
        csrf = re.search(r'<meta name="csrf-token" content="([^"]+)"', t)
        return (tok.group(1) if tok else ""), (uid.group(1) if uid else ""), (csrf.group(1) if csrf else "")

    def profiles(self):
        tok, uid, _ = self._pick_token()
        r = self.s.get(
            f"{API_COM}/v2/sites/{self.cfg['site_id']}/users/{uid}/profiles", headers={"Authorization": f"Bearer {tok}"}, timeout=TIMEOUT
        )
        return [
            {
                "index": p.get("index", i),
                "name": p.get("name", ""),
                "image": p.get("profile_image_url") or "",
                "locked": bool(p.get("pin_locked")),
            }
            for i, p in enumerate(r.json().get("profiles", []))
        ]

    def pick_profile(self, index):
        _, _, csrf = self._pick_token()
        r = self.s.post(
            self.cfg["web"] + "/profile/login",
            json={"profile_index": int(index)},
            headers={"X-CSRF-Token": csrf, "X-Requested-With": "XMLHttpRequest"},
            timeout=TIMEOUT,
        )
        if not r.ok:
            raise RuntimeError(f"couldn't pick that profile ({r.status_code})")
        self.profile = int(index)
        self._pick_page = ""
        return self.status()

    def login(self, email, password):
        page = self._page("/login")
        m = re.search(r'id="login-form-password".*?name="authenticity_token"[^>]*value="([^"]+)"', page.text, re.S) or re.search(
            r'name="authenticity_token"[^>]*value="([^"]+)"', page.text
        )
        if not m:
            raise RuntimeError("the sign-in page changed; sign in on the website instead")
        r = self.s.post(
            self.cfg["web"] + "/login",
            data={"email": email, "password": password, "authenticity_token": m.group(1), "utf8": "✓"},
            headers=self.HTML,
            timeout=TIMEOUT,
        )
        if "/login" in r.url and "logged_in" not in self.s.cookies:
            raise RuntimeError("That email and password didn't work.")
        return self.status()

    def import_browser(self):
        """Copy the site's sign-in from the TV's browser (see browser_cookies)."""
        got = browser_cookies(self.cfg["domain"])
        for c in got:
            self.s.cookies.set(c["name"], c["value"], domain=c["domain"], path=c.get("path", "/"))
        return any(c["name"] == "_session" for c in got)

    def sign_out(self):
        self.s.cookies.clear()
        self.token = ""
        try:
            os.remove(self.session_file)
        except OSError:
            pass

    # ------------------------------------------------------------------ API
    def _ensure(self):
        if not self.token or time.time() > self.token_exp - 120:
            if self.refresh() != "ok":
                raise SignInNeeded()

    def api(self, url, params=None, method="GET", retry=True):
        self._ensure()
        r = self.s.request(method, url, params=params, headers={"Authorization": f"Bearer {self.token}"}, timeout=TIMEOUT)
        if r.status_code == 401 and retry:
            self.token = ""
            return self.api(url, params, method, retry=False)
        r.raise_for_status()
        return r.json() if r.content else {}

    @property
    def uid(self):
        self._ensure()
        return self.user.get("id")

    def v2(self, path):
        return f"{API_COM}/v2/sites/{self.cfg['site_id']}{path}"

    @property
    def product(self):
        return f"{API_TV}/products/{self.cfg['product_id']}"

    def browse(self):
        """The website's home rows: [{title, kind, href, count, shape}] (shape: poster, square,
        landscape; kind: featured, watching, watchlist, row)."""
        b = self.api(
            f"{API_TV}/browse",
            {"site_id": self.cfg["site_id"], "product": self.product, "include_events": 1, "include_products": "true", "per_page": 100},
        )
        rows = []
        for r in b.get("_embedded", {}).get("items", []):
            href = ((r.get("_links") or {}).get("items") or {}).get("href", "")
            name = r.get("name") or ""
            if not href or not r.get("items_count"):
                continue
            kind = (
                "watching"
                if "/watching" in href
                else "watchlist"
                if "/watchlist" in href
                else "featured"
                if name.lower() == "featured"
                else "row"
            )
            t = r.get("thumbnail_type") or ""
            shape = "poster" if "2_3" in t else "square" if "1_1" in t else "wide"
            rows.append({"title": name, "kind": kind, "href": href, "count": r.get("items_count", 0), "shape": shape})
        return rows

    def featured(self):
        f = self.api(
            f"{API_TV}/products/featured_items", {"site_id": self.cfg["site_id"], "hub_id": self.cfg["featured_hub"], "per_page": 12}
        )
        return [card(i) for i in f.get("_embedded", {}).get("items", [])]

    def watching(self, page=1):
        w = self.api(
            self.v2(f"/users/{self.uid}/watching"),
            {"page": page, "per_page": 24, "include_events": 1, "include_coming_soon": 1, "include_collections": 1},
        )
        pg = w.get("pagination") or {}
        return {"items": [card(i) for i in w.get("items", [])], "more": pg.get("current", 0) < pg.get("count", 0)}

    def items(self, href, page=1, per_page=24):
        """A row or collection's items (api.vhx.tv _embedded.items), with watch progress for videos."""
        sep = "&" if "?" in href else "?"
        r = self.api(
            f"{href}{sep}page={page}&per_page={per_page}"
            + ("" if "product=" in href else f"&product={urllib.parse.quote(self.product, safe='')}")
        )
        cards = [card(i) for i in r.get("_embedded", {}).get("items", [])]
        self.add_progress(cards)
        return {"items": cards, "more": page * per_page < int(r.get("total") or 0), "total": int(r.get("total") or 0)}

    def add_progress(self, cards):
        ids = [c["id"] for c in cards if c["kind"] == "video" and not c["progress"]]
        for i in range(0, len(ids), 50):
            try:
                st = self.api(self.v2(f"/users/{self.uid}/play_state"), {"video_ids": ",".join(map(str, ids[i : i + 50]))})
            except requests.RequestException:
                return
            by = {e["video_id"]: e for e in st.get("entries", [])}
            for c in cards:
                e = by.get(c["id"])
                if e and c["duration"]:
                    c["timecode"], c["completed"] = int(e.get("timecode") or 0), bool(e.get("completed"))
                    c["progress"] = 1.0 if c["completed"] else min(1.0, c["timecode"] / c["duration"])

    def collection(self, cid):
        """A series, season, movie or collection: its card plus, for a series, its seasons."""
        c = self.api(f"{API_TV}/collections/{cid}", {"product": self.product})
        out = card(c)
        links = c.get("_links") or {}
        out["seriesId"] = int(re.sub(r"\D", "", (links.get("series") or {}).get("href", "").rsplit("/", 1)[-1]) or 0)
        out["trailer"] = ""
        tr = (c.get("_embedded") or {}).get("trailer")
        if tr:
            out["trailer"] = str(tr.get("id") or "")
        if out["kind"] == "series":
            s = self.api(f"{API_TV}/collections/{cid}/items", {"product": self.product, "per_page": 100})
            out["seasonList"] = [
                {
                    "id": i["id"],
                    "name": i.get("name") or f"Season {i.get('season_number')}",
                    "number": num(i.get("season_number")),
                    "count": int(i.get("items_count") or 0),
                }
                for i in s.get("_embedded", {}).get("items", [])
            ]
        return out

    def all_series(self):
        """Every show: the site's All Series collection, else its "Shows" row, else the shows in
        all its home rows."""
        if self.cfg.get("all_series"):
            return self.items(f"{API_TV}/collections/{self.cfg['all_series']}/items", 1, per_page=200)
        from concurrent.futures import ThreadPoolExecutor

        rows = [r for r in self.browse() if r["kind"] == "row"]
        named = [r for r in rows if r["title"].strip().lower() in ("all series", "all shows", "shows", "series")]
        if named:
            return self.items(named[0]["href"], 1, per_page=200)
        with ThreadPoolExecutor(6) as ex:
            lists = list(ex.map(lambda r: self.items(r["href"], 1, per_page=50)["items"], rows))
        seen, out = set(), []
        for cards in lists:
            for c in cards:
                if c["kind"] in ("series", "movie", "collection") and c["id"] not in seen:
                    seen.add(c["id"])
                    out.append(c)
        return {"items": out, "more": False}

    def collection_items(self, cid, page=1):
        return self.items(f"{API_TV}/collections/{cid}/items", page, per_page=50)

    def search(self, q, page=1):
        r = self.api(self.v2("/search"), {"q": q, "type": "video,collection", "page": page, "per_page": 30, "include_coming_soon": 1})
        cards = [card(i) for i in r.get("results", [])]
        self.add_progress(cards)
        pg = r.get("pagination") or {}
        return {"items": cards, "more": pg.get("current", 0) < pg.get("count", 0)}

    def video(self, vid):
        v = self.api(f"{API_TV}/videos/{vid}", {"product": self.product})
        c = card(v)
        cc = v.get("canonical_collection") or {}
        parent = ((cc.get("parent") or {}).get("_links") or {}).get("self", {}).get("href", "")
        c["seriesId"] = int(parent.rsplit("/", 1)[-1]) if parent else 0
        c["subtitles"] = [
            {"label": s.get("label") or "English", "url": (s.get("_links") or {}).get("vtt", {}).get("href", "")}
            for s in (v.get("tracks") or {}).get("subtitles", [])
            if not s.get("failed")
        ]
        self.add_progress([c])
        return c

    def playback(self, vid):
        """Everything the player needs: the HLS stream, subtitles, where to start, what's next."""
        c = self.video(vid)
        files = self.api(f"{API_TV}/videos/{vid}/files")
        hls = next((f for f in files if f.get("format") == "m3u8"), None) or files[0]
        src = hls["_links"]["source"]["href"]
        # The link redirects to the CDN's playlist, whose paths are relative to where it really
        # is: hand mpv the address after the redirect (ffmpeg resolves them against the first).
        try:
            r = self.s.get(src, timeout=TIMEOUT, stream=True)
            c["url"] = r.url
            r.close()
        except requests.RequestException:
            c["url"] = src
        resume = int(hls.get("current_time") or 0) or (0 if c["completed"] else c["timecode"])
        c["start"] = resume if resume < max(0, c["duration"] - 30) else 0
        c["next"] = None
        if c["collectionId"]:
            eps = self.collection_items(c["collectionId"])["items"]
            ids = [e["id"] for e in eps]
            if vid in ids and ids.index(vid) + 1 < len(ids):
                c["next"] = eps[ids.index(vid) + 1]
        return c

    def watchlist(self, op, kind, cid):
        typ = "collection" if kind in ("series", "season", "collection", "movie") else "video"
        self.api(f"{API_TV}/me/watchlist", {typ: f"{API_TV}/{typ}s/{cid}"}, method="PUT" if op == "add" else "DELETE")
        return {"ok": True}

    def my_list(self, page=1):
        return self.items(f"{API_TV}/customers/{self.uid}/watchlist", page)

    def on_watchlist(self, cid):
        r = self.api(f"{API_TV}/customers/{self.uid}/watchlist", {"product": self.product, "per_page": 100})
        return any(int(i.get("id") or 0) == int(cid) for i in r.get("_embedded", {}).get("items", []))

    # ------------------------------------------------------------------ progress
    def event(self, name, vid, collection_id, timecode, duration, session_id, subtitle="none"):
        """The website player's progress reports (collector.vhx.tv): Continue Watching and resume
        positions come from these."""
        q = {
            "name": name,
            "user_id": self.user.get("id", ""),
            "profile_id": self.profile,
            "user_email": self.user.get("email", ""),
            "site_id": self.cfg["site_id"],
            "user_agent": UA,
            "url": self.cfg["web"] + "/",
            "referrer": "https://embed.vhx.tv/",
            "session_id": session_id,
            "device": "html5",
            "collection_id": collection_id or "",
            "product_id": self.cfg["product_id"],
            "platform": "web",
            "type": "video",
            "video_id": vid,
            "current_type": "video",
            "current_subtitle": subtitle,
            "duration": int(duration or 0),
            "is_drm": 0,
            "is_fullscreen": 1,
            "is_trailer": 0,
            "is_chromecast": 0,
            "is_live": 0,
            "seconds": 10,
            "timecode": round(float(timecode), 3),
            "timestamp": int(time.time()),
        }
        try:
            self.s.get("https://collector.vhx.tv/events.gif", params=q, timeout=10)
        except requests.RequestException:
            pass
