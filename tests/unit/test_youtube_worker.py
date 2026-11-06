"""The stream worker (ytworker): yt-dlp's information kept until its addresses expire, a video
asked for before any prefetch, and the app's side of the pipe."""

import io
import json
import time

from couchbox.services import ytstream, ytworker


def fmt(fid, vcodec, acodec, height, expire):
    return {
        "format_id": fid,
        "vcodec": vcodec,
        "acodec": acodec,
        "height": height,
        "width": height * 16 // 9,
        "url": f"https://media.example/videoplayback?expire={expire}&itag={fid}",
    }


def info(vid, expire):
    return {"id": vid, "title": "A video", "duration": 600, "formats": [fmt("18", "avc1.42001E", "mp4a.40.2", 360, expire)]}


def test_kept_until_the_addresses_expire():
    c = ytworker.Cache()
    soon, later = int(time.time()) + 600, int(time.time()) + 6 * 3600
    c.put("a", info("a", soon))  # inside the margin: not kept
    c.put("b", info("b", later))
    assert c.get("a") is None and c.get("b")["id"] == "b"
    assert ytworker.expires(info("b", later)) == later


def test_resolve_first_then_prefetches_newest_first(monkeypatch):
    asked = []

    def extract(vid, phases=None, visitor=""):
        asked.append(vid)
        return info(vid, int(time.time()) + 6 * 3600)

    monkeypatch.setattr(ytstream, "extract", extract)
    out = io.StringIO()
    w = ytworker.Worker(out)
    w.take({"n": 1, "op": "prefetch", "args": {"id": "old"}})
    w.take({"n": 2, "op": "prefetch", "args": {"id": "new"}})
    w.take({"n": 3, "op": "resolve", "args": {"id": "now"}})
    while w.queue:
        prio, stamp, _, req = __import__("heapq").heappop(w.queue)
        w.run_one(req, -stamp if prio else time.monotonic())
    assert asked == ["now", "new", "old"]
    answers = [json.loads(ln) for ln in out.getvalue().splitlines()]
    assert answers[0]["n"] == 3 and answers[0]["result"]["url"].startswith("https://media.example/")
    # asked again: from what's kept, at once
    w.run_one({"n": 4, "op": "resolve", "args": {"id": "new"}}, time.monotonic())
    last = json.loads(out.getvalue().splitlines()[-1])
    assert last["result"]["timing"]["cached"] and asked == ["now", "new", "old"]


def test_an_unplayable_video_says_why(monkeypatch):
    def extract(vid, phases=None, visitor=""):
        raise ytstream.Unavailable("This video is private.")

    monkeypatch.setattr(ytstream, "extract", extract)
    out = io.StringIO()
    ytworker.Worker(out).run_one({"n": 9, "op": "resolve", "args": {"id": "x"}}, time.monotonic())
    assert json.loads(out.getvalue()) == {"n": 9, "error": "This video is private.", "unavailable": True}


def test_a_kept_video_is_answered_at_once_not_behind_a_prefetch(monkeypatch):
    out = io.StringIO()
    w = ytworker.Worker(out)
    w.cache.put("kept", info("kept", int(time.time()) + 6 * 3600))
    w.take({"n": 7, "op": "prefetch", "args": {"id": "other"}})  # queued (no worker thread runs here)
    w.take({"n": 8, "op": "resolve", "args": {"id": "kept"}})
    for _ in range(50):
        if out.getvalue():
            break
        time.sleep(0.02)
    answer = json.loads(out.getvalue().splitlines()[0])
    assert answer["n"] == 8 and answer["result"]["timing"]["cached"] and len(w.queue) == 1


def test_our_own_player_answer_deciphered():
    pr = {
        "playabilityStatus": {"status": "OK"},
        "videoDetails": {"videoId": "vid00000001", "title": "A video", "author": "Orbit Lab", "lengthSeconds": "600"},
        "streamingData": {
            "adaptiveFormats": [
                {
                    "itag": 137,
                    "mimeType": 'video/mp4; codecs="avc1.640028"',
                    "width": 1920,
                    "height": 1080,
                    "fps": 30,
                    "bitrate": 4000000,
                    "signatureCipher": "s=SIG1&sp=sig&url=https%3A%2F%2Fmedia.example%2Fvideoplayback%3Fitag%3D137%26n%3DNNN%26expire%3D1999999999",
                },
                {
                    "itag": 140,
                    "mimeType": 'audio/mp4; codecs="mp4a.40.2"',
                    "bitrate": 130000,
                    "audioChannels": 2,
                    "url": "https://media.example/videoplayback?itag=140&n=NNN&expire=1999999999",
                },
            ]
        },
        "storyboards": {
            "playerStoryboardSpecRenderer": {
                "spec": "https://i.example/sb/$L/$N.jpg?x=1|48#27#100#10#10#0#default#rs$A|80#45#100#10#10#2000#M$M#rs$B"
            }
        },
    }
    asked = {}

    def solve(n, sig):
        asked.update(n=n, sig=sig)
        return {"NNN": "nnn"}, {"SIG1": "sig1"}

    info = ytstream.from_player(pr, solve)
    v, a = ytstream.pick(info["formats"])
    assert asked == {"n": ["NNN", "NNN"], "sig": ["SIG1"]}
    assert v["format_id"] == "137" and "n=nnn" in v["url"] and "sig=sig1" in v["url"] and v["vcodec"] == "avc1.640028"
    assert a["format_id"] == "140" and "n=nnn" in a["url"]
    out = ytstream.playable(info)
    assert out["protocol"] == "dash" and out["url"].startswith("edl://") and not out["wait"]
    sb = ytstream.storyboard(info["formats"])
    assert sb["cols"] == 10 and sb["sheets"][0]["url"] == "https://i.example/sb/1/M0.jpg?x=1&sigh=rs$B"
    # a live stream, or one YouTube won't play: the usual way instead
    import pytest

    with pytest.raises(ytstream.Unavailable):
        ytstream.from_player(dict(pr, videoDetails={"isLive": True}), solve)
    with pytest.raises(ytstream.Unavailable):
        ytstream.from_player(dict(pr, playabilityStatus={"status": "LOGIN_REQUIRED", "reason": "Sign in"}), solve)


def test_sixty_frames_win_at_the_same_height():
    # H.264 1080p60 (299) over 1080p30 (137), 720p60 (298) under the 1080p cap's best
    fs = [
        {
            "format_id": "137",
            "vcodec": "avc1.640028",
            "acodec": "none",
            "height": 1080,
            "width": 1920,
            "fps": 30,
            "tbr": 4000,
            "url": "https://m/137",
        },
        {
            "format_id": "299",
            "vcodec": "avc1.64002a",
            "acodec": "none",
            "height": 1080,
            "width": 1920,
            "fps": 60,
            "tbr": 6000,
            "url": "https://m/299",
        },
        {
            "format_id": "298",
            "vcodec": "avc1.4d4020",
            "acodec": "none",
            "height": 720,
            "width": 1280,
            "fps": 60,
            "tbr": 3500,
            "url": "https://m/298",
        },
        {"format_id": "140", "vcodec": "none", "acodec": "mp4a.40.2", "abr": 128, "url": "https://m/140"},
    ]
    v, a = ytstream.pick(fs)
    assert v["format_id"] == "299" and a["format_id"] == "140"
    assert ytstream.pick(fs, max_height=720)[0]["format_id"] == "298"
    out = ytstream.playable({"formats": fs})
    assert out["itags"] == ["299", "140"] and out["fps"] == 60


MASTER = """#EXTM3U
#EXT-X-INDEPENDENT-SEGMENTS
#EXT-X-STREAM-INF:BANDWIDTH=1500000,CODECS="avc1.4d401f,mp4a.40.2",RESOLUTION=1280x720,FRAME-RATE=30
https://manifest.example/720.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=4500000,CODECS="avc1.64002a,mp4a.40.2",RESOLUTION=1920x1080,FRAME-RATE=60
https://manifest.example/1080p60.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=4000000,CODECS="avc1.640028,mp4a.40.2",RESOLUTION=1920x1080,FRAME-RATE=30
https://manifest.example/1080p30.m3u8
"""


def test_a_live_stream_signed_in_from_its_hls_master():
    pr = {
        "playabilityStatus": {"status": "OK"},
        "videoDetails": {"videoId": "live0000001", "isLive": True, "title": "Live"},
        "streamingData": {"hlsManifestUrl": "https://manifest.example/master.m3u8"},
    }

    class R:
        text = MASTER

    info = ytstream.from_player(pr, lambda n, sig: ({}, {}), lambda url, timeout=None: R())
    out = ytstream.playable(info)
    assert out["live"] and out["url"] == "https://manifest.example/1080p60.m3u8" and out["fps"] == 60 and out["protocol"] == "hls"


def test_hls_sound_renditions_go_with_video_only_variants():
    master = """#EXTM3U
#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="234",NAME="Default",DEFAULT=YES,URI="https://manifest.example/audio.m3u8"
#EXT-X-STREAM-INF:BANDWIDTH=4500000,CODECS="avc1.64002a",RESOLUTION=1920x1080,FRAME-RATE=30,AUDIO="234"
https://manifest.example/video.m3u8
"""
    out = ytstream.playable({"live_status": "is_live", "formats": ytstream.hls_formats(master)})
    assert out["url"] == "https://manifest.example/video.m3u8" and "audio-file=" in out["opts"] and "audio.m3u8" in out["opts"]
