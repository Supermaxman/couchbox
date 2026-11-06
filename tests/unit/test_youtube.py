"""The YouTube app's back end: InnerTube's TV pages (tiles, lockups, clusters, the watch page) become
plain cards and shelves, ads never get through, suggestions parse; and the stream picker chooses
H.264 at 1080p or less with stereo AAC, joins separate streams for mpv, and caps live streams.
The responses here are small made-up ones in YouTube's shapes (no real channels or videos)."""

import json

import pytest

from couchbox.services import youtube as Y
from couchbox.services import ytstream as S


def tile(vid, title, channel="Some Channel", meta=("1.2M views", "•", "3 days ago"), duration="12:34", badges=(), **kw):
    lines = [{"lineRenderer": {"items": [{"lineItemRenderer": {"text": {"runs": [{"text": channel}]}}}]}}]
    second = [{"lineItemRenderer": {"badge": {"metadataBadgeRenderer": {"label": b}}}} for b in badges]
    second += [{"lineItemRenderer": {"text": {"simpleText": m}}} for m in meta]
    lines.append({"lineRenderer": {"items": second}})
    overlays = [{"thumbnailOverlayTimeStatusRenderer": {"text": {"simpleText": duration}, "style": "DEFAULT"}}] if duration else []
    if kw.get("watched"):
        overlays.append({"thumbnailOverlayResumePlaybackRenderer": {"percentDurationWatched": kw["watched"]}})
    t = {
        "style": "TILE_STYLE_YTLR_DEFAULT",
        "header": {
            "tileHeaderRenderer": {
                "thumbnail": {"thumbnails": [{"url": f"https://i.ytimg.com/vi/{vid}/hq720.jpg", "width": 640, "height": 360}]},
                "thumbnailOverlays": overlays,
            }
        },
        "metadata": {"tileMetadataRenderer": {"title": {"simpleText": title}, "lines": lines}},
        "onSelectCommand": {"watchEndpoint": {"videoId": vid}},
        "contentId": vid,
        "contentType": "TILE_CONTENT_TYPE_VIDEO",
        "onLongPressCommand": {
            "showMenuCommand": {
                "menu": {
                    "menuRenderer": {
                        "items": [
                            {
                                "menuNavigationItemRenderer": {
                                    "navigationEndpoint": {"browseEndpoint": {"browseId": "UCchannel0000000000000001"}}
                                }
                            }
                        ]
                    }
                }
            }
        },
    }
    return {"tileRenderer": t}


def lockup(
    vid,
    title,
    kind="LOCKUP_CONTENT_TYPE_VIDEO",
    rows=(("A Channel",), ("2.1M views", "14 hours ago")),
    badges=("New", "4K"),
    duration="1:05:56",
):
    meta_rows = []
    for i, r in enumerate(rows):
        row = {"metadataParts": [{"text": {"content": p}} for p in r]}
        if i == len(rows) - 1 and badges:
            row["badges"] = [{"badgeViewModel": {"badgeText": b}} for b in badges]
        meta_rows.append(row)
    tap = {"reelWatchEndpoint": {"videoId": vid}} if kind == "LOCKUP_CONTENT_TYPE_SHORT" else {"watchEndpoint": {"videoId": vid}}
    return {
        "lockupViewModel": {
            "contentImage": {
                "thumbnailViewModel": {
                    "image": {"sources": [{"url": f"https://i.ytimg.com/vi/{vid}/hq720.jpg", "width": 640, "height": 360}]},
                    "overlays": [{"thumbnailBottomOverlayViewModel": {"badges": [{"thumbnailBadgeViewModel": {"text": duration}}]}}],
                }
            },
            "metadata": {
                "lockupMetadataViewModel": {
                    "title": {"content": title},
                    "metadata": {"contentMetadataViewModel": {"metadataRows": meta_rows, "delimiter": " • "}},
                }
            },
            "contentId": vid,
            "contentType": kind,
            "rendererContext": {"commandContext": {"onTap": {"innertubeCommand": tap}}},
        }
    }


AD = {"adSlotRenderer": {"adSlotMetadata": {"slotType": "SLOT_TYPE_IN_FEED"}, "fulfillmentContent": {}}}


def shelf(title, items, more=""):
    lst = {"items": items}
    if more:
        lst["continuations"] = [{"nextContinuationData": {"continuation": more}}]
    return {
        "shelfRenderer": {
            "content": {"horizontalListRenderer": lst},
            "headerRenderer": {"shelfHeaderRenderer": {"avatarLockup": {"avatarLockupRenderer": {"title": {"simpleText": title}}}}},
        }
    }


def tv_page(sections, header=None, more=""):
    sl = {"contents": sections}
    if more:
        sl["continuations"] = [{"nextContinuationData": {"continuation": more}}]
    surface = {"content": {"sectionListRenderer": sl}}
    if header:
        surface["header"] = header
    return {"contents": {"tvBrowseRenderer": {"content": {"tvSurfaceContentRenderer": surface}}}}


# ------------------------------------------------------------------ cards
def test_tile_becomes_a_card():
    c = Y.parse_any(tile("vid00000001", "Paper Bridges", badges=("4K",), watched=40))
    assert c["type"] == "video" and c["id"] == "vid00000001" and c["title"] == "Paper Bridges"
    assert c["lines"] == ["Some Channel", "1.2M views • 3 days ago"]
    assert c["badges"] == ["4K"] and c["duration"] == "12:34" and c["progress"] == pytest.approx(0.4)
    assert c["thumb"].endswith("/vid00000001/hq720.jpg") and c["channelId"] == "UCchannel0000000000000001"


def test_tile_kinds_live_channel_short():
    live = tile("vid00000002", "Live Now", duration="")
    live["tileRenderer"]["header"]["tileHeaderRenderer"]["thumbnailOverlays"] = [
        {"thumbnailOverlayTimeStatusRenderer": {"text": {"simpleText": "LIVE"}, "style": "LIVE"}}
    ]
    assert Y.parse_any(live)["type"] == "live" and Y.parse_any(live)["live"]
    ch = tile("x", "A Channel", duration="")
    ch["tileRenderer"].update(
        contentType="TILE_CONTENT_TYPE_CHANNEL", onSelectCommand={"browseEndpoint": {"browseId": "UCchannel0000000000000002"}}
    )
    c = Y.parse_any(ch)
    assert c["type"] == "channel" and c["id"] == "UCchannel0000000000000002"
    short = tile("vid00000003", "A Short", duration="")
    short["tileRenderer"]["onSelectCommand"] = {"reelWatchEndpoint": {"videoId": "vid00000003"}}
    assert Y.parse_any(short)["type"] == "short"


def test_lockup_becomes_the_same_card():
    c = Y.parse_any(lockup("vid00000004", "Alien Matter"))
    assert c == Y.item(
        type="video",
        id="vid00000004",
        title="Alien Matter",
        thumb="https://i.ytimg.com/vi/vid00000004/hq720.jpg",
        lines=["A Channel", "2.1M views • 14 hours ago"],
        badges=["New", "4K"],
        duration="1:05:56",
    )
    assert Y.parse_any(lockup("vid00000005", "Pizza Pi", kind="LOCKUP_CONTENT_TYPE_SHORT"))["type"] == "short"


def test_ads_never_get_through():
    page = Y.parse_page(
        tv_page(
            [
                {"tvMastheadRenderer": {"anything": 1}},
                shelf("Recommended", [AD, tile("vid00000006", "Real One"), lockup("vid00000007", "Promoted", badges=("Sponsored",))]),
            ]
        )
    )
    assert [s["title"] for s in page["shelves"]] == ["Recommended"]
    assert [i["id"] for i in page["shelves"][0]["items"]] == ["vid00000006"]


def test_unknown_and_broken_renderers_are_skipped():
    items = [{"someFutureRenderer": {}}, {"tileRenderer": {}}, tile("vid00000008", "Kept"), "junk", tile("vid00000008", "Kept again")]
    assert [i["id"] for i in Y.parse_items(items)] == ["vid00000008"]


# ------------------------------------------------------------------ pages
def test_tv_page_shelves_nudge_header_and_continuations():
    resp = tv_page(
        [
            {"searchBarRenderer": {"hack": True}},
            {"feedNudgeRenderer": {"title": {"runs": [{"text": "Make YouTube your own"}]}, "subtitle": {"simpleText": "Sign in."}}},
            shelf("Videos", [tile("vid00000009", "One"), tile("vid00000010", "Two")], more="tok-shelf"),
            shelf("Empty", []),
        ],
        header={
            "channelHeaderRenderer": {
                "title": {"simpleText": "Orbit Lab"},
                "avatar": {"thumbnails": [{"url": "//yt3.example/abc=s72-c-k-c0x00ffffff-no-rj", "width": 72}]},
                "subtitle": {
                    "lineRenderer": {
                        "items": [
                            {"lineItemRenderer": {"text": {"simpleText": "@orbitlab"}}},
                            {"lineItemRenderer": {"text": {"simpleText": "•"}}},
                            {"lineItemRenderer": {"text": {"simpleText": "4.2M subscribers"}}},
                        ]
                    }
                },
            }
        },
        more="tok-page",
    )
    page = Y.parse_page(resp)
    assert page["nudge"] == {"title": "Make YouTube your own", "subtitle": "Sign in."}
    assert [(s["title"], len(s["items"]), s["more"]) for s in page["shelves"]] == [("Videos", 2, "tok-shelf")]
    assert page["more"] == "tok-page"
    assert page["header"]["title"] == "Orbit Lab" and page["header"]["lines"] == ["@orbitlab", "4.2M subscribers"]
    assert page["header"]["avatar"] == "https://yt3.example/abc=s176-c-k-c0x00ffffff-no-rj"


def test_search_page_with_a_cluster_and_its_pills():
    resp = {
        "contents": {
            "sectionListRenderer": {
                "contents": [
                    shelf(
                        "Search results for paper",
                        [
                            AD,
                            lockup("vid00000011", "Paper"),
                            lockup(
                                "UCchannel0000000000000003",
                                "Paper Co",
                                kind="LOCKUP_CONTENT_TYPE_CHANNEL",
                                rows=(("@paperco",), ("1M subscribers",)),
                                badges=(),
                            ),
                        ],
                    ),
                    {
                        "clusterShelfRenderer": {
                            "clusters": [
                                {
                                    "clusterRenderer": {
                                        "headerRenderer": {
                                            "buttonViewModel": {
                                                "title": "Paper Co",
                                                "iconImage": {"url": "https://yt3.example/p=s88-c-k-no-rj"},
                                                "onTap": {
                                                    "innertubeCommand": {"browseEndpoint": {"browseId": "UCchannel0000000000000003"}}
                                                },
                                            }
                                        },
                                        "items": [lockup("vid00000012", "Hero")],
                                    }
                                },
                                {
                                    "clusterRenderer": {
                                        "headerRenderer": {
                                            "buttonViewModel": {
                                                "title": "Recently uploaded",
                                                "iconName": "SEARCH",
                                                "onTap": {"innertubeCommand": {"searchEndpoint": {"query": "paper videos"}}},
                                            }
                                        },
                                        "items": [lockup("vid00000013", "Newer")],
                                    }
                                },
                            ]
                        }
                    },
                ]
            }
        }
    }
    page = Y.parse_page(resp)
    first, cluster = page["shelves"]
    assert [i["type"] for i in first["items"]] == ["video", "channel"]
    assert first["items"][1]["id"] == "UCchannel0000000000000003"
    # the channel's section is one row: the large card under its pill, the list under its own
    hero, recent = cluster["cluster"]["hero"], cluster["cluster"]["list"]
    assert [i["id"] for i in cluster["items"]] == ["vid00000012", "vid00000013"]
    assert hero["pill"]["title"] == "Paper Co" and hero["pill"]["target"] == {"type": "channel", "id": "UCchannel0000000000000003"}
    assert recent["pill"]["icon"] == "search" and recent["pill"]["target"] == {"type": "search", "id": "paper videos"}


def test_shelf_continuation():
    resp = {
        "continuationContents": {
            "horizontalListContinuation": {
                "items": [tile("vid00000014", "More")],
                "continuations": [{"nextContinuationData": {"continuation": "next"}}],
            }
        }
    }
    assert Y.parse_more_items(resp) == {"items": [Y.parse_any(tile("vid00000014", "More"))], "more": "next"}


def test_watch_page():
    resp = {
        "contents": {
            "singleColumnWatchNextResults": {
                "results": {
                    "results": {
                        "contents": [
                            {
                                "itemSectionRenderer": {
                                    "contents": [
                                        {
                                            "videoMetadataRenderer": {
                                                "videoId": "vid00000015",
                                                "title": {"runs": [{"text": "The Thing"}]},
                                                "dateText": {"simpleText": "14h ago"},
                                                "viewCount": {"videoViewCountRenderer": {"shortViewCount": {"simpleText": "2M views"}}},
                                                "owner": {
                                                    "videoOwnerRenderer": {
                                                        "title": {"simpleText": "Orbit Lab"},
                                                        "navigationEndpoint": {"browseEndpoint": {"browseId": "UCchannel0000000000000004"}},
                                                        "subscriberCountText": {"simpleText": "4M subscribers"},
                                                        "thumbnail": {"thumbnails": [{"url": "https://yt3.example/o=s88-c", "width": 88}]},
                                                    }
                                                },
                                            }
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                },
                "autoplay": {
                    "autoplay": {
                        "sets": [
                            {
                                "mode": "NORMAL",
                                "autoplayVideoRenderer": {
                                    "autonavEndpointRenderer": {"endpoint": {"watchEndpoint": {"videoId": "vid00000016"}}}
                                },
                            },
                            {
                                "mode": "LOOP_ONE",
                                "autoplayVideoRenderer": {
                                    "autoplayEndpointRenderer": {"endpoint": {"watchEndpoint": {"videoId": "vid00000015"}}}
                                },
                            },
                        ]
                    }
                },
                "pivot": {
                    "sectionListRenderer": {
                        "contents": [
                            shelf(" ", [tile("vid00000016", "Next"), tile("vid00000015", "Itself"), AD]),
                            shelf(" ", [tile("vid00000017", "Later"), tile("vid00000016", "Next again")]),
                        ]
                    }
                },
            }
        }
    }
    w = Y.parse_watch(resp)
    assert w["video"]["title"] == "The Thing" and w["video"]["channelId"] == "UCchannel0000000000000004"
    assert w["video"]["views"] == "2M views" and w["video"]["date"] == "14h ago" and w["video"]["avatar"] == "https://yt3.example/o=s176-c"
    assert [i["id"] for i in w["related"]] == ["vid00000016", "vid00000017"]
    assert w["next"] == "vid00000016"


def test_suggestions():
    body = json.dumps(["pap", [["paper", 0, [512]], ["paper bridge", 0, [512]], ["paper", 0, []]], {"k": 1}])
    assert Y.parse_suggestions(body) == ["paper", "paper bridge"]
    assert Y.parse_suggestions("window.google.ac.h(" + body + ")") == ["paper", "paper bridge"]
    assert Y.parse_suggestions("nonsense") == []


def test_text_and_endpoints():
    assert Y.text({"runs": [{"text": "a"}, {"text": "b"}]}) == "ab" and Y.text({"simpleText": "x"}) == "x" and Y.text(None) == ""
    assert Y.endpoint({"watchEndpoint": {"videoId": "v", "startTimeSeconds": 61}}) == {"type": "video", "id": "v", "start": 61}
    assert Y.endpoint({"browseEndpoint": {"browseId": "VLPL123"}}) == {"type": "playlist", "id": "PL123"}
    cmd = {"commandExecutorCommand": {"commands": [{"signalAction": {}}, {"browseEndpoint": {"browseId": "UCx"}}]}}
    assert Y.endpoint(cmd) == {"type": "channel", "id": "UCx"}
    assert Y.seconds("1:05:56") == 3956 and Y.seconds("LIVE") == 0


def test_guest_searches_are_remembered(tmp_path):
    y = Y.YouTube(data_dir=str(tmp_path))
    for q in ("paper", "trail", "Paper", " "):
        y.remember_search(q)
    assert y.searches() == ["Paper", "trail"]
    assert (tmp_path / "searches.json").stat().st_mode & 0o777 == 0o600


def test_guest_home_fills_from_the_tabs(monkeypatch, tmp_path):
    y = Y.YouTube(data_dir=str(tmp_path))
    nudge_only = tv_page([{"feedNudgeRenderer": {"title": {"simpleText": "Make YouTube your own"}}}])
    tab = tv_page([shelf("Top", [tile(f"v{n:010d}", f"T{n}") for n in range(4)]), shelf("Few", [tile("v9999999999", "x")])])
    monkeypatch.setattr(y, "call", lambda ep, body, cache=True: nudge_only if body.get("browseId") == "FEtopics" else tab)
    home = y.home()
    assert home["nudge"]["title"] == "Make YouTube your own"
    # the same shelf from every tab: shown once (repeats left out), short shelves dropped
    assert [s["title"] for s in home["shelves"]] == ["Top"]


def test_demo_is_complete():
    d = Y.Demo()
    assert d.home()["shelves"] and d.search("x")["shelves"][0]["items"][1]["type"] == "channel"
    assert d.channel(Y.DEMO_CHANNELS[1][0])["header"]["title"] == Y.DEMO_CHANNELS[1][1]
    w = d.watch("demo0000003")
    assert len(w["related"]) == 9 and w["next"] == "demo0000004"
    s = Y.demo_stream("demo0000003")
    assert s["chapters"][0]["start"] == 0 and s["url"].startswith("demo://")


# ------------------------------------------------------------------ streams
def fmt(fid, vcodec="none", acodec="none", height=None, fps=None, proto="https", tbr=None, ch=None, **kw):
    return {
        "format_id": fid,
        "vcodec": vcodec,
        "acodec": acodec,
        "height": height,
        "fps": fps,
        "protocol": proto,
        "tbr": tbr,
        "audio_channels": ch,
        "url": f"https://media.example/{fid}",
        **kw,
    }


FORMATS = [
    fmt("18", "avc1.42001E", "mp4a.40.2", 360, 30, ch=2),
    fmt("137", "avc1.640028", height=1080, fps=30, tbr=4000),
    fmt("299", "avc1.64002A", height=1080, fps=60, tbr=6000),
    fmt("303", "vp9", height=1080, fps=60, tbr=3000),
    fmt("401", "av01.0.12M.08", height=2160, fps=60, tbr=20000),
    fmt("312", "avc1.64002A", height=1080, fps=60, proto="m3u8_native", tbr=7400),
    fmt("140", acodec="mp4a.40.2", ch=2, abr=129),
    fmt("140-drc", acodec="mp4a.40.2", ch=2, abr=129),
    fmt("258", acodec="mp4a.40.2", ch=6, abr=388),
    fmt("251", acodec="opus", ch=2, abr=135),
    fmt("sb0", "none", "none", 180, proto="mhtml"),
]


def test_pick_prefers_h264_1080p60_dash_and_stereo_aac():
    v, a = S.pick(FORMATS)
    assert v["format_id"] == "299" and a["format_id"] == "140"


def test_pick_without_h264_and_with_a_lower_cap():
    v, _ = S.pick(FORMATS, h264=False)
    assert v["format_id"] in ("299", "303")  # the best 1080p60 (never the 4K AV1)
    v, a = S.pick(FORMATS, max_height=720)
    assert v["format_id"] == "18" and a is None  # muxed: sound of its own
    only_vp9 = [f for f in FORMATS if not f["vcodec"].startswith("avc1")]
    assert S.pick(only_vp9)[0]["format_id"] == "303"  # no H.264 at all: whatever there is


def test_playable_joins_video_and_audio():
    out = S.playable({"formats": FORMATS, "live_status": "not_live"})
    assert out["wait"] == 0
    assert out["url"] == S.edl("https://media.example/299", "https://media.example/140")
    assert out["url"] == "edl://%25%https://media.example/299;!new_stream;%25%https://media.example/140"
    assert (out["height"], out["fps"], out["vcodec"], out["acodec"], out["live"]) == (1080, 60, "avc1", "mp4a", False)


def test_playable_live_plays_the_video_playlist_with_its_sound():
    live = [
        fmt("233", acodec=None, proto="m3u8_native", format_note="Default, low"),
        fmt("234", acodec=None, proto="m3u8_native", format_note="Default, high"),
        fmt("232", "avc1.4D401F", height=720, proto="m3u8_native", tbr=2448),
        fmt("270", "avc1.640028", height=1080, proto="m3u8_native", tbr=4561),
    ]
    out = S.playable({"formats": live, "live_status": "is_live"})
    assert out["live"] and out["url"] == "https://media.example/270"
    assert out["opts"] == "audio-file=%25%https://media.example/234" and out["acodec"] == ""


def test_formats_that_play_now_beat_ones_waiting_out_ads():
    now = 1_000_000
    formats = [
        fmt("299", "avc1.64002A", height=1080, fps=60, tbr=6000, available_at=now + 30),
        fmt("140", acodec="mp4a.40.2", ch=2, abr=129, available_at=now + 30),
        fmt("312", "avc1.64002A", height=1080, fps=60, proto="m3u8_native", tbr=7400, available_at=now - 5),
        fmt("234", acodec="mp4a.40.2", proto="m3u8_native", tbr=130),
    ]
    v, a = S.pick(formats, now=now)
    assert (v["format_id"], a["format_id"]) == ("312", "234")
    v, a = S.pick(formats[:2], now=now)  # nothing else: those, and the player waits
    assert (v["format_id"], a["format_id"]) == ("299", "140")


def test_playable_with_nothing_playable():
    with pytest.raises(S.Unavailable):
        S.playable({"formats": [fmt("sb0", proto="mhtml")]})


def test_resolve_reports_chapters_and_portrait(monkeypatch):
    info = {
        "id": "vid00000018",
        "title": "Tall",
        "channel": "Orbit Lab",
        "duration": 59,
        "chapters": [{"start_time": 0, "title": "Start"}, {"start_time": 30, "title": "Middle"}, {"start_time": 40}],
        "formats": [fmt("18", "avc1.42001E", "mp4a.40.2", 1920, 30, width=1080)],
    }
    monkeypatch.setattr(S, "extract", lambda vid, phases=None: info)
    out = S.resolve("vid00000018")
    assert out["portrait"] and out["chapters"] == [{"start": 0.0, "title": "Start"}, {"start": 30.0, "title": "Middle"}]
    assert out["url"] == "https://media.example/18" and out["title"] == "Tall"


def test_js_runtimes_found_on_the_path(monkeypatch, tmp_path):
    node = tmp_path / "node"
    node.write_text("#!/bin/sh\n")
    node.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr(S, "RUNTIMES", (("deno", ("/nonexistent/deno", "deno")), ("node", ("node", "nodejs"))))
    assert S.js_runtimes() == {"node": {"path": str(node)}}
