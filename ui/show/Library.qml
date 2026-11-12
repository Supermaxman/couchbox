// The Reels app's list (couchbox-show --reels): every kept reel (couchbox.reels), newest first,
// four across, under the week or month they're from. The arrows move, OK plays the one in focus
// (played()), Back leaves (leave()).
import QtQuick

FocusScope {
    id: lib
    property var groups: []                  // [{name, reels: [{id, kind, title, day, span, art, first}]}]
    property bool loading: true
    readonly property int cols: 4
    // the rows the arrows move through: [{g: group index, items: [reel...], first: index of the first in the group}]
    readonly property var rows: {
        const out = [];
        groups.forEach((g, gi) => {
            for (let i = 0; i < g.reels.length; i += cols) out.push({g: gi, from: i, items: g.reels.slice(i, i + cols)});
        });
        return out;
    }
    property int ri: 0
    property int ci: 0
    readonly property var current: rows[ri] ? rows[ri].items[Math.min(ci, rows[ri].items.length - 1)] : null
    signal played(var reel)
    signal leave()

    function load(keep) {
        S.call("reels", {}, r => {
            lib.rowItems = [];
            lib.groups = r.groups;
            lib.loading = false;
            if (!keep) { ri = 0; ci = 0; }
            ri = Math.min(ri, Math.max(0, rows.length - 1));
            place();
        }, () => { lib.loading = false; });
    }
    function move(dr, dc) {
        if (!rows.length) return;
        if (dc) ci = Math.max(0, Math.min(rows[ri].items.length - 1, ci + dc));
        if (dr) {
            const r = ri + dr;
            if (r < 0 || r >= rows.length) return;
            ri = r;
            ci = Math.min(ci, rows[ri].items.length - 1);
        }
        place();
    }
    function place() {                       // the row in focus in view (its group's name too, at a group's top)
        const row = rowItems[ri];
        if (!row) { flick.contentY = 0; return; }
        const top = row.y;                   // (a group's first row starts with its name)
        const bottom = row.y + row.height + 40 * S.u;
        // whole rows only: one that isn't all in view comes to the top (nothing cut off above it)
        if (ri === 0) flick.contentY = 0;
        else if (top < flick.contentY || bottom > flick.contentY + flick.height) flick.contentY = Math.max(0, top);
    }
    property var rowItems: []

    Keys.onLeftPressed: move(0, -1)
    Keys.onRightPressed: move(0, 1)
    Keys.onUpPressed: move(-1, 0)
    Keys.onDownPressed: move(1, 0)
    Keys.onReturnPressed: if (current) played(current)
    Keys.onEnterPressed: if (current) played(current)
    Keys.onEscapePressed: leave()
    Keys.onBackPressed: leave()

    Rectangle { anchors.fill: parent; color: "#0b0c0f" }

    Text {
        id: heading
        x: S.side; y: 64 * S.u
        text: "Reels"
        color: S.text
        font.family: S.font; font.pixelSize: 52 * S.u; font.weight: Font.Bold
    }

    Flickable {
        id: flick
        anchors { left: parent.left; right: parent.right; top: heading.bottom; bottom: parent.bottom; topMargin: 8 * S.u }
        contentHeight: col.height + 80 * S.u
        interactive: false
        clip: true
        Behavior on contentY { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
        Column {
            id: col
            x: S.side
            width: lib.width - 2 * S.side
            Repeater {
                model: lib.rows
                delegate: Item {
                    id: row
                    required property var modelData
                    required property int index
                    readonly property bool opens: modelData.from === 0     // the first row of a group: its name above
                    readonly property real headH: opens ? name.height + 22 * S.u + (index > 0 ? 34 * S.u : 18 * S.u) : 0
                    readonly property real cardW: (col.width - (lib.cols - 1) * gap) / lib.cols
                    readonly property real gap: 32 * S.u
                    width: col.width
                    height: headH + cards.height + 40 * S.u
                    Component.onCompleted: { const a = lib.rowItems.slice(); a[index] = row; lib.rowItems = a; }
                    Text {
                        id: name
                        visible: row.opens
                        y: row.index > 0 ? 34 * S.u : 18 * S.u
                        text: row.opens ? lib.groups[row.modelData.g].name : ""
                        color: S.text2
                        font.family: S.font; font.pixelSize: 30 * S.u; font.weight: Font.DemiBold
                    }
                    Row {
                        id: cards
                        y: row.headH
                        spacing: row.gap
                        Repeater {
                            model: row.modelData.items
                            delegate: Item {
                                id: card
                                required property var modelData
                                required property int index
                                readonly property bool here: lib.activeFocus && lib.ri === row.index && Math.min(lib.ci, row.modelData.items.length - 1) === index
                                width: row.cardW
                                height: pic.height + 22 * S.u + title.implicitHeight + 6 * S.u + meta.implicitHeight
                                opacity: lib.activeFocus && !here ? 0.62 : 1
                                Behavior on opacity { NumberAnimation { duration: 180 } }
                                Rectangle {
                                    id: pic
                                    width: parent.width; height: Math.round(width * 9 / 16)
                                    radius: 14 * S.u
                                    color: S.panel
                                    clip: true
                                    Image {                          // made-up reels (screenshots) have no picture
                                        anchors.centerIn: parent
                                        visible: still.status !== Image.Ready
                                        width: 72 * S.u; height: width
                                        opacity: 0.16
                                        sourceSize: S.sz(width, height)
                                        source: Qt.resolvedUrl("../frigate/icons/" + (card.modelData.first || "object") + ".svg")
                                    }
                                    Image {
                                        id: still
                                        anchors.fill: parent
                                        source: card.modelData.art ? "file://" + card.modelData.art : ""
                                        sourceSize: S.sz(width, height)
                                        fillMode: Image.PreserveAspectCrop
                                        asynchronous: true
                                    }
                                    Rectangle {                      // focus ring
                                        anchors.fill: parent
                                        radius: parent.radius
                                        color: "transparent"
                                        border.color: "white"
                                        border.width: 4 * S.u
                                        visible: card.here
                                    }
                                }
                                Text {
                                    id: title
                                    anchors { top: pic.bottom; topMargin: 22 * S.u }
                                    width: parent.width
                                    text: card.modelData.title
                                    color: S.text
                                    elide: Text.ElideRight
                                    font.family: S.font; font.pixelSize: 30 * S.u; font.weight: Font.DemiBold
                                }
                                Text {
                                    id: meta
                                    anchors { top: title.bottom; topMargin: 6 * S.u }
                                    width: parent.width
                                    text: card.modelData.day + "  ·  " + card.modelData.span
                                    color: S.dim
                                    elide: Text.ElideRight
                                    font.family: S.font; font.pixelSize: 24 * S.u
                                    font.features: {"tnum": 1}
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    Text {
        anchors.centerIn: parent
        visible: !lib.loading && !lib.rows.length
        text: "No reels yet"
        color: S.dim
        font.family: S.font; font.pixelSize: 36 * S.u
    }
}
