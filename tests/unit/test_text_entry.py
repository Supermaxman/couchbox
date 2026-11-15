"""CouchKit's on-screen keyboard (setup, Settings, the apps, the boot screen): the cursor never
leaves the keys, whatever the remote presses, and closing it gives the remote back.

On the test box (v0.28.0, setup's Wi-Fi password) Down from the right of the numbers row into
the shorter bottom row left the cursor past that row's end for a moment: "TextEntry.qml:49:
TypeError: Value is undefined", and the remote then did nothing."""

import os
from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtQuick")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QByteArray, QEvent, Qt, QUrl, qInstallMessageHandler  # noqa: E402
from PySide6.QtGui import QGuiApplication, QKeyEvent  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402

UI = Path(__file__).resolve().parents[2] / "ui"
SCENE = """
import QtQuick
import CouchKit
Window {
    width: 1920; height: 1080; visible: true
    property string got: ""
    property var lengths: kb.layout.map(r => r.length)
    FocusScope { id: back; objectName: "back"; anchors.fill: parent; focus: true }
    FocusScope { id: page; objectName: "page"; anchors.fill: parent }
    TextEntry { id: kb; objectName: "kb"; anchors.fill: parent; phoneDir: "/nonexistent"; fallbackFocus: page; onAccepted: t => got = t }
    // a row that had the focus, then went away while the keyboard was open (its page rebuilt)
    function openFromAGoneRow() {
        const row = Qt.createQmlObject("import QtQuick; FocusScope {}", page);
        row.forceActiveFocus();
        kb.open("", row);
        row.destroy();
    }
}
"""
KEYS = {"up": Qt.Key_Up, "down": Qt.Key_Down, "left": Qt.Key_Left, "right": Qt.Key_Right, "ok": Qt.Key_Return, "back": Qt.Key_Escape}


@pytest.fixture
def scene():
    app = QGuiApplication.instance() or QGuiApplication([])
    problems: list[str] = []

    def handler(mode, ctx, msg):
        if ("TextEntry" in msg or "Error" in msg or "undefined" in msg) and "phone.png" not in msg:
            problems.append(msg)

    old = qInstallMessageHandler(handler)
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(UI))
    engine.loadData(QByteArray(SCENE.encode()), QUrl.fromLocalFile(str(UI / "scene.qml")))
    win = engine.rootObjects()[0]
    from PySide6.QtCore import QObject

    kb = win.findChild(QObject, "kb")
    win.back = win.findChild(QObject, "back")

    def press(*names):
        for n in names:
            for t in (QEvent.KeyPress, QEvent.KeyRelease):
                QGuiApplication.sendEvent(win, QKeyEvent(t, KEYS[n], Qt.NoModifier))
            app.processEvents()

    yield app, win, kb, press, problems
    qInstallMessageHandler(old)
    win.close()


def test_every_key_every_direction_stays_on_a_key(scene):
    app, win, kb, press, problems = scene
    kb.open("", win.back)
    app.processEvents()
    lengths = [int(n) for n in win.property("lengths").toVariant()]
    for r, n in enumerate(lengths):
        for c in range(n):
            for d in ("up", "down", "left", "right"):
                kb.setProperty("row", r)
                kb.setProperty("col", c)
                press(d)
                row, col = kb.property("row"), kb.property("col")
                assert 0 <= row < len(lengths) and 0 <= col < lengths[row], (r, c, d, row, col)
    assert problems == []


def test_down_from_the_numbers_into_the_bottom_row_then_done(scene):
    """The test box's steps: the right of the numbers row, Down, then on to Done and OK."""
    app, win, kb, press, problems = scene
    kb.open("secret", win.back)
    app.processEvents()
    press(*["down"] * 2, *["right"] * 12, "down", *["right"] * 5, "ok")
    assert not kb.property("visible") and win.property("got") == "secret"
    assert win.back.property("activeFocus")  # the remote is back on the page
    assert problems == []


def test_closing_after_the_row_went_away_gives_the_remote_back(scene):
    from PySide6.QtCore import QMetaObject, QObject

    app, win, kb, press, problems = scene
    QMetaObject.invokeMethod(win, "openFromAGoneRow")
    app.processEvents()
    press("back")
    assert not kb.property("visible")
    assert win.findChild(QObject, "page").property("activeFocus")
    assert problems == []
