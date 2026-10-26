import json

import pytest

from couchbox import apps, home, settings


def ids(row):
    return [a.id for a in row]


def test_default_row_hides_apps_that_need_setup():
    row = ids(apps.home_row())
    assert row == ["youtube", "dropout", "2ndtry", "nebula", "twitch", "search", "settings"]
    assert "jellyfin" not in row and "seerr" not in row  # no server set
    assert "fcast" not in row and "twitch-web" not in row  # hidden by default


def test_configured_servers_show_their_apps():
    settings.update({"media.jellyfin.url": "http://jf.local:8096"})
    assert ids(apps.home_row())[:2] == ["youtube", "jellyfin"]


def test_user_order_hidden_names_and_disabled():
    settings.update(
        {"home.layout": ["twitch", "youtube"], "home.hidden": ["nebula"], "home.names": {"youtube": "YT"}, "apps.disabled": ["dropout"]}
    )
    row = apps.home_row()
    assert ids(row) == ["twitch", "youtube", "2ndtry", "search", "settings"]
    assert row[1].name == "YT"


def test_settings_tile_can_not_be_hidden_and_stays_last():
    settings.update({"home.hidden": ["settings"], "home.layout": ["settings", "youtube"]})
    assert ids(apps.home_row())[-1] == "settings"


def test_move():
    s = settings.load()
    layout = apps.move(s["home.layout"], "twitch", 0, s)
    assert layout[:2] == ["twitch", "youtube"]
    settings.update({"home.layout": layout})
    layout = apps.move(layout, "twitch", 99)
    assert ids(apps.home_row())[0] == "twitch" and layout[-1] == "twitch"
    with pytest.raises(settings.SettingsError):
        apps.move(layout, "fcast", 0)


def test_hidden_by_default_app_shows_when_ordered():
    settings.update({"home.layout": ["youtube", "fcast"]})
    assert "fcast" in ids(apps.home_row())


def test_user_websites():
    settings.update({"home.web_apps": [{"name": "News", "url": "https://news.example"}]})
    a = apps.get("web-news")
    assert a and a.kind == "web" and a.desktop == "couchbox-web-web-news.desktop"
    assert "web-news" in ids(apps.home_row())


def test_build_writes_home_json_and_launchers(box, runner):
    settings.update(
        {
            "home.web_apps": [{"name": "News", "url": "https://news.example"}],
            "location.name": "Springfield",
            "location.lat": 39.8,
            "location.lon": -89.6,
        }
    )
    data = home.build()
    f = box / "var/lib/couchbox/home/home.json"
    assert json.loads(f.read_text()) == data
    assert data["weather"]["name"] == "Springfield"
    assert [a["app"] for a in data["apps"]][-1] == "settings"
    web = box / "usr/local/share/applications/couchbox-web-web-news.desktop"
    text = web.read_text()
    assert "--app=https://news.example" in text and "--remote-debugging-port=9223" in text
    # removed websites lose their launchers
    settings.update({"home.web_apps": []})
    home.build()
    assert not web.exists()


def test_renamed_app_gets_a_user_desktop_override(box, runner):
    src = box / "var/lib/flatpak/exports/share/applications/rocks.shy.VacuumTube.desktop"
    src.parent.mkdir(parents=True)
    src.write_text("[Desktop Entry]\nName=VacuumTube\nName[de]=VacuumTube\nExec=flatpak run rocks.shy.VacuumTube\nIcon=vt\n")
    home.build()
    o = (box / "home/tv/.local/share/applications/rocks.shy.VacuumTube.desktop").read_text()
    assert "Name=YouTube" in o and "Name[de]" not in o and "--remote-debugging-port=9222" in o
    favs = (box / "home/tv/.config/bigscreen-favs").read_text()
    assert "storageId=rocks.shy.VacuumTube.desktop" in favs and "icon=vt" in favs


def test_overlay_falls_back_for_untested_bigscreen(box, monkeypatch):
    stock = box / "usr/share/plasma/plasmoids" / home.PLASMOID / "contents/ui"
    stock.mkdir(parents=True)
    (stock / "main.qml").write_text("// stock")
    (box / "usr/share/couchbox/shell/home/couchbox").mkdir(parents=True)
    (box / "usr/share/couchbox/shell/home/HomeHeader.qml").write_text("// ours")
    monkeypatch.setattr(home, "bigscreen_version", lambda: "6.7.5")
    assert home.overlay({"apps": []}) == "couchbox"
    ours = box / "usr/local/share/plasma/plasmoids" / home.PLASMOID / "contents/ui"
    assert (ours / "main.qml").exists() and (ours / "HomeHeader.qml").read_text() == "// ours"
    assert "var data" in (ours / "couchbox/home-data.js").read_text()
    monkeypatch.setattr(home, "bigscreen_version", lambda: "6.9.0")
    assert home.overlay({"apps": []}) == "stock"
    assert not ours.exists()
