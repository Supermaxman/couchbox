"""The YouTube app's player pages: the Description panel's parts, chapters with pictures, comments,
Shorts (the sequence and a Short's details), the cards' shapes on the tabs, and captions and
qualities from yt-dlp. Made-up responses in YouTube's shapes."""

from couchbox.services import youtube as Y
from couchbox.services import ytstream as S

WATCH = {
    "engagementPanels": [
        {
            "engagementPanelSectionListRenderer": {
                "panelIdentifier": "comment-item-section",
                "header": {"engagementPanelTitleHeaderRenderer": {"contextualInfo": {"runs": [{"text": "4K"}]}}},
                "content": {
                    "sectionListRenderer": {
                        "contents": [
                            {
                                "itemSectionRenderer": {
                                    "contents": [
                                        {"continuationItemRenderer": {"continuationEndpoint": {"continuationCommand": {"token": "tok-c1"}}}}
                                    ]
                                }
                            }
                        ]
                    }
                },
            }
        },
        {
            "engagementPanelSectionListRenderer": {
                "panelIdentifier": "video-description-ep-identifier",
                "content": {
                    "structuredDescriptionContentRenderer": {
                        "items": [
                            {
                                "videoDescriptionHeaderRenderer": {
                                    "factoid": [
                                        {"factoidRenderer": {"value": {"simpleText": "46K"}, "label": {"simpleText": "Likes"}}},
                                        {"factoidRenderer": {"value": {"simpleText": "2,088,453"}, "label": {"simpleText": "Views"}}},
                                    ]
                                }
                            },
                            {"expandableVideoDescriptionBodyRenderer": {"descriptionBodyText": {"runs": [{"text": "We built it."}]}}},
                            {"expandableMetadataRenderer": {"header": {"collapsedTitle": {"simpleText": "They build a thing."}}}},
                            {
                                "videoDescriptionCommentsSectionRenderer": {
                                    "content": {
                                        "commentsEntryPointRenderer": {
                                            "authorText": {"simpleText": "@viewer"},
                                            "contentText": {"runs": [{"text": "Great one"}]},
                                            "commentCount": {"simpleText": "3.7K"},
                                        }
                                    }
                                }
                            },
                        ]
                    }
                },
            }
        },
    ],
    "frameworkUpdates": {
        "entityBatchUpdate": {
            "mutations": [
                {
                    "payload": {
                        "macroMarkersListEntity": {
                            "markersList": {
                                "markerType": "MARKER_TYPE_CHAPTERS",
                                "markers": [
                                    {
                                        "title": {"simpleText": "Intro"},
                                        "startMillis": "0",
                                        "thumbnailDetails": {"thumbnails": [{"url": "https://i.ytimg.com/a.jpg", "width": 320}]},
                                    },
                                    {"title": {"simpleText": "The answer"}, "startMillis": "119000"},
                                ],
                            }
                        }
                    }
                },
                {"payload": {"macroMarkersListEntity": {"markersList": {"markerType": "MARKER_TYPE_HEATMAP", "markers": [{}]}}}},
            ]
        }
    },
    "contents": {"singleColumnWatchNextResults": {"autoplay": {"autoplay": {"countDownSecs": 8, "sets": []}}}},
}


def test_description_panel_and_chapters():
    w = Y.parse_watch(WATCH)
    d = w["details"]
    assert d["facts"] == [{"value": "46K", "label": "Likes"}, {"value": "2,088,453", "label": "Views"}]
    assert (d["text"], d["summary"], d["comments"]) == ("We built it.", "They build a thing.", "3.7K")
    assert d["teaser"]["author"] == "@viewer" and d["teaser"]["text"] == "Great one"
    assert d["commentsToken"] == "tok-c1"
    assert w["chapters"] == [
        {"title": "Intro", "start": 0.0, "thumb": "https://i.ytimg.com/a.jpg"},
        {"title": "The answer", "start": 119.0, "thumb": ""},
    ]
    assert w["countdown"] == 8


def test_comments_page():
    resp = {
        "continuationContents": {
            "itemSectionContinuation": {
                "contents": [
                    {
                        "commentThreadRenderer": {
                            "comment": {
                                "commentRenderer": {
                                    "authorText": {"simpleText": "@maker"},
                                    "contentText": {"runs": [{"text": "Thanks "}, {"text": "all"}]},
                                    "publishedTimeText": {"simpleText": "2 days ago"},
                                    "voteCount": {"simpleText": "166"},
                                    "replyCount": 49,
                                    "pinnedCommentBadge": {},
                                }
                            }
                        }
                    },
                    {"continuationItemRenderer": {"continuationEndpoint": {"continuationCommand": {"token": "tok-c2"}}}},
                ]
            }
        }
    }
    c = Y.parse_comments(resp)
    assert c["items"][0] == {
        "id": "",
        "author": "@maker",
        "photo": "",
        "text": "Thanks all",
        "time": "2 days ago",
        "likes": "166",
        "replies": 49,
        "pinned": True,
        "vote": "",
    }
    assert c["more"] == "tok-c2"


def test_shorts_sequence_and_details():
    seq = {
        "entries": [
            {
                "command": {
                    "reelWatchEndpoint": {
                        "videoId": "short000001",
                        "thumbnail": {
                            "thumbnails": [{"url": "https://i.ytimg.com/s.jpg", "width": 360}],
                            "darkColorPalette": {"section1Color": 4141608},
                        },
                    }
                }
            },
            {"command": {"browseEndpoint": {}}},
        ],
        "continuation": "tok-s",
    }
    s = Y.parse_short_sequence(seq)
    assert s == {
        "items": [{"type": "short", "id": "short000001", "thumb": "https://i.ytimg.com/s.jpg", "color": "#3f3228"}],
        "more": "tok-s",
    }
    item = {
        "overlay": {
            "reelPlayerOverlayRenderer": {
                "reelPlayerHeaderSupportedRenderers": {
                    "reelPlayerHeaderRenderer": {
                        "reelTitleText": {"runs": [{"text": "A tiny bridge"}]},
                        "channelTitleText": {"runs": [{"text": "@orbitlab"}]},
                        "channelNavigationEndpoint": {"browseEndpoint": {"browseId": "UCorbit"}},
                    }
                },
                "subscribeButtonRenderer": {"subscribeButtonRenderer": {"subscribed": True}},
            }
        }
    }
    d = Y.parse_short(item)
    assert (d["title"], d["handle"], d["channelId"], d["subscribed"]) == ("A tiny bridge", "@orbitlab", "UCorbit", True)


def test_card_shapes():
    assert Y.tile_shape("TILE_STYLE_YTLR_SQUARE", None) == "square"
    assert Y.tile_shape("TILE_STYLE_YTLR_DEFAULT", {"thumbnails": [{"width": 279, "height": 402}]}) == "poster"
    assert Y.tile_shape("TILE_STYLE_YTLR_DEFAULT", {"thumbnails": [{"width": 640, "height": 360}]}) == "wide"
    poster = {
        "tileRenderer": {
            "style": "TILE_STYLE_YTLR_DEFAULT",
            "header": {
                "tileHeaderRenderer": {
                    "thumbnail": {"thumbnails": [{"url": "https://i.ytimg.com/p.jpg", "width": 279, "height": 402}]},
                    "thumbnailOverlays": [{"tileMetadataRenderer": {"title": {"simpleText": "A Film"}}}],
                }
            },
            "onSelectCommand": {"watchEndpoint": {"videoId": "film0000001"}},
        }
    }
    c = Y.parse_any(poster)
    assert (c["title"], c["shape"]) == ("A Film", "poster")


def test_captions_and_qualities():
    info = {
        "subtitles": {
            "de": [{"ext": "json3", "url": "x"}, {"ext": "vtt", "url": "https://c/de.vtt", "name": "German"}],
            "en": [{"ext": "vtt", "url": "https://c/en.vtt", "name": "English"}],
        },
        "automatic_captions": {
            "en": [{"ext": "vtt", "url": "https://c/en-auto.vtt", "name": "English"}],
            "fr": [{"ext": "vtt", "url": "https://c/fr.vtt"}],
        },
    }
    caps = S.captions(info)
    assert [(c["name"], c["auto"]) for c in caps] == [("English", False), ("German", False), ("English (auto-generated)", True)]
    fmts = [
        {"vcodec": "avc1.64002A", "height": 1080, "url": "a"},
        {"vcodec": "avc1.4D401F", "height": 720, "url": "b"},
        {"vcodec": "vp9", "height": 1440, "url": "c"},
        {"vcodec": "avc1", "height": 1920, "width": 1080, "url": "d"},  # a Short: "1080p"
    ]
    assert S.heights(fmts) == [1080, 720]
    assert S.heights(fmts, h264=False) == [1440, 1080, 720]


def test_ytdlp_errors_in_plain_words():
    assert S.friendly("ERROR: [youtube] abc: Sign in to confirm you’re not a bot. Use --cookies-from-browser").startswith(
        "YouTube wants this TV"
    )
    assert S.friendly("ERROR: [youtube] abc: Private video. Sign in if you've been granted access") == "This video is private."
    assert S.friendly("ERROR: [youtube] abc: Something new happened\nmore") == "abc: Something new happened"


def test_comment_threads_and_their_replies():
    thread = {
        "commentThreadRenderer": {
            "comment": {"commentRenderer": {"authorText": {"simpleText": "@a"}, "contentText": {"simpleText": "Hi"}, "replyCount": 2}},
            "replies": {
                "commentRepliesRenderer": {
                    "contents": [{"continuationItemRenderer": {"continuationEndpoint": {"continuationCommand": {"token": "tok-replies"}}}}]
                }
            },
        }
    }
    page = {
        "continuationContents": {
            "itemSectionContinuation": {
                "contents": [
                    thread,
                    {
                        "commentThreadRenderer": {
                            "comment": {
                                "commentRenderer": {"authorText": {"simpleText": "@b"}, "contentText": {"simpleText": "No replies"}}
                            }
                        }
                    },
                    {"continuationItemRenderer": {"continuationEndpoint": {"continuationCommand": {"token": "tok-page2"}}}},
                ]
            }
        }
    }
    c = Y.parse_comments(page)
    assert [x["author"] for x in c["items"]] == ["@a", "@b"]
    assert c["items"][0]["repliesToken"] == "tok-replies" and "repliesToken" not in c["items"][1]
    assert c["more"] == "tok-page2"  # the page's, not the first thread's replies
    replies = {
        "onResponseReceivedEndpoints": [
            {
                "appendContinuationItemsAction": {
                    "continuationItems": [
                        {"commentRenderer": {"authorText": {"simpleText": "@c"}, "contentText": {"simpleText": "A reply"}}},
                        {
                            "continuationItemRenderer": {
                                "button": {"buttonRenderer": {"command": {"continuationCommand": {"token": "tok-more-replies"}}}}
                            }
                        },
                    ]
                }
            }
        ]
    }
    r = Y.parse_comments(replies)
    assert [x["text"] for x in r["items"]] == ["A reply"] and r["more"] == "tok-more-replies"


def test_a_reply_shown_twice_in_a_page_lists_once():
    """A replies page can hold a reply twice (seen on the TV: one reply, listed two times)."""
    reply = {"commentRenderer": {"commentId": "Ugx1", "authorText": {"simpleText": "@m"}, "contentText": {"simpleText": "Same one"}}}
    other = {"commentRenderer": {"commentId": "Ugx2", "authorText": {"simpleText": "@m"}, "contentText": {"simpleText": "Same one"}}}
    page = {"onResponseReceivedEndpoints": [{"appendContinuationItemsAction": {"continuationItems": [reply, reply, other]}}]}
    r = Y.parse_comments(page)
    assert [x["id"] for x in r["items"]] == ["Ugx1", "Ugx2"]  # (the same words twice, but two comments: both)


def test_tv_comment_replies_come_from_its_detail_view():
    """The TV's threads carry their replies' continuation in the comment's detailViewEndpoint
    (an engagement panel), not under "replies"."""
    page = {
        "contents": [
            {
                "commentThreadRenderer": {
                    "comment": {
                        "commentRenderer": {
                            "authorText": {"simpleText": "@a"},
                            "contentText": {"simpleText": "Hi"},
                            "replyCount": 27,
                            "detailViewEndpoint": {
                                "showEngagementPanelEndpoint": {
                                    "engagementPanel": {
                                        "engagementPanelSectionListRenderer": {
                                            "content": {
                                                "sectionListRenderer": {
                                                    "contents": [
                                                        {
                                                            "itemSectionRenderer": {
                                                                "continuations": [{"nextContinuationData": {"continuation": "tok-replies"}}]
                                                            }
                                                        }
                                                    ]
                                                }
                                            }
                                        }
                                    }
                                }
                            },
                        }
                    }
                }
            }
        ]
    }
    c = Y.parse_comments(page)
    assert c["items"][0]["repliesToken"] == "tok-replies"


def _toggle(icon, on, off, after_on, after_off):
    def ep(tok, n, status):
        return {
            "performCommentActionEndpoint": {
                "action": tok,
                "clientActions": [{"updateCommentVoteAction": {"voteCount": {"simpleText": n}, "voteStatus": status}}],
            }
        }

    return {
        "toggleButtonRenderer": {
            "defaultIcon": {"iconType": icon},
            "defaultServiceEndpoint": ep(on, after_on, icon),
            "toggledServiceEndpoint": ep(off, after_off, "INDIFFERENT"),
        }
    }


def test_a_comments_own_page_has_its_buttons_then_its_replies():
    """The TV's page for one comment (its detailViewEndpoint): the comment itself (with Like and
    Dislike: perform_comment_action tokens, and the likes to show after each), YouTube's line on
    replying from the phone, then the replies as threads (each opening its own page)."""
    page = {
        "continuationContents": {
            "itemSectionContinuation": {
                "contents": [
                    {
                        "commentRenderer": {
                            "commentId": "Ug1",
                            "authorText": {"simpleText": "@a"},
                            "contentText": {"simpleText": "Hi"},
                            "voteCount": {"simpleText": "9"},
                            "voteStatus": "INDIFFERENT",
                            "replyCount": 1,
                            "actionButtons": {
                                "commentActionButtonsRenderer": {
                                    "likeButton": _toggle("LIKE", "t-like", "t-unlike", "10", "9"),
                                    "dislikeButton": _toggle("DISLIKE", "t-dis", "t-undis", "9", "9"),
                                }
                            },
                        }
                    },
                    {
                        "handoffInstructionRenderer": {
                            "text": {"runs": [{"text": "Open the YouTube mobile app to add comments and replies."}]}
                        }
                    },
                    {
                        "commentThreadRenderer": {
                            "comment": {
                                "commentRenderer": {
                                    "commentId": "Ug2",
                                    "authorText": {"simpleText": "@b"},
                                    "contentText": {"simpleText": "A reply"},
                                    "voteStatus": "LIKE",
                                    "detailViewEndpoint": {"x": {"continuations": [{"nextContinuationData": {"continuation": "tok-ug2"}}]}},
                                }
                            }
                        }
                    },
                ]
            }
        }
    }
    r = Y.parse_comments(page)
    assert r["head"]["id"] == "Ug1"
    assert r["head"]["actions"] == {
        "like": "t-like",
        "unlike": "t-unlike",
        "dislike": "t-dis",
        "undislike": "t-undis",
        "counts": {"like": "10", "unlike": "9", "dislike": "9", "undislike": "9"},
    }
    assert r["handoff"] == "Open the YouTube mobile app to add comments and replies."
    assert [(x["id"], x["vote"], x.get("open")) for x in r["items"]] == [("Ug2", "like", "tok-ug2")]


def test_every_comment_opens_its_own_page():
    """A comment without replies opens too (its page: its buttons)."""
    page = {
        "contents": [
            {
                "commentThreadRenderer": {
                    "comment": {
                        "commentRenderer": {
                            "commentId": "Ug3",
                            "authorText": {"simpleText": "@c"},
                            "contentText": {"simpleText": "No replies"},
                            "isLiked": True,
                            "detailViewEndpoint": {"x": {"continuations": [{"nextContinuationData": {"continuation": "tok-ug3"}}]}},
                        }
                    }
                }
            }
        ]
    }
    c = Y.parse_comments(page)["items"][0]
    assert (c["open"], c["vote"], c.get("repliesToken")) == ("tok-ug3", "like", None)
    assert "head" not in Y.parse_comments(page)


def test_a_comment_vote_sends_its_action():
    y = Y.YouTube.__new__(Y.YouTube)
    sent = []
    y.profile = {"id": "a:"}
    y.call = lambda ep, body, cache=True, as_client=None: sent.append((ep, body, cache)) or {}
    y.changed = lambda: sent.append("changed")
    assert y.comment_vote("t-like") == {"ok": True}
    assert sent == [("comment/perform_comment_action", {"actions": ["t-like"]}, False), "changed"]


def test_demo_comment_votes_stick():
    d = Y.Demo()
    d.use("demo1:")
    page = d.comments("demo-open-1")
    assert page["head"]["vote"] == ""
    d.comment_vote(page["head"]["actions"]["like"])
    assert d.comments("demo-open-1")["head"]["vote"] == "like"
    assert d.comments("demo-comments")["items"][1]["vote"] == "like"


def test_a_shorts_subscription_comes_from_its_entity():
    resp = {
        "overlay": {
            "reelPlayerOverlayRenderer": {"subscribeButtonRenderer": {"subscribed": False, "subscribedEntityKey": "k1", "channelId": "UCx"}}
        },
        "frameworkUpdates": {
            "entityBatchUpdate": {
                "mutations": [{"entityKey": "k1", "payload": {"subscriptionStateEntity": {"key": "k1", "subscribed": True}}}]
            }
        },
    }
    assert Y.parse_short(resp)["subscribed"] is True
    assert Y.parse_short({"overlay": {"subscribeButtonRenderer": {"subscribed": False}}})["subscribed"] is False
