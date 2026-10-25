from couchbox import migrate_mtv, settings

CONF = """# sample prototype settings (made up)
MTV_HOSTNAME=livingroom
MTV_TIMEZONE=Europe/Berlin     # comment
MTV_WEATHER="52.52,13.40,Berlin"
MTV_MODE=1920x1080@60
MTV_SCALE=1.5
MTV_OSD_NAME=livingroom
MTV_VOLUME=tv
MTV_TV_INPUTS="1.0.0.0 2.0.0.0"
MTV_AIRPLAY_PIN=
MTV_TS_TAGS=tag:tv
MTV_LLM_URL=https://llm.example/v1
MTV_LLM_MODEL=some-model
MTV_STT_URL=https://stt.example/v1
MTV_STT_MODEL=whisper-x
MTV_SEERR_URL=https://seerr.example
MTV_YT_CAPTIONS=en
MTV_APP_IDLE_MINUTES=60
MTV_SWAP_GB=8
MTV_WEB_CACHE_BYTES=268435456
"""


def test_import(tmp_path):
    (tmp_path / "secrets").mkdir()
    (tmp_path / "mtv.conf").write_text(CONF)
    (tmp_path / "secrets/llm-key").write_text("sk-test\n")
    (tmp_path / "home.tsv").write_text("# c\nrocks.shy.VacuumTube.desktop\tYouTube\tyoutube\nmtv-twitch.desktop\tTwitch\ttwitch\n")
    (tmp_path / "apps.tsv").write_text(
        "jellyfin\tJellyfin\thttps://jf.example\tx\ntwitch\tTwitch (web)\thttps://www.twitch.tv\tx\nnews\tNews\thttps://news.example\tx\n"
    )
    (tmp_path / "theme").write_text("MTV_THEME=amber\n")
    s, secrets = migrate_mtv.read(str(tmp_path))
    assert s["appearance.theme"] == "amber" and s["apps.twitch.skip_ads"] is True
    assert s["network.hostname"] == "livingroom" and s["time.timezone"] == "Europe/Berlin"
    assert s["location.name"] == "Berlin" and s["location.lat"] == 52.52
    assert s["home.layout"] == ["youtube", "twitch"]
    assert s["media.jellyfin.url"] == "https://jf.example"
    assert s["home.web_apps"] == [{"name": "News", "url": "https://news.example"}]
    assert s["voice.mode"] == "assistant" and s["apps.web_cache_mb"] == 256
    assert "apps.airplay.pin" not in s
    assert secrets == {"voice.llm.api_key": "sk-test"}
    settings.update(s)  # everything it produces is valid
