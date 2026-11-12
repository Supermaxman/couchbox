"""While you were out (couchbox.away): out and back, inside and outside cameras, choosing and
captioning the clips, the card."""

import datetime

from couchbox import away, home, ontv, settings
from couchbox.services import frigate

H = 3600
T0 = 1_800_000_000.0


# ------------------------------------------------------------------ out and back
def run(tr, steps):
    """steps: (now, last key, playing, left) -> the events tick() answered."""
    return [ev for step in steps if (ev := tr.tick(*step))]


def test_quiet_three_hours_then_a_press_is_back():
    tr = away.Tracker(now=T0)
    assert run(tr, [(T0 + 60, T0 + 60, False, None)]) == []  # someone at the TV
    assert tr.tick(T0 + 2 * H, T0 + 60, False, None) is None and tr.out is None
    tr.tick(T0 + 3 * H + 120, T0 + 60, False, None)
    assert tr.out == T0 + 60 and tr.st["why"] == "quiet"
    assert tr.tick(T0 + 5 * H, T0 + 5 * H, False, None) == ("back", T0 + 60, T0 + 5 * H)
    assert tr.out is None
    assert tr.tick(T0 + 5 * H + 10, T0 + 5 * H + 10, False, None) is None  # just using the TV


def test_playing_keeps_the_tv_in_use():
    tr = away.Tracker(now=T0)
    tr.tick(T0 + 1, T0, False, None)
    for h in range(1, 6):  # a film plays on without a press
        tr.tick(T0 + h * H, T0, True, None)
    assert tr.out is None
    assert tr.tick(T0 + 6 * H, T0 + 6 * H, False, None) is None


def test_a_leaving_moment_starts_the_absence_at_once():
    tr = away.Tracker(now=T0)
    tr.tick(T0, T0, False, None)
    tr.tick(T0 + 10, T0 + 10, True, T0 + 10)  # pet music started with the remote
    assert tr.out == T0 + 10 and tr.st["why"] == "left"
    # a press just after (the volume, say) doesn't end it; the music plays all along
    assert tr.tick(T0 + 120, T0 + 120, True, T0 + 10) is None and tr.out == T0 + 10
    assert tr.tick(T0 + 2 * H, T0 + 2 * H, True, T0 + 10) == ("back", T0 + 10, T0 + 2 * H)


def test_an_old_leaving_moment_is_not_an_absence():
    tr = away.Tracker(now=T0)  # started after the service: pet music from yesterday
    tr.tick(T0 + 5, T0 + 5, False, T0 - 20 * H)
    assert tr.out is None


def test_an_absence_the_service_missed_still_counts():
    tr = away.Tracker({"busy": T0, "key": T0}, now=T0 + 6 * H)
    assert tr.tick(T0 + 6 * H, T0 + 6 * H, False, None) == ("back", T0, T0 + 6 * H)


# ------------------------------------------------------------------ cameras
def test_sides_from_an_outside_group():
    s = away.sides(frigate.DEMO_CONFIG)
    assert s["front_door"] and s["garage"] and s["backyard_side_gate"]
    assert not s["living_room"] and not s["stairs"]


def test_sides_from_an_inside_group_or_what_they_track():
    cfg = {"cameras": {"porch": {}, "den": {}}, "camera_groups": {"Indoor": {"cameras": ["den"]}}}
    assert away.sides(cfg) == {"porch": True, "den": False}
    cfg = {"cameras": {"a": {"objects": {"track": ["person", "car"]}}, "b": {"objects": {"track": ["person", "dog"]}}}}
    assert away.sides(cfg) == {"a": True, "b": False}


def row(i, cam, objs, start, dur=20, sev="detection"):
    return {"id": f"r{i}", "camera": cam, "severity": sev, "start_time": start, "end_time": start + dur, "data": {"objects": objs}}


SIDE = {"front": True, "yard": True, "lounge": False, "hall": False}


def test_candidates_outside_then_pets_and_edges():
    since, until = T0, T0 + 4 * H
    rows = [
        row(1, "front", ["person"], since + 60),  # the household leaving: left out
        row(2, "front", ["person", "package"], since + H, sev="alert"),
        row(3, "lounge", ["person"], since + H),  # people inside: not shown
        row(4, "lounge", ["dog"], since + 2 * H),
        row(5, "yard", ["dog"], since + 2 * H),  # an animal on its own outside: the pets
        row(6, "yard", ["bird"], since + 2 * H + 300),
        row(7, "front", ["person"], until - 60),  # the household arriving: left out
        {**row(8, "front", ["car"], since + H), "end_time": None},  # still going on
    ]
    got = {c["id"]: c["section"] for c in away.candidates(rows, SIDE, since, until)}
    assert got == {"r2": "outside", "r4": "pets", "r5": "pets", "r6": "pets"}


def test_choose_prefers_lively_and_keeps_outside_first():
    since = T0
    cands = away.candidates(
        [row(i, "lounge", ["dog"], since + H + i * 600) for i in range(6)]
        + [row(10, "front", ["person"], since + 3 * H), row(11, "hall", ["cat"], since + 2 * H)],
        SIDE,
        since,
        since + 8 * H,
    )
    by = {c["id"]: c for c in cands}
    for i in range(6):
        by[f"r{i}"]["lively"] = 1.0  # a sleeping dog
    by["r3"]["lively"] = 9.0
    by["r11"]["lively"] = 7.0
    by["r10"]["lively"] = 4.0
    picked = away.choose(cands, n=4)
    ids = [c["id"] for c in picked]
    assert ids[0] == "r10"  # outside first
    assert "r3" in ids and "r11" in ids
    assert sum(1 for c in picked if c["camera"] == "lounge") <= away.PER_CAMERA
    pets = [c["start"] for c in picked if c["section"] == "pets"]
    assert pets == sorted(pets)


def test_choose_spreads_one_camera_out():
    cands = away.candidates([row(i, "lounge", ["dog"], T0 + H + i * 10) for i in range(5)], SIDE, T0, T0 + 4 * H)
    assert len(away.choose(cands)) == 1  # all within two minutes: one of them


def test_parse_look():
    assert away.parse_look('```json\n{"lively": 8, "best": 2, "caption": "a person runs across the yard."}\n```') == {
        "lively": 8.0,
        "best": 2,
        "caption": "A person runs across the yard",
    }
    assert away.parse_look('{"lively": "lots"}') is None
    assert away.parse_look("I can't see that") is None
    assert away.parse_look('{"lively": 14, "best": 9, "caption": ""}')["lively"] == 10


def test_once_the_model_looked_only_looked_at_clips_and_no_empty_ones():
    cands = away.candidates([row(i, "front", ["person"], T0 + H + i * 600) for i in range(5)], SIDE, T0, T0 + 8 * H)
    cands[0]["lively"] = 0.0  # snow on the driveway
    cands[1]["lively"] = 6.0
    cands[2]["lively"] = 2.0
    assert [c["id"] for c in away.choose(cands)] == ["r1", "r2"]


def test_clip_window_stays_near_the_item():
    c = {"start": 100.0, "end": 160.0, "best_t": 148.0}
    s, e = away.clip_window(c)
    assert e - s == away.CLIP and 100 <= s <= 160
    s, e = away.clip_window({"start": 100.0, "end": 101.0, "thumb": 100.5})
    assert s >= 99 and e - s == away.CLIP


def test_captions():
    t = datetime.datetime(2026, 11, 12, 14, 14).timestamp()
    c = {"start": t, "objects": ["person", "amazon"], "caption": "A delivery driver leaves a box"}
    assert away.caption(c, "Front door", False) == "2:14 pm · Front door · A delivery driver leaves a box"
    assert away.caption(dict(c, caption=None), "Front door", True) == "14:14 · Front door · Person and package"
    assert away.fallback_caption(["dog", "cat"]) == "Dog and cat"
    assert away.camera_name("front_door") == "Front door"
    assert away.camera_name("x", "Back Gate") == "Back Gate"


def test_card_and_its_lifetime(box):
    reel = away.demo_reel(now=T0)
    assert reel["card"]["title"] == "While you were out"
    assert reel["card"]["subtitle"] == "4 h · 7 moments"
    assert away.length(45 * 60) == "45 min" and away.length(3 * 86400) == "3 days"
    tv = box / "home/tv"
    assert away.current(tv) is None
    away.write_json(away.reel_file(tv), reel)
    assert away.current(tv, now=T0)["card"]["target"] == "frigate:reel"
    assert away.current(tv, now=T0 + away.HOLD + 120) is None  # half a day later
    away.mark_seen(tv)
    assert away.current(tv, now=T0) is None


def test_home_json_names_the_card_file(box):
    settings.update({"media.frigate.url": "https://frigate.example"})
    assert home.row_json()["away"]["file"].endswith(".cache/couchbox-away/reel.json")
    settings.update({"home.away": False})
    assert home.row_json()["away"] is None


def test_the_card_opens_the_reel():
    assert ontv.split_target("frigate:reel") == ("frigate", "reel")
    try:
        ontv.split_target("frigate:camera:x")
    except ValueError:
        pass
    else:
        raise AssertionError("only the reel")
    assert ontv.launch_command("frigate", "reel", unit="u")[-3:] == ["/usr/lib/couchbox/bin/couchbox-frigate", "--open", "reel"]
