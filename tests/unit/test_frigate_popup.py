"""The Frigate pop-up: which review items pop up (cameras, labels, alerts or detections), once
each, the cooldown after one closes, how long one stays, its settings, the labels the Frigate
app offers for it, and couchbox-input handing it OK and Back only while it shows."""

import importlib.machinery
import importlib.util
import pathlib
import time

import pytest

from couchbox import frigate_popup as fp
from couchbox import settings
from couchbox.services import frigate

ROOT = pathlib.Path(__file__).resolve().parents[2]
NOW = 1_800_000_000.0


def item(rid="r1", camera="front_door", severity="alert", labels=("person",), start=NOW - 5, live=True, end=0):
    return {
        "id": rid,
        "camera": camera,
        "severity": severity,
        "labelKeys": list(labels),
        "start": start,
        "live": live,
        "end": end,
        "kinds": [{"kind": frigate.kind(x), "label": frigate.label(x)} for x in labels],
        "zones": [],
        "names": [],
    }


DEFAULTS = {"enabled": True, "cameras": [], "labels": ["person"], "severity": "alert", "seconds": 30, "cooldown": 60}


def test_filters_cameras_labels_and_severity():
    p = dict(DEFAULTS)
    assert fp.matches(item(), p)
    assert not fp.matches(item(labels=("car",)), p)
    assert not fp.matches(item(labels=()), p)  # motion only
    assert not fp.matches(item(severity="detection"), p)
    assert fp.matches(item(severity="detection"), dict(p, severity="any"))
    assert fp.matches(item(camera="garage"), p)  # no cameras chosen: all
    assert not fp.matches(item(camera="garage"), dict(p, cameras=["front_door", "driveway"]))
    assert fp.matches(item(labels=("car", "package")), dict(p, labels=["package"]))
    assert fp.matches(item(labels=()), dict(p, labels=[]))  # no labels chosen: anything


def test_only_ongoing_or_recent_items_pop():
    assert fp.fresh(item(live=True, start=NOW - 110), NOW)
    assert fp.fresh(item(live=False, start=NOW - 20, end=NOW - 10), NOW)
    assert not fp.fresh(item(live=False, start=NOW - 90, end=NOW - 60), NOW)


def test_each_item_pops_once_newest_first():
    pk, p = fp.Picker(), dict(DEFAULTS)
    items = [item("old", start=NOW - 20), item("new", camera="driveway", start=NOW - 3), item("car", labels=("car",), start=NOW - 1)]
    got = pk.pick(items, p, NOW)
    assert got["id"] == "new"
    pk.mark(got["id"], NOW)
    assert pk.pick(items, p, NOW + 2)["id"] == "old"
    pk.mark("old", NOW + 2)
    assert pk.pick(items, p, NOW + 4) is None
    # still listed: still remembered, long after it would otherwise be forgotten
    for t in range(0, 2 * fp.FORGET, 60):
        assert pk.pick(items, p, NOW + 4 + t) is None


def test_cooldown_after_a_pop_up_closes():
    pk, p = fp.Picker(), dict(DEFAULTS)
    pk.mark("a", NOW)
    pk.closed("front_door", NOW, 60)
    assert pk.pick([item("b", start=NOW + 1)], p, NOW + 2) is None  # cooling down
    assert pk.pick([item("c", camera="driveway", start=NOW + 1)], p, NOW + 2)["id"] == "c"
    assert pk.cooling(NOW + 2) == {"front_door": 58}
    # an item that came during the cooldown and is still going pops once it's over
    assert pk.pick([item("b", start=NOW + 1)], p, NOW + 61)["id"] == "b"
    assert pk.cooling(NOW + 61) == {}
    pk.closed("garage", NOW, 0)  # no cooldown
    assert pk.pick([item("d", camera="garage", start=NOW)], p, NOW + 1)["id"] == "d"


def test_how_long_a_pop_up_stays():
    assert fp.deadline(NOW, 30, NOW) == NOW + 30
    assert fp.deadline(NOW, 30, NOW + 40, live=True) == NOW + 45  # still going: a little longer
    assert fp.deadline(NOW, 30, NOW + 200, live=True) == NOW + 90  # ... at most 3 times as long
    assert fp.deadline(NOW, 30, NOW + 50, end=NOW + 40) == NOW + 45  # ended: a few seconds after
    assert fp.deadline(NOW, 30, NOW + 10, end=NOW + 2) == NOW + 30  # ended early: the usual time


def test_what_was_seen_and_the_frigate_app_in_front():
    x = dict(item(labels=("person", "dog")), zones=["Front Door"])
    assert fp.seen(x) == "Person, Dog · Front Door"
    assert fp.seen(dict(item(labels=()), kinds=[])) == "Motion"
    assert fp.is_frigate({"class": "couchbox-frigate"}) and fp.is_frigate({"app": "couchbox-frigate.desktop"})
    assert not fp.is_frigate({"class": "plasmashell", "shell": True}) and not fp.is_frigate({})


def test_settings_defaults_and_limits():
    p = fp.prefs(settings.load())
    assert p == {
        "enabled": True,
        "cameras": [],
        "labels": ["person"],
        "severity": "alert",
        "seconds": 30,
        "cooldown": 60,
        "position": "top-right",
        "size": "medium",
        "picture": "live",
    }
    settings.update({"media.frigate.popup.labels": ["person", "package"], "media.frigate.popup.position": "bottom-left"})
    assert fp.prefs(settings.load())["labels"] == ["person", "package"]
    for key, bad in [
        ("seconds", 5),
        ("seconds", 301),
        ("cooldown", -1),
        ("cooldown", 3601),
        ("severity", "all"),
        ("position", "middle"),
        ("size", "huge"),
        ("picture", "video"),
        ("cameras", [""]),
    ]:
        with pytest.raises(settings.SettingsError):
            settings.validate(fp.PREFIX + key, bad)


def test_the_flag_lives_next_to_the_control_socket(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    if fp.flag_path().parent != tmp_path / "couchbox":  # root: the TV user's
        pytest.skip("running as root")
    assert fp.flag_path() == tmp_path / "couchbox" / "frigate-popup.shown"


def test_review_items_carry_frigates_own_labels():
    f = frigate.Frigate(demo=True)
    r = f._review_item(
        {
            "id": "x",
            "camera": "front_door",
            "start_time": NOW,
            "end_time": None,
            "data": {"objects": ["person-verified", "car"], "audio": ["speech"], "sub_labels": ["Max"], "zones": []},
        }
    )
    assert r["labelKeys"] == ["person", "car", "speech"]
    assert r["objects"] == ["Max", "Person Verified", "Car", "Speech"]  # as before
    demo = {x["id"]: x for x in f.reviews("all")["items"]}
    assert demo["demo-0"]["labelKeys"] == ["person", "dog"]
    # the demo's live alert at the front door is what pops up with the default settings
    assert fp.Picker().pick(list(demo.values()), fp.prefs(settings.load()), time.time())["camera"] == "front_door"


def test_config_lists_what_the_cameras_track():
    labels = frigate.Frigate(demo=True).config()["labels"]
    names = [x["name"] for x in labels]
    assert names[:4] == ["person", "dog", "cat", "bird"]  # the cameras in order: backyard_side_gate first
    assert {"bicycle", "license_plate", "speech", "bark"} <= set(names) and len(names) == len(set(names))
    assert {"name": "speech", "label": "Speech", "kind": "audio"} in labels
    assert {"name": "license_plate", "label": "License Plate", "kind": "license_plate"} in labels
    # audio detection off: its labels aren't offered; nothing tracked at all: the common ones
    cfg = {"cameras": {"a": {"objects": {"track": ["person"]}, "audio": {"enabled": False, "listen": ["speech"]}}}}
    assert [x["name"] for x in frigate.tracked(cfg, ["a"])] == ["person"]
    assert [x["name"] for x in frigate.tracked({"cameras": {"a": {}}}, ["a"])] == list(frigate.COMMON_LABELS)


# ------------------------------------------------------------------ couchbox-input
def load_input(monkeypatch):
    pytest.importorskip("evdev")
    loader = importlib.machinery.SourceFileLoader("couchbox_input", str(ROOT / "bin/couchbox-input"))
    spec = importlib.util.spec_from_loader("couchbox_input", loader)
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setenv("COUCHBOX_INPUT_CONFIG", str(ROOT / "data/input/default.toml"))
    loader.exec_module(mod)
    return mod


def test_ok_and_back_are_mapped_through_the_pop_up(monkeypatch):
    mod = load_input(monkeypatch)
    e = mod.e
    sections = dict((name, km) for name, _, km in mod.load_sections(str(ROOT / "data/input/default.toml")))
    for sec in ("fire-remote", "tv-remote-cec"):
        keymap = sections[sec][0]
        assert keymap[e.KEY_SELECT] == ("popup", e.KEY_ENTER)
        assert keymap[e.KEY_ENTER] == ("popup", e.KEY_ENTER)
        assert keymap[e.KEY_BACK] == ("voice", e.KEY_ESC)
    assert sections["fire-remote"][0][e.KEY_KPENTER] == ("popup", e.KEY_ENTER)
    assert sections["tv-remote-cec"][0][e.KEY_OK] == ("popup", e.KEY_ENTER)


def test_couchbox_input_asks_the_pop_up_only_while_it_shows(monkeypatch, tmp_path):
    from couchbox import appctl

    mod = load_input(monkeypatch)
    flag = tmp_path / "frigate-popup.shown"
    monkeypatch.setitem(mod._popup, "flag", str(flag))
    asked = []

    def answer(reply):
        def call(site, req, timeout=30):
            asked.append((site, req, timeout))
            if isinstance(reply, Exception):
                raise reply
            return reply

        return call

    monkeypatch.setattr(appctl, "call", answer({"handled": True, "did": "opened Front Door"}))
    assert mod.popup_key("ok") is False and not asked  # no flag: not even asked
    flag.write_text("{}")
    assert mod.popup_key("ok") == "opened Front Door"
    assert asked[-1][:2] == ("frigate-popup", {"op": "key", "key": "ok"}) and asked[-1][2] <= 1
    monkeypatch.setattr(appctl, "call", answer({"handled": True, "did": "dismissed Front Door"}))
    assert mod.popup_key("back")
    assert flag.exists()  # the service removes it, not this
    # a leftover flag (the service crashed, or isn't showing anything): it goes, the key goes on
    monkeypatch.setattr(appctl, "call", answer(appctl.NotRunning("frigate-popup")))
    assert mod.popup_key("back") is False and not flag.exists()
    flag.write_text("{}")
    monkeypatch.setattr(appctl, "call", answer({"handled": False}))
    assert mod.popup_key("ok") is False and not flag.exists()
    flag.write_text("{}")
    monkeypatch.setattr(appctl, "call", answer(TimeoutError("timed out")))
    assert mod.popup_key("ok") is False and not flag.exists()
