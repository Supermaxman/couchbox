"""Casting from the phone app: the Lounge's streamed answers taken apart, the phone's commands
read, the TV's replies put together, and DIAL's documents. Made-up data in YouTube's shapes."""

import json

from couchbox.services import ytcast as C


def chunk(arr):
    body = json.dumps(arr)
    return f"{len(body)}\n{body}"


def test_the_bind_stream():
    first = [[0, ["c", "SID123", "", 8]], [1, ["S", "gsess"]], [2, ["loungeStatus", {"devices": "[]"}]]]
    second = [
        [3, ["setPlaylist", {"videoId": "vid00000001", "currentTime": "42.5", "videoIds": "vid00000000,vid00000001", "currentIndex": "1"}]]
    ]
    text = chunk(first) + "\n" + chunk(second)
    assert [e[0] for e in C.parse_chunks(text)] == [0, 1, 2, 3]
    # a chunk cut off mid-way stays for the next read
    entries, rest = C.split_chunks(text[:-5])
    assert [e[0] for e in entries] == [0, 1, 2] and rest.strip().startswith(str(len(json.dumps(second))))
    assert C.command(second[0]) == (3, "setPlaylist", second[0][1][1])
    assert C.command([4, ["noop"]]) == (4, "noop", {})


def test_the_session_and_commands_reach_their_handler():
    lounge = C.Lounge("Test TV", screen_id="s", device_id="d")
    lounge.token, lounge.token_expires = "t", 1e12
    got = []
    lounge.on_command = lambda n, a: got.append(n)
    lounge._handle(C.parse_chunks(chunk([[0, ["c", "SID1", "", 8]], [1, ["S", "gs1"]], [2, ["play"]], [3, ["noop"]]])))
    assert (lounge.sid, lounge.gsession, lounge.aid) == ("SID1", "gs1", 3)
    assert got == ["play"]
    p = lounge._params(RID="rpc")
    assert p["SID"] == "SID1" and p["gsessionid"] == "gs1" and p["AID"] == "3" and p["device"] == "LOUNGE_SCREEN"


def test_playlists():
    p = C.playlist({"videoIds": "a1,b2,c3", "currentIndex": "2", "currentTime": "10"})
    assert p == {"videoId": "c3", "start": 10.0, "videoIds": ["a1", "b2", "c3"], "index": 2, "listId": ""}
    p = C.playlist({"videoId": "zz", "listId": "RDzz"})
    assert p["videoIds"] == ["zz"] and p["index"] == 0 and p["listId"] == "RDzz"


def test_what_the_tv_says():
    form = C.outgoing([("nowPlaying", {"videoId": "a1", "currentTime": 3.5}), ("onVolumeChanged", {"volume": 40})], ofs=7)
    assert form == {
        "count": "2",
        "ofs": "7",
        "req0__sc": "nowPlaying",
        "req0_videoId": "a1",
        "req0_currentTime": "3.5",
        "req1__sc": "onVolumeChanged",
        "req1_volume": "40",
    }


def test_dial_documents():
    assert "<friendlyName>Couchbox YouTube (beta)</friendlyName>" in C.device_xml("Couchbox YouTube (beta)", "u-1")
    app = C.app_xml(True, "screen&1")
    assert "<state>running</state>" in app and "screen&amp;1" in app and 'rel="run"' in app
    assert "<state>stopped</state>" in C.app_xml(False, "x")
    reply = C.ssdp_reply("http://192.0.2.5:56789/dd.xml", "u-1").decode()
    assert reply.startswith("HTTP/1.1 200 OK") and "LOCATION: http://192.0.2.5:56789/dd.xml" in reply and C.DIAL_ST in reply


def test_phones_list_the_tv_under_its_name(box):
    from couchbox import settings

    assert C.cast_name() == "Couchbox"
    settings.update({"network.hostname": "living-room"})
    assert C.cast_name() == "living-room"
    settings.update({"media.youtube.client": "vacuumtube"})
    (box / "var/lib/flatpak/app/rocks.shy.VacuumTube").mkdir(parents=True)
    assert C.cast_name() == "living-room (Couchbox YouTube)"  # beside VacuumTube's own
