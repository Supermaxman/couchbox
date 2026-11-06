"""Live streams from their adaptive formats (ytlive): segments joined into one MP4 for mpv."""

from couchbox.services import ytlive, ytstream


def box(kind, payload=b""):
    return (8 + len(payload)).to_bytes(4, "big") + kind.encode() + payload


def segment(n):
    return box("ftyp", b"iso6") + box("moov", b"m") + box("emsg", b"e") + box("moof", bytes([n])) + box("mdat", b"x" * n)


def test_segments_after_the_first_keep_moof_and_mdat():
    s = segment(3)
    assert ytlive.fragments(s, True) == s
    assert ytlive.fragments(s, False) == box("moof", bytes([3])) + box("mdat", b"xxx")
    assert [k for k, _ in ytlive.boxes(s)] == ["ftyp", "moov", "emsg", "moof", "mdat"]


class Resp:
    def __init__(self, status, content=b"", headers=None):
        self.status_code, self.content, self.headers = status, content, headers or {}

    def close(self):
        pass


class Session:
    """Segments 10..12 exist, the head is 12; 13 is gone (403: the stream's address expired)."""

    def __init__(self):
        self.asked = []

    def get(self, url, timeout=None, stream=False):
        sq = int(url.rsplit("&sq=", 1)[1])
        self.asked.append(sq)
        if sq == 0:
            return Resp(200, b"", {"X-Head-Seqnum": "12"})
        if 10 <= sq <= 12:
            return Resp(200, segment(sq))
        return Resp(403)


def test_a_group_starts_behind_the_head_and_joins_its_segments():
    p = ytlive.Proxy(session=Session())
    p.start = lambda: None  # (no server: the generator alone)
    local = p.group({"299": "https://v.example/videoplayback?id=1", "140": "https://v.example/videoplayback?id=2"})
    assert set(local) == {"299", "140"} and all("/live/g1/" in u for u in local.values())
    out = list(p.segments("g1", "299"))
    assert len(out) == 3 and out[0] == segment(10)  # 12 - BEHIND, whole; then moof+mdat
    assert out[1] == ytlive.fragments(segment(11), False)
    assert p.groups["g1"]["start"] == 10
    assert list(p.segments("g1", "140"))[0] == segment(10)  # the sound starts at the same segment


def test_live_without_hls_plays_its_adaptive_formats_through_the_box():
    pr = {
        "playabilityStatus": {"status": "OK"},
        "videoDetails": {"videoId": "live0000001", "title": "A live one", "isLive": True},
        "streamingData": {
            "adaptiveFormats": [
                {
                    "itag": 299,
                    "url": "https://v.example/vp?itag=299",
                    "mimeType": 'video/mp4; codecs="avc1.64002A"',
                    "width": 1920,
                    "height": 1080,
                    "fps": 60,
                },
                {"itag": 140, "url": "https://v.example/vp?itag=140", "mimeType": 'audio/mp4; codecs="mp4a.40.2"', "audioChannels": 2},
            ]
        },
    }
    info = ytstream.from_player(pr, lambda n, s: ({}, {}))
    assert info["is_live"] and all(f["url"].startswith("http://127.0.0.1:") for f in info["formats"])
    p = ytstream.playable(info)
    assert p["live"] and p["itags"] == ["299", "140"] and p["url"].endswith("/299") and "/140," in p["opts"] and p["opts"].endswith("force-seekable=yes")
