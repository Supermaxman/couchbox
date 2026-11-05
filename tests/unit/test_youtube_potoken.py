"""PO tokens for the YouTube app's streams: where they come from (the bgutil provider's server,
its script, or nowhere), the retry after a bot check, and the log of which client served a
video. No yt-dlp or provider here: fakes in their shapes."""

import http.server
import threading
import types

import pytest

from couchbox.services import ytstream as S


@pytest.fixture
def plugin(tmp_path, monkeypatch):
    """The provider's plugin installed, its script not, nothing answering on POT_URL."""
    zip_ = tmp_path / "bgutil-ytdlp-pot-provider.zip"
    zip_.write_bytes(b"PK")
    monkeypatch.setenv("COUCHBOX_YT_POT_PLUGIN", str(zip_))
    monkeypatch.setenv("COUCHBOX_YT_POT_HOME", str(tmp_path / "server"))
    monkeypatch.setattr(S, "POT_URL", "http://127.0.0.1:9")  # discard: nothing listens
    return tmp_path


def test_no_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("COUCHBOX_YT_POT_PLUGIN", str(tmp_path / "missing.zip"))
    assert S.pot_mode() == "none"


def test_script_when_the_server_is_down(plugin, monkeypatch):
    monkeypatch.setattr(S, "js_runtimes", lambda: {"node": {"path": "/usr/bin/node"}})
    assert S.pot_mode() == "none"  # no script yet
    (plugin / "server" / "build").mkdir(parents=True)
    (plugin / "server" / "build" / "generate_once.js").write_text("")
    assert S.pot_mode() == "script"
    monkeypatch.setattr(S, "js_runtimes", lambda: {"deno": {"path": "/usr/bin/deno"}})
    assert S.pot_mode() == "none"  # the script needs node


def test_http_when_the_server_answers(plugin, monkeypatch):
    class Ping(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200 if self.path == "/ping" else 404)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), Ping)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        monkeypatch.setattr(S, "POT_URL", f"http://127.0.0.1:{srv.server_port}")
        assert S.pot_mode() == "http"
    finally:
        srv.shutdown()


def test_options_point_the_plugin_at_the_provider(plugin):
    o = S._options()
    args = o["extractor_args"]
    assert args["youtubepot-bgutilhttp"] == {"base_url": [S.POT_URL]}
    assert args["youtubepot-bgutilscript"] == {"server_home": [str(plugin / "server")]}
    assert "player_client" not in args["youtube"]  # yt-dlp's own choice of clients
    assert S._options(["mweb", "tv"])["extractor_args"]["youtube"]["player_client"] == ["mweb", "tv"]


def test_served_by_names_the_client_never_the_token():
    secret = "MnSECRETtokenVALUE"
    by = S.served_by(
        f"https://rr1.googlevideo.com/videoplayback?expire=1&c=MWEB&itag=137&pot={secret}",
        f"https://rr1.googlevideo.com/videoplayback?expire=1&c=MWEB&itag=140&pot={secret}",
    )
    assert by == {"client": "MWEB", "pot": True}
    assert secret not in repr(by)
    assert S.served_by("https://rr1.googlevideo.com/videoplayback?c=TVHTML5&itag=18") == {"client": "TVHTML5", "pot": False}
    # HLS: parameters in the path; a manifest that doesn't say
    assert S.served_by("https://manifest.googlevideo.com/api/manifest/hls_playlist/expire/1/c/IOS/pot/x/file/index.m3u8") == {
        "client": "IOS",
        "pot": True,
    }
    assert S.served_by("https://manifest.googlevideo.com/api/manifest/hls_playlist/expire/1/file/index.m3u8")["client"] == "HLS"
    assert S.served_by("") == {"client": "?", "pot": False}


BOT = "ERROR: [youtube] abc: Sign in to confirm you’re not a bot. Use --cookies-from-browser"


def fake_ytdlp(monkeypatch, plugin, answers):
    """yt-dlp whose usual YoutubeDL and retry YoutubeDL (told apart by player_client) answer in
    turn from answers["usual"] / answers["retry"]: an info dict, or an error message to raise."""
    made = []

    class YoutubeDL:
        def __init__(self, params):
            self.kind = "retry" if params["extractor_args"]["youtube"].get("player_client") else "usual"
            made.append(self.kind)

        def extract_info(self, url, download, process):
            got = answers[self.kind].pop(0)
            if isinstance(got, str):
                raise RuntimeError(got)
            return dict(got)

    monkeypatch.setattr(S, "module", lambda: types.SimpleNamespace(YoutubeDL=YoutubeDL))
    monkeypatch.setattr(S, "_ydl", None)
    monkeypatch.setattr(S, "_ydl_retry", None)
    return made


def test_plays_without_a_retry(plugin, monkeypatch):
    made = fake_ytdlp(monkeypatch, plugin, {"usual": [{"id": "abc"}], "retry": []})
    info = S.extract("abc")
    assert info["id"] == "abc" and info["_couchbox_retry"] is False
    assert made == ["usual"]


def test_bot_check_retries_once_with_other_clients(plugin, monkeypatch, capsys):
    made = fake_ytdlp(monkeypatch, plugin, {"usual": [BOT], "retry": [{"id": "abc"}]})
    info = S.extract("abc")
    assert info["_couchbox_retry"] is True
    assert made == ["usual", "retry"]
    assert "bot check; trying again with mweb, tv" in capsys.readouterr().out


def test_bot_check_twice_says_so_in_plain_words(plugin, monkeypatch):
    fake_ytdlp(monkeypatch, plugin, {"usual": [BOT], "retry": [BOT]})
    with pytest.raises(S.Unavailable) as err:
        S.extract("abc")
    assert str(err.value).startswith("YouTube wants this TV to prove it isn't a bot")


def test_other_errors_are_not_retried(plugin, monkeypatch):
    made = fake_ytdlp(monkeypatch, plugin, {"usual": ["ERROR: [youtube] abc: Private video. Sign in"], "retry": []})
    with pytest.raises(S.Unavailable, match="This video is private."):
        S.extract("abc")
    assert made == ["usual"]


def test_resolve_logs_the_client_and_po_token_path(plugin, monkeypatch, capsys):
    secret = "MnSECRETtokenVALUE"
    info = {
        "id": "abc",
        "title": "A made-up video",
        "formats": [
            {
                "format_id": "137",
                "vcodec": "avc1.640028",
                "acodec": "none",
                "height": 1080,
                "width": 1920,
                "url": f"https://rr1.googlevideo.com/videoplayback?c=MWEB&itag=137&pot={secret}",
            },
            {
                "format_id": "140",
                "vcodec": "none",
                "acodec": "mp4a.40.2",
                "abr": 128,
                "url": f"https://rr1.googlevideo.com/videoplayback?c=MWEB&itag=140&pot={secret}",
            },
        ],
    }
    fake_ytdlp(monkeypatch, plugin, {"usual": [BOT], "retry": [info]})
    out = S.resolve("abc")
    log = capsys.readouterr().out
    assert "client=MWEB pot=yes" in log and "retry" in log
    assert secret not in log
    assert out["client"] == "MWEB" and out["pot"] is True
