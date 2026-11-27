// A menu's rows (the card menu's, the player's side panels'): grey pills, and the focus a white
// one that glides from row to row, the row's icon and words turning dark as it arrives.
// options: [{label, icon?, value?, checked?, trailing?, section?}]: a section's heading (Audio
// track's "Auto-dubbed") above its first row, in small grey words, not a row of its own
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
    property real sectionH: 62 * Y.u          // a section's heading, above its row
    // a row's top: the rows above it, and the headings at or above it
    function rowY(i) {
        let y = i * (rowH + gap);
        for (let j = 0; j <= i && j < options.length; j++)
            if (options[j].section) y += sectionH;
        return y;
    }
    // the white row moves (not jumps) only for a key: a new list or a menu opening puts it there
    property bool settled: false
    onOptionsChanged: { settled = false; Qt.callLater(() => { if (rows) rows.settled = true; }); }
    onVisibleChanged: if (!visible) settled = false; else Qt.callLater(() => { if (rows) rows.settled = true; })
    implicitHeight: options.length ? rowY(options.length - 1) + rowH : 0
    height: implicitHeight

    Repeater {
        model: rows.options
        Rectangle {
            required property int index
            required property var modelData
            y: rows.rowY(index)
            width: rows.width; height: rows.rowH; radius: 16 * Y.u
            color: Y.raised
            Text {
                visible: !!parent.modelData.section
                x: 0; y: -rows.sectionH + 8 * Y.u
                height: rows.sectionH - 8 * Y.u - rows.gap; verticalAlignment: Text.AlignVCenter
                text: parent.modelData.section || ""
                color: Y.dim; font.family: Y.font; font.pixelSize: 24 * Y.u; font.weight: Font.Medium
            }
        }
    }
    Rectangle {
        id: hl
        visible: rows.focused && rows.options.length > 0
        y: rows.rowY(Math.max(0, Math.min(rows.index, rows.options.length - 1)))
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
            y: rows.rowY(index)
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
