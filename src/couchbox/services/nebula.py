"""Nebula client for the couchbox TV app (the same screens and player as Dropout / 2nd Try).

Nebula has its own API (as used by its website and apps, and by yt-dlp):
  sign-in    POST users.api.nebula.app/api/v1/auth/login/ {email, password} -> {"key"} (kept), or the website's
             nebula_auth.apiToken cookie copied from the TV browser
  token      POST users.api.nebula.app/api/v1/authorization/ (Authorization: Token <key>) -> JWT
  content    content.api.nebula.app: featured_pages/featured/ (heroes = the banner, rails =
             the rows), content/<slug>/ (a channel, its seasons and playlists), video_episodes/
             .../manifest.m3u8 (HLS), .../progress/ (watch position), search
Everything comes out as the same "cards" as vhx.py, with Nebula's string ids.
"""

import base64
import json
import os
import re
import time
import urllib.parse

import requests

from . import vhx

CONTENT = "https://content.api.nebula.app"
USERS = "https://users.api.nebula.app/api/v1"
WEB = "https://nebula.tv"
TIMEOUT = (10, 30)


def src(images, *names):
    for n in names:
        v = (images or {}).get(n)
        if isinstance(v, dict) and v.get("src"):
            return v["src"]
    return ""


class Nebula:
    def __init__(self, site="nebula"):
        self.site = site
        self.cfg = vhx.SITES[site]
        self.dir = os.path.expanduser(f"~/.local/share/couchbox-{site}")
        os.makedirs(self.dir, mode=0o700, exist_ok=True)
        self.s = requests.Session()
        self.s.headers["User-Agent"] = vhx.UA
        self.key = ""
        self.token = ""
        self.token_exp = 0
        self.user = {}
        try:
            self.key = json.load(open(self.session_file)).get("key", "")
        except (OSError, ValueError):
            pass

    # ------------------------------------------------------------------ session
    @property
    def session_file(self):
        return os.path.join(self.dir, "session.json")

    def _save(self):
        tmp = self.session_file + ".tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump({"key": self.key}, f)
        os.replace(tmp, self.session_file)

    def refresh(self):
        headers = {"Authorization": f"Token {self.key}"} if self.key else {}
        r = self.s.post(f"{USERS}/authorization/", headers=headers, timeout=TIMEOUT)
        if r.status_code in (401, 403) and self.key:
            return "signin"
        r.raise_for_status()
        self.token = r.json()["token"]
        try:
            payload = json.loads(base64.urlsafe_b64decode(self.token.split(".")[1] + "=="))
            self.token_exp = int(payload.get("exp") or 0) or time.time() + 3600
        except (ValueError, IndexError):
            self.token_exp = time.time() + 3600
        # tests: COUCHBOX_TEST_ANON=1 browses with an anonymous token (no playback)
        return "ok" if self.key or os.environ.get("COUCHBOX_TEST_ANON") == "1" else "signin"

    def status(self):
        st = self.refresh() if self.key or os.environ.get("COUCHBOX_TEST_ANON") == "1" else "signin"
        out = {"state": st, "site": self.cfg["name"]}
        if st == "ok":
            try:
                me = self.s.get(f"{USERS}/auth/user/", headers=self._auth(), timeout=TIMEOUT).json()
                self.user = me
                out["user"] = me.get("email") or me.get("name") or ""
            except (requests.RequestException, ValueError):
                pass
        return out

    def login(self, email, password):
        # users.api's login (nebula.tv/auth/login/ now wants the web page's challenge first)
        r = self.s.post(f"{USERS}/auth/login/", json={"email": email, "password": password}, timeout=TIMEOUT)
        if r.status_code == 400:
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            msg = " ".join(sum((v if isinstance(v, list) else [str(v)] for v in body.values()), [])) if body else ""
            raise RuntimeError("That email and password didn't work." if "credentials" in msg or not msg else msg)
        r.raise_for_status()
        self.key = r.json().get("key", "")
        if not self.key:
            raise RuntimeError("Nebula didn't sign in.")
        self._save()
        return self.status()

    def import_browser(self):
        got = vhx.browser_cookies("nebula.tv")
        key = next((c["value"] for c in got if c["name"] == "nebula_auth.apiToken"), "")
        if key:
            self.key = urllib.parse.unquote(key)
            self._save()
        return bool(key)

    def sign_out(self):
        self.key = self.token = ""
        try:
            os.remove(self.session_file)
        except OSError:
            pass

    def pick_profile(self, index):
        return self.status()

    # ------------------------------------------------------------------ API
    def _auth(self):
        if not self.token or time.time() > self.token_exp - 120:
            if self.refresh() != "ok":
                raise vhx.SignInNeeded()
        return {"Authorization": f"Bearer {self.token}"}

    def api(self, url, params=None, method="GET", body=None, retry=True):
        if not url.startswith("http"):
            url = CONTENT + url
        r = self.s.request(method, url, params=params, json=body, headers=self._auth(), timeout=TIMEOUT)
        if r.status_code in (401, 403) and retry:
            self.token = ""
            return self.api(url, params, method, body, retry=False)
        r.raise_for_status()
        return r.json() if r.content else {}

    @staticmethod
    def img(url, width):
        return f"{url}?width={int(width)}&format=webp" if url else ""

    def card(self, e):
        t = e.get("type") or ""
        im = e.get("images") or {}
        if t in ("video_episode", "lesson"):
            eng = e.get("engagement") or {}
            prog = eng.get("progress") if isinstance(eng.get("progress"), dict) else {}
            dur = int(e.get("duration") or 0)
            tc = int(prog.get("value") or 0)
            done = bool(prog.get("completed"))
            return {
                "kind": "video",
                "id": e.get("id", ""),
                "slug": e.get("slug", ""),
                "title": e.get("title", ""),
                "description": e.get("short_description") or e.get("description") or "",
                "longDescription": e.get("description") or "",
                "landscape": self.img(src(im, "thumbnail"), 1280),
                "poster": "",
                "square": "",
                "background": self.img(src(im, "thumbnail"), 1920),
                "logo": "",
                "duration": dur,
                "timecode": tc,
                "completed": done,
                "progress": (1.0 if done else min(1.0, tc / dur)) if dur and (tc or done) else 0.0,
                "series": e.get("channel_title") or "",
                "seasonNumber": 0,
                "seasonName": "",
                "episode": 0,
                "seasons": 0,
                "items": 0,
                "collectionId": e.get("channel_slug") or "",
                "upNext": 0,
                "watchLater": bool(eng.get("watch_later")),
            }
        # a channel (video_channel), a playlist, a podcast or a class: opens as a "show"
        slug = e.get("slug") or (e.get("app_path") or "").strip("/").split("/")[0]
        return {
            "kind": "series",
            "id": slug,
            "slug": slug,
            "title": e.get("title", ""),
            "description": e.get("short_description") or e.get("description") or "",
            "longDescription": e.get("description") or "",
            "landscape": self.img(src(im, "featured", "banner", "cover_fallback", "hero", "avatar"), 1280),
            "poster": "",
            "square": self.img(src(im, "avatar", "featured"), 600),
            "background": self.img(src(im, "banner", "hero", "featured"), 1920),
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
            "items": int(e.get("episodes_count") or 0),
            "collectionId": "",
            "upNext": 0,
        }

    def page(self, url, params=None):
        r = self.api(url, params)
        if isinstance(r, list):  # some collections (Top ...) are plain lists
            return {"items": [self.card(e) for e in r], "next": None}
        return {"items": [self.card(e) for e in r.get("results") or []], "next": r.get("next")}

    # ------------------------------------------------------------------ the app's calls (as vhx.Vhx)
    PLAYABLE = ("video_episodes", "video_channels", "lessons", "classes")

    def browse(self):
        f = self.api("/featured_pages/featured/")
        rows = []
        for r in f.get("rails", []):
            ct = r.get("content_type") or ""
            if not r.get("collection") or ct not in self.PLAYABLE:
                continue
            attrs = r.get("attributes") or []
            kind = "watching" if "continue_watching" in attrs else "watchlist" if "watch_later" in attrs else "row"
            shape = "square" if ct != "video_episodes" and r.get("size") == "small" else "wide"
            rows.append({"title": r.get("title", ""), "kind": kind, "href": r["collection"], "count": 1, "shape": shape})
        return rows

    def featured(self):
        f = self.api("/featured_pages/featured/")
        out = []
        for h in f.get("heroes", []):
            path = urllib.parse.urlsplit(h.get("url") or "").path.strip("/").split("/")
            if not path or not path[0]:
                continue
            im = h.get("images") or {}
            c = {
                "kind": "video" if path[0] == "videos" else "series",
                "id": path[1] if path[0] == "videos" and len(path) > 1 else path[0],
                "slug": path[-1],
                "title": h.get("title", ""),
                "description": h.get("short_description", ""),
                "longDescription": "",
                "landscape": self.img(src(im, "background_wide", "background_wide_fallback"), 1280),
                "background": self.img(src(im, "background_wide", "background_wide_fallback"), 1920),
                "logo": self.img(src(im, "title_logo"), 900),
                "poster": "",
                "square": "",
                "duration": 0,
                "progress": 0.0,
                "collectionId": "",
                "seasons": 0,
                "items": 0,
                "episode": 0,
                "seasonNumber": 0,
            }
            out.append(c)
        return out

    def items(self, href, page=1, per_page=24):
        sep = "&" if "?" in href else "?"
        p = self.page(f"{href}{sep}page_size={per_page}&offset={(page - 1) * per_page}")
        return {"items": p["items"], "more": bool(p["next"])}

    def watching(self, page=1):
        out = self.items(f"{CONTENT}/video_episodes/auto_collections/continue/", page)
        from concurrent.futures import ThreadPoolExecutor

        def prog(c):  # progress bars: each one's position
            try:
                p = self.api(f"/video_episodes/{c['id']}/progress/")
                c["timecode"], c["completed"] = int(p.get("value") or 0), bool(p.get("completed"))
                if c["duration"]:
                    c["progress"] = 1.0 if c["completed"] else min(1.0, c["timecode"] / c["duration"])
            except requests.RequestException:
                pass

        with ThreadPoolExecutor(6) as ex:
            list(ex.map(prog, out["items"]))
        return out

    def my_list(self, page=1):
        return self.items(f"{CONTENT}/video_episodes/auto_collections/watch_later/", page)

    def all_series(self):
        if getattr(self, "_channels", None) and time.time() - self._channels[0] < 3600:
            return {"items": self._channels[1], "more": False}
        out, url = [], f"{CONTENT}/video_channels/?page_size=100"
        while url and len(out) < 600:
            p = self.page(url)
            out += p["items"]
            url = p["next"]
        out.sort(key=lambda c: c["title"].lower())
        self._channels = (time.time(), out)
        return {"items": out, "more": False}

    def collection(self, slug):
        """A channel: title, artwork, description, and its "seasons": a series' seasons, else
        its latest videos plus its playlists. Season ids say where their episodes come from."""
        slug = str(slug)
        c = self.api(f"/content/{slug}/")
        out = self.card(c)
        epi = c.get("episodic") or {}
        out["logo"] = self.img(src(epi.get("images") or {}, "title_image"), 900)
        out["trailer"] = ""
        seasons = []
        for i, s in enumerate(epi.get("seasons") or []):
            n = (s.get("app_path") or "").rstrip("/").rsplit("/", 1)[-1]
            seasons.append(
                {
                    "id": f"season|{slug}|{n}",
                    "name": s.get("title") or f"{epi.get('season_label_type') or 'Season'} {n}",
                    "number": vhx.num(n) or i + 1,
                    "count": int(s.get("episodes_count") or 0),
                }
            )
        if not seasons:
            seasons.append({"id": f"channel|{c.get('id')}", "name": "Latest Videos", "number": 1, "count": 0})
            for pl in c.get("playlists") or []:
                url = pl.get("video_episodes_url") or pl.get("miniseries_episodes_url")
                if url:
                    seasons.append(
                        {
                            "id": f"url|{url}",
                            "name": pl.get("title") or "Playlist",
                            "number": 0,
                            "count": int(pl.get("episodes_count") or 0),
                        }
                    )
        out["kind"] = "series"
        out["seasons"] = len(epi.get("seasons") or [])
        out["seasonList"] = seasons
        return out

    def collection_items(self, cid, page=1):
        kind, _, rest = str(cid).partition("|")
        if kind == "season":
            slug, _, n = rest.partition("|")
            s = self.api(f"/content/{slug}/season/{n}/")
            cards = []
            for e in s.get("episodes") or []:  # season_episode: {title, label, video}
                v = e.get("video") or e.get("video_episode")
                if not isinstance(v, dict):
                    continue  # announced, not out yet
                c = self.card(v)
                c["title"] = e.get("title") or c["title"]
                c["description"] = e.get("short_description") or c["description"]
                cards.append(c)
            for i, c in enumerate(cards):
                c["episode"] = i + 1
                c["seasonNumber"] = vhx.num(n)
            return {"items": cards, "more": False}
        if kind == "channel":
            return self.items(f"{CONTENT}/video_channels/{rest}/video_episodes/", page, per_page=30)
        if kind == "url":
            return self.items(rest, page, per_page=30)
        return self.items(f"{CONTENT}/video_channels/{cid}/video_episodes/", page, per_page=30)

    def search(self, q, page=1):
        qq = urllib.parse.quote(q)
        chans = self.page(f"/video_channels/search/?q={qq}&page_size=12")["items"] if page == 1 else []
        vids = self.items(f"{CONTENT}/video_episodes/search/?q={qq}", page)
        return {"items": chans + vids["items"], "more": vids["more"]}

    def video(self, vid):
        vid = str(vid)
        e = self.api(f"/content/videos/{vid}/") if not vid.startswith("video_episode:") else self.api(f"/video_episodes/{vid}/")
        return self.card(e)

    def pick_streams(self, master_url, text, max_height=1080):
        """A copy of the HLS master playlist with only the best video stream the Pi plays well:
        HEVC (hardware decoder) else H.264, at most 1080p; audio and subtitles kept. Nebula
        offers up to 4K, and mpv on its own would take the highest bitrate."""
        lines = text.splitlines()
        absu = lambda u: urllib.parse.urljoin(master_url, u)
        head, variants = [], []
        i = 0
        while i < len(lines):
            ln = lines[i]
            if ln.startswith("#EXT-X-STREAM-INF"):
                uri = lines[i + 1] if i + 1 < len(lines) else ""
                h = int((re.search(r"RESOLUTION=\d+x(\d+)", ln) or [0, 0])[1])
                bw = int((re.search(r"[,:]BANDWIDTH=(\d+)", ln) or [0, 0])[1])
                codecs = (re.search(r'CODECS="([^"]+)"', ln) or [0, ""])[1]
                variants.append((ln, absu(uri), h, bw, codecs))
                i += 2
                continue
            if ln.startswith("#EXT-X-MEDIA") and 'URI="' in ln:
                ln = re.sub(r'URI="([^"]+)"', lambda m: f'URI="{absu(m.group(1))}"', ln)
            if ln.startswith(("#EXT-X-I-FRAME-STREAM-INF", "#EXT-X-IMAGE-STREAM-INF")):
                i += 1
                continue
            head.append(ln)
            i += 1
        ok = [v for v in variants if v[2] <= max_height] or variants
        hevc = [v for v in ok if v[4].startswith(("hvc1", "hev1"))]
        best = max(hevc or ok, key=lambda v: (v[2], v[3]))
        return "\n".join(head + [best[0], best[1]]) + "\n"

    def playback(self, vid):
        c = self.video(vid)
        url = f"{CONTENT}/video_episodes/{c['id']}/manifest.m3u8"
        params = {"token": self.token, "app_version": "23.10.0", "platform": "ios"}
        r = self.s.get(url, params=params, timeout=TIMEOUT)
        if r.status_code in (401, 403):
            raise RuntimeError("Nebula needs a subscription for this one, or a fresh sign-in.")
        r.raise_for_status()
        path = os.path.join(self.dir, "playing.m3u8")
        with open(path, "w") as f:
            f.write(self.pick_streams(r.url, r.text))
        c["url"] = path
        try:  # where it was left (the progress endpoint)
            p = self.api(f"/video_episodes/{c['id']}/progress/")
            c["timecode"], c["completed"] = int(p.get("value") or 0), bool(p.get("completed"))
        except requests.RequestException:
            pass
        c["start"] = c["timecode"] if not c["completed"] and c["timecode"] < max(0, c["duration"] - 30) else 0
        c["subtitles"] = []
        c["next"] = None
        try:  # what's next on its channel (oldest to newest)
            if c["collectionId"]:
                ch = self.api(f"/content/{c['collectionId']}/")
                lst = self.page(f"/video_channels/{ch['id']}/video_episodes/?page_size=50")["items"]
                ids = [x["id"] for x in lst]
                if c["id"] in ids and ids.index(c["id"]) > 0:
                    c["next"] = lst[ids.index(c["id"]) - 1]  # the list is newest first
        except (requests.RequestException, KeyError, ValueError):
            pass
        return c

    def watchlist(self, op, kind, cid):
        raise RuntimeError("Not on Nebula yet.")

    def on_watchlist(self, cid):
        return False

    # ------------------------------------------------------------------ progress
    def event(self, name, vid, collection_id, timecode, duration, session_id, subtitle="none"):
        if name not in ("timeupdate", "pause", "ended", "firstplay"):
            return
        try:
            self.api(f"/video_episodes/{vid}/progress/", method="PATCH", body={"value": int(timecode), "completed": name == "ended"})
        except requests.RequestException:
            pass
