"""Spotify: phone sign-in (PKCE) and single-use refresh tokens shared by two processes, the
fallbacks for what a development-mode app can't do, Spotify's player (Soloist: download,
build expiry, its WebSocket events), playing on this TV, and the voice assistant's actions."""

import io
import json
import os
import stat
import tarfile
import time
import urllib.parse

import pytest

from couchbox.services import soloist, spotify, spotify_tv

CLIENT = "0123456789abcdef0123456789abcdef"


class Resp:
    def __init__(self, status, body=None, headers=None):
        self.status_code = status
        self.body = body
        self.ok = status < 400
        self.headers = headers or {}
        self.content = b"" if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
        self.text = self.content.decode(errors="ignore")

    def json(self):
        return json.loads(self.content)

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(self.status_code)


class FakeSpotify:
    """accounts.spotify.com and api.spotify.com: refresh tokens are single use; routes are
    "METHOD /path" -> body or (status, body) or a function(params, json)."""

    def __init__(self):
        self.headers = {}
        self.calls = []
        self.valid_refresh = {"r1"}
        self.n = 1
        self.routes = {"GET /me": {"id": "max", "display_name": "Max", "product": "premium"}}

    def post(self, url, data=None, timeout=None):
        self.calls.append(("POST", url, dict(data or {})))
        if data["grant_type"] == "authorization_code":
            return Resp(200, {"access_token": "a1", "refresh_token": "r1", "expires_in": 3600, "scope": spotify.SCOPES})
        if data["refresh_token"] not in self.valid_refresh:
            return Resp(400, {"error": "invalid_grant"})
        self.valid_refresh.discard(data["refresh_token"])
        self.n += 1
        self.valid_refresh.add(f"r{self.n}")
        return Resp(200, {"access_token": f"a{self.n}", "refresh_token": f"r{self.n}", "expires_in": 3600})

    def request(self, method, url, params=None, json=None, timeout=None, headers=None):
        path = url.replace(spotify.API, "").split("?")[0]
        self.calls.append((method, path, params, json))
        r = self.routes.get(f"{method} {path}", (404, {"error": {"status": 404, "message": "Not found"}}))
        if callable(r):
            r = r(params or {}, json)
        if isinstance(r, tuple):
            return Resp(*r)
        return Resp(200, r) if r != {} else Resp(204)

    def get(self, url, timeout=None):
        return self.routes["DOWNLOAD"]


@pytest.fixture
def fake(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    f = FakeSpotify()
    monkeypatch.setattr(spotify.requests, "Session", lambda: f)
    monkeypatch.setattr(spotify.time, "sleep", lambda s: None)
    return f


def signed_in(fake, expires_in=3600):
    sp = spotify.Spotify(CLIENT)
    sp.auth = {
        "client_id": CLIENT,
        "access_token": "a1",
        "refresh_token": "r1",
        "expires_at": time.time() + expires_in,
        "user": {"id": "max", "name": "Max"},
    }
    sp._save()
    return sp


# ------------------------------------------------------------------ sign-in
def test_phone_sign_in_with_pkce(fake):
    sp = spotify.Spotify(CLIENT)
    r = sp.start_login("https://tv.example.ts.net/spotify/callback")
    q = urllib.parse.parse_qs(urllib.parse.urlparse(r["url"]).query)
    assert q["client_id"] == [CLIENT] and q["code_challenge_method"] == ["S256"] and "playlist-modify-private" in q["scope"][0]
    pend = json.loads(sp.pending_file.read_text())
    assert pend["url"] == r["url"] and stat.S_IMODE(os.stat(sp.pending_file).st_mode) == 0o600
    with pytest.raises(spotify.SpotifyError, match="doesn't match"):
        sp.finish_login("code", "someone-elses-state")
    st = sp.finish_login("code", q["state"][0])
    assert st["signedIn"] and st["user"] == "Max"
    ex = [c for c in fake.calls if c[0] == "POST"][0][2]
    assert ex["code_verifier"] == pend["verifier"] and ex["redirect_uri"] == "https://tv.example.ts.net/spotify/callback"
    assert stat.S_IMODE(os.stat(sp.session_file).st_mode) == 0o600 and not sp.pending_file.exists()


def test_pasted_callback_address_finishes_sign_in(fake):
    sp = spotify.Spotify(CLIENT)
    state = urllib.parse.parse_qs(urllib.parse.urlparse(sp.start_login(spotify.LOOPBACK_REDIRECT)["url"]).query)["state"][0]
    assert sp.finish_login(pasted=f"http://127.0.0.1:8792/callback?code=abc&state={state}")["signedIn"]
    with pytest.raises(spotify.SpotifyError, match="access denied"):
        sp.finish_login(pasted="http://127.0.0.1:8792/callback?error=access_denied&state=x")


def test_refresh_rotates_and_a_stale_process_adopts_it(fake):
    app = signed_in(fake, expires_in=-10)
    other = spotify.Spotify(CLIENT)  # couchbox-spotify --connect, same file
    assert other.token() == "a2"  # spent r1
    assert app.token() == "a2"  # still holds r1: re-reads instead of refreshing
    assert sum(1 for c in fake.calls if c[0] == "POST") == 1


def test_refused_refresh_signs_out(fake):
    sp = signed_in(fake, expires_in=-10)
    fake.valid_refresh.clear()  # revoked, or past Spotify's six months
    with pytest.raises(spotify.SignInNeeded):
        sp.token()
    assert not sp.session_file.exists()


def test_401_refreshes_once_and_retries(fake):
    sp = signed_in(fake)
    seen = []
    fake.routes["GET /me/top/tracks"] = lambda p, j: (seen.append(1), (401, {}) if len(seen) == 1 else {"items": []})[1]
    assert sp.get("/me/top/tracks") == {"items": []}
    assert len(seen) == 2 and sp.auth["access_token"] == "a2"


# ------------------------------------------------------------------ what a development-mode app may do
def test_like_uses_the_library_endpoint_or_the_old_one(fake):
    sp = signed_in(fake)
    fake.routes["PUT /me/tracks"] = {}
    sp.save(["spotify:track:t1"])  # /me/library 404 (older app): falls back
    assert [c[:2] for c in fake.calls[-2:]] == [("PUT", "/me/library"), ("PUT", "/me/tracks")]
    fake.routes["GET /me/library/contains"] = [True]
    assert sp.is_saved(["spotify:track:t1"]) == [True]


def test_artist_popular_songs_come_from_search_without_top_tracks(fake):
    sp = signed_in(fake)
    fake.routes["GET /artists/ar1"] = {
        "id": "ar1",
        "uri": "spotify:artist:ar1",
        "name": "Juniper Vale",
        "images": [],
        "genres": ["dream pop"],
    }
    mine = {
        "id": "t1",
        "uri": "spotify:track:t1",
        "name": "Glass Houses",
        "artists": [{"id": "ar1", "name": "Juniper Vale"}],
        "album": {"id": "al"},
    }
    cover = {"id": "t2", "uri": "spotify:track:t2", "name": "Glass Houses (cover)", "artists": [{"id": "zz", "name": "Someone"}]}
    fake.routes["GET /search"] = {"tracks": {"items": [mine, cover]}}
    fake.routes["GET /artists/ar1/albums"] = lambda p, j: {
        "items": [
            {
                "id": p["include_groups"],
                "uri": "spotify:album:x",
                "name": p["include_groups"],
                "album_type": "single" if p["include_groups"] == "single" else "album",
                "release_date": "2026-01-02",
            }
        ]
    }
    a = sp.artist("ar1")
    assert [t["name"] for t in a["top"]] == ["Glass Houses"]
    assert a["albums"][0]["name"] == "album" and a["singles"][0]["type"] == "single"


def test_others_playlists_play_but_their_songs_are_not_listed(fake):
    sp = signed_in(fake)
    fake.routes["GET /playlists/dw"] = (404, {"error": {"status": 404}})
    sp.remember_context("spotify:playlist:dw", "Discover Weekly")
    p = sp.playlist("dw")
    assert p["name"] == "Discover Weekly" and p["tracks"] == [] and "Press Play" in p["note"]
    fake.routes["GET /playlists/mine"] = {
        "id": "mine",
        "uri": "spotify:playlist:mine",
        "name": "Road Trip",
        "owner": {"id": "max"},
        "items": {"total": 1},
    }
    fake.routes["GET /playlists/mine/tracks"] = {
        "items": [{"track": {"id": "t1", "uri": "spotify:track:t1", "name": "Song", "type": "track"}}]
    }
    p = sp.playlist("mine")  # /items 404 (older app): /tracks
    assert p["mine"] and [t["name"] for t in p["tracks"]] == ["Song"] and not p["note"]


def test_made_for_you_includes_what_played_on_this_tv(fake):
    sp = signed_in(fake)
    fake.routes["GET /me/playlists"] = {
        "items": [
            {"id": "rr", "uri": "spotify:playlist:rr", "name": "Release Radar", "owner": {"id": "spotify"}},
            {"id": "m", "uri": "spotify:playlist:m", "name": "Mine", "owner": {"id": "max"}},
        ]
    }
    sp.remember_context("spotify:playlist:dw", "Discover Weekly")
    sp.remember_context("spotify:track:x", "A song")  # songs aren't contexts
    assert [p["name"] for p in sp.made_for_you()] == ["Release Radar", "Discover Weekly"]


def test_new_releases_from_your_artists_are_recent_and_cached(fake):
    sp = signed_in(fake)
    fake.routes["GET /me/following"] = {"artists": {"items": [{"id": "a1"}]}}
    fake.routes["GET /me/top/artists"] = {"items": [{"id": "a1"}, {"id": "a2"}]}
    today = time.strftime("%Y-%m-%d")
    fake.routes["GET /artists/a1/albums"] = {
        "items": [
            {"id": "new", "uri": "spotify:album:new", "name": "New", "release_date": today},
            {"id": "old", "uri": "spotify:album:old", "name": "Old", "release_date": "2001-01-01"},
        ]
    }
    fake.routes["GET /artists/a2/albums"] = {"items": []}
    assert [a["name"] for a in sp.new_releases()] == ["New"]
    n = len(fake.calls)
    sp.new_releases()
    assert len(fake.calls) == n  # cached for hours


# ------------------------------------------------------------------ Spotify's player (Soloist)
def archive(files):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def test_install_takes_only_the_soloist_program(fake):
    fake.routes["DOWNLOAD"] = Resp(
        200,
        archive(
            {
                "../evil": b"x",
                "soloist_release/README": b"r",
                "soloist_release/soloist": b"#!/bin/sh\necho Spotify Soloist 1.2.3 built 2026-10-01T10:00\n",
            }
        ),
    )
    info = soloist.install(session=fake)
    assert os.access(soloist.binary(), os.X_OK) and info["version"] == "1.2.3"
    assert sorted(os.listdir(soloist.home())) == ["soloist"]


def test_builds_are_replaced_well_before_they_expire():
    now = time.time()
    assert not soloist.needs_update({"days_left": 80})
    assert soloist.needs_update({"days_left": 25})
    assert soloist.needs_update(None)
    v = soloist.parse_version(time.strftime("soloist 0.9.1 (build %Y-%m-%d %H:%M)", time.localtime(now - 10 * 86400)))
    assert v["version"] == "0.9.1" and 79 <= v["days_left"] <= 80


def test_api_key_is_private_and_checked(fake):
    with pytest.raises(ValueError):
        soloist.set_api_key("no spaces allowed here")
    soloist.set_api_key("sk_abcDEF123456")
    assert soloist.api_key() == "sk_abcDEF123456" and stat.S_IMODE(os.stat(soloist.key_file()).st_mode) == 0o600
    assert soloist.command("Living Room")[:5] == [str(soloist.binary()), "--device-name", "Living Room", "--api-key", "sk_abcDEF123456"]


class FakeWS:
    def __init__(self):
        self.sent = []

    def send(self, s):
        self.sent.append(json.loads(s))


def test_player_follows_soloist_events_and_sends_commands():
    changes = []
    p = soloist.Player(on_change=lambda st, ev: changes.append(ev))
    p.ws = FakeWS()
    p.handle({"type": "auth_state", "logged_in": True})
    assert [c["command"] for c in p.ws.sent] == ["get_state", "get_queue"]
    p.handle(
        {
            "type": "playback_state",
            "status": "playing",
            "item": {"uri": "spotify:track:t1", "decorations": {"identity": {"name": "Song"}}},
            "context": {"uri": "spotify:playlist:dw", "decorations": {"identity": {"name": "Discover Weekly"}}},
            "position": {"position_ms": 1000, "timestamp_ms": time.time() * 1000 - 2000, "speed": 1.0},
            "volume": 40,
            "is_active": True,
            "options": {"shuffle": True, "repeat": "context"},
        }
    )
    assert p.state["logged_in"] and p.state["shuffle"] and soloist.name_of(p.state["context"]) == "Discover Weekly"
    assert 2.5 < p.position() < 4
    p.handle(
        {
            "type": "queue_changed",
            "upcoming": [
                {"uid": "u", "source": "queue", "item": {"uri": "spotify:track:t2", "decorations": {"identity": {"name": "Next"}}}}
            ],
        }
    )
    assert p.state["queue"] == [{"uri": "spotify:track:t2", "name": "Next", "source": "queue"}]
    p.ws.sent.clear()
    p.toggle()
    p.repeat("track")
    p.play("spotify:album:x")
    assert [c["command"] for c in p.ws.sent] == ["pause", "set_repeat_context", "set_repeat_track", "play"]
    assert p.ws.sent[-1]["uri"] == "spotify:album:x" and "playback_state" in changes


# ------------------------------------------------------------------ playing on this TV
class FakePlayer:
    def __init__(self, logged_in=True):
        self.state = {
            "connected": True,
            "logged_in": logged_in,
            "item": {"uri": "spotify:track:t1", "decorations": {"identity": {"name": "Song"}}},
        }
        self.sent = []

    def __getattr__(self, name):
        return lambda *a: (self.sent.append((name, *a)), True)[1]


def test_play_starts_a_song_inside_its_album_through_the_web_api(fake):
    sp = signed_in(fake)
    fake.routes["GET /me/player/devices"] = {"devices": [{"id": "dev1", "name": "Living Room"}]}
    fake.routes["PUT /me/player/play"] = {}
    assert spotify_tv.play_on_tv(sp, FakePlayer(), context="spotify:album:al", offset="spotify:track:t3", device="living room") == "web"
    m, path, params, body = fake.calls[-1]
    assert params == {"device_id": "dev1"} and body == {"context_uri": "spotify:album:al", "offset": {"uri": "spotify:track:t3"}}
    spotify_tv.play_on_tv(sp, FakePlayer(), context="liked", device="Living Room")
    assert fake.calls[-1][3]["context_uri"] == "spotify:user:max:collection"


def test_play_falls_back_to_the_player_and_needs_pairing(fake):
    sp = signed_in(fake)
    fake.routes["GET /me/player/devices"] = {"devices": []}
    pl = FakePlayer()
    assert spotify_tv.play_on_tv(sp, pl, context="spotify:playlist:dw", device="Living Room") == "player"
    assert ("activate",) in pl.sent and ("play", "spotify:playlist:dw") in pl.sent
    with pytest.raises(spotify.SpotifyError, match="Pick Living Room"):
        spotify_tv.play_on_tv(sp, FakePlayer(logged_in=False), context="x", device="Living Room")


def test_client_id_is_checked(fake):
    with pytest.raises(spotify.SpotifyError):
        spotify_tv.set_client_id("not-a-client-id")
    spotify_tv.set_client_id(CLIENT.upper())
    assert spotify_tv.client_id() == CLIENT


# ------------------------------------------------------------------ the voice assistant
def test_voice_plays_the_artist_a_name_means(fake):
    sp = signed_in(fake)
    fake.routes["GET /search"] = {
        "tracks": {
            "items": [
                {
                    "id": "t",
                    "uri": "spotify:track:t",
                    "name": "Anti-Hero",
                    "artists": [{"id": "ts", "name": "Taylor Swift"}],
                    "album": {"uri": "spotify:album:m"},
                }
            ]
        },
        "artists": {"items": [{"id": "ts", "uri": "spotify:artist:ts", "name": "Taylor Swift"}]},
        "albums": {"items": []},
        "playlists": {"items": []},
    }
    fake.routes["GET /me/player/devices"] = {"devices": [{"id": "d", "name": spotify_tv.device_name()}]}
    fake.routes["PUT /me/player/play"] = {}
    fake.routes["PUT /me/player/shuffle"] = {}
    v = spotify_tv.Voice(sp, FakePlayer())
    assert v.run("play", "taylor swift") == "Playing Taylor Swift."
    assert [c for c in fake.calls if c[1] == "/me/player/play"][-1][3]["context_uri"] == "spotify:artist:ts"
    assert v.run("play", "anti-hero") == "Playing Anti-Hero by Taylor Swift."


def test_voice_makes_a_playlist_from_songs_it_thought_of(fake):
    sp = signed_in(fake)
    asked = []
    fake.routes["GET /search"] = lambda p, j: (
        asked.append(p["q"]),
        {
            "tracks": {
                "items": [] if "Nope" in p["q"] else [{"id": p["q"], "uri": f"spotify:track:{len(asked)}", "name": "x", "artists": []}]
            }
        },
    )[1]
    fake.routes["POST /me/playlists"] = {"id": "new", "uri": "spotify:playlist:new", "name": "90s Rock", "owner": {"id": "max"}}
    fake.routes["POST /playlists/new/items"] = {"snapshot_id": "s"}
    v = spotify_tv.Voice(sp, FakePlayer())
    out = v.run("make_playlist", name="90s Rock", songs=["Nirvana - Lithium", "Zombie by The Cranberries", "Nope - Nope"], play=False)
    assert out == "Made 90s Rock with 2 songs (1 weren't on Spotify)."
    assert asked[:2] == ['track:"Lithium" artist:"Nirvana"', 'track:"Zombie" artist:"The Cranberries"']
    assert [c for c in fake.calls if c[1] == "/playlists/new/items"][0][3] == {"uris": ["spotify:track:1", "spotify:track:2"]}


def test_voice_likes_the_song_playing_and_needs_setup(fake):
    sp = signed_in(fake)
    fake.routes["PUT /me/library"] = {}
    assert spotify_tv.Voice(sp, FakePlayer()).run("like") == "Added Song to your Liked Songs."
    assert spotify_tv.Voice(spotify.Spotify(""), FakePlayer()).run("now").startswith("Spotify isn't set up")
