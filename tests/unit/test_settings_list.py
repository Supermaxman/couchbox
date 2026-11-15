"""Settings and setup lists refresh in place: when a page rebuilds its rows (a Wi-Fi scan every
few seconds), rows that stay are the same items, nothing flashes, and the cursor stays on the
same row even when rows above it come, go or move. On the test box each scan rebuilt the list,
the focus dropped or jumped, and the owner took it for the remote not working."""

import json
import os
from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtQuick")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QByteArray, QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402

UI = Path(__file__).resolve().parents[2] / "ui"
SCENE = """
import QtQuick
import "settings"
Window {
    width: 1280; height: 1080; visible: true
    property string result: ""
    property int choiceIndex: choice.list.currentIndex
    SettingsPage { id: page; anchors.fill: parent; focus: true; showHeading: false }
    function net(n, v) { return {kind: "action", label: n, value: v || "", act: () => {}}; }
    function check(tag) {
        const l = page.list;
        return {tag: tag, cur: l.currentIndex, label: page.rows[l.currentIndex].label, item: l.currentItem};
    }
    function trial() {
        const out = [];
        page.rows = [T.info("You're online", "", {key: "status"}), net("Home"), net("Neighbours"), net("Cafe")];
        page.list.currentIndex = 2;                                   // on Neighbours
        const before = check("start");
        page.rows = [T.info("You're online", "", {key: "status"}), net("NETGEAR"), net("Cafe", "35%"), net("Home"), net("Neighbours", "61%")];
        const after = check("reordered");
        out.push({cur: after.cur, label: after.label, same: after.item === before.item});
        page.rows = [T.info("Not online yet", "", {key: "status"}), net("Home"), net("Cafe")];   // Neighbours gone
        out.push(check("gone"));
        result = JSON.stringify(out.map(x => ({cur: x.cur, label: x.label, same: x.same})));
    }
    // a page opening on a choice already made (Updates: Manual, from the preseed)
    SettingsPage { id: choice; objectName: "choice"
        rows: [{kind: "action", label: "Automatic", act: () => {}}, {kind: "action", label: "Manual", current: true, act: () => {}}] }
}
"""


def test_refresh_keeps_rows_and_the_cursor():
    from PySide6.QtCore import QMetaObject

    app = QGuiApplication.instance() or QGuiApplication([])
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(UI))
    engine.loadData(QByteArray(SCENE.encode()), QUrl.fromLocalFile(str(UI / "scene.qml")))
    win = engine.rootObjects()[0]
    app.processEvents()
    QMetaObject.invokeMethod(win, "trial")
    app.processEvents()
    reordered, gone = json.loads(win.property("result"))
    assert reordered == {"cur": 4, "label": "Neighbours", "same": True}  # moved with its row, the same item
    assert gone["label"] in ("Cafe", "Home") and gone["cur"] in (1, 2)  # its row went: the nearest one
    assert win.property("choiceIndex") == 1  # starts on Manual
    win.close()
