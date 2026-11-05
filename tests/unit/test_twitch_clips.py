"""Twitch clips (links sent to the TV): the best MP4 up to 1080p, signed with the clip's
access token, as a card the player takes like a video's."""

import pytest

from couchbox.services import twitch


@pytest.fixture
def tw(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return twitch.Twitch()


def test_a_clip_plays_its_best_quality_signed(tw, monkeypatch):
    asked = []

    def gql(query, variables=None):
        asked.append(variables)
        return {
            "clip": {
                "id": "1",
                "title": "What a play",
                "durationSeconds": 28,
                "thumbnailURL": "https://img/x.jpg",
                "broadcaster": {"login": "somestreamer", "displayName": "SomeStreamer"},
                "playbackAccessToken": {"signature": "sig1", "value": '{"clip_uri":"x"}'},
                "videoQualities": [
                    {"quality": "360", "frameRate": 30, "sourceURL": "https://clips/360.mp4"},
                    {"quality": "1440", "frameRate": 60, "sourceURL": "https://clips/1440.mp4"},
                    {"quality": "1080", "frameRate": 30, "sourceURL": "https://clips/1080-30.mp4"},
                    {"quality": "1080", "frameRate": 60, "sourceURL": "https://clips/1080-60.mp4"},
                ],
            }
        }

    monkeypatch.setattr(tw, "gql", gql)
    c = tw.playback("clip:FunnyClip-AbC")
    assert asked[0]["s"] == "FunnyClip-AbC"
    assert c["url"] == "https://clips/1080-60.mp4?sig=sig1&token=%7B%22clip_uri%22%3A%22x%22%7D"
    assert (c["id"], c["title"], c["series"], c["duration"], c["start"], c["live"]) == (
        "clip:FunnyClip-AbC",
        "What a play",
        "SomeStreamer",
        28,
        0,
        False,
    )
    assert c["chat"] == "" and c["next"] is None


def test_a_gone_clip_says_so(tw, monkeypatch):
    monkeypatch.setattr(tw, "gql", lambda q, v=None: {"clip": None})
    with pytest.raises(RuntimeError, match="isn't on Twitch"):
        tw.playback("clip:gone")
