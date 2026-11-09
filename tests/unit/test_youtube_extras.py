"""The YouTube app's extras: SponsorBlock's segments and DeArrow's titles picked out of their
privacy answers (every video with the id's hash prefix), the settings file, and Hide Shorts.
Made-up answers in the services' shapes; no network."""

import hashlib

import pytest

from couchbox.services import ytextras as X


def test_the_hash_prefix_is_all_they_are_told():
    assert X.prefix("vid00000001") == hashlib.sha256(b"vid00000001").hexdigest()[:4]


def test_segments_for_this_video_only_in_order():
    data = [
        {"videoID": "other000001", "segments": [{"category": "sponsor", "segment": [1, 2], "actionType": "skip"}]},
        {
            "videoID": "vid00000001",
            "segments": [
                {"category": "selfpromo", "segment": [300.5, 320], "actionType": "skip"},
                {"category": "sponsor", "segment": [60, 120], "actionType": "skip"},
                {"category": "nonsense", "segment": [1, 2]},
                {"category": "intro", "segment": [5, 5]},
            ],
        },
    ]
    segs = X.parse_segments(data, "vid00000001")
    assert [(s["category"], s["start"], s["end"]) for s in segs] == [("sponsor", 60.0, 120.0), ("selfpromo", 300.5, 320.0)]
    assert segs[0]["label"] == "Sponsor"
    assert X.parse_segments({"error": 1}, "vid00000001") == []


def test_dearrow_picks_a_new_title_and_a_frame():
    data = {
        "vid00000001": {
            "titles": [
                {"title": "YOU WON'T BELIEVE", "original": True, "votes": 9},
                {"title": "Bad one", "original": False, "votes": -2, "locked": False},
                {"title": "> How a bridge of paper holds a car", "original": False, "votes": 3},
            ],
            "thumbnails": [{"original": True, "votes": 1}, {"timestamp": 42.5, "original": False, "votes": 2}],
        }
    }
    b = X.parse_branding(data, "vid00000001")
    assert b["title"] == "How a bridge of paper holds a car"
    assert b["thumb"].endswith("videoID=vid00000001&time=42.5")
    assert X.parse_branding(data, "other000001") == {}
    assert X.parse_branding({"vid00000001": {"titles": [{"title": "Same", "original": True}]}}, "vid00000001") == {}


def test_settings_default_like_vacuumtube_and_keep_changes(tmp_path):
    s = X.Settings(str(tmp_path))
    st = s.get()
    assert st["sponsorblock"] and st["skip"]["sponsor"] and not st["skip"]["selfpromo"] and st["h264"] and not st["dearrow"]
    st = s.set("skip.selfpromo", True)
    st = s.set("hide_shorts", True)
    again = X.Settings(str(tmp_path)).get()
    assert again["skip"]["selfpromo"] and again["hide_shorts"] and again["skip"]["sponsor"]
    for bad in ("skip.nonsense", "nonsense", "skip"):
        try:
            s.set(bad, True)
        except ValueError:
            continue
        raise AssertionError(bad)


def test_hide_shorts():
    page = {
        "shelves": [
            {"title": "Shorts", "items": [{"type": "short", "id": "s1"}]},
            {"title": "Mixed", "items": [{"type": "video", "id": "v1"}, {"type": "short", "id": "s2"}]},
            {"title": "", "items": [], "refresh": {"title": "Refresh", "token": "t"}},  # Home's Refresh row stays
        ],
        "more": "",
    }
    out = X.hide_shorts(page)
    assert [s["title"] for s in out["shelves"]] == ["Mixed", ""] and [i["id"] for i in out["shelves"][0]["items"]] == ["v1"]
    assert X.hide_shorts({"items": [{"type": "short"}, {"type": "video"}]}) == {"items": [{"type": "video"}]}


def test_captions_always_and_frame_rate_matching_settings(tmp_path):
    s = X.Settings(str(tmp_path))
    assert s.get()["captions_always"] is True and s.get()["match_rate"] == "off"
    assert s.set("captions_always", False)["captions_always"] is False
    assert s.set("match_rate", "always")["match_rate"] == "always"
    with pytest.raises(ValueError):
        s.set("match_rate", "sometimes")
