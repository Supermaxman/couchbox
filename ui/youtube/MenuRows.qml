// A menu's rows (the card menu's, the player's side panels'): grey pills, and the focus a white
// one that glides from row to row, the row's icon and words turning dark as it arrives.
// options: [{label, icon?, value?, checked?, trailing?}]
import QtQuick

Item {
    id: rows
    property var options: []
    property int index: 0
    property bool focused: true               // the focus is on the menu (else no white row)
    property real rowH: 84 * Y.u
    property real gap: 14 * Y.u
    property real iconX: 28 * Y.u
    property real iconSize: 36 * Y.u
    property real textX: 90 * Y.u             // the words, with an icon
    property real plainX: iconX               // ... and without one
    property real textSize: 30 * Y.u
    property int weight: Font.Medium
    property real trailSize: 36 * Y.u
    // the white row moves (not jumps) only for a key: a new list or a menu opening puts it there
    property bool settled: false
    onOptionsChanged: { settled = false; Qt.callLater(() => { if (rows) rows.settled = true; }); }
    onVisibleChanged: if (!visible) settled = false; else Qt.callLater(() => { if (rows) rows.settled = true; })
    implicitHeight: options.length ? options.length * rowH + (options.length - 1) * gap : 0
    height: implicitHeight

    Repeater {
        model: rows.options
        Rectangle {
            required property int index
            y: index * (rows.rowH + rows.gap)
            width: rows.width; height: rows.rowH; radius: 16 * Y.u
            color: Y.raised
        }
    }
    Rectangle {
        id: hl
        visible: rows.focused && rows.options.length > 0
        y: Math.max(0, Math.min(rows.index, rows.options.length - 1)) * (rows.rowH + rows.gap)
        width: rows.width; height: rows.rowH; radius: 16 * Y.u
        color: Y.text
        Behavior on y { enabled: rows.settled; NumberAnimation { duration: Y.tFocus; easing.type: Easing.OutCubic } }
    }
    Repeater {
        model: rows.options
        Item {
            id: r
            required property var modelData
            required property int index
            readonly property bool on: rows.focused && rows.index === index
            property color ink: on ? Y.ink : Y.text
            Behavior on ink { enabled: rows.settled; ColorAnimation { duration: Y.tFocus } }
            y: index * (rows.rowH + rows.gap)
            width: rows.width; height: rows.rowH
            Icon {
                visible: !!r.modelData.icon
                x: rows.iconX; anchors.verticalCenter: parent.verticalCenter
                name: r.modelData.icon || ""; size: rows.iconSize; color: r.ink
            }
            Text {
                anchors { left: parent.left; leftMargin: r.modelData.icon ? rows.textX : rows.plainX; right: parent.right; rightMargin: 84 * Y.u; verticalCenter: parent.verticalCenter }
                text: r.modelData.label; elide: Text.ElideRight
                color: r.ink; font.family: Y.font; font.pixelSize: rows.textSize; font.weight: rows.weight
            }
            Text {
                visible: !!r.modelData.value
                anchors { right: parent.right; rightMargin: 28 * Y.u; verticalCenter: parent.verticalCenter }
                text: r.modelData.value || ""
                color: r.on ? "#606060" : Y.dim
                font.family: Y.font; font.pixelSize: 26 * Y.u
            }
            Icon {
                visible: !!r.modelData.checked || !!r.modelData.trailing
                anchors { right: parent.right; rightMargin: 28 * Y.u; verticalCenter: parent.verticalCenter }
                name: r.modelData.trailing || "check"; size: rows.trailSize; color: r.ink
            }
        }
    }
}
