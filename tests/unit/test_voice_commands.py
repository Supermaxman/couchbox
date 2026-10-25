import pytest

from couchbox.voice import commands


@pytest.mark.parametrize(
    "text,want",
    [
        ("Pause.", ("pause", "")),
        ("stop the video", ("pause", "")),
        ("Keep playing", ("play", "")),
        ("go home", ("key", "home")),
        ("Back!", ("key", "back")),
        ("open YouTube", ("open", "youtube")),
        ("launch the twitch app", ("open", "twitch")),
        ("turn it up", ("tv", "volume_up")),
        ("quieter", ("tv", "volume_down")),
        ("turn off the TV", ("tv", "off")),
        ("search for cat videos", ("search", "cat videos")),
        ("youtube lofi beats", ("search", "lofi beats")),
        ("what's the weather like", None),
        ("", None),
    ],
)
def test_parse(text, want):
    assert commands.parse(text) == want


@pytest.mark.parametrize(
    "spoken,want",
    [
        ("you tube", "YouTube"),
        ("second try", "2nd Try"),
        ("nebula", "Nebula"),
        ("netflix", None),
    ],
)
def test_match_app(spoken, want):
    assert commands.match_app(spoken, ["YouTube", "2nd Try", "Nebula", "Twitch"]) == want
