"""Cards as YouTube's TV app shows them: the channel on its own line, music videos marked, paid
badges told apart, and Movies & TV's wormholes shelf as the large-title (hero) row. Made-up
responses in YouTube's shapes."""

from couchbox.services import youtube as Y


def tile(title, lines, overlays=None, badges=()):
    meta_lines = [{"lineRenderer": {"items": [{"lineItemRenderer": {"text": {"simpleText": t}}} for t in lines]}}]
    if badges:
        meta_lines.append(
            {
                "lineRenderer": {
                    "items": [
                        {"lineItemRenderer": {"badge": {"metadataBadgeRenderer": {"label": label, "style": style}}}}
                        for label, style in badges
                    ]
                }
            }
        )
    return {
        "tileRenderer": {
            "contentId": "vid00000001",
            "contentType": "TILE_CONTENT_TYPE_VIDEO",
            "header": {"tileHeaderRenderer": {"thumbnailOverlays": overlays or []}},
            "metadata": {"tileMetadataRenderer": {"title": {"simpleText": title}, "lines": meta_lines}},
            "onSelectCommand": {"watchEndpoint": {"videoId": "vid00000001"}},
        }
    }


def test_the_channel_gets_its_own_line():
    it = Y.parse_any(tile("A song", ["Some Singer • 74M views • 13 days ago"]))
    assert it["lines"] == ["Some Singer", "74M views • 13 days ago"]
    # already apart, or not a video's line: left alone
    assert Y.split_channel(["Chan", "4M views • 2 months ago"]) == ["Chan", "4M views • 2 months ago"]
    assert Y.split_channel(["Drama • 2026 • HBO"]) == ["Drama • 2026 • HBO"]


def test_music_videos_and_paid_badges():
    note = [{"thumbnailOverlayTimeStatusRenderer": {"text": {"simpleText": "3:37"}, "style": "DEFAULT", "icon": {"iconType": "AUDIO"}}}]
    it = Y.parse_any(
        tile("A song", ["Singer", "1M views"], note, badges=[("Try now", "BADGE_STYLE_TYPE_YPC"), ("TV-MA", "BADGE_STYLE_TYPE_SIMPLE")])
    )
    assert it["music"] is True and it["duration"] == "3:37"
    assert it["badges"] == ["Try now", "TV-MA"] and it["pay"] == ["Try now"]
    plain = Y.parse_any(tile("A talk", ["Chan", "1M views"], [{"thumbnailOverlayTimeStatusRenderer": {"text": {"simpleText": "9:00"}}}]))
    assert "music" not in plain and "pay" not in plain


def test_wormholes_are_the_hero_row():
    shelf = {
        "shelfRenderer": {
            "tvhtml5ShelfRendererType": "TVHTML5_SHELF_RENDERER_TYPE_WORMHOLES",
            "headerRenderer": {"shelfHeaderRenderer": {"title": {"simpleText": "Trending shows"}}},
            "content": {"horizontalListRenderer": {"items": [tile("A show", ["Network • Drama • 2026"])]}},
        }
    }
    (row,) = Y.parse_shelf(shelf)
    assert row["hero"] is True and row["items"][0]["title"] == "A show"


def test_subscriptions_rail_all_first_and_a_heading_not_a_row():
    from couchbox.services import youtube as Y

    def tab(title, bid="", thumb=True):
        tr = {"title": {"simpleText": title}, "endpoint": {"browseEndpoint": {"browseId": bid}}}
        if thumb:
            tr["thumbnail"] = {"thumbnails": [{"url": "https://yt3.ggpht.com/x=s88-c-k", "width": 88}]}
        return {"tabRenderer": tr}

    resp = {
        "contents": {
            "tvSecondaryNavRenderer": {
                "sections": [
                    {
                        "tvSecondaryNavSectionRenderer": {
                            "tabs": [
                                tab("All", "FEsubscriptions", thumb=False),
                                tab("Orbit Lab", "UCaaaaaaaaaaaaaaaaaaaaaa"),
                                tab("A-Z", "FEsubscriptions_az", thumb=False),
                                tab("Kettle & Crumb", "UCbbbbbbbbbbbbbbbbbbbbbb"),
                            ]
                        }
                    }
                ]
            }
        }
    }
    chans = Y.parse_subscriptions(resp)["channels"]
    assert [c["title"] for c in chans] == ["All", "Orbit Lab", "Kettle & Crumb"]
    assert chans[0].get("all") and chans[2]["section"] == "A-Z" and not chans[1]["section"]


def test_card_menu_feedback_options():
    def opt(label, icon, token):
        return {
            "menuServiceItemRenderer": {
                "text": {"runs": [{"text": label}]},
                "icon": {"iconType": icon},
                "serviceEndpoint": {"feedbackEndpoint": {"feedbackToken": token}},
            }
        }

    cmd = {
        "showMenuCommand": {
            "menu": {
                "menuRenderer": {
                    "items": [
                        opt("Not interested", "NOT_INTERESTED", "t1"),
                        opt("Don't recommend channel", "REMOVE", "t2"),
                        opt("Remove from watch history", "", "t3"),
                        {"menuServiceItemRenderer": {"text": {"simpleText": "Save"}, "serviceEndpoint": {"playlistEditEndpoint": {}}}},
                    ]
                }
            }
        }
    }
    got = Y.menu_feedback(cmd)
    assert [(o["kind"], o["token"]) for o in got] == [("not_interested", "t1"), ("no_channel", "t2"), ("remove_history", "t3")]
    assert Y.menu_feedback(None) == []
