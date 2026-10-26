// Add songs to one of your playlists, or a new one (its name typed with the keyboard pop-up).
import QtQuick

FocusScope {
    id: p
    property var uris: []
    property string what: ""                 // "Northern Lights" or "12 songs"
    property var playlists: []
    property int idx: 0
    property bool busy: false
    signal closed()
    signal askName()
    readonly property var rows: [{id: "new", name: "New playlist…"}].concat(playlists)
    function load() {
        idx = 0; busy = true;
        S.call("my_playlists", {}, r => { p.playlists = r.filter(x => x.mine || x.collaborative); p.busy = false; }, e => { p.busy = false; S.toast(e); });
    }
    function addTo(pl) {
        S.call("add_to_playlist", {id: pl.id, uris: uris}, () => { S.toast("Added " + what + " to " + pl.name + "."); p.closed(); });
    }
    function create(name) {
        if (!name) return;
        S.call("create_playlist", {name: name}, pl => p.addTo(pl));
    }
    Keys.onUpPressed: idx = Math.max(0, idx - 1)
    Keys.onDownPressed: idx = Math.min(rows.length - 1, idx + 1)
    Keys.onReturnPressed: idx === 0 ? askName() : addTo(rows[idx])
    Keys.onEnterPressed: idx === 0 ? askName() : addTo(rows[idx])
    Keys.onEscapePressed: closed()
    Keys.onBackPressed: closed()

    Rectangle { anchors.fill: parent; color: "#b0000000" }
    Rectangle {
        anchors.centerIn: parent
        width: 820 * S.u; height: Math.min(parent.height - 160 * S.u, 220 * S.u + p.rows.length * 80 * S.u)
        radius: 22 * S.u
        color: S.panel
        border.color: S.line
        Text { id: h; x: 40 * S.u; y: 36 * S.u; width: parent.width - 80 * S.u; elide: Text.ElideRight
               text: "Add " + p.what + " to"; color: S.text; font.family: S.font; font.pixelSize: S.tHead; font.weight: Font.Bold }
        ListView {
            anchors { left: parent.left; right: parent.right; top: h.bottom; bottom: parent.bottom; margins: 30 * S.u }
            clip: true
            interactive: false
            model: p.rows
            currentIndex: p.idx
            spacing: 8 * S.u
            highlightRangeMode: ListView.ApplyRange
            preferredHighlightBegin: 80 * S.u; preferredHighlightEnd: height - 160 * S.u
            delegate: Rectangle {
                required property var modelData
                required property int index
                width: ListView.view.width; height: 72 * S.u; radius: 12 * S.u
                color: p.idx === index ? S.panel2 : "transparent"
                border.color: p.idx === index ? S.focus : "transparent"; border.width: 3 * S.u
                Art { id: a; visible: index > 0; x: 14 * S.u; anchors.verticalCenter: parent.verticalCenter; width: 52 * S.u; height: width; item: modelData }
                Image { visible: index === 0; x: 22 * S.u; anchors.verticalCenter: parent.verticalCenter; width: 36 * S.u; height: width; sourceSize: Qt.size(width, height); source: S.icon("plus") }
                Text { anchors { left: parent.left; leftMargin: 86 * S.u; right: parent.right; rightMargin: 20 * S.u; verticalCenter: parent.verticalCenter }
                       text: modelData.name; elide: Text.ElideRight; color: index === 0 ? S.accent : S.text; font.family: S.font; font.pixelSize: S.tBody }
            }
        }
        Text { anchors.centerIn: parent; visible: p.busy; text: "Loading your playlists…"; color: S.dim; font.family: S.font; font.pixelSize: S.tBody }
    }
}
