"""Moments: the list (validated as a setting, found by a spoken name), their home tiles, and the
voice service's runtime: starting, repeating, noticing the end, putting sound and picture back."""

import pytest

from couchbox import home, moments, settings
from couchbox.voice import commands, tools
from couchbox.voice import moments as player

VID = "dQw4w9WgXcQ"


def pet(**kw):
    return dict({"name": "Pet music", "app": "youtube", "target": f"video:{VID}", "title": "Calm piano for dogs"}, **kw)


def test_a_moment_is_checked_and_tidied():
    m = moments.clean(pet(volume="40", repeat=1))
    assert m == {
        "id": "pet-music",
        "name": "Pet music",
        "app": "youtube",
        "target": f"video:{VID}",
        "title": "Calm piano for dogs",
        "art": "",
        "volume": 40,
        "repeat": True,
        "dark": False,
        "leaving": False,
    }
    for bad in (pet(app="spotify"), pet(target="video:nope"), pet(name=""), pet(app="jellyfin", target="play:1"), "x"):
        with pytest.raises(moments.MomentError):
            moments.clean(bad)
    assert moments.clean(pet(app="twitch", target="play:live:somechannel"))["target"] == "play:live:somechannel"
    assert moments.clean(pet(volume=500))["volume"] == 100


def test_the_list_is_a_setting():
    settings.update({"moments.list": [pet(), pet(name="Bedtime", app="jellyfin", target="0123456789abcdef")]})
    assert [m["id"] for m in moments.all()] == ["pet-music", "bedtime"]
    with pytest.raises(settings.SettingsError):
        settings.update({"moments.list": [pet(), pet(title="again")]})  # the same id twice


def test_found_by_what_is_said():
    settings.update({"moments.list": [pet(), pet(name="Bedtime", title="Rain")]})
    assert moments.find("the pet music")["id"] == "pet-music"
    assert moments.find("Pet Music!")["id"] == "pet-music"
    assert moments.find("pet")["id"] == "pet-music"  # the only one with that word
    assert moments.find("bedtime moment")["id"] == "bedtime"
    assert moments.find("cartoons") is None


def test_taught_again_replaces_it_in_place():
    ms = moments.with_moment([], pet())
    ms = moments.with_moment(ms, pet(name="Bedtime"))
    ms = moments.with_moment(ms, pet(name="pet music", title="New one"))
    assert [(m["name"], m["title"]) for m in ms] == [("pet music", "New one"), ("Bedtime", "Calm piano for dogs")]


def test_leaving_is_noted_when_one_starts():
    st = moments.read_state()
    moments.note_started(st, moments.clean(pet()), now=100)
    assert st["left"] is None
    moments.note_started(st, moments.clean(pet(leaving=True)), now=200)
    moments.write_state(st)
    assert moments.left_at() == 200
    assert moments.read_state()["started"] == {"pet-music": 200}


def test_home_row_starts_with_a_tile_per_moment():
    settings.update({"moments.list": [pet(), pet(name="Stream", app="twitch", target="play:live:x")]})
    row = home.row_json()["apps"]
    tiles = [a for a in row if a.get("moment")]
    assert [t["name"] for t in tiles] == ["Pet music", "Stream"] and row[:2] == tiles
    assert row[-1]["app"] == "settings" and row[-1]["hideable"] is False
    assert all(t["hideable"] is False and t["app"].startswith("moment:") for t in tiles)
    settings.update({"home.hidden": ["twitch"]})  # its app hidden: its tile goes too
    assert [a["name"] for a in home.row_json()["apps"] if a.get("moment")] == ["Pet music"]


def test_dictation_phrases():
    assert commands.parse("Remember this as pet music.") == ("remember", "pet music")
    assert commands.parse("play pet music") == ("moment", "pet music")
    assert commands.parse("play pet music", moments=False) is None
    assert commands.parse("start youtube", moments=False) == ("open", "youtube")
    assert commands.parse("play it") == ("play", "")
    assert commands.parse("stop the moment") == ("stop_moment", "")


def test_the_tool_lists_the_moments_and_stays_short():
    settings.update({"moments.list": [pet()]})
    t = next(t["function"] for t in tools.schemas() if t["function"]["name"] == "moments")
    assert len(t["description"]) <= 120
    assert "Pet music" in t["parameters"]["properties"]["name"]["description"]


# ------------------------------------------------------------------ the runtime, with fake apps
class Box:
    """A fake TV: what the YouTube app plays, the box's sound level, what was asked of it."""

    def __init__(self, monkeypatch):
        self.playing = None  # {id, position, duration, ...}
        self.volume = 1.0
        self.did = []
        self.logs = []
        monkeypatch.setattr(
            player, "now_playing", lambda app: dict(self.playing, title="", paused=False, live=False) if self.playing else None
        )
        monkeypatch.setattr(player, "get_volume", lambda: self.volume)
        monkeypatch.setattr(player, "set_volume", lambda v: setattr(self, "volume", v))
        monkeypatch.setattr(player, "media", lambda app, action: self.did.append(action))
        monkeypatch.setattr(player, "open_in_app", self.open)
        monkeypatch.setattr(player, "DARK_FLAG", str(moments.state_file().parent / "dark"))

    def open(self, m):
        self.did.append("open " + m["target"])
        self.playing = {"id": m["target"].split(":")[1], "position": 0, "duration": 36000}


@pytest.fixture
def tv(monkeypatch):
    return Box(monkeypatch)


def test_start_sets_volume_and_dark_and_stop_puts_them_back(tv):
    settings.update({"moments.list": [pet(volume=40, dark=True, leaving=True)]})
    out = player.start("pet-music")
    assert out.startswith("Playing Pet music") and tv.did == [f"open video:{VID}"]
    assert tv.volume == 0.4 and player.dark() and moments.left_at()
    assert player.wake() is True and not player.dark()  # a key: the picture back, still playing
    assert moments.active_id() == "pet-music"
    assert player.stop().startswith("Stopped Pet music")
    assert tv.volume == 1.0 and "pause" in tv.did and moments.active_id() is None


def test_repeat_goes_back_to_the_start_near_the_end(tv):
    settings.update({"moments.list": [pet(repeat=True)]})
    player.start("pet-music")
    tv.playing["position"] = 35990
    player.tick(tv.logs.append)
    assert tv.did[-1] == "open video:" + VID  # far from the end: nothing
    tv.playing["position"] = 35997
    player.tick(tv.logs.append)
    assert tv.did[-1] == "restart"


def test_it_is_over_when_something_else_plays(tv):
    settings.update({"moments.list": [pet(volume=50, dark=True)]})
    player.start("pet-music")
    t = moments.read_state()["active"]["since"]
    player.tick(tv.logs.append, now=t + 5)
    tv.playing = {"id": "otherVideo1", "position": 3, "duration": 300}
    player.tick(tv.logs.append, now=t + 7)  # (a moment's gap is allowed)
    assert moments.active_id() == "pet-music"
    player.tick(tv.logs.append, now=t + 15)
    assert moments.active_id() is None and tv.volume == 1.0 and not player.dark()
    assert "something else is playing" in tv.logs[-1]


def test_an_app_gets_time_to_start_it(tv):
    settings.update({"moments.list": [pet()]})
    player.start("pet-music")
    t = moments.read_state()["active"]["since"]
    tv.playing = None
    player.tick(tv.logs.append, now=t + 30)
    assert moments.active_id() == "pet-music"
    player.tick(tv.logs.append, now=t + 61)
    assert moments.active_id() is None and "it didn't start" in tv.logs[-1]


def test_a_repeat_that_ended_anyway_starts_again(tv):
    settings.update({"moments.list": [pet(repeat=True)]})
    player.start("pet-music")
    t = moments.read_state()["active"]["since"]
    tv.playing["position"] = 35990  # (missed: the next look is past the end)
    player.tick(tv.logs.append, now=t + 70)
    tv.playing = None  # the app moved on to its end screen
    player.tick(tv.logs.append, now=t + 80)
    assert tv.did[-1] == f"open video:{VID}" and moments.active_id() == "pet-music"


def test_teaching_saves_what_plays(tv, monkeypatch):
    monkeypatch.setattr(player, "capture", lambda: {"app": "youtube", "target": f"video:{VID}", "title": "Calm piano", "art": ""})
    tv.volume = 0.6  # the household turned the box's own sound down
    m, again = player.teach("pet music", repeat=True, leaving=True)
    assert not again and m["name"] == "Pet music" and m["volume"] == 60 and m["repeat"] and m["leaving"]
    m, again = player.teach("Pet Music", dark=True)
    assert again and m["repeat"] and m["dark"] and len(moments.all()) == 1
