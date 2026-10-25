import json
import stat

import pytest

from couchbox import paths, secrets, settings


def test_defaults_cover_every_key_with_a_page():
    sch = settings.schema()
    for k, v in sch["settings"].items():
        assert v["page"] in sch["pages"], k
        assert "label" in v, k
        settings.validate(k, v["default"])  # every default is valid


def test_only_changed_keys_are_stored(box):
    settings.update({"voice.mode": "dictation", "network.hostname": "couchbox"})
    data = json.loads(paths.settings_file().read_text())
    assert data["values"] == {"voice.mode": "dictation"}  # the default hostname isn't stored
    assert settings.get("voice.mode") == "dictation"


def test_setting_back_to_default_removes_it():
    settings.update({"voice.mode": "assistant"})
    settings.update({"voice.mode": "off"})
    assert settings.changed() == {}


@pytest.mark.parametrize(
    "key,value",
    [
        ("network.hostname", "Bad Name"),
        ("network.hostname", "a" * 40),
        ("voice.mode", "loud"),
        ("appearance.scale", 3),
        ("apps.idle_minutes", 1.5),
        ("apps.airplay.pin", "12a4"),
        ("media.jellyfin.url", "ftp://x"),
        ("media.jellyfin.url", "jellyfin.local"),
        ("tv.cec.name", "x" * 15),
        ("updates.window", "25:00-06:00"),
        ("location.name", "two\nlines"),
        ("home.web_apps", [{"name": "x", "url": "javascript:alert(1)"}]),
    ],
)
def test_bad_values_are_refused(key, value):
    with pytest.raises(settings.SettingsError):
        settings.update({key: value})
    assert settings.changed() == {}


def test_update_is_all_or_nothing():
    with pytest.raises(settings.SettingsError):
        settings.update({"voice.mode": "assistant", "network.hostname": "NOPE!"})
    assert settings.get("voice.mode") == "off"


def test_normalizing():
    assert settings.validate("media.seerr.url", " https://seerr.example/ ") == "https://seerr.example"
    assert settings.validate("ssh.enabled", "on") is True
    assert settings.validate("apps.idle_minutes", "90") == 90
    assert settings.validate("home.web_apps", [{"name": "My Site", "url": "https://example.com"}]) == [
        {"id": "web-my-site", "name": "My Site", "url": "https://example.com"}
    ]


def test_broken_file_runs_on_defaults(box):
    paths.settings_file().parent.mkdir(parents=True, exist_ok=True)
    paths.settings_file().write_text("{not json")
    assert settings.load()["voice.mode"] == "off"


def test_bad_stored_value_falls_back_to_default(box):
    paths.settings_file().parent.mkdir(parents=True, exist_ok=True)
    paths.settings_file().write_text(json.dumps({"version": 1, "values": {"voice.mode": "loud", "apps.idle_minutes": 30, "gone.key": 1}}))
    s = settings.load()
    assert s["voice.mode"] == "off" and s["apps.idle_minutes"] == 30 and "gone.key" not in s


def test_env_file(box):
    settings.update({"apps.airplay.pin": "1234", "tv.inputs": ["1.0.0.0", "4.0.0.0"], "voice.notes": "it's 'quoted'\nmulti"})
    text = paths.env_file().read_text()
    assert "COUCHBOX_APPS_AIRPLAY_PIN='1234'" in text
    assert "COUCHBOX_TV_INPUTS='1.0.0.0 4.0.0.0'" in text
    assert "COUCHBOX_AIRPLAY_NAME='couchbox'" in text  # derived: defaults to the device name
    assert "VOICE_NOTES" not in text  # free text stays out of the shell file


def test_derived_units_and_clock():
    assert settings.derived()["units"] == "metric"
    settings.update({"time.timezone": "America/Los_Angeles"})
    d = settings.derived()
    assert d["units"] == "imperial" and d["clock24"] is False
    settings.update({"home.clock": "24h"})
    assert settings.derived()["clock24"] is True


def test_weather_needs_a_location():
    assert settings.derived()["weather"] == ""
    settings.update({"location.name": "Springfield", "location.lat": 39.8, "location.lon": -89.6})
    assert settings.derived()["weather"] == "39.8,-89.6,Springfield"
    settings.update({"home.weather": False})
    assert settings.derived()["weather"] == ""


def test_migrations_run_in_order(monkeypatch):
    from couchbox.settings import migrations

    monkeypatch.setitem(migrations.MIGRATIONS, 1, lambda v: {("new.key" if k == "old.key" else k): x for k, x in v.items()})
    assert settings.migrate({"version": 1, "values": {"old.key": 5}}) == {"version": 2, "values": {"new.key": 5}}


def test_secrets_are_root_only_and_never_exported(box):
    secrets.put("voice.llm.api_key", "sk-abcdef123456")
    f = paths.secrets_dir() / "voice.llm.api_key"
    assert stat.S_IMODE(f.stat().st_mode) == 0o600
    assert stat.S_IMODE(paths.secrets_dir().stat().st_mode) == 0o700
    assert secrets.get("voice.llm.api_key") == "sk-abcdef123456"
    assert secrets.status()["voice.llm.api_key"] is True
    assert "sk-abc" not in json.dumps(settings.load())
    assert secrets.mask("key=sk-abcdef123456") == "key=sk-…"
    secrets.clear("voice.llm.api_key")
    assert secrets.get("voice.llm.api_key") == ""


def test_secret_names_are_checked():
    with pytest.raises(settings.SettingsError):
        secrets.put("../etc/passwd", "x")
    with pytest.raises(settings.SettingsError):
        secrets.put("voice.llm.api_key", "two\nlines")


def test_phone_token_is_made_once():
    t = secrets.ensure_token()
    assert len(t) >= 20 and secrets.ensure_token() == t
