"""Links sent to the TV (couchbox.links): real-world link shapes from share sheets and address
bars go to the right app with the right id, bad input is refused with a reason, and opening
reaches the apps the way the voice tools do."""

import pytest

from couchbox import links
from couchbox.links import BadLink, Link

JF = "http://jellyfin.example:8096"
ITEM = "0123456789abcdef0123456789abcdef"


def where(text, jellyfin=JF):
    link = links.parse(text, jellyfin)
    return (link.app, link.kind, link.id)


@pytest.mark.parametrize(
    "text, want",
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", ("youtube", "video", "dQw4w9WgXcQ")),
        ("https://youtube.com/watch?v=dQw4w9WgXcQ&feature=share", ("youtube", "video", "dQw4w9WgXcQ")),
        ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", ("youtube", "video", "dQw4w9WgXcQ")),
        ("https://music.youtube.com/watch?v=dQw4w9WgXcQ&si=abc", ("youtube", "video", "dQw4w9WgXcQ")),
        ("https://youtu.be/dQw4w9WgXcQ?si=Ab12Cd34", ("youtube", "video", "dQw4w9WgXcQ")),
        ("youtu.be/dQw4w9WgXcQ", ("youtube", "video", "dQw4w9WgXcQ")),
        ("HTTPS://WWW.YOUTUBE.COM/watch?v=dQw4w9WgXcQ", ("youtube", "video", "dQw4w9WgXcQ")),
        ("https://www.youtube.com/shorts/aBcDeFgHiJk", ("youtube", "video", "aBcDeFgHiJk")),
        ("https://youtube.com/shorts/aBcDeFgHiJk?feature=share", ("youtube", "video", "aBcDeFgHiJk")),
        ("https://www.youtube.com/live/aBcDeFgHiJk?si=x", ("youtube", "video", "aBcDeFgHiJk")),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ?start=30", ("youtube", "video", "dQw4w9WgXcQ")),
        ("https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ", ("youtube", "video", "dQw4w9WgXcQ")),
        ("https://www.youtube.com/v/dQw4w9WgXcQ", ("youtube", "video", "dQw4w9WgXcQ")),
        (
            "https://www.youtube.com/playlist?list=PLx0sYbCqOb8TBPRdmBHs5Iftvv9TPboYG",
            ("youtube", "playlist", "PLx0sYbCqOb8TBPRdmBHs5Iftvv9TPboYG"),
        ),
        ("https://www.youtube.com/embed/videoseries?list=PLabc123", ("youtube", "playlist", "PLabc123")),
        ("https://www.youtube.com/channel/UCuAXFkgsw1L7xaCfnd5JJOw", ("youtube", "channel", "UCuAXFkgsw1L7xaCfnd5JJOw")),
        ("https://www.youtube.com/@veritasium", ("youtube", "handle", "@veritasium")),
        ("https://www.youtube.com/@veritasium/videos", ("youtube", "handle", "@veritasium")),
        ("https://www.youtube.com/c/SomeName", ("youtube", "handle", "c/SomeName")),
        ("https://www.youtube.com/user/someone", ("youtube", "handle", "user/someone")),
        ("https://www.youtube.com/results?search_query=lofi+beats", ("youtube", "search", "lofi beats")),
        ("https://www.youtube.com/", ("youtube", "home", "")),
        ("https://www.youtube.com/feed/subscriptions", ("youtube", "home", "")),
    ],
)
def test_youtube_links(text, want):
    assert where(text) == want


@pytest.mark.parametrize(
    "text, start",
    [
        ("https://youtu.be/dQw4w9WgXcQ?t=42", 42),
        ("https://youtu.be/dQw4w9WgXcQ?si=abc&t=42", 42),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=1h2m3s", 3723),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=90s", 90),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=2m", 120),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ#t=1m30s", 90),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ?start=75", 75),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=nonsense", 0),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", 0),
    ],
)
def test_youtube_timestamps(text, start):
    assert links.parse(text).start == start


def test_a_video_in_a_playlist_keeps_both():
    link = links.parse("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLabc123&index=4")
    assert (link.kind, link.id, link.playlist) == ("video", "dQw4w9WgXcQ", "PLabc123")


@pytest.mark.parametrize(
    "text, want",
    [
        ("https://www.twitch.tv/SomeStreamer", ("twitch", "live", "somestreamer")),
        ("https://m.twitch.tv/some_streamer?sr=a", ("twitch", "live", "some_streamer")),
        ("twitch.tv/somestreamer", ("twitch", "live", "somestreamer")),
        ("https://www.twitch.tv/somestreamer/videos?filter=archives", ("twitch", "channel", "somestreamer")),
        ("https://www.twitch.tv/somestreamer/about", ("twitch", "channel", "somestreamer")),
        ("https://www.twitch.tv/videos/2245678901", ("twitch", "vod", "2245678901")),
        ("https://www.twitch.tv/videos/2245678901?t=1h2m3s", ("twitch", "vod", "2245678901")),
        ("https://m.twitch.tv/videos/2245678901", ("twitch", "vod", "2245678901")),
        ("https://www.twitch.tv/somestreamer/v/123456", ("twitch", "vod", "123456")),
        ("https://clips.twitch.tv/FunnyCleverClipSlug-AbC123_xYz", ("twitch", "clip", "FunnyCleverClipSlug-AbC123_xYz")),
        ("https://clips.twitch.tv/embed?clip=FunnyClip-AbC&parent=example.com", ("twitch", "clip", "FunnyClip-AbC")),
        ("https://www.twitch.tv/somestreamer/clip/FunnyClip-AbC?filter=clips", ("twitch", "clip", "FunnyClip-AbC")),
        ("https://player.twitch.tv/?channel=SomeStreamer&parent=example.com", ("twitch", "live", "somestreamer")),
        ("https://player.twitch.tv/?video=v2245678901&parent=example.com", ("twitch", "vod", "2245678901")),
        ("https://www.twitch.tv/", ("twitch", "home", "")),
        ("https://www.twitch.tv/directory/category/chess", ("twitch", "home", "")),
    ],
)
def test_twitch_links(text, want):
    assert where(text) == want


@pytest.mark.parametrize(
    "text, want",
    [
        ("https://nebula.tv/videos/jetlag-we-played-tag-across-japan", ("nebula", "video", "jetlag-we-played-tag-across-japan")),
        ("https://nebula.tv/videos/jetlag-something?ref=share", ("nebula", "video", "jetlag-something")),
        ("https://nebula.tv/jetlag", ("nebula", "series", "jetlag")),
        ("https://www.nebula.tv/real-engineering/", ("nebula", "series", "real-engineering")),
        ("https://nebula.app/videos/some-video", ("nebula", "video", "some-video")),
        ("https://nebula.tv/", ("nebula", "home", "")),
        ("https://nebula.tv/explore", ("nebula", "home", "")),
        ("https://www.dropout.tv/dimension-20", ("dropout", "series", "dimension-20")),
        ("https://www.dropout.tv/game-changer/season:6", ("dropout", "series", "game-changer")),
        ("https://www.dropout.tv/game-changer/season:6/videos/sam-says-6", ("dropout", "video", "sam-says-6")),
        ("https://watch.dropout.tv/videos/some-special", ("dropout", "video", "some-special")),
        ("https://dropout.tv/", ("dropout", "home", "")),
        ("https://www.dropout.tv/browse", ("dropout", "home", "")),
        ("https://www.2ndtry.tv/some-show/season:1/videos/episode-one", ("2ndtry", "video", "episode-one")),
    ],
)
def test_streaming_app_links(text, want):
    assert where(text) == want


@pytest.mark.parametrize(
    "text, want",
    [
        (f"{JF}/web/#/details?id={ITEM}&serverId=abc", ("jellyfin", "item", ITEM)),
        (f"{JF}/web/index.html#!/details?id={ITEM}", ("jellyfin", "item", ITEM)),
        (f"{JF}/web/index.html#!/itemdetails.html?id={ITEM}", ("jellyfin", "item", ITEM)),
        (f"{JF}/web/#/details?id=01234567-89ab-cdef-0123-456789abcdef", ("jellyfin", "item", ITEM)),
        (f"{JF}/web/#/details?id={ITEM.upper()}", ("jellyfin", "item", ITEM)),
        # the phone knows the server by another name: the address names its server, so it's Jellyfin's
        (f"https://media.example.org/web/#/details?id={ITEM}&serverId=f00", ("jellyfin", "item", ITEM)),
        (f"{JF}/web/#/home.html", ("jellyfin", "home", "")),
        (f"{JF}/web/#/details?id=nothex", ("jellyfin", "home", "")),
    ],
)
def test_jellyfin_links(text, want):
    assert where(text) == want


def test_jellyfin_links_need_the_server_set():
    assert where(f"{JF}/web/#/details?id={ITEM}&serverId=abc", jellyfin="")[0] == "web"
    # another server's page that doesn't say it's one: just a web page
    assert where(f"http://other.example:8096/web/#/details?id={ITEM}")[0] == "web"
    # the same host on another port isn't the server
    assert where(f"http://jellyfin.example:9000/web/#/details?id={ITEM}")[0] == "web"
    assert where(f"https://jellyfin.example/web/#/details?id={ITEM}", jellyfin="jellyfin.example:443") == ("jellyfin", "item", ITEM)


@pytest.mark.parametrize(
    "text, url",
    [
        ("https://en.wikipedia.org/wiki/Television", "https://en.wikipedia.org/wiki/Television"),
        ("Look at this https://example.com/a?b=c#d, it's great!", "https://example.com/a?b=c#d"),
        ("(https://example.com/page)", "https://example.com/page"),
        ("https://en.wikipedia.org/wiki/Foo_(bar)", "https://en.wikipedia.org/wiki/Foo_(bar)"),
        ("“https://example.com/q”", "https://example.com/q"),
        ("  example.com/path  ", "https://example.com/path"),
        ("https://Example.COM./x", "https://example.com/x"),
        ("https://example.com", "https://example.com/"),
        ("http://192.168.1.20:8123/lovelace/0", "http://192.168.1.20:8123/lovelace/0"),
        ("https://example.com/café?q=über", "https://example.com/caf%C3%A9?q=%C3%BCber"),
        ("https://bücher.example/", "https://xn--bcher-kva.example/"),
        ("https://example.com/a%20b", "https://example.com/a%20b"),
        ("https://[2001:db8::1]:8080/x", "https://[2001:db8::1]:8080/x"),
    ],
)
def test_other_links_open_as_web_pages_tidied(text, url):
    link = links.parse(text)
    assert (link.app, link.kind, link.url) == ("web", "page", url)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "not a link",
        "javascript:alert(1)",
        "file:///etc/passwd",
        "ftp://example.com/x",
        "data:text/html,<script>alert(1)</script>",
        "chrome://settings",
        "https://",
        "https://user:pass@example.com/",
        "https://user@example.com/",
        "https://example.com:99999/",
        "https://example.com/\x00",
        "https://example.com/a\x1b[31m",
        "https://" + "a" * 5000 + ".com",
        "https://youtu.be/",
        "https://www.youtube.com/watch?v=short",
        "https://www.youtube.com/watch",
        "https://www.youtube.com/shorts/",
        "https://www.twitch.tv/videos/notanumber",
        "https://www.twitch.tv/not-a-login!",
        "https://clips.twitch.tv/",
        "https://player.twitch.tv/?parent=example.com",
        "https://nebula.tv/videos/%3Cscript%3E",
        # the box itself: the TV apps' DevTools ports are on it
        "http://localhost:9222/json",
        "http://127.0.0.1:9222/json",
        "http://127.1:9222/json",
        "http://2130706433:9222/json",
        "http://0x7f000001/",
        "http://[::1]:9222/",
        "http://[::ffff:127.0.0.1]/",
        "http://0.0.0.0:8791/",
        "http://169.254.169.254/latest/meta-data/",
        "http://tv.localhost/",
    ],
)
def test_bad_input_is_refused_with_a_reason(text):
    with pytest.raises(BadLink) as err:
        links.parse(text, JF)
    assert str(err.value)


def test_not_text_is_refused():
    for bad in (None, 42, ["https://example.com"], {"url": "x"}):
        with pytest.raises(BadLink):
            links.normalise(bad)


@pytest.mark.parametrize(
    "t, s", [("90", 90), ("90s", 90), ("1m30s", 90), ("1h", 3600), ("1:30", 90), ("1:02:03", 3723), ("", 0), ("x", 0), ("-5", 0)]
)
def test_timestamps(t, s):
    assert links.seconds(t) == s


# ------------------------------------------------------------------ opening


@pytest.fixture
def tv(monkeypatch):
    """The TV's apps, faked: what was opened where."""
    from couchbox import appctl
    from couchbox.voice import cdp, streaming, tools, ytnative

    got = {"yt": [], "ytn": [], "open": [], "calls": [], "raised": [], "jf": []}
    monkeypatch.setattr(ytnative, "show", lambda target, raise_app=None, wait=25: got["ytn"].append(target) or True)
    monkeypatch.setattr(tools, "youtube_page", lambda: {"webSocketDebuggerUrl": "ws://x"})
    monkeypatch.setattr(cdp, "call", lambda page, js, cmd, wait, timeout=20: got["yt"].append(cmd) or {})
    monkeypatch.setattr(tools, "yt_title", lambda vid: f"“Video {vid}” by Someone")
    monkeypatch.setattr(tools, "raise_window", lambda *a: got["raised"].append(a))
    monkeypatch.setattr(tools, "open_app", lambda name, wait=True: got["open"].append(("app", name)) or f"Opened {name}.")
    monkeypatch.setattr(streaming, "ensure", lambda site, start: None)
    answers = {}

    def call(site, fn, **args):
        got["calls"].append((site, fn, args))
        a = answers.get((site, fn), {})
        if isinstance(a, Exception):
            raise a
        return a

    monkeypatch.setattr(streaming, "call", call)
    monkeypatch.setattr(appctl, "call", lambda site, req, timeout=30: got["open"].append((site, req["target"])) or {"ok": True})
    monkeypatch.setattr(
        tools,
        "jellyfin",
        lambda action, query=None, id=None: got["jf"].append((action, id))
        or f"playing episode {id} | Show S1E2 Pilot (2020) · resume at 12 min",
    )
    got["answers"] = answers
    return got


def test_youtube_video_plays_from_the_timestamp(tv):
    res = links.open_link("Watch this! https://youtu.be/dQw4w9WgXcQ?t=1m5s&list=PLabc123")
    assert res.ok and res.app == "youtube"
    assert tv["ytn"] == ["video:dQw4w9WgXcQ@65"] and tv["yt"] == []
    assert res.message == "Playing on the TV: “Video dQw4w9WgXcQ” by Someone, from 1:05"


def test_vacuumtube_plays_it_in_its_playlist(tv, box):
    from couchbox import settings

    settings.update({"media.youtube.client": "vacuumtube"})
    (box / "var/lib/flatpak/app/rocks.shy.VacuumTube").mkdir(parents=True)
    res = links.open_link("Watch this! https://youtu.be/dQw4w9WgXcQ?t=1m5s&list=PLabc123")
    assert res.ok and tv["ytn"] == []
    assert tv["yt"] == [{"watchEndpoint": {"videoId": "dQw4w9WgXcQ", "startTimeSeconds": 65, "playlistId": "PLabc123"}}]


def test_youtube_pages(tv, monkeypatch):
    links.open_link("https://www.youtube.com/playlist?list=PLabc123")
    links.open_link("https://www.youtube.com/channel/UCuAXFkgsw1L7xaCfnd5JJOw")
    links.open_link("https://www.youtube.com/results?search_query=lofi+beats")
    monkeypatch.setattr(links, "youtube_channel_id", lambda path: "UCuAXFkgsw1L7xaCfnd5JJOw" if path == "@known" else "")
    links.open_link("https://www.youtube.com/@known")
    assert links.open_link("https://www.youtube.com/@unknown").message == "Searched YouTube on the TV for @unknown."
    assert tv["ytn"] == [
        "playlist:PLabc123",
        "channel:UCuAXFkgsw1L7xaCfnd5JJOw",
        "search:lofi beats",
        "channel:UCuAXFkgsw1L7xaCfnd5JJOw",
        "search:@unknown",
    ]


def test_hidden_apps_dont_open_links(tv):
    from couchbox import settings

    settings.update({"home.hidden": ["youtube"]})
    res = links.open_link("https://youtu.be/dQw4w9WgXcQ")
    assert not res.ok and "home screen" in res.message and tv["yt"] == tv["ytn"] == []


def test_twitch_live_or_the_channel_page(tv):
    tv["answers"][("twitch", "streamInfo")] = {"live": True, "title": "Speedruns"}
    res = links.open_link("https://www.twitch.tv/SomeStreamer")
    assert res.message == "Playing on the TV: somestreamer, live: Speedruns"
    tv["answers"][("twitch", "streamInfo")] = {"live": False}
    res = links.open_link("https://www.twitch.tv/other")
    assert res.ok and "isn't live" in res.message
    links.open_link("https://www.twitch.tv/videos/2245678901")
    links.open_link("https://clips.twitch.tv/FunnyClip-AbC")
    assert [t for s, t in tv["open"] if s == "twitch"] == [
        "play:live:somestreamer",
        "series:other",
        "play:vod:2245678901",
        "play:clip:FunnyClip-AbC",
    ]


def test_nebula_checks_the_slug_then_plays_it(tv):
    tv["answers"][("nebula", "video")] = {"title": "We Played Tag"}
    assert links.open_link("https://nebula.tv/videos/jetlag-tag").message == "Playing on the TV: We Played Tag"
    tv["answers"][("nebula", "collection")] = RuntimeError("404")
    res = links.open_link("https://nebula.tv/no-such-channel")
    assert res.ok and "searched" in res.message
    assert [t for s, t in tv["open"] if s == "nebula"] == ["play:jetlag-tag", "search:no such channel"]


def test_dropout_finds_ids_by_slug(tv):
    tv["answers"][("dropout", "search")] = {
        "items": [
            {"kind": "video", "id": 111, "slug": "sam-says-5", "title": "Sam Says 5"},
            {"kind": "video", "id": 222, "slug": "sam-says-6", "title": "Sam Says 6"},
        ]
    }
    tv["answers"][("dropout", "allSeries")] = {"items": [{"kind": "series", "id": 9, "slug": "game-changer", "title": "Game Changer"}]}
    assert links.open_link("https://www.dropout.tv/game-changer/season:6/videos/sam-says-6").message == "Playing on the TV: Sam Says 6"
    assert links.open_link("https://www.dropout.tv/game-changer").message == "Game Changer is on the TV."
    res = links.open_link("https://www.dropout.tv/videos/unknown-thing")
    assert res.ok and "searched" in res.message
    assert [t for s, t in tv["open"] if s == "dropout"] == ["play:222", "series:9", "search:unknown thing"]


def test_jellyfin_items_play(tv):
    from couchbox import settings

    settings.update({"media.jellyfin.url": JF})
    res = links.open_link(f"{JF}/web/#/details?id={ITEM}&serverId=abc")
    assert res.ok and res.message == "Playing on the TV: Show S1E2 Pilot (2020)" and tv["jf"] == [("play", ITEM)]


def test_jellyfin_errors_reach_the_phone(tv, monkeypatch):
    from couchbox import settings
    from couchbox.voice import tools

    settings.update({"media.jellyfin.url": JF})
    monkeypatch.setattr(tools, "jellyfin", lambda *a, **k: "Jellyfin: the TV's Jellyfin session isn't connected")
    res = links.open_link(f"{JF}/web/#/details?id={ITEM}")
    assert not res.ok and "isn't connected" in res.message


def test_other_pages_open_in_search(tv):
    res = links.open_link("https://en.wikipedia.org/wiki/Television")
    assert res.ok and res.message == "Opened on the TV: en.wikipedia.org"
    assert ("search", "url:https://en.wikipedia.org/wiki/Television") in tv["open"]


def test_bad_links_say_why(tv):
    res = links.open_link("javascript:alert(1)")
    assert not res.ok and res.app == "" and "link" in res.message
    assert tv["open"] == [] and tv["yt"] == []


def test_app_errors_are_reported(tv, monkeypatch):
    from couchbox.voice import streaming

    def boom(site, fn, **args):
        raise RuntimeError("Sign in to Twitch first (open it on the TV).")

    monkeypatch.setattr(streaming, "call", boom)
    res = links.open_link("https://www.twitch.tv/somestreamer")
    assert not res.ok and res.app == "twitch" and "Sign in to Twitch" in res.message


def test_voice_open_uses_the_same_opener(tv):
    from couchbox.voice import tools

    assert tools.search_tool("open", "https://youtu.be/dQw4w9WgXcQ").startswith("Playing on the TV")
    assert tools.search_tool("open", "https://en.wikipedia.org/wiki/TV") == "Opening https://en.wikipedia.org/wiki/TV."


def test_link_is_a_value():
    assert Link("web", "page", url="https://x/") == Link("web", "page", url="https://x/")
