"""Every MpvVideo function the QML calls (video.x(...), Y.video.x(...)) is one QML can call: a Slot
of couchbox.player.MpvVideo (the stop() that lost its decorator stopped no video in any app)."""

import re
from pathlib import Path

import pytest

UI = Path(__file__).resolve().parents[2] / "ui"


def called():
    names = set()
    for f in UI.rglob("*.qml"):
        if "stubs" in f.parts:
            continue
        names |= set(re.findall(r"\bvideo\.([a-zA-Z]+)\(", f.read_text()))
    return names


def test_qml_calls_only_slots():
    player = pytest.importorskip("couchbox.player")
    mo = player.MpvVideo.staticMetaObject
    slots = {bytes(mo.method(i).name()).decode() for i in range(mo.methodCount())}
    missing = sorted(n for n in called() if n not in slots)
    assert not missing, f"called from QML but not Slots: {missing}"


def test_the_stub_has_them_too():
    stub = (UI / "stubs/CouchPlayer/MpvVideo.qml").read_text()
    missing = sorted(n for n in called() if not re.search(rf"function {n}\(", stub))
    assert not missing, f"missing from the QML stub (screenshots): {missing}"
