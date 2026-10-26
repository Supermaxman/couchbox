"""Spotify for the TV app and the voice assistant: the user's account through the Spotify Web
API, with their own developer app (a client ID: see docs/design/spotify.md for why).

Sign-in is OAuth with PKCE, done on a phone: the TV shows a QR code to Spotify's sign-in page,
and Spotify sends the phone back to the box's phone page (https://<box>.<tailnet>/spotify/
callback, when Tailscale serves it) or to http://127.0.0.1:8792/callback, an address the phone
can't open: then its address bar holds the code, and it's typed into the TV. Tokens live in
~/.local/share/couchbox-spotify/session.json (mode 0600). Spotify's refresh tokens are single
use, and the app and couchbox-spotify --connect both refresh: a lock file, and re-reading the
file before refreshing, keep one process from spending a token another already swapped.

What a development-mode app may do changed in 2024 and 2026 (no recommendations, no
algorithmic or editorial playlist contents, no new releases, no artist top tracks, playlist
songs only for your own playlists, 10 search results). So:
  new releases  -> the latest albums and singles of artists you follow and listen to most
  popular songs -> a search for the artist's songs (Spotify ranks them by popularity)
  made for you  -> Spotify's playlists you saved, and those played on this TV (couchbox-spotify
                   --connect notes their names from the player); they play, but their song
                   lists can't be read
Every call falls back to the older endpoint when the newer one isn't there (older apps).
"""

import base64
import fcntl
import hashlib
import json
import os
import re
import secrets
import threading
import time
import urllib.parse
from pathlib import Path

import requests

API = "https://api.spotify.com/v1"
ACCOUNTS = "https://accounts.spotify.com"
LOOPBACK_REDIRECT = "http://127.0.0.1:8792/callback"
TIMEOUT = 15
SCOPES = (
    "user-read-private user-read-playback-state user-modify-playback-state user-read-currently-playing "
    "user-read-recently-played user-top-read user-library-read user-library-modify user-follow-read "
    "playlist-read-private playlist-read-collaborative playlist-modify-private playlist-modify-public"
)


class SignInNeeded(Exception):
    pass


class SpotifyError(Exception):
    pass


def data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    d = Path(base) / "couchbox-spotify"
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    return d


def _write_private(path: Path, obj) -> None:
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f)
    os.replace(tmp, path)


def _read(path: Path, default=None):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def parse_callback(text: str) -> dict:
    """code/state/error from a callback address (or just its query), as typed from a phone."""
    text = (text or "").strip()
    q = urllib.parse.urlparse(text).query if "?" in text else text
    p = urllib.parse.parse_qs(q)
    return {k: p[k][0] for k in ("code", "state", "error") if p.get(k)}


# ------------------------------------------------------------------ normalized items
def _img(images, want=300):
    """The image closest to `want` pixels wide."""
    if not images:
        return ""
    return min(images, key=lambda i: abs((i.get("width") or want) - want)).get("url", "")


def norm_artist(a):
    return {
        "kind": "artist",
        "uri": a.get("uri", ""),
        "id": a.get("id", ""),
        "name": a.get("name", ""),
        "image": _img(a.get("images")),
        "genres": a.get("genres") or [],
    }


def norm_album(a):
    kind = (a.get("album_type") or "album").lower()
    return {
        "kind": "album",
        "uri": a.get("uri", ""),
        "id": a.get("id", ""),
        "name": a.get("name", ""),
        "artists": [{"id": x.get("id", ""), "name": x.get("name", "")} for x in a.get("artists") or []],
        "image": _img(a.get("images")),
        "year": (a.get("release_date") or "")[:4],
        "date": a.get("release_date") or "",
        "type": "single" if kind == "single" else "compilation" if kind == "compilation" else "album",
        "group": a.get("album_group") or kind,
        "total": a.get("total_tracks") or 0,
    }


def norm_track(t, album=None):
    t = t or {}
    al = t.get("album") or album or {}
    return {
        "kind": "track",
        "uri": t.get("uri", ""),
        "id": t.get("id", ""),
        "name": t.get("name", ""),
        "artists": [{"id": x.get("id", ""), "name": x.get("name", "")} for x in t.get("artists") or []],
        "album": {"id": al.get("id", ""), "uri": al.get("uri", ""), "name": al.get("name", "")},
        "image": _img(al.get("images"), 160),
        "duration": round((t.get("duration_ms") or 0) / 1000),
        "explicit": bool(t.get("explicit")),
        "playable": t.get("is_playable", True) is not False,
    }


def norm_playlist(p, me=""):
    owner = p.get("owner") or {}
    total = (p.get("items") or p.get("tracks") or {}).get("total", 0) if isinstance(p.get("items") or p.get("tracks"), dict) else 0
    return {
        "kind": "playlist",
        "uri": p.get("uri", ""),
        "id": p.get("id", ""),
        "name": p.get("name", ""),
        "owner": owner.get("display_name") or owner.get("id", ""),
        "owner_id": owner.get("id", ""),
        "image": _img(p.get("images")),
        "total": total,
        "mine": bool(me) and owner.get("id") == me,
        "collaborative": bool(p.get("collaborative")),
        "spotify": owner.get("id") == "spotify",
        "description": re.sub(r"<[^>]+>", "", p.get("description") or ""),
    }


class Spotify:
    def __init__(self, client_id="", demo=False):
        self.client_id = client_id
        self.demo = demo
        self.dir = data_dir()
        self.session_file = self.dir / "session.json"
        self.pending_file = self.dir / "pending.json"
        self.contexts_file = self.dir / "contexts.json"
        self.cache_file = self.dir / "cache.json"
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "Couchbox (TV app)"
        self.auth = {}
        self._lock = threading.Lock()
        self._reload()

    # ------------------------------------------------------------------ sign-in
    def _reload(self):
        self.auth = _read(self.session_file, {}) or {}

    def _save(self):
        _write_private(self.session_file, self.auth)

    @property
    def signed_in(self):
        return bool(self.demo or self.auth.get("refresh_token"))

    def status(self):
        if self.demo:
            return {"configured": True, "signedIn": True, "user": "Demo Listener", "client_id": "demo"}
        self._reload()
        return {
            "configured": bool(self.client_id),
            "signedIn": self.signed_in and self.auth.get("client_id") == self.client_id,
            "user": (self.auth.get("user") or {}).get("name", ""),
            "client_id": self.client_id,
        }

    def start_login(self, redirect_uri):
        """Spotify's sign-in page for a phone (PKCE); the code comes back to finish_login."""
        if not self.client_id:
            raise SpotifyError("Add your Spotify client ID first.")
        verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        state = secrets.token_urlsafe(12)
        q = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": SCOPES,
            "state": state,
            "code_challenge_method": "S256",
            "code_challenge": challenge,
        }
        url = f"{ACCOUNTS}/authorize?" + urllib.parse.urlencode(q)
        _write_private(
            self.pending_file,
            {
                "state": state,
                "verifier": verifier,
                "redirect_uri": redirect_uri,
                "client_id": self.client_id,
                "created": time.time(),
                "url": url,
            },
        )
        return {"url": url, "redirect_uri": redirect_uri}

    def finish_login(self, code="", state="", error="", pasted=""):
        """The code from the callback (the phone page) or a pasted callback address."""
        if pasted:
            p = parse_callback(pasted)
            code, state, error = p.get("code", ""), p.get("state", ""), p.get("error", "")
        if error:
            raise SpotifyError("Spotify said: " + error.replace("_", " ") + ".")
        pend = _read(self.pending_file, {}) or {}
        if not code or not pend or not secrets.compare_digest(str(state), str(pend.get("state", ""))):
            raise SpotifyError("That sign-in doesn't match this TV. Scan the new code and try again.")
        if time.time() - pend.get("created", 0) > 900:
            raise SpotifyError("That sign-in took too long. Scan the new code and try again.")
        r = self.s.post(
            f"{ACCOUNTS}/api/token",
            timeout=TIMEOUT,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": pend["redirect_uri"],
                "client_id": pend["client_id"],
                "code_verifier": pend["verifier"],
            },
        )
        if not r.ok:
            raise SpotifyError(f"Spotify didn't accept the sign-in ({r.status_code}): {r.text[:160]}")
        j = r.json()
        with self._file_lock():
            self.auth = {
                "client_id": pend["client_id"],
                "access_token": j["access_token"],
                "refresh_token": j["refresh_token"],
                "expires_at": time.time() + int(j.get("expires_in") or 3600),
                "scope": j.get("scope", ""),
                "signed_in_at": time.time(),
                "refreshed_at": time.time(),
            }
            self._save()
        self.pending_file.unlink(missing_ok=True)
        me = self.get("/me")
        self.auth["user"] = {
            "id": me.get("id", ""),
            "name": me.get("display_name") or me.get("id", ""),
            "product": me.get("product", ""),
            "country": me.get("country", ""),
        }
        with self._file_lock():
            self._save()
        return self.status()

    def _file_lock(self):
        class _L:
            def __enter__(s):
                s.f = open(self.dir / ".lock", "w")
                fcntl.flock(s.f, fcntl.LOCK_EX)
                return s

            def __exit__(s, *a):
                s.f.close()

        return _L()

    def token(self, force=False):
        """The access token, refreshed near expiry; SignInNeeded when signed out."""
        if not self.auth.get("refresh_token"):
            self._reload()
        if not self.auth.get("refresh_token"):
            raise SignInNeeded("Sign in to Spotify.")
        if force or time.time() > self.auth.get("expires_at", 0) - 300:
            with self._lock, self._file_lock():
                mine = self.auth.get("refresh_token")
                self._reload()  # the other process may have refreshed already
                if not self.auth.get("refresh_token"):
                    raise SignInNeeded("Sign in to Spotify.")
                if self.auth["refresh_token"] != mine and time.time() < self.auth.get("expires_at", 0) - 300:
                    return self.auth["access_token"]
                r = self.s.post(
                    f"{ACCOUNTS}/api/token",
                    timeout=TIMEOUT,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": self.auth["refresh_token"],
                        "client_id": self.auth.get("client_id") or self.client_id,
                    },
                )
                if r.ok:
                    j = r.json()
                    self.auth.update(
                        access_token=j["access_token"],
                        refresh_token=j.get("refresh_token") or self.auth["refresh_token"],
                        expires_at=time.time() + int(j.get("expires_in") or 3600),
                        refreshed_at=time.time(),
                    )
                    self._save()
                elif r.status_code in (400, 401):  # revoked, or past Spotify's six months
                    print(f"spotify: refresh refused ({r.status_code} {r.text[:120]}): signed out", flush=True)
                    self.sign_out()
                    raise SignInNeeded("Spotify signed this TV out. Sign in again.")
                else:
                    raise SpotifyError(f"Spotify's sign-in service answered {r.status_code}.")
        return self.auth["access_token"]

    def sign_out(self):
        self.auth = {}
        self.session_file.unlink(missing_ok=True)
        return self.status() if not self.demo else {}

    # ------------------------------------------------------------------ requests
    def request(self, method, path, params=None, body=None, _retry=True):
        if self.demo:
            raise SpotifyError("demo")
        r = self.s.request(
            method, API + path, params=params, json=body, timeout=TIMEOUT, headers={"Authorization": f"Bearer {self.token()}"}
        )
        if r.status_code == 401 and _retry:
            self.token(force=True)
            return self.request(method, path, params, body, _retry=False)
        if r.status_code == 429 and _retry:
            time.sleep(min(5, int(r.headers.get("Retry-After") or 1)))
            return self.request(method, path, params, body, _retry=False)
        if r.status_code in (200, 201) and r.content:
            try:
                return r.json()
            except ValueError:
                return {}
        if r.status_code in (200, 201, 202, 204):
            return {}
        err = SpotifyError(f"Spotify answered {r.status_code} for {path.split('?')[0]}")
        err.status = r.status_code
        try:
            err.message = r.json().get("error", {}).get("message", "")
        except (ValueError, AttributeError):
            err.message = ""
        raise err

    def get(self, path, **params):
        return self.request("GET", path, params=params or None)

    def _try(self, *calls, default=None):
        """The first of several (method, path, params, body) that Spotify accepts (newer
        endpoints first; 403/404/405 mean "not for this app")."""
        last = None
        for method, path, params, body in calls:
            try:
                return self.request(method, path, params, body)
            except SpotifyError as err:
                if getattr(err, "status", 0) not in (400, 403, 404, 405):
                    raise
                last = err
        if default is not None:
            return default
        raise last

    @property
    def me(self):
        return (self.auth.get("user") or {}).get("id", "")

    # ------------------------------------------------------------------ cache (slow lists)
    def _cached(self, key, max_age, fn):
        c = _read(self.cache_file, {}) or {}
        e = c.get(key)
        if e and time.time() - e.get("t", 0) < max_age:
            return e["v"]
        v = fn()
        c = _read(self.cache_file, {}) or {}
        c[key] = {"t": time.time(), "v": v}
        try:
            _write_private(self.cache_file, c)
        except OSError:
            pass
        return v

    # ------------------------------------------------------------------ browsing
    def home(self):
        if self.demo:
            return demo_home()
        out = {"recent": [], "playlists": [], "made_for_you": [], "new": [], "top_artists": [], "top_tracks": []}
        try:
            rp = self.get("/me/player/recently-played", limit=30).get("items") or []
        except SpotifyError:
            rp = []
        seen = set()
        for it in rp:
            t = norm_track(it.get("track"))
            if t["uri"] and t["uri"] not in seen:
                seen.add(t["uri"])
                out["recent"].append(t)
        out["recent"] = out["recent"][:16]
        pls = self.my_playlists()
        out["playlists"] = [p for p in pls if not p["spotify"]][:20]
        out["made_for_you"] = self.made_for_you(pls)
        for kind, key in (("artists", "top_artists"), ("tracks", "top_tracks")):
            try:
                items = self.get(f"/me/top/{kind}", limit=20, time_range="short_term").get("items") or []
                out[key] = [norm_artist(a) if kind == "artists" else norm_track(a) for a in items]
            except SpotifyError:
                pass
        out["new"] = self.new_releases()
        return out

    def my_playlists(self):
        if self.demo:
            return demo_home()["playlists"]
        items = []
        for page in range(4):
            j = self.get("/me/playlists", limit=50, offset=page * 50)
            items += [norm_playlist(p, self.me) for p in j.get("items") or [] if p]
            if not j.get("next"):
                break
        return items

    def made_for_you(self, playlists=None):
        """Spotify's own playlists you saved, then the ones played on this TV (their names
        come from the player: the Web API won't show them to a development-mode app)."""
        if self.demo:
            return demo_home()["made_for_you"]
        pls = playlists if playlists is not None else self.my_playlists()
        out = [p for p in pls if p["spotify"]]
        have = {p["uri"] for p in out}
        for c in sorted(_read(self.contexts_file, []) or [], key=lambda c: -c.get("last", 0)):
            if c.get("uri", "").startswith("spotify:playlist:") and c["uri"] not in have and c.get("name"):
                have.add(c["uri"])
                out.append(
                    {
                        "kind": "playlist",
                        "uri": c["uri"],
                        "id": c["uri"].rsplit(":", 1)[-1],
                        "name": c["name"],
                        "owner": "Spotify",
                        "owner_id": "",
                        "image": c.get("image", ""),
                        "total": 0,
                        "mine": False,
                        "collaborative": False,
                        "spotify": True,
                        "description": "Played on this TV",
                    }
                )
        return out[:20]

    def new_releases(self):
        """The newest albums and singles (last ~8 weeks) of artists you follow and play most."""
        if self.demo:
            return demo_home()["new"]

        def build():
            artists = []
            try:
                artists += [a["id"] for a in (self.get("/me/following", type="artist", limit=50).get("artists") or {}).get("items") or []]
            except SpotifyError:
                pass
            try:
                artists += [a["id"] for a in self.get("/me/top/artists", limit=20, time_range="medium_term").get("items") or []]
            except SpotifyError:
                pass
            ids = list(dict.fromkeys(artists))[:30]
            cutoff = time.strftime("%Y-%m-%d", time.gmtime(time.time() - 56 * 86400))
            found = {}
            for aid in ids:
                try:
                    j = self.get(f"/artists/{aid}/albums", include_groups="album,single", limit=5)
                except SpotifyError:
                    continue
                for a in j.get("items") or []:
                    n = norm_album(a)
                    if n["date"] >= cutoff:
                        found[n["uri"]] = n
            return sorted(found.values(), key=lambda a: a["date"], reverse=True)[:20]

        return self._cached("new_releases", 6 * 3600, build)

    def search(self, q, types="track,artist,album,playlist"):
        if self.demo:
            return demo_search(q)
        j = self.get("/search", q=q, type=types, limit=10)
        return {
            "tracks": [norm_track(t) for t in (j.get("tracks") or {}).get("items") or [] if t],
            "artists": [norm_artist(a) for a in (j.get("artists") or {}).get("items") or [] if a],
            "albums": [norm_album(a) for a in (j.get("albums") or {}).get("items") or [] if a],
            "playlists": [norm_playlist(p, self.me) for p in (j.get("playlists") or {}).get("items") or [] if p],
        }

    def artist(self, aid):
        if self.demo:
            return demo_artist(aid)
        a = norm_artist(self.get(f"/artists/{aid}"))
        try:
            top = [norm_track(t) for t in self.get(f"/artists/{aid}/top-tracks", market="from_token").get("tracks") or []]
        except SpotifyError:  # removed for new apps (2026): a search ranks by popularity
            j = self.get("/search", q=f'artist:"{a["name"]}"', type="track", limit=10)
            top = [
                norm_track(t)
                for t in (j.get("tracks") or {}).get("items") or []
                if t and any(x.get("id") == aid for x in t.get("artists") or [])
            ]
        groups = {"album": [], "single": [], "appears_on": [], "compilation": []}
        for g in groups:
            try:
                j = self.get(f"/artists/{aid}/albums", include_groups=g, limit=20)
                groups[g] = [norm_album(x) for x in j.get("items") or [] if x]
            except SpotifyError:
                pass
        for g in groups.values():
            g.sort(key=lambda x: x["date"], reverse=True)
        return {
            **a,
            "top": top[:10],
            "albums": groups["album"],
            "singles": groups["single"],
            "appears_on": groups["appears_on"] + groups["compilation"],
        }

    def album(self, aid):
        if self.demo:
            return demo_album(aid)
        j = self.get(f"/albums/{aid}")
        al = norm_album(j)
        items = list((j.get("tracks") or {}).get("items") or [])
        nxt = (j.get("tracks") or {}).get("next")
        while nxt and len(items) < 300:
            k = self.request("GET", nxt.replace(API, ""))
            items += k.get("items") or []
            nxt = k.get("next")
        al["tracks"] = [norm_track(t, j) for t in items]
        al["label"] = j.get("label", "")
        return al

    def playlist(self, pid, name=""):
        """A playlist and its songs. Spotify lets a development-mode app list only the songs of
        your own (and collaborative) playlists: others come back without them, still playable."""
        if self.demo:
            return demo_playlist(pid)
        uri = f"spotify:playlist:{pid}"
        try:
            p = norm_playlist(
                self.get(f"/playlists/{pid}", fields="id,uri,name,owner,images,description,collaborative,items(total),tracks(total)"),
                self.me,
            )
        except SpotifyError as err:
            if getattr(err, "status", 0) not in (403, 404):
                raise
            known = next((c for c in _read(self.contexts_file, []) or [] if c.get("uri") == uri), {})
            p = {
                "kind": "playlist",
                "uri": uri,
                "id": pid,
                "name": name or known.get("name") or "Playlist",
                "owner": "Spotify",
                "owner_id": "spotify",
                "image": known.get("image", ""),
                "total": 0,
                "mine": False,
                "collaborative": False,
                "spotify": True,
                "description": "",
            }
        tracks, note = [], ""
        if p["mine"] or p["collaborative"]:
            off = 0
            while off < 500:
                j = self._try(
                    ("GET", f"/playlists/{pid}/items", {"limit": 100, "offset": off}, None),
                    ("GET", f"/playlists/{pid}/tracks", {"limit": 100, "offset": off}, None),
                )
                rows = j.get("items") or []
                for r in rows:
                    t = r.get("item") or r.get("track")
                    if t and t.get("type", "track") == "track":
                        tracks.append(norm_track(t))
                if not j.get("next"):
                    break
                off += 100
        else:
            note = "Spotify only shows this app the songs of your own playlists. Press Play to hear this one."
        p["tracks"] = tracks
        p["note"] = note
        return p

    def liked_tracks(self, offset=0, limit=50):
        if self.demo:
            return {"items": demo_home()["top_tracks"], "total": 6}
        j = self.get("/me/tracks", limit=limit, offset=offset)
        return {"items": [norm_track(r.get("track")) for r in j.get("items") or [] if r.get("track")], "total": j.get("total", 0)}

    def library(self):
        if self.demo:
            d = demo_home()
            return {"playlists": d["playlists"] + d["made_for_you"], "albums": d["new"], "artists": d["top_artists"], "liked_total": 248}
        out = {"playlists": self.my_playlists(), "albums": [], "artists": [], "liked_total": 0}
        try:
            out["albums"] = [norm_album(r["album"]) for r in self.get("/me/albums", limit=50).get("items") or [] if r.get("album")]
        except SpotifyError:
            pass
        try:
            out["artists"] = [
                norm_artist(a) for a in (self.get("/me/following", type="artist", limit=50).get("artists") or {}).get("items") or []
            ]
        except SpotifyError:
            pass
        try:
            out["liked_total"] = self.get("/me/tracks", limit=1).get("total", 0)
        except SpotifyError:
            pass
        return out

    def track(self, tid):
        if self.demo:
            return next((t for t in demo_home()["top_tracks"] if t["id"] == tid), demo_home()["top_tracks"][0])
        return norm_track(self.get(f"/tracks/{tid}"))

    # ------------------------------------------------------------------ your library
    def is_saved(self, uris):
        if self.demo or not uris:
            return [False] * len(uris)
        ids = [u.rsplit(":", 1)[-1] for u in uris]
        kind = uris[0].split(":")[1]
        return self._try(
            ("GET", "/me/library/contains", {"uris": ",".join(uris)}, None),
            ("GET", f"/me/{kind}s/contains", {"ids": ",".join(ids)}, None),
            default=[False] * len(uris),
        )

    def save(self, uris, on=True):
        """Like songs / save albums (on=False: remove)."""
        if self.demo:
            return {"ok": True}
        ids = [u.rsplit(":", 1)[-1] for u in uris]
        kind = uris[0].split(":")[1]
        m = "PUT" if on else "DELETE"
        self._try((m, "/me/library", {"uris": ",".join(uris)}, None), (m, f"/me/{kind}s", {"ids": ",".join(ids)}, None))
        return {"ok": True}

    def create_playlist(self, name, description="Made on the TV"):
        if self.demo:
            return {"kind": "playlist", "uri": "spotify:playlist:demo-new", "id": "demo-new", "name": name, "mine": True}
        body = {"name": name, "public": False, "description": description}
        j = self._try(("POST", "/me/playlists", None, body), ("POST", f"/users/{self.me}/playlists", None, body))
        return norm_playlist(j, self.me)

    def add_to_playlist(self, pid, uris):
        if self.demo:
            return {"ok": True}
        for i in range(0, len(uris), 100):
            chunk = {"uris": uris[i : i + 100]}
            self._try(("POST", f"/playlists/{pid}/items", None, chunk), ("POST", f"/playlists/{pid}/tracks", None, chunk))
        return {"ok": True}

    def find_my_playlist(self, name):
        """One of your playlists by a spoken name ("road trip" -> "Road Trip 2026")."""
        q = " ".join(re.sub(r"\b(my|the|playlist)\b", " ", (name or "").lower()).split())
        pls = self.my_playlists() + [p for p in self.made_for_you() if p not in self.my_playlists()]
        for p in pls:
            if p["name"].lower() == q:
                return p
        hits = [p for p in pls if q and (q in p["name"].lower() or p["name"].lower() in q)]
        return min(hits, key=lambda p: len(p["name"])) if hits else None

    # ------------------------------------------------------------------ playback (Spotify Connect)
    def devices(self):
        return self.get("/me/player/devices").get("devices") or []

    def device_id(self, name):
        for d in self.devices():
            if d.get("name", "").lower() == (name or "").lower():
                return d.get("id")
        return None

    def play(self, device, context_uri="", uris=None, offset_uri="", position_ms=0):
        """Start playback on this TV's player (device id): a context from a song, or songs."""
        if self.demo:
            return {"ok": True}
        body = {}
        if context_uri:
            body["context_uri"] = context_uri
            if offset_uri:
                body["offset"] = {"uri": offset_uri}
        elif uris:
            body["uris"] = uris
        if position_ms:
            body["position_ms"] = position_ms
        self.request("PUT", "/me/player/play", params={"device_id": device}, body=body)
        return {"ok": True}

    def remember_context(self, uri, name, image=""):
        """couchbox-spotify --connect: what played here (Made For You can't be listed otherwise)."""
        if not uri or not name or uri.startswith("spotify:track:"):
            return
        with self._file_lock():
            cs = [c for c in _read(self.contexts_file, []) or [] if c.get("uri") != uri]
            cs.insert(0, {"uri": uri, "name": name, "image": image, "last": time.time()})
            _write_private(self.contexts_file, cs[:40])


# ------------------------------------------------------------------ demo data (screenshots, --demo)
def _dt(i, name, artist, album, dur, aid="ar1"):
    return {
        "kind": "track",
        "uri": f"spotify:track:demo{i}",
        "id": f"demo{i}",
        "name": name,
        "artists": [{"id": aid, "name": artist}],
        "album": {"id": f"al{i % 4}", "uri": f"spotify:album:al{i % 4}", "name": album},
        "image": "",
        "duration": dur,
        "explicit": False,
        "playable": True,
    }


_DEMO_TRACKS = [
    _dt(1, "Northern Lights", "The Midnight Arcade", "Neon Harbor", 214),
    _dt(2, "Paper Planes Over Lisbon", "Saltwater Choir", "Low Tide", 247, "ar2"),
    _dt(3, "Glass Houses", "Juniper Vale", "Wildflower Season", 198, "ar3"),
    _dt(4, "Static & Starlight", "The Midnight Arcade", "Neon Harbor", 263),
    _dt(5, "Kitchen Radio", "Orla Finch", "Small Hours", 182, "ar4"),
    _dt(6, "A Very Long Song Title That Has To Shorten Neatly On A Television", "Saltwater Choir", "Low Tide", 305, "ar2"),
]
_DEMO_ARTISTS = [
    {"kind": "artist", "uri": f"spotify:artist:ar{i}", "id": f"ar{i}", "name": n, "image": "", "genres": g}
    for i, n, g in [
        (1, "The Midnight Arcade", ["synthwave"]),
        (2, "Saltwater Choir", ["indie folk"]),
        (3, "Juniper Vale", ["dream pop"]),
        (4, "Orla Finch", ["singer-songwriter"]),
    ]
]


def _da(i, name, artist, year, kind="album"):
    return {
        "kind": "album",
        "uri": f"spotify:album:al{i}",
        "id": f"al{i}",
        "name": name,
        "artists": [{"id": "ar1", "name": artist}],
        "image": "",
        "year": year,
        "date": f"{year}-10-01",
        "type": kind,
        "group": kind,
        "total": 11 if kind == "album" else 2,
    }


_DEMO_ALBUMS = [
    _da(0, "Neon Harbor", "The Midnight Arcade", "2026"),
    _da(1, "Low Tide", "Saltwater Choir", "2025"),
    _da(2, "Wildflower Season", "Juniper Vale", "2026", "single"),
    _da(3, "Small Hours", "Orla Finch", "2024"),
]


def _dp(i, name, owner, spotify=False, total=40):
    return {
        "kind": "playlist",
        "uri": f"spotify:playlist:pl{i}",
        "id": f"pl{i}",
        "name": name,
        "owner": owner,
        "owner_id": "spotify" if spotify else "demo",
        "image": "",
        "total": total,
        "mine": not spotify,
        "collaborative": False,
        "spotify": spotify,
        "description": "",
    }


def demo_home():
    return {
        "recent": _DEMO_TRACKS,
        "playlists": [
            _dp(1, "Road Trip 2026", "Demo Listener"),
            _dp(2, "Sunday Morning", "Demo Listener"),
            _dp(3, "Workout", "Demo Listener"),
            _dp(4, "Dinner Party", "Demo Listener"),
        ],
        "made_for_you": [
            _dp(10, "Discover Weekly", "Spotify", True, 30),
            _dp(11, "Release Radar", "Spotify", True, 30),
            _dp(12, "Daily Mix 1", "Spotify", True, 50),
        ],
        "new": _DEMO_ALBUMS,
        "top_artists": _DEMO_ARTISTS,
        "top_tracks": _DEMO_TRACKS,
    }


def demo_search(q):
    return {"tracks": _DEMO_TRACKS[:5], "artists": _DEMO_ARTISTS, "albums": _DEMO_ALBUMS, "playlists": demo_home()["playlists"]}


def demo_artist(aid):
    a = next((x for x in _DEMO_ARTISTS if x["id"] == aid), _DEMO_ARTISTS[0])
    return {**a, "top": _DEMO_TRACKS, "albums": _DEMO_ALBUMS[:2], "singles": _DEMO_ALBUMS[2:3], "appears_on": _DEMO_ALBUMS[3:]}


def demo_album(aid):
    a = next((x for x in _DEMO_ALBUMS if x["id"] == aid), _DEMO_ALBUMS[0])
    return {**a, "tracks": _DEMO_TRACKS, "label": "Demo Records"}


def demo_playlist(pid):
    p = next((x for x in demo_home()["playlists"] + demo_home()["made_for_you"] if x["id"] == pid), demo_home()["playlists"][0])
    return {
        **p,
        "tracks": [] if p["spotify"] else _DEMO_TRACKS,
        "note": "Spotify only shows this app the songs of your own playlists. Press Play to hear this one." if p["spotify"] else "",
    }
