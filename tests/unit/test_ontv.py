"""What's on this TV (couchbox.ontv): the apps' answers shaped into one kind of item, the
Continue watching row's order across apps, which apps are asked, and how each item opens."""

import json
import os

import pytest

from couchbox import home, ontv, settings
from couchbox.services import vhx

NOW = 1_800_000_000.0
SERVER = "http://jf.example:8096"


# ------------------------------------------------------------------ shaping
def test_dates_and_minutes_left():
    assert ontv.when_of("2027-01-15T10:00:00.1234567Z") == pytest.approx(1800007200.123456)
    assert ontv.when_of("2027-01-15T10:00:00") == ontv.when_of("2027-01-15T10:00:00Z")
    assert ontv.when_of("") == 0 and ontv.when_of("yesterday") == 0
    assert ontv.minutes_left(3000, 1140) == "31 min left"
    assert ontv.minutes_left(7200, 1680) == "1 h 32 min left"
    assert ontv.minutes_left(600, 600) == ""


def test_episode_labels_match_the_streaming_app():
    assert ontv.ep_label({"episode": 1, "seasonName": "Fantasy High", "seasonNumber": 4}) == "Fantasy High · E1"
    assert ontv.ep_label({"episode": 2, "seasonName": "Season 5", "seasonNumber": 5}) == "S5 · E2"
    assert ontv.ep_label({"episode": 3}) == "Episode 3"
    assert ontv.ep_label({"episode": 0, "seasonNumber": 2}) == ""


def jf_episode(**kw):
    it = {
        "Id": "ep1",
        "Type": "Episode",
        "Name": "Low Tide",
        "SeriesName": "The Long Harbor",
        "SeriesId": "s1",
        "ParentIndexNumber": 2,
        "IndexNumber": 4,
        "RunTimeTicks": 3000 * 10**7,
        "ImageTags": {"Primary": "t1"},
        "UserData": {"PlaybackPositionTicks": 1140 * 10**7, "PlayedPercentage": 38.0, "LastPlayedDate": "2027-01-15T10:00:00.0000000Z"},
    }
    it.update(kw)
    return it


def test_a_jellyfin_episode_as_an_item():
    it = ontv.jellyfin_item(jf_episode(), SERVER)
    assert it["key"] == "jellyfin:ep1" and it["app"] == "jellyfin" and it["name"] == "Jellyfin"
    assert it["title"] == "The Long Harbor" and it["subtitle"] == "S2 · E4 · Low Tide"
    assert it["progress"] == 0.38 and it["left"] == "31 min left"
    assert it["when"] == ontv.when_of("2027-01-15T10:00:00Z")
    assert it["target"] == "jellyfin:ep1" and it["desktop"] == "couchbox-jellyfin.desktop"
    assert it["art"].startswith(f"{SERVER}/Items/ep1/Images/Primary?") and "tag=t1" in it["art"] and not it["fit"]


def test_jellyfin_pictures_prefer_wide_ones():
    movie = {
        "Id": "m1",
        "Type": "Movie",
        "Name": "Paper Moons",
        "ProductionYear": 2019,
        "ImageTags": {"Primary": "p"},
        "BackdropImageTags": ["b"],
    }
    it = ontv.jellyfin_item(movie, SERVER)
    assert "/Items/m1/Images/Backdrop/0?" in it["art"] and not it["fit"] and it["subtitle"] == "2019"
    poster_only = dict(movie, BackdropImageTags=[])
    assert ontv.jellyfin_art(poster_only, SERVER) == (f"{SERVER}/Items/m1/Images/Primary?maxWidth=560&quality=85&tag=p", True)
    # an episode without a still: the show's thumb, else its poster
    ep = jf_episode(ImageTags={}, ParentThumbItemId="s1", ParentThumbImageTag="th")
    assert "/Items/s1/Images/Thumb?" in ontv.jellyfin_art(ep, SERVER)[0]
    ep = jf_episode(ImageTags={}, SeriesPrimaryImageTag="sp")
    assert ontv.jellyfin_art(ep, SERVER) == (f"{SERVER}/Items/s1/Images/Primary?maxWidth=560&quality=85&tag=sp", True)
    assert ontv.jellyfin_art({"Id": "x", "Type": "Movie"}, SERVER) == ("", False)
    # progress from the position when Jellyfin gives no percentage
    it = ontv.jellyfin_item(jf_episode(UserData={"PlaybackPositionTicks": 750 * 10**7}), SERVER)
    assert it["progress"] == 0.25 and it["when"] == 0


def vhx_video(vid, tc, dur=1800, done=False, series="Game Changer"):
    return vhx.card(
        {
            "entity": {
                "id": vid,
                "type": "video",
                "title": "Sam Says",
                "duration": {"seconds": dur},
                "metadata": {"series_name": series, "season_number": 6, "episode_number": 3},
                "thumbnail": {"source": "https://vhx.imgix.net/x/thumb.jpg"},
            },
            "entity_type": "video",
            "play_state": {"timecode": tc, "completed": done},
        }
    )


def test_continue_watching_from_dropout_keeps_what_is_started_and_not_finished():
    cards = [
        vhx_video(101, 1080),
        vhx_video(102, 1790),
        vhx_video(103, 50, done=True),
        {"kind": "series", "id": 7, "title": "Dimension 20"},
    ]
    items = ontv.watching("dropout", cards)
    assert [i["key"] for i in items] == ["dropout:101", "dropout:7"]
    a = items[0]
    assert a["title"] == "Game Changer" and a["subtitle"] == "S6 · E3 · Sam Says" and a["left"] == "12 min left"
    assert a["progress"] == 0.6 and a["target"] == "dropout:play:101" and a["position"] == 1080
    assert "w=560" in a["art"] and "h=315" in a["art"]
    assert items[1]["target"] == "dropout:series:7"


def test_twitch_live_channels_and_search_cards():
    live = {
        "kind": "video",
        "id": "live:northcliff",
        "slug": "northcliff",
        "live": True,
        "series": "Northcliff",
        "title": "Speedrun",
        "description": "Retro",
        "viewers": "4.2K viewers",
        "landscape": "https://img/live.jpg",
        "started": "2027-01-15T08:00:00Z",
    }
    vod = {"kind": "video", "id": "vod:9", "title": "Old", "live": False}
    items = ontv.watching("twitch", [live, vod])
    assert len(items) == 1
    it = items[0]
    assert it["target"] == "twitch:play:live:northcliff" and it["live"] and it["viewers"] == "4.2K viewers"
    assert it["title"] == "Northcliff" and it["subtitle"] == "Speedrun" and it["when"] == ontv.when_of("2027-01-15T08:00:00Z")
    cat = ontv.stream_item("twitch", {"kind": "category", "id": "cat:Minecraft", "slug": "Minecraft", "title": "Minecraft", "poster": "p"})
    assert cat["target"] == "twitch:category:Minecraft" and cat["fit"]
    chan = ontv.stream_item(
        "twitch", {"kind": "series", "id": "northcliff", "title": "Northcliff", "description": "Offline", "square": "a"}
    )
    assert chan["target"] == "twitch:series:northcliff" and chan["art"] == "a" and chan["fit"]
    assert ontv.stream_item("nebula", {"kind": "video", "id": ""}) is None


def test_movies_and_shows_from_movies_and_tv():
    found = {
        "movies": [{"type": "movie", "id": 1, "title": "Quiet", "year": "2001", "popularity": 3, "backdrop": "", "poster": "po"}],
        "tv": [{"type": "tv", "id": 2, "title": "Loud", "year": "2010", "popularity": 9, "score": 8.1, "backdrop": "bd"}],
        "people": [{"type": "person", "id": 3}],
    }
    items = ontv.movies_items(found)
    assert [i["target"] for i in items] == ["movies:tv:2", "movies:movie:1"]
    assert items[0]["subtitle"] == "2010 · Show · ★ 8.1" and items[0]["art"] == "bd" and not items[0]["fit"]
    assert items[1]["subtitle"] == "2001 · Movie" and items[1]["fit"]
    yt = ontv.youtube_item("  lofi beats ")
    assert yt["target"] == "youtube:search:lofi beats" and yt["title"] == "Search YouTube for “lofi beats”"


# ------------------------------------------------------------------ order
def it(app, key, when=0.0, pos=None, live=False):
    out = ontv.item(app, key, key, f"{app}:play:{key}", when=when, live=live)
    if pos is not None:
        out["position"] = pos
    return out


def test_first_look_puts_undated_items_after_dated_ones_in_the_apps_order():
    seen = {}
    jf = [it("jellyfin", "j1", when=NOW - 86400)]
    d = [it("dropout", "d1", pos=100), it("dropout", "d2", pos=50)]
    ontv.place("jellyfin", jf, seen, NOW, first=True)
    ontv.place("dropout", d, seen, NOW, first=True)
    assert [x["key"] for x in ontv.merge({"jellyfin": jf, "dropout": d})] == ["jellyfin:j1", "dropout:d1", "dropout:d2"]
    assert "position" not in d[0] and seen["dropout:d1"]["pos"] == 100


def test_an_item_that_moved_on_was_just_watched():
    seen = {}
    ontv.place("dropout", [it("dropout", "d1", pos=100), it("dropout", "d2", pos=50)], seen, NOW, first=True)
    later = NOW + 3600
    d = [it("dropout", "d2", pos=900), it("dropout", "d1", pos=100), it("dropout", "d3", pos=10)]
    jf = [it("jellyfin", "j1", when=NOW + 1800)]
    ontv.place("dropout", d, seen, later, first=False)
    row = ontv.merge({"jellyfin": jf, "dropout": d})
    # d2 moved on and d3 is new (both just now, in Dropout's order); d1 sat still
    assert [x["key"] for x in row] == ["dropout:d2", "dropout:d3", "jellyfin:j1", "dropout:d1"]
    assert seen["dropout:d1"]["at"] == -0.0 and seen["dropout:d2"]["at"] == later


def test_positions_are_forgotten_after_a_month_away():
    seen = {"dropout:old": {"pos": 1, "at": 5.0, "seen": NOW - ontv.FORGET - 1}, "nebula:x": {"pos": 1, "at": 5.0, "seen": 0}}
    ontv.place("dropout", [], seen, NOW, first=False)
    assert "dropout:old" not in seen and "nebula:x" in seen


def test_merge_caps_live_channels_and_the_row():
    lives = [it("twitch", f"live:{i}", when=NOW - i, live=True) for i in range(10)]
    vids = [it("nebula", f"v{i}", when=NOW - 100 - i) for i in range(30)]
    row = ontv.merge({"twitch": lives, "nebula": vids})
    assert len(row) == ontv.MAX_ITEMS
    assert sum(1 for x in row if x["live"]) == ontv.MAX_LIVE
    assert [x["key"] for x in row[:2]] == ["twitch:live:0", "twitch:live:1"]
    # ties: the order of the apps, then each app's own order; the same item once
    tie = ontv.merge({"nebula": [it("nebula", "a", when=5)], "jellyfin": [it("jellyfin", "b", when=5), it("jellyfin", "b", when=5)]})
    assert [x["key"] for x in tie] == ["jellyfin:b", "nebula:a"]


# ------------------------------------------------------------------ which apps
def write_home(box, ids):
    f = box / "var/lib/couchbox/home/home.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"apps": [{"app": a} for a in ids]}))


def test_only_apps_on_the_home_row_are_asked(box):
    write_home(box, ["youtube", "twitch", "nebula", "jellyfin", "settings"])
    assert ontv.sources("continue") == ["jellyfin", "nebula", "twitch", "youtube"]
    assert ontv.sources("search") == ["jellyfin", "nebula", "twitch", "youtube"]
    # VacuumTube as the tile's app: its history is only in its page
    settings.update({"media.youtube.client": "vacuumtube"})
    (box / "var/lib/flatpak/app/rocks.shy.VacuumTube").mkdir(parents=True)
    assert ontv.sources("continue") == ["jellyfin", "nebula", "twitch"]
    settings.update({"media.youtube.client": "native"})
    # no home.json yet: the registry's row (Jellyfin needs its server set)
    (box / "var/lib/couchbox/home/home.json").unlink()
    settings.update({"apps.disabled": ["twitch"], "home.hidden": ["nebula"]})
    assert ontv.sources("continue") == ["dropout", "2ndtry", "youtube"]


def test_home_json_names_the_rows_file_unless_turned_off(box, runner):
    data = home.row_json()
    assert data["continueWatching"] == {"file": str(box / "home/tv/.cache/couchbox-ontv/continue.json")}
    settings.update({"home.continue": False})
    assert home.row_json()["continueWatching"] is None


# ------------------------------------------------------------------ opening
def test_targets_are_checked_before_anything_runs():
    assert ontv.split_target("dropout:play:123") == ("dropout", "play:123")
    assert ontv.split_target("nebula:play:video_episode:abc") == ("nebula", "play:video_episode:abc")
    assert ontv.split_target("twitch:category:Just Chatting") == ("twitch", "category:Just Chatting")
    assert ontv.split_target("movies:tv:1399") == ("movies", "tv:1399")
    assert ontv.split_target("jellyfin:0f3a9c2e8b7d4e10") == ("jellyfin", "0f3a9c2e8b7d4e10")
    assert ontv.split_target("youtube:video:dQw4w9WgXcQ") == ("youtube", "video:dQw4w9WgXcQ")
    bads = (
        "",
        "dropout",
        "dropout:",
        "spotify:play:1",
        "dropout:rm -rf",
        "movies:person:3",
        "jellyfin:../x",
        "youtube:play:x",
        "youtube:video:x y",
    )
    for bad in bads:
        with pytest.raises(ValueError):
            ontv.split_target(bad)


def test_how_each_app_is_opened():
    cmd = ontv.launch_command("dropout", "play:123", unit="app-couchbox-dropout@t.service")
    assert cmd == [
        "systemd-run",
        "--user",
        "--quiet",
        "--collect",
        "--unit=app-couchbox-dropout@t.service",
        "--",
        "/usr/lib/couchbox/bin/couchbox-dropout",
        "--open",
        "play:123",
    ]
    assert ontv.launch_command("twitch", "play:live:x")[4].startswith("--unit=app-couchbox-twitch@ontv-")
    assert ontv.voice_request("jellyfin", "ep1") == ("/play/jellyfin", {"id": "ep1"})
    assert ontv.voice_request("youtube", "search:lofi beats") == ("/search/youtube", {"query": "lofi beats"})
    yt = ontv.launch_command("youtube", "video:dQw4w9WgXcQ")
    assert yt[4].startswith("--unit=app-couchbox-yt@ontv-") and yt[-3:] == [
        "/usr/lib/couchbox/bin/couchbox-yt",
        "--open",
        "video:dQw4w9WgXcQ",
    ]


def test_open_uses_the_running_app_or_starts_it(monkeypatch):
    from couchbox import appctl

    calls, ran = [], []
    monkeypatch.setattr(appctl, "running", lambda site: site in ("nebula", "yt"))
    monkeypatch.setattr(appctl, "call", lambda site, req, timeout=0: calls.append((site, req)))
    monkeypatch.setattr(ontv, "kwin_raise", lambda app_id: calls.append(("raise", app_id)))
    monkeypatch.setattr(ontv.subprocess, "run", lambda cmd, **kw: ran.append(cmd))
    ontv.open_target("nebula:play:v9")
    assert calls == [("nebula", {"op": "open", "target": "play:v9"}), ("raise", "couchbox-nebula")]
    ontv.open_target("dropout:series:7")
    assert ran[0][-3:] == ["/usr/lib/couchbox/bin/couchbox-dropout", "--open", "series:7"]
    calls.clear()
    ontv.open_target("youtube:video:dQw4w9WgXcQ")  # Couchbox's own YouTube app: where the profile left off
    ontv.open_target("youtube:search:lofi")
    assert calls == [
        ("yt", {"op": "open", "target": "video:dQw4w9WgXcQ"}),
        ("raise", "couchbox-yt"),
        ("yt", {"op": "open", "target": "search:lofi"}),
        ("raise", "couchbox-yt"),
    ]


def test_youtube_continues_the_part_watched_videos_of_its_history():
    from couchbox.services import youtube

    page = youtube.Demo("demo1:").browse("FEhistory")
    items = ontv.youtube_continue(page)
    assert [i["key"] for i in items] == ["youtube:demo0000006", "youtube:demo0000010"]
    it = items[0]
    assert it["target"] == "youtube:video:demo0000006" and it["subtitle"] == "Orbit Lab" and it["progress"] == 0.35
    assert it["left"] == "30 min left" and it["desktop"] == "couchbox-yt.desktop" and it["position"] == 0.35
    assert ontv.length("1:02:03") == 3723 and ontv.length("LIVE") == 0


def test_youtube_needs_a_signed_in_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(ontv.NotSignedIn):
        ontv.fetch_continue("youtube", ontv.Clients())


# ------------------------------------------------------------------ Jellyfin's sign-in
class FakeResponse:
    def __init__(self, code, body):
        self.status_code, self.body = code, body

    def json(self):
        return self.body

    def raise_for_status(self):
        import requests

        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


def test_jellyfin_keeps_the_apps_sign_in_and_sends_only_the_token(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    auth = {"server": SERVER + "/", "token": "tok", "user": "u1"}
    monkeypatch.setattr(ontv.Jellyfin, "from_app", staticmethod(lambda: auth))
    j = ontv.Jellyfin.from_tv()
    f = tmp_path / ".local/share/couchbox-ontv/jellyfin.json"
    assert json.loads(f.read_text()) == auth and oct(os.stat(f).st_mode & 0o777) == "0o600"
    assert j.server == SERVER and j.s.headers["Authorization"] == 'MediaBrowser Token="tok"'
    # Jellyfin not running: the kept copy
    monkeypatch.setattr(ontv.Jellyfin, "from_app", staticmethod(lambda: None))
    assert ontv.Jellyfin.from_tv().user == "u1"
    f.unlink()
    assert ontv.Jellyfin.from_tv() is None

    asked = []

    def get(url, params=None, timeout=None):
        asked.append(url)
        if url.endswith("/UserItems/Resume"):  # an older server
            return FakeResponse(404, {})
        return FakeResponse(200, {"Items": [jf_episode()]})

    monkeypatch.setattr(j.s, "get", get)
    assert [x["key"] for x in j.resume()] == ["jellyfin:ep1"]
    assert asked == [f"{SERVER}/UserItems/Resume", f"{SERVER}/Users/u1/Items/Resume"]
    monkeypatch.setattr(j.s, "get", lambda *a, **kw: FakeResponse(401, {}))
    with pytest.raises(ontv.NotSignedIn):
        j.resume()


def test_demo_items_open_like_real_ones():
    for x in ontv.demo_continue(NOW) + [y for s in ontv.SEARCH_APPS for y in ontv.demo_search(s, "harbor")]:
        assert ontv.split_target(x["target"])[0] == x["app"]


def test_clients_are_made_again_only_for_a_new_sign_in(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    made = []

    class Fake:
        def __init__(self, site):
            made.append(site)

    monkeypatch.setattr(vhx, "Vhx", Fake)
    c = ontv.Clients()
    a = c.get("dropout")
    f = tmp_path / ".local/share/couchbox-dropout/session.json"
    f.parent.mkdir(parents=True)
    f.write_text("{}")  # the client saved a refreshed token while in use
    c.done("dropout")
    assert c.get("dropout") is a
    os.utime(f, (1, 1))  # the app signed in again
    assert c.get("dropout") is not a and made == ["dropout", "dropout"]
