"""Talking to what's playing: the subtitles read up to the current second (nothing later reaches
the model for questions about the story), the last minutes for a recap, the whole video to find
a moment; the screen's picture goes to the model when it takes pictures."""

import copy
import json
import threading

import pytest

from couchbox.voice import agent, tools, watching

SRT = """1
00:00:01,000 --> 00:00:03,500
<i>Previously, at the bakery...</i>

2
00:00:05,000 --> 00:00:07,000
MARA: Theo, you're late again.

3
00:01:10,000 --> 00:01:12,000
{\\an8}THEO: The oven's been off all night.

4
00:10:00,000 --> 00:10:02,000
Mara tastes the bread.
It's perfect.

5
00:20:00,000 --> 00:20:03,000
THEO: I sold the bakery.
"""

# YouTube's automatic captions: each cue repeats the line before and grows word by word
ASR_VTT = """WEBVTT
Kind: captions
Language: en

00:00:00.320 --> 00:00:02.960 align:start position:0%
\x20
so<00:00:00.640><c> today</c><00:00:01.040><c> we're</c><00:00:01.360><c> making</c>

00:00:02.960 --> 00:00:02.970 align:start position:0%
so today we're making
\x20

00:00:02.970 --> 00:00:05.200 align:start position:0%
so today we're making
pancakes<00:00:03.400><c> from</c><00:00:03.900><c> scratch</c>

00:00:05.200 --> 00:00:05.210 align:start position:0%
pancakes from scratch
\x20

00:00:05.210 --> 00:00:08.000 align:start position:0%
pancakes from scratch
mmm<00:00:06.000><c> that's</c><00:00:06.500><c> good</c>
"""


def test_subtitles_read_as_lines_once_each():
    cues = watching.parse(SRT)
    assert [c[2] for c in cues] == [
        "Previously, at the bakery...",
        "MARA: Theo, you're late again.",
        "THEO: The oven's been off all night.",
        "Mara tastes the bread.",
        "It's perfect.",
        "THEO: I sold the bakery.",
    ]
    assert cues[2][0] == 70.0 and cues[-1][0] == 1200.0
    asr = watching.parse(ASR_VTT)
    assert [c[2] for c in asr] == ["so today we're making", "pancakes from scratch", "mmm that's good"]
    assert [c[0] for c in asr] == [0.32, 2.97, 5.21]
    # Couchbox's YouTube app's own copy (word by word, a cue each): the same three lines
    rolling = "WEBVTT\n\n" + "\n\n".join(
        f"00:00:0{n}.000 --> 00:00:0{n + 1}.000\n{t}" for n, t in enumerate(["so", "so today", "so today we're making", "pancakes"])
    )
    assert [c[2] for c in watching.parse(rolling)] == ["so today we're making", "pancakes"]


def test_lines_carry_their_times():
    cues = watching.parse(SRT)
    assert watching.lines(cues) == [
        "[0:01] Previously, at the bakery... MARA: Theo, you're late again.",
        "[1:10] THEO: The oven's been off all night.",
        "[10:00] Mara tastes the bread. It's perfect.",
        "[20:00] THEO: I sold the bakery.",
    ]
    assert watching.lines(cues, 60, 700) == ["[1:10] THEO: The oven's been off all night.", "[10:00] Mara tastes the bread. It's perfect."]
    assert watching.clock(3725) == "1:02:05"


def test_a_long_text_starts_on_a_whole_ten_minutes():
    cues = [(float(s), s + 1.0, f"line {s} " + "word " * 20) for s in range(0, 3600, 10)]
    rows, start = watching.since(cues, 2000, 8000)
    assert start % 600 == 0 and start > 0 and rows[0].startswith(f"[{watching.clock(start)}]")
    assert sum(len(r) + 1 for r in rows) <= 8000 and rows[-1].startswith("[33:20]")
    assert watching.since(cues, 2005, 8000)[1] == start  # a question a few seconds later: the same text, cached
    assert watching.since(cues[:5], 40, 8000)[1] == 0


def test_the_subtitles_to_read():
    streams = [
        {"Type": "Video", "Index": 0},
        {"Type": "Subtitle", "Index": 2, "Language": "eng", "IsTextSubtitleStream": True, "IsForced": True},
        {"Type": "Subtitle", "Index": 3, "Language": "eng", "IsTextSubtitleStream": True},
        {"Type": "Subtitle", "Index": 4, "Language": "spa", "IsTextSubtitleStream": True},
        {"Type": "Subtitle", "Index": 5, "Language": "eng", "IsTextSubtitleStream": False},
    ]
    assert watching.pick_subtitles(streams)["Index"] == 3  # English, all of it (not just the forced lines)
    assert watching.pick_subtitles(streams, chosen=4)["Index"] == 4  # the ones showing
    assert watching.pick_subtitles(streams, chosen=5)["Index"] == 3  # showing, but pictures
    assert watching.pick_subtitles(streams[4:]) is None


class FakePlaying(watching.Playing):
    app, title, duration = "Jellyfin", "“Crumbs S1E3 The Oven”", 1500.0

    def __init__(self, position):
        self.position = position

    def cues(self):
        return watching.parse(SRT)

    def earlier(self):
        return "S1E2 The Flour: Mara buys the bakery."


@pytest.fixture
def now(monkeypatch):
    p = FakePlaying(75.0)
    monkeypatch.setattr(watching, "playing", lambda: p)
    return p


def test_the_story_stops_at_the_current_second(now):
    out = watching.run("story", picture=lambda: "data:image/jpeg;base64,AAAA")
    assert "THEO: The oven's been off all night." in out and "Mara buys the bakery." in out
    assert "tastes" not in out and "sold" not in out  # what comes later never reaches the model
    assert "Now: playing at 1:15 of 25:00." in out and "nothing about what comes after 1:15" in out
    assert out.index("[1:10]") < out.index("Now:")  # what changes comes last: the server's cache keeps the rest
    assert out.image == "data:image/jpeg;base64,AAAA"


def test_a_recap_is_the_last_minutes(now):
    now.position = 1210.0
    out = watching.run("recent", picture=None)
    assert "[20:00] THEO: I sold the bakery." in out and "tastes" not in out and "oven" not in out
    assert "three short lines" in out and out.image is None


def test_find_reads_it_all_to_jump(now):
    out = watching.run("find", query="where she tastes it")
    assert "[10:00] Mara tastes the bread." in out and "[20:00]" in out and "media seek" in out
    assert out.image is None


def test_nothing_readable_playing(monkeypatch):
    monkeypatch.setattr(watching, "playing", lambda: None)
    assert watching.run("story").startswith("Nothing is playing that I can read along with")


def test_a_film_too_long_to_read_whole_is_cut_to_what_matches():
    rows = [f"[{watching.clock(n * 8)}] blah blah {n}" for n in range(500)]
    rows[300] = "[40:00] she finally tastes the soup"
    got = watching.matching(rows, "where she tastes it", 200)
    assert "[40:00] she finally tastes the soup" in got and len(got) == 7


def test_jellyfin_reads_the_tvs_session(monkeypatch):
    calls = []

    class Api:
        user = "u1"

        def get(self, path, params=None):
            calls.append(path)
            if path.startswith("/Users/"):
                return {
                    "MediaSources": [
                        {"Id": "src", "MediaStreams": [{"Type": "Subtitle", "Index": 3, "Language": "eng", "IsTextSubtitleStream": True}]}
                    ]
                }
            if path.startswith("/Shows/"):
                return {
                    "Items": [
                        {
                            "Id": "e1",
                            "ParentIndexNumber": 1,
                            "IndexNumber": 1,
                            "Name": "Dough",
                            "Overview": "They meet.",
                            "UserData": {"Played": True},
                        },
                        {"Id": "e2", "ParentIndexNumber": 1, "IndexNumber": 2, "Name": "Skipped", "Overview": "Not seen.", "UserData": {}},
                        {"Id": "e3", "ParentIndexNumber": 1, "IndexNumber": 3, "Name": "Oven", "Overview": "Now.", "UserData": {}},
                        {"Id": "e4", "ParentIndexNumber": 1, "IndexNumber": 4, "Name": "Later", "Overview": "Spoiler.", "UserData": {}},
                    ]
                }
            raise AssertionError(path)

        def text(self, path):
            calls.append(path)
            return SRT

    item = {
        "Id": "e3",
        "Type": "Episode",
        "Name": "Oven",
        "SeriesName": "Crumbs",
        "SeriesId": "s",
        "ParentIndexNumber": 1,
        "IndexNumber": 3,
        "RunTimeTicks": 15e9,
    }
    watching._cache.clear()
    p = watching.JellyfinPlaying(Api(), item, {"PositionTicks": 600e7, "IsPaused": True, "MediaSourceId": "src"}, position=612.4)
    assert p.title == "“Crumbs S1E3 Oven”" and p.position == 612.4 and p.paused
    assert len(p.cues()) == 6 and "/Videos/e3/src/Subtitles/3/0/Stream.srt" in calls
    p.cues()
    assert calls.count("/Videos/e3/src/Subtitles/3/0/Stream.srt") == 1  # fetched once a session
    assert p.earlier() == "S1E1 Dough: They meet."  # watched, and before this one


def test_subtitles_are_fetched_when_jellyfin_starts_playing(monkeypatch):
    fetched = threading.Event()

    class P:
        def cues(self):
            fetched.set()
            return []

    watching._cache.clear()
    watching._warming.clear()
    monkeypatch.setattr(
        watching, "mpv_get", lambda prop: "https://jf.example/videos/0123456789abcdef0123456789abcdef/stream.mkv?static=true"
    )
    monkeypatch.setattr(watching, "jellyfin_playing", lambda: P())
    assert watching.warm() == "0123456789abcdef0123456789abcdef"
    assert fetched.wait(2)
    assert watching.warm() is None  # once
    monkeypatch.setattr(watching, "mpv_get", lambda prop: None)
    assert watching.warm() is None


def test_youtube_from_the_apps_state(monkeypatch):
    from couchbox.voice import ytnative

    monkeypatch.setattr(
        ytnative,
        "state",
        lambda: {"page": "player", "videoId": "abc123", "title": "Pancakes", "position": 61, "duration": 600, "paused": False},
    )
    p = watching.youtube_playing(True)
    assert (p.vid, p.title, p.position, p.native) == ("abc123", "“Pancakes”", 61.0, True)
    monkeypatch.setattr(ytnative, "state", lambda: {"page": "player", "videoId": "abc123", "live": True})
    assert watching.youtube_playing(True) is None  # live: no captions file to read


def test_the_tool_is_offered_and_keeps_its_picture(monkeypatch):
    assert "watching" in {t["function"]["name"] for t in tools.schemas()}
    pic = watching.Text("subtitles")
    pic.image = "data:image/jpeg;base64,AAAA"
    monkeypatch.setattr(watching, "run", lambda *a: pic)
    out = tools.run_tool("watching", {"action": "story"})
    assert out == "subtitles" and out.image == pic.image
    assert tools.status_text("watching", {"action": "recent"}) == "Catching up"


# ------------------------------------------------------------------ the agent: pictures and thinking
class Server:
    """The model server: answers from a script of messages, records each request."""

    def __init__(self, script, refuse=()):
        self.script, self.bodies, self.refuse = list(script), [], refuse

    def __call__(self, url, json=None, **kw):
        self.bodies.append(copy.deepcopy(json))  # (the agent drops the picture from its history later)
        has_pic = any(isinstance(m.get("content"), list) for m in json["messages"])

        class R:
            pass

        r = R()
        if ("pictures" in self.refuse and has_pic) or ("kwargs" in self.refuse and "chat_template_kwargs" in json):
            r.status_code, r.text = 400, "unsupported: image input" if has_pic else "unknown field chat_template_kwargs"
            r.raise_for_status = lambda: (_ for _ in ()).throw(RuntimeError(r.text))
            return r
        msg = self.script.pop(0)
        r.status_code, r.text = 200, ""
        r.raise_for_status = lambda: None
        r.json = lambda: {"choices": [{"message": msg}], "usage": {}}
        return r


def call(name, **args):
    return {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "function": {"name": name, "arguments": json.dumps(args)}}]}


@pytest.fixture
def ask(monkeypatch):
    monkeypatch.setattr(agent.Agent, "note", staticmethod(lambda: "[Screen: Jellyfin in front.]"))
    pic = watching.Text("MARA: Theo, you're late again.")
    pic.image = "data:image/jpeg;base64,AAAA"
    monkeypatch.setattr(tools, "run_tool", lambda name, args: pic if name == "watching" else "ok")

    def ask(server, text="who is this guy again"):
        monkeypatch.setattr(agent.requests, "post", server)
        a = agent.Agent("http://x", "m", "k", lambda *_: None)
        return a, a.run(text, lambda *x: None, threading.Event())

    return ask


def test_the_picture_goes_to_the_model_then_leaves_the_history(ask):
    s = Server([call("watching", action="story"), {"role": "assistant", "content": "That's Theo, the baker.\n\nHe's late again."}])
    a, reply = ask(s)
    assert reply == "That's Theo, the baker.\nHe's late again."  # lines, not paragraphs
    last = s.bodies[1]["messages"][-1]
    assert last["role"] == "user" and last["content"][1] == {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,AAAA"}}
    assert s.bodies[1]["chat_template_kwargs"] == {"enable_thinking": False}  # answered without minutes of thinking
    assert "chat_template_kwargs" not in s.bodies[0]
    assert not agent.has_picture(a.history()) and agent.NO_PICTURE in json.dumps(a.history())


def test_a_model_without_pictures_answers_from_the_text(ask):
    s = Server([call("watching", action="story"), {"role": "assistant", "content": "That's Theo."}], refuse=("pictures",))
    a, reply = ask(s)
    assert reply == "That's Theo." and a.pictures is False
    assert not agent.has_picture(s.bodies[-1]["messages"])


def test_a_server_without_template_switches_keeps_thinking(ask):
    s = Server([call("watching", action="recent"), {"role": "assistant", "content": "Theo came in late."}], refuse=("kwargs",))
    a, reply = ask(s, "what did I miss")
    assert reply == "Theo came in late." and a.no_think is False
    assert "chat_template_kwargs" not in s.bodies[-1]
