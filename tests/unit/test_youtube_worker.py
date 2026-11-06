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

    def extract(vid, phases=None):
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
    def extract(vid, phases=None):
        raise ytstream.Unavailable("This video is private.")

    monkeypatch.setattr(ytstream, "extract", extract)
    out = io.StringIO()
    ytworker.Worker(out).run_one({"n": 9, "op": "resolve", "args": {"id": "x"}}, time.monotonic())
    assert json.loads(out.getvalue()) == {"n": 9, "error": "This video is private.", "unavailable": True}
