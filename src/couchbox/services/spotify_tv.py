"""Spotify on this box: the glue between the Web API (spotify.py), Spotify's player (soloist.py),
the TV app, the background service (couchbox-spotify --connect) and the voice assistant.

  config.json        the developer app's client ID (in ~/.local/share/couchbox-spotify, 0600)
  device_name()      what this TV is called in Spotify's device list (the AirPlay name)
  redirects()        where Spotify sends the phone after sign-in
  play_on_tv()       start music here: through the Web API (it can start a song inside an
                     album or playlist) when it sees this TV, else through the player itself
  Voice              what the voice assistant asks the background service for
"""

import random
import re
import subprocess
import time

from couchbox.services import soloist
from couchbox.services.spotify import LOOPBACK_REDIRECT, SignInNeeded, SpotifyError, _read, _write_private, data_dir

UNIT = "couchbox-spotify-connect.service"
PHONE_URL = "/run/couchbox/phone/phone.url"


def config():
    return _read(data_dir() / "config.json", {}) or {}


def set_config(**kw):
    c = config()
    c.update(kw)
    _write_private(data_dir() / "config.json", c)
    return c


def client_id():
    return config().get("client_id", "")


def set_client_id(value):
    v = (value or "").strip()
    if not re.fullmatch(r"[0-9a-fA-F]{32}", v):
        raise SpotifyError("A Spotify client ID is 32 letters and digits (0-9, a-f). Copy it from your app's Settings.")
    set_config(client_id=v.lower())


def device_name():
    try:
        from couchbox import settings

        s = settings.load()
        return (s.get("apps.airplay.name") or s.get("network.hostname") or "Couchbox").strip()
    except Exception:  # noqa: BLE001
        import socket

        return socket.gethostname()


def phone_base():
    """The phone page's address (couchbox-phone writes it): https://<box>.<tailnet> when
    Tailscale serves it, else http://<box>.local:8791."""
    try:
        return open(PHONE_URL).read().strip().split("#", 1)[0].rstrip("/")
    except OSError:
        return ""


def redirects():
    base = phone_base()
    return {"tailscale": f"{base}/spotify/callback" if base.startswith("https://") else "", "loopback": LOOPBACK_REDIRECT}


def service(action):
    """systemctl --user for the background service (the TV user's)."""
    try:
        r = subprocess.run(["systemctl", "--user", action, UNIT], capture_output=True, text=True, timeout=20)
        return r.stdout.strip() or r.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as err:
        return str(err)


def status(sp, player=None):
    st = sp.status()
    info = soloist.build_info()
    ps = player.state if player else {}
    st.update(
        device=device_name(),
        **{f"redirect_{k}": v for k, v in redirects().items()},
        player={
            "installed": bool(info),
            "version": (info or {}).get("version", ""),
            "days_left": (info or {}).get("days_left"),
            "key": bool(soloist.api_key()),
            "running": bool(ps.get("connected")),
            "logged_in": bool(ps.get("logged_in")),
        },
    )
    return st


def play_on_tv(sp, player, context="", offset="", uris=None, shuffle=None, device=None):
    """Play here: a context (album, playlist, artist, "liked") from a song, or songs."""
    device = device or device_name()
    if context == "liked":
        context = f"spotify:user:{sp.me}:collection"
    if player is not None and not player.state.get("connected"):
        raise SpotifyError("Spotify's player isn't running on this TV. Open Spotify → Setup.")
    if player is not None and not player.state.get("logged_in"):
        raise SpotifyError(f"Pick {device} in the Spotify app on your phone once (Spotify → Setup, step 4).")
    did = None
    try:
        did = sp.device_id(device)
        if not did and player is not None:
            player.activate()
            for _ in range(6):
                time.sleep(0.5)
                did = sp.device_id(device)
                if did:
                    break
    except (SpotifyError, SignInNeeded):
        did = None
    if did:
        if shuffle is not None:
            _shuffle(sp, did, shuffle)
        if shuffle and context and not offset and not uris:
            offset = _random_track(sp, context)
        sp.play(did, context, uris, offset)
        if shuffle is not None:
            _shuffle(sp, did, shuffle)
        return "web"
    if player is None:
        raise SpotifyError(f"Spotify doesn't see {device} right now.")
    if shuffle is not None:  # no Web API: the player plays the whole thing
        player.shuffle(shuffle)
    if not player.play(context or (uris or [""])[0]):
        raise SpotifyError("Spotify's player on this TV didn't answer.")
    return "player"


def _shuffle(sp, did, on):
    try:
        sp.request("PUT", "/me/player/shuffle", params={"state": "true" if on else "false", "device_id": did})
    except SpotifyError:
        pass


def _random_track(sp, context):
    """Shuffle starts on a random song, as Spotify's apps do (when the songs can be listed)."""
    try:
        kind, cid = context.split(":")[1], context.rsplit(":", 1)[-1]
        if kind == "album":
            items = sp.album(cid)["tracks"]
        elif kind == "playlist":
            items = sp.playlist(cid)["tracks"]
        else:
            return ""
        return random.choice(items)["uri"] if items else ""
    except Exception:  # noqa: BLE001
        return ""


# ------------------------------------------------------------------ voice
def best(results, kind=""):
    """The result a spoken request means: the kind asked for, else songs, artists, albums."""
    order = [kind + "s"] if kind else ["tracks", "artists", "albums", "playlists"]
    for k in order:
        if results.get(k):
            return results[k][0]
    return None


def split_song(s):
    """ "Artist - Title" or "Title by Artist" -> a search query."""
    s = (s or "").strip()
    m = re.match(r"(.+?)\s+by\s+(.+)$", s, re.I)
    if m:
        return f'track:"{m.group(1).strip()}" artist:"{m.group(2).strip()}"'
    if " - " in s:
        a, t = s.split(" - ", 1)
        return f'track:"{t.strip()}" artist:"{a.strip()}"'
    return s


class Voice:
    """The voice assistant's Spotify actions, run by couchbox-spotify --connect (the TV user's,
    with the sign-in and the player). Each returns a short sentence for the assistant."""

    def __init__(self, sp, player):
        self.sp = sp
        self.player = player

    def run(self, action, query="", kind="", name="", songs=None, play=True):
        if not self.sp.client_id or not self.sp.signed_in:
            return "Spotify isn't set up on this TV yet: open Spotify and follow Setup."
        a = {
            "play": lambda: self.play(query, kind),
            "now": self.now,
            "like": lambda: self.like(True),
            "unlike": lambda: self.like(False),
            "add_to_playlist": lambda: self.add_current(name or query),
            "make_playlist": lambda: self.make_playlist(name or query, songs or [], play),
            "pause": lambda: (self.player.pause(), "Paused.")[1],
            "resume": lambda: (self.player.play(), "Playing.")[1],
            "next": lambda: (self.player.next(), "Next song.")[1],
            "previous": lambda: (self.player.previous(), "Previous song.")[1],
        }.get(action)
        if not a:
            return f"Unknown action {action}."
        try:
            return a()
        except SignInNeeded as err:
            return str(err)
        except SpotifyError as err:
            return f"Spotify: {err}"

    def play(self, query, kind=""):
        q = (query or "").strip()
        if not q:
            self.player.play()
            return "Playing."
        if kind in ("", "playlist") and re.search(r"\b(my|liked|discover|release radar|daily mix|on repeat)\b", q, re.I):
            if re.search(r"\bliked( songs)?\b", q, re.I):
                play_on_tv(self.sp, self.player, context="liked", shuffle=True)
                return "Playing your Liked Songs, shuffled."
            p = self.sp.find_my_playlist(q)
            if p:
                play_on_tv(self.sp, self.player, context=p["uri"])
                return f"Playing {p['name']}."
        r = self.sp.search(split_song(q) if kind == "track" else q, types=f"{kind}" if kind else "track,artist,album,playlist")
        hit = best(r, kind) if kind else _spoken_best(r, q)
        if not hit:
            return f"Nothing on Spotify matches {q!r}."
        if hit["kind"] == "track":
            ctx = hit["album"]["uri"]
            play_on_tv(self.sp, self.player, context=ctx, offset=hit["uri"]) if ctx else play_on_tv(self.sp, self.player, uris=[hit["uri"]])
            return f"Playing {hit['name']} by {', '.join(a['name'] for a in hit['artists'])}."
        play_on_tv(self.sp, self.player, context=hit["uri"], shuffle=True if hit["kind"] == "artist" else None)
        by = f" by {', '.join(a['name'] for a in hit.get('artists', []))}" if hit.get("artists") else ""
        return f"Playing {hit['name']}{by}."

    def now(self):
        st = self.player.state
        if not st.get("item"):
            return "Nothing is playing on Spotify here."
        name = soloist.name_of(st["item"])
        try:
            t = self.sp.track(st["item"]["uri"].rsplit(":", 1)[-1])
            who = ", ".join(a["name"] for a in t["artists"])
            line = f"{t['name']} by {who}, from {t['album']['name']}"
        except Exception:  # noqa: BLE001
            line = name
        state = "Playing" if st.get("status") in ("playing", "buffering") else "Paused on"
        ctx = soloist.name_of(st.get("context"))
        return f"{state} {line}" + (f" (from {ctx})" if ctx and ctx not in line else "") + "."

    def current_uri(self):
        uri = ((self.player.state.get("item") or {}).get("uri")) or ""
        if not uri.startswith("spotify:track:"):
            raise SpotifyError("No song is playing on this TV.")
        return uri

    def like(self, on):
        uri = self.current_uri()
        self.sp.save([uri], on)
        name = soloist.name_of(self.player.state.get("item"))
        return f"{'Added' if on else 'Removed'} {name} {'to' if on else 'from'} your Liked Songs."

    def add_current(self, name):
        uri = self.current_uri()
        p = self.sp.find_my_playlist(name)
        if not p or not (p.get("mine") or p.get("collaborative")):
            return f"You don't have a playlist called {name!r}. Ask me to make it first."
        self.sp.add_to_playlist(p["id"], [uri])
        return f"Added {soloist.name_of(self.player.state.get('item'))} to {p['name']}."

    def make_playlist(self, name, songs, play=True):
        """A new playlist from songs the assistant thought of ("Artist - Title"): each one is
        looked up on Spotify. (Spotify's data never goes to the model: it only gets the count.)"""
        if not name:
            return "What should the playlist be called?"
        uris, missing = [], 0
        for s in songs[:60]:
            r = self.sp.search(split_song(s), types="track")
            t = (r.get("tracks") or [None])[0]
            if t and t["uri"] not in uris:
                uris.append(t["uri"])
            else:
                missing += 1
        if not uris:
            return "I couldn't find any of those songs on Spotify."
        p = self.sp.create_playlist(name, "Made by the TV's voice assistant")
        self.sp.add_to_playlist(p["id"], uris)
        if play:
            play_on_tv(self.sp, self.player, context=p["uri"])
        return (
            f"Made {name} with {len(uris)} songs"
            + (f" ({missing} weren't on Spotify)" if missing else "")
            + (", playing it now." if play else ".")
        )


def _spoken_best(r, q):
    """ "Taylor Swift" means the artist, "Anti-Hero" the song, "1989" the album: prefer the
    result whose name is the request itself."""
    ql = re.sub(r"[^a-z0-9 ]", "", q.lower()).strip()
    for k in ("artists", "tracks", "albums", "playlists"):
        for x in (r.get(k) or [])[:3]:
            if re.sub(r"[^a-z0-9 ]", "", x["name"].lower()).strip() == ql:
                return x
    return best(r)
