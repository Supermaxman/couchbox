"""The voice assistant's tools: they follow the home row, reach the streaming apps through
their control socket, and keep the prompt cache-friendly."""

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
