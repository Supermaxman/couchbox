"""The voice assistant's tools: they follow the home row, reach the streaming apps through
their control socket, and keep the prompt cache-friendly."""

import json
import time

import pytest

from couchbox import appctl, settings
from couchbox.voice import streaming, tools


def names():
    return {t["function"]["name"] for t in tools.schemas()}


def test_tools_follow_the_home_row():
    have = names()
    assert {"youtube", "dropout", "second_try", "nebula", "twitch", "open_app", "media"} <= have
    assert "jellyfin" not in have and "seerr" not in have  # no servers set
    settings.update({"home.hidden": ["dropout", "youtube"]})
    have = names()
    assert "dropout" not in have and "youtube" not in have and "nebula" in have
    assert "Dropout" not in tools.schemas()[0]["function"]["parameters"]["properties"]["name"]["enum"]
    assert tools.run_tool("dropout", {"action": "continue"}) == "dropout isn't available on this box."


def test_jellyfin_needs_its_server_and_its_tile():
    settings.update({"media.jellyfin.url": "https://jf.example"})
    assert "jellyfin" in names()
    settings.update({"home.hidden": ["jellyfin"]})
    assert "jellyfin" not in names()


def test_descriptions_stay_short():
    for t in tools.schemas():
        f = t["function"]
        assert len(f["description"]) <= 120, f["name"]
        for p in f["parameters"]["properties"].values():
            assert len(p.get("description", "")) <= 330, f["name"]


def test_windows_map_to_apps():
    assert tools.app_of_window({"class": "plasmashell", "app": "org.kde.plasmashell"}) == "home"
    assert tools.app_of_window({}) == "home"
    assert tools.app_of_window({"class": "couchbox-dropout", "app": "couchbox-dropout"}).id == "dropout"
    assert tools.app_of_window({"class": "x", "app": "rocks.shy.VacuumTube"}).id == "youtube"
    assert tools.app_of_window({"class": "something-else", "app": ""}) is None


def test_system_prompt_is_the_same_every_time(monkeypatch):
    from couchbox.voice import agent

    a = agent.Agent("http://x", "m", "k", lambda *_: None)
    first = a.system()
    monkeypatch.setattr(agent.time, "strftime", lambda *a: "another time")
    assert a.system() == first and "Now" not in first["content"]


@pytest.fixture
def app(tmp_path, monkeypatch):
    """A stand-in streaming app on its control socket."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    calls = []
    data = {
        "search": {"items": [{"kind": "series", "id": 7, "title": "Game Changer"}, {"kind": "video", "id": 1, "title": "Clip"}]},
        "collection": {
            "title": "Game Changer",
            "seasonList": [{"id": 71, "name": "Season 1", "number": 1}, {"id": 77, "name": "Season 7", "number": 7}],
        },
        "collectionItems": {
            "items": [{"kind": "video", "id": 700 + n, "title": f"Ep {n}", "episode": n, "seasonNumber": 7} for n in (1, 2, 3, 4)]
        },
        "watching": {"items": [{"kind": "video", "id": 703, "title": "Ep 3", "series": "Game Changer", "progress": 0.4}]},
    }

    def handler(req):
        calls.append(req)
        if req["op"] == "ping":
            return {"ok": True}
        if req["op"] == "call":
            return data[req["fn"]]
        if req["op"] == "state":
            return {
                "page": "player",
                "title": "Ep 3",
                "series": "Game Changer",
                "episode": "S7E3",
                "position": 75,
                "duration": 2400,
                "paused": False,
            }
        return {"ok": True}

    srv = appctl.Server("dropout", handler)
    srv.start()
    yield calls
    srv.close()


def test_latest_is_the_newest_season_newest_first(app):
    out = streaming.run("dropout", "latest", query="game changer", start=lambda: None, raise_app=lambda: None)
    assert out.splitlines()[0] == "Game Changer, newest first:"
    assert out.splitlines()[1].startswith("video 704 | Ep 4 | S7E4")
    assert {"op": "call", "fn": "collectionItems", "args": {"id": 77}} in app


def test_resume_plays_from_continue_watching(app):
    raised = []
    out = streaming.run("dropout", "resume", query="game changer", start=lambda: None, raise_app=lambda: raised.append(1))
    assert out.startswith("Playing Ep 3") and raised
    assert {"op": "open", "target": "play:703"} in app


def test_screen_line_for_a_streaming_app(app):
    assert streaming.state_line("dropout", "Dropout") == "Dropout in front: Game Changer S7E3 “Ep 3” playing at 1:15 of 40:00"


def test_not_running_starts_the_app(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(streaming.time, "sleep", lambda s: None)
    started = []
    with pytest.raises(RuntimeError, match="didn't start"):
        streaming.ensure("nebula", lambda: started.append(1))
    assert started == [1]


def test_cookie_browser_is_stopped_even_when_it_escaped(tmp_path):
    """flatpak's bwrap leaves our process group: the browser must still be stopped."""
    import subprocess
    import time

    from couchbox.services import vhx

    tmp = str(tmp_path / "prof")
    proc = subprocess.Popen(
        ["sh", "-c", f'setsid python3 -c "import time; time.sleep(300)" --user-data-dir={tmp} & sleep 300'],
        start_new_session=True,
    )
    for _ in range(50):
        if subprocess.run(["pgrep", "-f", f"--user-data-dir={tmp}"], capture_output=True).returncode == 0:
            break
        time.sleep(0.1)
    vhx.stop_browser(proc, tmp)
    assert proc.poll() is not None
    assert subprocess.run(["pgrep", "-f", f"--user-data-dir={tmp}"], capture_output=True).returncode != 0


def test_frigate_needs_its_server_and_finds_cameras_by_name():
    assert "frigate" not in names()
    settings.update({"media.frigate.url": "https://frigate.example"})
    assert "frigate" in names()
    settings.update({"home.hidden": ["frigate"]})
    assert "frigate" not in names()
    cams = [
        {"name": "front_door", "label": "Front Door"},
        {"name": "backyard", "label": "Backyard"},
        {"name": "backyard_left", "label": "Backyard Left"},
    ]
    assert tools.match_camera("front door", cams)["name"] == "front_door"
    assert tools.match_camera("the backyard camera", cams)["name"] == "backyard"
    assert tools.match_camera("backyard left cam", cams)["name"] == "backyard_left"
    assert tools.match_camera("garage", cams) is None


def test_frigate_timeline_opens_the_named_camera(monkeypatch):
    calls = []
    cams = [{"name": "front_door", "label": "Front Door"}, {"name": "garage", "label": "Garage"}]
    monkeypatch.setattr(tools.registry, "get", lambda *a: type("A", (), {"name": "Frigate", "desktop": "couchbox-frigate"})())
    monkeypatch.setattr(tools.streaming, "ensure", lambda *a, **k: None)
    monkeypatch.setattr(tools, "raise_window", lambda *a: None)
    monkeypatch.setattr(tools.appctl, "call", lambda site, req, **k: calls.append(req) or {"cameras": cams})
    assert tools.frigate_tool("timeline", "the garage") == "Showing the last day of Garage."
    assert calls[-1] == {"op": "open", "target": "timeline:garage"}
    assert tools.frigate_tool("timeline") == "Showing the last day."
    assert calls[-1] == {"op": "open", "target": "timeline"}


def test_weather_needs_a_town_and_answers_from_the_forecast(monkeypatch):
    from couchbox.services import weather

    assert "weather" not in names()
    settings.update({"location.name": "Lakeside", "location.lat": 45.6, "location.lon": -122.7, "time.timezone": "America/Los_Angeles"})
    assert "weather" in names()
    monkeypatch.setattr(tools, "_weather", weather.Weather(demo=True))
    out = tools.weather_tool("day", "tomorrow")
    assert "Tomorrow" in out and "°F" in out and "Shown" not in out
    calls = []
    monkeypatch.setattr(tools.registry, "get", lambda *a: type("A", (), {"name": "Weather", "desktop": "couchbox-weather"})())
    monkeypatch.setattr(tools.streaming, "ensure", lambda *a, **k: None)
    monkeypatch.setattr(tools, "raise_window", lambda *a: None)
    monkeypatch.setattr(tools.appctl, "call", lambda site, req, **k: calls.append((site, req)) or {"ok": True})
    tools.weather_tool("day", "tomorrow", show=True)
    assert calls[-1][0] == "weather" and calls[-1][1]["target"].startswith("day:")
    tools.weather_tool("week", show=True)
    assert calls[-1][1] == {"op": "open", "target": "week"}
    assert "Today" in tools.weather_tool("now")


def test_search_tool_searches_and_reads_the_page(monkeypatch):
    calls = []
    monkeypatch.setattr(tools.registry, "get", lambda *a: type("A", (), {"name": "Search", "desktop": "couchbox-search"})())
    monkeypatch.setattr(tools.streaming, "ensure", lambda *a, **k: None)
    monkeypatch.setattr(tools, "raise_window", lambda *a: None)
    page = {"title": "Eiffel Tower", "url": "https://example.org/e", "text": "It is 330 m tall."}
    monkeypatch.setattr(tools.appctl, "call", lambda site, req, **k: calls.append((site, req)) or page)
    assert tools.search_tool("search", " how tall is the eiffel tower ") == "Showing Google's results for 'how tall is the eiffel tower'."
    assert calls[-1] == ("search", {"op": "open", "target": "search:how tall is the eiffel tower"})
    assert tools.search_tool("open", "example.org") == "Opening example.org."
    assert calls[-1][1]["target"] == "url:example.org"
    assert tools.search_tool("read") == "Page: Eiffel Tower (https://example.org/e)\nIt is 330 m tall."
    assert tools.search_tool("search", "") == "Missing query."
    assert "search" in names()
    settings.update({"home.hidden": ["search"]})
    assert "search" not in names()


def test_maps_is_a_tool_and_reads_arrival_times():
    assert "maps" in names()
    settings.update({"home.hidden": ["maps"]})
    assert "maps" not in names()
    now = time.mktime((2030, 1, 1, 15, 0, 0, 0, 0, -1))
    assert time.localtime(tools.arrival_time("17:00", now)).tm_hour == 17
    assert time.localtime(tools.arrival_time("5 pm", now))[2:5] == (1, 17, 0)
    assert time.localtime(tools.arrival_time("9:30", now))[2:5] == (2, 9, 30)  # already past today: tomorrow
    with pytest.raises(ValueError):
        tools.arrival_time("soon")


def test_maps_tool_answers_and_opens_the_route(monkeypatch):
    calls = []
    work = {"name": "Work", "kind": "work", "lat": 1.0, "lon": 2.0}
    route = {"duration_text": "23 min", "distance_text": "9.1 mi", "summary": "I-5 N", "traffic": "light", "arrive": time.time() + 1380}

    def call(site, req, **k):
        calls.append(req)
        if req["op"] == "open":
            return {"ok": True}
        return {
            "resolve": work,
            "directions": {"routes": [route]},
            "leave_by": {"leave": time.time() + 3600, "late": False, "traffic": True, "route": dict(route, arrive=time.time() + 4980)},
        }[req["fn"]]

    monkeypatch.setattr(tools.registry, "get", lambda *a: type("A", (), {"name": "Maps", "desktop": "couchbox-maps"})())
    monkeypatch.setattr(tools.streaming, "ensure", lambda *a, **k: None)
    monkeypatch.setattr(tools, "raise_window", lambda *a: None)
    monkeypatch.setattr(tools.appctl, "call", call)
    said = tools.maps_tool("eta", "work")
    assert said.startswith("Work: 23 min by car in light traffic right now via I-5 N, 9.1 mi, arriving")
    assert calls[-1]["op"] == "open" and calls[-1]["target"].startswith("to:")
    assert json.loads(calls[-1]["target"][3:])["place"] == work
    said = tools.maps_tool("leave_by", "work", when="17:00")
    assert said.startswith("Leave by ") and "with expected traffic" in said
    assert calls[-1]["target"].startswith("leave:")


def test_movies_needs_seerr_or_a_tmdb_key():
    from couchbox import secrets

    assert "movies" not in names()
    secrets.put("media.tmdb.token", "test-fake-tmdb")
    assert "movies" in names()
    settings.update({"home.hidden": ["movies"]})
    assert "movies" not in names()


def test_movies_answers_and_opens_the_app(monkeypatch, tmp_path):
    from couchbox.services import movies

    opened = []
    monkeypatch.setattr(movies.Movies, "for_root", classmethod(lambda cls: cls(movies.Demo(), movies.demo_ratings(tmp_path / "r.bin"))))
    monkeypatch.setattr(tools, "open_movies", opened.append)
    said = tools.movies_tool("title", "the long harbor")
    assert said.startswith("The Long Harbor (2024 movie, PG-13, 118 min") and "Directed by Ines Okafor." in said
    assert "IMDb 8.3/10" in said and "Rotten Tomatoes 91% critics" in said and "It's in Jellyfin." in said
    assert opened[-1] == "movie:101"
    said = tools.movies_tool("person", "ines okafor", role="directing")
    assert (
        said.startswith("Ines Okafor, director, born 1988-04-12") and "Directing (3, newest first): Paper Orchards (2025, Director)" in said
    )
    assert opened[-1] == "person:303:Directing"
    assert tools.movies_tool("top", type="tv").startswith("Top rated shows: 1. Saltmarsh (2022, 8.6)")
    assert opened[-1] == "top:tv"


def test_movie_facts_get_a_nudge_to_the_movies_tool():
    from couchbox.voice import agent

    a = agent.Agent("http://x", "m", "k", lambda *_: None)
    a.tool_list = [{"function": {"name": n}} for n in ("movies", "jellyfin")]
    for q in ("who directed Arrival", "what's the IMDb rating of Severance", "what else has Florence Pugh been in",
              "show me Denis Villeneuve's movies", "who plays Mark in Severance", "top rated shows"):
        assert "movies tool" in a.hint(q), q
    for q in ("play Severance", "pause", "cast this to the TV", "what's the weather tomorrow"):
        assert a.hint(q) == "", q
    a.tool_list = [{"function": {"name": "jellyfin"}}]  # no Movies & TV app: nothing to nudge to
    assert a.hint("who directed Arrival") == ""
