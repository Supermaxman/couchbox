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
