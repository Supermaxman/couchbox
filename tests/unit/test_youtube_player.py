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
        "author": "@maker",
        "photo": "",
        "text": "Thanks all",
        "time": "2 days ago",
        "likes": "166",
        "replies": 49,
        "pinned": True,
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
