"""qtcheck: a focused card that grows past a clipping list is reported; one with room isn't."""

import os

import pytest

pytest.importorskip("PySide6.QtQuick")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QByteArray, QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402

from couchbox import qtcheck  # noqa: E402

SCENE = """
import QtQuick
Window {
    width: 800; height: 400; visible: true
    ListView {
        objectName: "list"
        x: 100; y: 50; width: 600; height: 300
        clip: true
        orientation: ListView.Horizontal
        spacing: 20
        leftMargin: %(pad)s
        model: 3
        delegate: Item {
            width: 150; height: 300
            Rectangle { objectName: "card" + index; y: 50; width: 150; height: 200; scale: index === 0 ? 1.1 : 1 }
        }
    }
}
"""


def _clipped(pad):
    app = QGuiApplication.instance() or QGuiApplication([])
    engine = QQmlApplicationEngine()
    engine.loadData(QByteArray((SCENE % {"pad": pad}).encode()), QUrl("inline.qml"))
    win = engine.rootObjects()[0]
    app.processEvents()
    lines = []
    found = [(item.objectName(), clipper.objectName(), cut) for item, clipper, cut in qtcheck.clipped(win, log=lines.append)]
    win.close()
    return found, lines


def test_a_grown_first_card_cut_off_by_its_list_is_reported():
    found, lines = _clipped(0)
    assert len(found) == 1
    item, clipper, cut = found[0]
    assert (item, clipper) == ("card0", "list")
    assert cut[0] == pytest.approx(7.5, abs=0.6)  # 150 * 0.1 / 2 at the left
    assert lines and lines[0].startswith("focus-clip: card0")


def test_room_at_the_edge_is_fine():
    found, lines = _clipped(12)
    assert found == [] and lines == []
