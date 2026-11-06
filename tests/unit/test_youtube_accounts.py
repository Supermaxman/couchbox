"""The YouTube app signed in: the device-code sign-in (and that a code survives leaving the page or
restarting the app), accounts and their brand channels as profiles, tokens kept in mode-600 files
and renewed, InnerTube calls as a profile, the signed-in pages (Subscriptions, Library), likes,
subscriptions, saving, and history reports. Made-up responses in YouTube's shapes."""

import json
import os
import time

import pytest

from couchbox.services import youtube as Y
from couchbox.services import ytauth as A


class Resp:
    def __init__(self, data, status=200):
        self.data, self.status_code = data, status
        self.headers = {"content-type": "application/json"}
        self.text = json.dumps(data)

    def json(self):
        return self.data


class FakeSession:
    """Answers POSTs from a {url fragment: [responses...]} table (the last one repeats)."""

    def __init__(self, answers=None):
        self.answers = answers or {}
        self.posts, self.gets = [], []
        self.headers = {}

    def post(self, url, json=None, headers=None, timeout=None):
        self.posts.append((url, json, headers or {}))
        for frag, rs in self.answers.items():
            if frag in url:
                r = rs[0] if len(rs) == 1 else rs.pop(0)
                return r if isinstance(r, Resp) else Resp(r)
        return Resp({})

    def get(self, url, params=None, headers=None, timeout=None):
        self.gets.append((url, params or {}, headers or {}))
        return Resp({})


DEVICE = {
    "device_code": "dev-secret",
    "user_code": "ABC-DEF-GHI",
    "expires_in": 1800,
    "interval": 5,
    "verification_url": "https://www.google.com/device",
}
TOKENS = {"access_token": "acc-1", "refresh_token": "ref-1", "expires_in": 3600}
CHANNELS = [
    {"name": "Robin Vale", "handle": "@robinvale", "photo": "", "email": "robin@example.com", "pageId": "", "main": True},
    {"name": "Juniper Hollow", "handle": "@juniper", "photo": "", "email": "", "pageId": "page-9", "main": False},
]


def mode(path):
    return os.stat(path).st_mode & 0o777


def auth(tmp_path, answers):
    a = A.Auth(str(tmp_path), session=FakeSession(answers))
    a.channels_for = lambda token: [dict(c) for c in CHANNELS]
    return a


# ------------------------------------------------------------------ signing in
def test_a_code_is_shown_kept_and_waited_for(tmp_path):
    a = auth(tmp_path, {"device/code": [DEVICE], "oauth2/token": [{"error": "authorization_pending"}]})
    a.resume = lambda: None  # no thread here: the checks are made by hand
    c = a.start()
    assert c["state"] == "waiting" and c["code"] == "ABC-DEF-GHI" and c["url"] == "youtube.com/activate"
    assert c["full"] == "https://www.google.com/device?user_code=ABC-DEF-GHI"
    assert mode(a.pending_file) == 0o600 and mode(a.adir) == 0o700
    url, body, _ = a.s.posts[0]
    assert body["client_id"] == A.CLIENT_ID and body["device_id"] == a.device_id()
    # leaving the page (or a new start of the app) changes nothing: the same code is still waited for
    b = auth(tmp_path, {})
    assert b.code()["code"] == "ABC-DEF-GHI"
    assert a.exchange(json.load(open(a.pending_file))) == {"state": "waiting"}


def test_the_code_used_later_signs_in_in_the_background(tmp_path):
    a = auth(tmp_path, {"device/code": [DEVICE], "oauth2/token": [{"error": "authorization_pending"}, {"error": "slow_down"}, TOKENS]})
    events = []
    a.on_event = lambda name, data: events.append((name, data))
    a.resume = lambda: None
    a.start()
    p = json.load(open(a.pending_file))
    p["interval"] = 0.01
    A._write(a.pending_file, p)
    a._wait()  # what the Waiter thread runs: three checks, the last one signs in
    assert events and events[0][0] == "signedIn" and events[0][1]["name"] == "Robin Vale"
    assert not os.path.exists(a.pending_file)
    acct = a.accounts()[0]
    assert acct["refresh_token"] == "ref-1" and mode(a._path(acct["id"])) == 0o600
    assert "ref-1" not in acct["id"] and a.code()["state"] == "ok"


def test_an_expired_or_denied_code(tmp_path):
    a = auth(tmp_path, {"oauth2/token": [{"error": "access_denied"}]})
    assert a.exchange({"device_code": "x"}) == {"state": "denied"}
    A._write(a.pending_file, {"device_code": "x", "user_code": "Q", "expires_at": time.time() - 1, "interval": 5})
    assert a.code()["state"] == "expired"
    events = []
    a.on_event = lambda name, data: events.append(name)
    a._wait()
    assert events == ["signInExpired"] and not os.path.exists(a.pending_file)


# ------------------------------------------------------------------ accounts and tokens
def test_profiles_are_every_channel_of_every_account(tmp_path):
    a = auth(tmp_path, {})
    acct = a.add(TOKENS)
    profiles = a.profiles()
    assert [(p["name"], p["pageId"]) for p in profiles] == [("Robin Vale", ""), ("Juniper Hollow", "page-9")]
    assert profiles[0]["id"] == f"{acct['id']}:" and profiles[1]["id"] == f"{acct['id']}:page-9"
    a.set_premium(acct["id"], True)
    assert all(p["premium"] for p in a.profiles())
    a.remove(acct["id"])
    assert a.profiles() == []


def test_tokens_are_renewed_and_a_revoked_one_signs_out(tmp_path):
    a = auth(tmp_path, {"oauth2/token": [{"access_token": "acc-2", "expires_in": 3600}, {"error": "invalid_grant"}]})
    acct = a.add(TOKENS)
    assert a.token(acct["id"]) == "acc-1"  # still good
    a.expire(acct["id"])
    assert a.token(acct["id"]) == "acc-2"
    _, body, _ = a.s.posts[-1]
    assert body["grant_type"] == "refresh_token" and body["refresh_token"] == "ref-1"
    a.expire(acct["id"])
    with pytest.raises(A.SignedOut):
        a.token(acct["id"])


ACCOUNTS_LIST = {
    "contents": [
        {
            "accountSectionListRenderer": {
                "contents": [
                    {
                        "accountItemSectionRenderer": {
                            "contents": [
                                {
                                    "accountItem": {
                                        "accountName": {"simpleText": "Robin Vale"},
                                        "accountPhoto": {"thumbnails": [{"url": "https://yt3.example/r=s88-c-k", "width": 88}]},
                                        "channelHandle": {"simpleText": "@robinvale"},
                                        "accountByline": {"simpleText": "robin@example.com"},
                                        "serviceEndpoint": {
                                            "selectActiveIdentityEndpoint": {"supportedTokens": [{"accountStateToken": {}}]}
                                        },
                                    }
                                },
                                {
                                    "accountItem": {
                                        "accountName": {"simpleText": "Juniper Hollow"},
                                        "channelHandle": {"simpleText": "@juniper"},
                                        "serviceEndpoint": {
                                            "selectActiveIdentityEndpoint": {"supportedTokens": [{"pageIdToken": {"pageId": "page-9"}}]}
                                        },
                                    }
                                },
                                {"accountItem": {"accountName": {"simpleText": "Gone"}, "isDisabled": True}},
                            ]
                        }
                    }
                ]
            }
        }
    ]
}


def test_accounts_list():
    chans = Y.parse_accounts(ACCOUNTS_LIST)
    assert [(c["name"], c["handle"], c["pageId"], c["main"]) for c in chans] == [
        ("Robin Vale", "@robinvale", "", True),
        ("Juniper Hollow", "@juniper", "page-9", False),
    ]
    assert chans[0]["email"] == "robin@example.com" and chans[0]["photo"] == "https://yt3.example/r=s352-c-k"


# ------------------------------------------------------------------ InnerTube as a profile
def client(tmp_path, answers):
    y = Y.YouTube(data_dir=str(tmp_path))
    y.s = FakeSession(answers)
    y.auth.s = FakeSession({"oauth2/token": [{"access_token": "acc-new", "expires_in": 3600}]})
    y.auth.channels_for = lambda token: [dict(c) for c in CHANNELS]
    acct = y.auth.add(TOKENS)
    return y, acct


def test_calls_as_a_brand_account_carry_its_token_and_page(tmp_path):
    y, acct = client(tmp_path, {"browse": [{"contents": {}, "topbar": {"iconType": "YOUTUBE_PREMIUM_LOGO"}}]})
    y.use(f"{acct['id']}:page-9")
    y.browse("FEtopics")
    _, body, headers = y.s.posts[-1]
    assert headers["Authorization"] == "Bearer acc-1"
    assert body["context"]["user"] == {"onBehalfOfUser": "page-9"}
    assert y.auth.profiles()[1]["premium"]  # YouTube's Premium logo was on the page
    y.use("guest")
    y.browse("FEtopics_music")
    _, body, headers = y.s.posts[-1]
    assert "Authorization" not in headers and "user" not in body["context"]


def test_a_refused_token_is_renewed_once(tmp_path):
    y, acct = client(tmp_path, {"browse": [Resp({}, 401), {"contents": {}}]})
    y.use(f"{acct['id']}:")
    y.browse("FEhistory")
    assert [p[2]["Authorization"] for p in y.s.posts] == ["Bearer acc-1", "Bearer acc-new"]


def test_signed_in_actions(tmp_path):
    y, acct = client(tmp_path, {"get_add_to_playlist": [SAVE]})
    with pytest.raises(Y.YouTubeError):
        y.like("vid00000001", "like")  # a guest
    y.use(f"{acct['id']}:")
    y.like("vid00000001", "like")
    y.like("vid00000001", "none")
    y.subscribe("UCchannel0000000000000001", True)
    y.notify("params-all", "all")
    assert y.save_options("vid00000001")["playlists"][0] == {"id": "WL", "title": "Watch later", "saved": True}
    y.save("vid00000001", "PLabc", False)
    eps = [(u.split("/v1/")[1].split("?")[0], b) for u, b, _ in y.s.posts]
    assert eps[0] == ("like/like", eps[0][1]) and eps[0][1]["target"] == {"videoId": "vid00000001"}
    assert eps[1][0] == "like/removelike"
    assert eps[2][0] == "subscription/subscribe" and eps[2][1]["channelIds"] == ["UCchannel0000000000000001"]
    assert eps[3] == ("notification/modify_channel_preference", eps[3][1]) and eps[3][1]["params"] == "params-all"
    assert eps[5][0] == "browse/edit_playlist"
    assert eps[5][1]["actions"] == [{"action": "ACTION_REMOVE_VIDEO_BY_VIDEO_ID", "removedVideoId": "vid00000001"}]


SAVE = {
    "contents": [
        {
            "addToPlaylistRenderer": {
                "playlists": [
                    {
                        "playlistAddToOptionRenderer": {
                            "playlistId": "PLabc",
                            "title": {"simpleText": "Road trip"},
                            "containsSelectedVideos": "NONE",
                        }
                    },
                    {
                        "playlistAddToOptionRenderer": {
                            "playlistId": "WL",
                            "title": {"simpleText": "Watch later"},
                            "containsSelectedVideos": "ALL",
                        }
                    },
                ]
            }
        }
    ]
}


def test_history_reports(tmp_path):
    player = {
        "playbackTracking": {
            "videostatsPlaybackUrl": {"baseUrl": "https://s.youtube.com/api/stats/playback?docid=v"},
            "videostatsWatchtimeUrl": {"baseUrl": "https://s.youtube.com/api/stats/watchtime?docid=v"},
        }
    }
    y, acct = client(tmp_path, {"player": [player]})
    assert y.report("vid00000001", "cpn1", "start", 0, 100) == {"ok": False}  # a guest: nothing
    y.use(f"{acct['id']}:")
    y.report("vid00000001", "cpn1", "start", 12, 100)
    y.report("vid00000001", "cpn1", "progress", 22, 100)
    y.report("vid00000001", "cpn1", "end", 100, 100)
    urls = [(u.split("?")[0].rsplit("/", 1)[1], q) for u, q, _ in y.s.gets]
    assert [u for u, _ in urls] == ["playback", "watchtime", "watchtime"]  # into History once
    assert urls[0][1]["cpn"] == "cpn1" and urls[0][1]["ver"] == "2" and urls[0][1]["cmt"] == "12.000"
    assert (urls[1][1]["st"], urls[1][1]["et"], urls[1][1]["state"]) == ("12.000", "22.000", "playing")
    assert urls[2][1]["final"] == "1" and urls[2][1]["state"] == "paused"
    assert all(h["Authorization"] == "Bearer acc-1" for _, _, h in y.s.gets)
    assert [u.split("/v1/")[1].split("?")[0] for u, _, _ in y.s.posts] == ["player"]  # asked once


# ------------------------------------------------------------------ signed-in pages
def tab(title, browse="", thumb="", selected=False, content=None):
    t = {"title": title, "endpoint": {"browseEndpoint": {"browseId": browse}} if browse else {}}
    if thumb:
        t["thumbnail"] = {"thumbnails": [{"url": thumb, "width": 88}]}
    if selected:
        t["selected"] = True
        t["content"] = content
    return {"tabRenderer": t}


def video_tile(vid):
    return {
        "tileRenderer": {
            "metadata": {"tileMetadataRenderer": {"title": {"simpleText": f"Video {vid}"}}},
            "onSelectCommand": {"watchEndpoint": {"videoId": vid}},
            "contentType": "TILE_CONTENT_TYPE_VIDEO",
        }
    }


def test_subscriptions_channels_and_feed():
    grid = {"tvSurfaceContentRenderer": {"content": {"gridRenderer": {"items": [video_tile("v1"), video_tile("v2")]}}}}
    resp = {
        "contents": {
            "tvBrowseRenderer": {
                "content": {
                    "tvSecondaryNavRenderer": {
                        "sections": [
                            {
                                "tvSecondaryNavSectionRenderer": {
                                    "tabs": [
                                        tab("All", selected=True, content=grid),
                                        tab("Orbit Lab", "UCorbit", "https://yt3.example/o=s88-c"),
                                    ]
                                }
                            },
                            {
                                "tvSecondaryNavSectionRenderer": {
                                    "title": {"simpleText": "A-Z"},
                                    "tabs": [tab("Kettle & Crumb", "UCkettle")],
                                }
                            },
                        ]
                    }
                }
            }
        }
    }
    s = Y.parse_subscriptions(resp)
    assert [(c["title"], c["id"], c["section"]) for c in s["channels"]] == [
        ("All", "", ""),
        ("Orbit Lab", "UCorbit", ""),
        ("Kettle & Crumb", "UCkettle", "A-Z"),
    ]
    assert s["channels"][1]["thumb"] == "https://yt3.example/o=s176-c"
    assert s["page"]["shelves"][0]["grid"] and [i["id"] for i in s["page"]["shelves"][0]["items"]] == ["v1", "v2"]


def test_an_unknown_page_shape_still_shows_its_cards():
    resp = {"contents": {"somethingNewRenderer": {"panes": [{"list": [video_tile("v3"), video_tile("v4")]}]}}}
    page = Y.parse_page(resp)
    assert [i["id"] for i in page["shelves"][0]["items"]] == ["v3", "v4"]


def test_watch_page_signed_in_parts():
    states = [
        {
            "stateId": 2,
            "state": {"buttonRenderer": {"icon": {"iconType": "NOTIFICATIONS_ACTIVE"}}},
            "inlineMenuButton": {
                "buttonRenderer": {
                    "text": {"simpleText": "All"},
                    "serviceEndpoint": {"modifyChannelNotificationPreferenceEndpoint": {"params": "p-all"}},
                }
            },
        },
        {
            "stateId": 3,
            "state": {"buttonRenderer": {"icon": {"iconType": "NOTIFICATIONS_NONE"}}},
            "inlineMenuButton": {
                "buttonRenderer": {
                    "text": {"simpleText": "Personalized"},
                    "serviceEndpoint": {"modifyChannelNotificationPreferenceEndpoint": {"params": "p-some"}},
                }
            },
        },
        {"state": {"buttonRenderer": {"text": {"simpleText": "Unsubscribe"}}}},
    ]
    resp = {
        "transportControls": {
            "transportControlsRenderer": {
                "buttons": [
                    {"button": {"likeButtonRenderer": {"likeStatus": "LIKE", "likeCount": 1234}}},
                    {
                        "button": {
                            "subscribeButtonRenderer": {
                                "subscribed": True,
                                "channelId": "UCorbit",
                                "notificationPreferenceButton": {
                                    "subscriptionNotificationToggleButtonRenderer": {"states": states, "currentStateId": 3}
                                },
                            }
                        }
                    },
                ]
            }
        },
        "currentVideoEndpoint": {"watchEndpoint": {"videoId": "v1", "startTimeSeconds": 3076}},
    }
    w = Y.parse_watch(resp)
    v = w["video"]
    assert (v["like"], v["likes"], v["subscribed"], v["notify"], v["channelId"]) == ("like", 1234, True, "personalized", "UCorbit")
    assert [(o["level"], o["params"]) for o in v["notifyOptions"]] == [("all", "p-all"), ("personalized", "p-some")]
    assert w["start"] == 3076
    flip = dict(resp, frameworkUpdates={"entityBatchUpdate": {"mutations": [{"payload": {"likeStatusEntity": {"likeStatus": "DISLIKE"}}}]}})
    assert Y.parse_watch(flip)["video"]["like"] == "dislike"


def test_tracking_and_premium():
    assert Y.tracking({"playbackTracking": {"videostatsPlaybackUrl": {"baseUrl": "a"}}}) == {"playback": "a", "watchtime": ""}
    assert Y.is_premium({"x": [{"iconType": "YOUTUBE_PREMIUM_LOGO"}]}) and not Y.is_premium({"iconType": "YOUTUBE_LOGO"})


def test_demo_profiles_and_pages():
    d = Y.Demo()
    assert d.profiles()["current"] == "demo1:" and len(d.profiles()["profiles"]) == 3
    assert d.subscriptions()["channels"][0]["title"] == "All" and d.library()["tiles"][0]["title"] == "History"
    d.like("demo0000001", "like")
    assert d.watch("demo0000001")["video"]["like"] == "like"
    d.use("")
    with pytest.raises(Y.YouTubeError):
        d.subscriptions()
    assert d.home()["nudge"]


def test_a_playlist_page_and_its_continuation():
    resp = {
        "contents": {
            "tvBrowseRenderer": {
                "content": {
                    "tvSurfaceContentRenderer": {
                        "content": {
                            "twoColumnRenderer": {
                                "leftColumn": {"entityMetadataRenderer": {"title": {"simpleText": "Watch later"}}},
                                "rightColumn": {
                                    "playlistVideoListRenderer": {
                                        "contents": [video_tile("v5"), video_tile("v6")],
                                        "continuations": [{"nextContinuationData": {"continuation": "more-wl"}}],
                                    }
                                },
                            }
                        }
                    }
                }
            }
        }
    }
    shelf = Y.parse_page(resp)["shelves"][0]
    assert (shelf["title"], [i["id"] for i in shelf["items"]], shelf["grid"], shelf["more"]) == (
        "Watch later",
        ["v5", "v6"],
        True,
        "more-wl",
    )
    more = {"continuationContents": {"playlistVideoListContinuation": {"contents": [video_tile("v7")]}}}
    assert [i["id"] for i in Y.parse_more_items(more)["items"]] == ["v7"]


def test_a_bare_account_id_is_its_own_channel(tmp_path):
    # couchbox-yt --profile ACCOUNT (the box check, playerProbe's profile): no picker, no colon needed
    y, acct = client(tmp_path, {})
    assert y.use(acct["id"])["profile"]["id"] == f"{acct['id']}:"
    assert y.auth.last_profile() == f"{acct['id']}:"
    assert y.find_profile(f"{acct['id']}:page-9")["pageId"] == "page-9"
    assert y.find_profile("nobody") is None and y.find_profile("guest") is None


def history_tile(vid, title, token):
    menu = {
        "menuRenderer": {
            "items": [
                {
                    "menuServiceItemRenderer": {
                        "text": {"runs": [{"text": "Remove from watch history"}]},
                        "serviceEndpoint": {"feedbackEndpoint": {"feedbackToken": token}},
                    }
                }
            ]
        }
    }
    return {
        "tileRenderer": {
            "contentType": "TILE_CONTENT_TYPE_VIDEO",
            "contentId": vid,
            "metadata": {"tileMetadataRenderer": {"title": {"simpleText": title}}},
            "onSelectCommand": {"watchEndpoint": {"videoId": vid}},
            "onLongPressCommand": {"showMenuCommand": {"menu": menu}},
        }
    }


def test_the_check_removes_only_todays_entries_of_its_own_videos(tmp_path):
    def shelf(title, tiles):
        return {
            "shelfRenderer": {
                "headerRenderer": {"shelfHeaderRenderer": {"title": {"simpleText": title}}},
                "content": {"horizontalListRenderer": {"items": tiles}},
            }
        }

    history = {
        "contents": {
            "sectionListRenderer": {
                "contents": [
                    shelf(
                        "Today",
                        [
                            history_tile("played00001", "Played by the check", "tok-1"),
                            history_tile("family00001", "Watched by the family", "tok-2"),
                        ],
                    ),
                    shelf("Yesterday", [history_tile("played00002", "Played yesterday", "tok-3")]),
                ]
            }
        }
    }
    y, acct = client(tmp_path, {"browse": [history], "feedback": [{"feedbackResponses": [{"isProcessed": True}]}]})
    y.use(acct["id"])
    today = y.history_today()
    assert [(e["id"], e["token"], e["label"]) for e in today] == [
        ("played00001", "tok-1", "Remove from watch history"),
        ("family00001", "tok-2", "Remove from watch history"),
    ]
    assert y.remove_from_history("tok-1")
    _, body, headers = y.s.posts[-1]
    assert body["feedbackTokens"] == ["tok-1"] and headers["Authorization"].startswith("Bearer ")
