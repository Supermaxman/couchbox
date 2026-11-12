"""Today at home (couchbox.dayreel) and the reels kept for the Reels app (couchbox.reels)."""

import datetime

from couchbox import away, dayreel, home, ontv, reels, settings

THU = datetime.date(2026, 11, 12)  # a Thursday
SAT = datetime.date(2026, 11, 14)
H = 3600


def at(day, hour, minute=0):
    return datetime.datetime(day.year, day.month, day.day, hour, minute).timestamp()


def row(i, cam, objs, start, dur=20):
    return {"id": f"r{i}", "camera": cam, "severity": "detection", "start_time": start, "end_time": start + dur, "data": {"objects": objs}}


SIDE = {"front": True, "yard": True, "lounge": False, "kitchen": False}


# ------------------------------------------------------------------ when
def test_weekdays_seven_to_three_by_default():
    s = settings.load()
    assert dayreel.window(THU, s) == (at(THU, 7), at(THU, 15))
    assert dayreel.window(SAT, s) is None
    assert dayreel.window(THU, dict(s, **{"home.day": False})) is None
    assert dayreel.window(THU, dict(s, **{"home.day_from": 9, "home.day_to": 24}))[1] == at(THU + datetime.timedelta(days=1), 0)


def test_made_once_the_hours_are_over():
    s = settings.load()
    assert dayreel.making_time(at(THU, 14, 59), s) is None
    assert dayreel.making_time(at(THU, 15, 1), s) is None  # (the last items still closing)
    assert dayreel.making_time(at(THU, 15, 10), s) == (at(THU, 7), at(THU, 15))
    assert dayreel.making_time(at(THU, 22), s) is not None  # (the box was off at three)
    assert dayreel.making_time(at(SAT, 16), s) is None


# ------------------------------------------------------------------ what goes in
def test_people_and_pets_at_home_not_deliveries():
    start, end = at(THU, 7), at(THU, 15)
    rows = [
        row(1, "lounge", ["person"], at(THU, 9)),  # someone at home: in (While you were out leaves them out)
        row(2, "kitchen", ["cat"], at(THU, 10)),
        row(3, "yard", ["dog"], at(THU, 11)),  # the dog in the yard
        row(4, "yard", ["person", "dog"], at(THU, 11, 30)),  # playing with the dog outside
        row(5, "front", ["person", "package"], at(THU, 12)),  # a delivery: While you were out's
        row(6, "front", ["car"], at(THU, 13)),
        row(7, "lounge", ["person"], at(THU, 6)),  # before the hours
        row(8, "lounge", ["dog"], at(THU, 16)),  # after
    ]
    got = {c["id"]: c["section"] for c in dayreel.candidates(rows, SIDE, start, end)}
    assert got == {"r1": "home", "r2": "home", "r3": "home", "r4": "home"}
    # While you were out still leaves people inside out
    assert "r1" not in {c["id"] for c in away.candidates(rows, SIDE, start - H, end + H)}


def test_the_question_asks_for_sweet_moments():
    c = {"objects": ["dog", "person"], "section": "home"}
    q = dayreel.look_prompt(c, "Living room", False)
    assert "sweet or fun" in q and "inside the house" in q and "Living room" in q
    assert "outside" in dayreel.look_prompt({"objects": ["dog"]}, "Yard", True)


# ------------------------------------------------------------------ the card
def test_card_until_the_next_morning_or_watched(box):
    tv = box / "home/tv"
    entry = dayreel.demo_reel(at(THU, 15, 10))
    made = at(THU, 15, 10)
    dayreel.offer(entry, False, now=made, home=tv)
    c = dayreel.current(tv, now=at(THU, 19))["card"]
    assert c["title"] == "Today at home" and c["subtitle"] == "7 am – 3 pm · 7 moments"
    assert c["target"] == f"reels:{entry['id']}" and c["app"] == "reels"
    assert dayreel.made_today(tv, now=at(THU, 20))
    assert dayreel.current(tv, now=at(THU + datetime.timedelta(days=1), 4, 1)) is None  # the next morning
    dayreel.mark_seen("day-1", home=tv)  # another reel: no change
    assert dayreel.current(tv, now=at(THU, 19))
    dayreel.mark_seen(entry["id"], home=tv)
    assert dayreel.current(tv, now=at(THU, 19)) is None


def test_a_day_with_nothing_has_no_card_but_counts_as_made(box):
    tv = box / "home/tv"
    dayreel.offer(None, False, now=at(THU, 15, 10), home=tv)
    assert dayreel.current(tv, now=at(THU, 16)) is None and dayreel.made_today(tv, now=at(THU, 16))
    assert not dayreel.made_today(tv, now=at(THU + datetime.timedelta(days=1), 16))


def test_home_json_and_the_card_opens_the_reels_app(box):
    settings.update({"media.frigate.url": "https://frigate.example"})
    assert home.row_json()["day"]["file"].endswith(".cache/couchbox-reels/today.json")
    assert "reels" in [a["app"] for a in home.row_json()["apps"]]
    settings.update({"home.day": False})
    assert home.row_json()["day"] is None
    assert ontv.split_target("reels:day-1794006000") == ("reels", "day-1794006000")
    for bad in ("reels:../x", "reels:"):
        try:
            ontv.split_target(bad)
        except ValueError:
            continue
        raise AssertionError(bad)
    assert ontv.launch_command("reels", "day-1794006000", unit="u")[-3:] == [
        "/usr/lib/couchbox/bin/couchbox-reels",
        "--open",
        "day-1794006000",
    ]


# ------------------------------------------------------------------ kept reels
def clip(d, name, review):
    f = d / f"{name}.mp4"
    f.write_bytes(b"x" * 1000)
    p = d / f"{name}.jpg"
    p.write_bytes(b"j")
    return {"file": str(f), "poster": str(p), "review": {"id": review, "objects": ["dog"]}, "camera": "lounge"}


def test_kept_reels_survive_the_cards_files(box):
    tv = box / "home/tv"
    cache = tv / ".cache/couchbox-away"
    cache.mkdir(parents=True)
    clips = [clip(cache, "a", "r1"), clip(cache, "b", "r2")]
    e = reels.save("away", clips, at(THU, 8), at(THU, 18), home=tv)
    assert e["id"] == f"away-{int(at(THU, 18))}"
    away.clear(tv)  # the card's copies go
    kept = reels.get(e["id"], tv)
    assert [open(c["file"], "rb").read() for c in kept["clips"]] == [b"x" * 1000] * 2
    assert reels.ids("away", THU, tv) == {"r1", "r2"} and reels.ids("day", THU, tv) == set()
    assert reels.get("../../etc", tv) is None
    assert reels.save("away", [], 0, 1, home=tv) is None


def test_the_oldest_go_past_the_limit(box):
    tv = box / "home/tv"
    src = tv / "src"
    src.mkdir(parents=True)
    for i in range(4):
        reels.save("day", [clip(src, f"c{i}", f"r{i}")], at(THU, 7) - i * 86400, at(THU, 15) - i * 86400, home=tv)
    reels.prune(tv, keep=3200)  # two reels' worth
    assert [r["id"] for r in reels.all_reels(tv)] == [f"day-{int(at(THU, 15))}", f"day-{int(at(THU, 15) - 86400)}"]


def test_how_the_reels_app_lists_them():
    now = at(THU, 20)
    day = {"id": "day-1", "kind": "day", "since": at(THU, 7), "until": at(THU, 15), "clips": [{"poster": "/p.jpg"}]}
    x = reels.listing(day, False, now=now)
    assert (x["title"], x["day"], x["span"], x["art"]) == ("Today at home", "Today", "7 am – 3 pm", "/p.jpg")
    old = dict(day, since=at(THU, 7) - 9 * 86400, until=at(THU, 15) - 9 * 86400)
    x = reels.listing(old, True, now=now)
    assert (x["title"], x["day"], x["span"]) == ("At home", "Tue, Nov 3", "07:00 – 15:00")
    out = {"id": "away-1", "kind": "away", "since": at(THU, 9), "until": at(THU, 13), "clips": [{}]}
    assert reels.listing(out, False, now=now)["span"] == "4 h out"
    assert reels.group(day, now) == "This week"
    assert reels.group(dict(day, until=at(THU, 12) - 7 * 86400), now) == "Last week"
    assert reels.group(dict(day, until=at(datetime.date(2026, 10, 2), 12)), now) == "October"
    assert reels.group(dict(day, until=at(datetime.date(2025, 10, 2), 12)), now) == "October 2025"
    assert reels.hours(at(THU, 7, 30), at(THU, 15), False) == "7:30 am – 3 pm"
