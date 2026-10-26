// A short list of things to do with a place (Directions, Leave by…, Save, Rename…), over the page.
// Up/Down move, OK picks, Back closes.
import QtQuick

FocusScope {
    id: sheet
    property string title: ""
    property string sub: ""
    property var actions: []                 // [{label, icon, act: function, danger}]
    property int idx: 0
    property Item back: null                 // focus goes back here
    visible: false
    z: 150
    function open(t, s, acts, from) {
        title = t; sub = s || ""; actions = acts; idx = 0; back = from;
        visible = true; forceActiveFocus();
    }
    function close() { visible = false; if (back) back.forceActiveFocus(); }
    Keys.onUpPressed: idx = Math.max(0, idx - 1)
    Keys.onDownPressed: idx = Math.min(actions.length - 1, idx + 1)
    Keys.onReturnPressed: pick()
    Keys.onEnterPressed: pick()
    Keys.onEscapePressed: close()
    Keys.onBackPressed: close()
    function pick() { const a = actions[idx]; close(); if (a && a.act) a.act(); }

    Rectangle { anchors.fill: parent; color: "#b3000000" }
    Rectangle {
        anchors.centerIn: parent
        width: 760 * M.u
        height: col.implicitHeight + 80 * M.u
        radius: 22 * M.u
        color: M.panel; border.color: M.line
        Column {
            id: col
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 40 * M.u }
            spacing: 14 * M.u
            Text { width: parent.width; text: sheet.title; color: M.text; font.family: M.font; font.pixelSize: 36 * M.u; font.weight: Font.Bold; elide: Text.ElideRight }
            Text { width: parent.width; visible: !!sheet.sub; text: sheet.sub; color: M.dim; font.family: M.font; font.pixelSize: M.tMeta; wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight }
            Item { width: 1; height: 8 * M.u }
            Repeater {
                model: sheet.actions
                delegate: Rectangle {
                    required property var modelData
                    required property int index
                    readonly property bool cur: sheet.idx === index
                    width: col.width; height: 76 * M.u; radius: 12 * M.u
                    color: cur ? M.panel2 : "transparent"
                    border.color: cur ? M.focus : "transparent"; border.width: 3 * M.u
                    Image {
                        id: aic
                        x: 22 * M.u; anchors.verticalCenter: parent.verticalCenter
                        width: 32 * M.u; height: width; sourceSize: Qt.size(width, height)
                        source: M.icon(parent.modelData.icon || "pin")
                    }
                    Text {
                        anchors { left: aic.right; leftMargin: 20 * M.u; right: parent.right; rightMargin: 20 * M.u; verticalCenter: parent.verticalCenter }
                        text: parent.modelData.label
                        color: parent.modelData.danger ? M.heavy : M.text
                        font.family: M.font; font.pixelSize: 28 * M.u; font.weight: parent.cur ? Font.DemiBold : Font.Normal
                        elide: Text.ElideRight
                    }
                }
            }
        }
    }
}
