// The actions for a song, album, playlist or artist (the remote's Menu key): play, add to the
// queue, like, add to a playlist, go to the album or artist. Up/Down, OK, Back closes.
import QtQuick

FocusScope {
    id: m
    property var item: ({})
    property var context: ({})
    property int idx: 0
    signal closed()
    signal pick(string action)
    readonly property var actions: {
        const x = item || {};
        const a = [];
        if (x.kind === "track") {
            a.push({id: "play", label: "Play"});
            a.push({id: "queue", label: "Play next"});
            a.push({id: "like", label: S.liked[x.uri] ? "Remove from Liked Songs" : "Add to Liked Songs"});
            a.push({id: "add", label: "Add to a playlist…"});
            if (x.album && x.album.id) a.push({id: "album", label: "Go to the album"});
            for (const ar of (x.artists || []).slice(0, 2)) a.push({id: "artist:" + ar.id, label: "Go to " + ar.name});
        } else if (x.kind === "album" || x.kind === "playlist" || x.kind === "liked") {
            a.push({id: "play", label: "Play"});
            a.push({id: "shuffle", label: "Shuffle"});
            if (x.kind !== "liked") a.push({id: "open", label: "Open"});
            if (x.kind === "album") a.push({id: "save", label: S.liked[x.uri] ? "Remove from Your Library" : "Save to Your Library"});
            if ((x.tracksUris || []).length) a.push({id: "addall", label: "Add all songs to a playlist…"});
            if (x.kind === "album") for (const ar of (x.artists || []).slice(0, 2)) a.push({id: "artist:" + ar.id, label: "Go to " + ar.name});
        } else if (x.kind === "artist") {
            a.push({id: "play", label: "Play"});
            a.push({id: "shuffle", label: "Shuffle"});
            a.push({id: "open", label: "Open"});
        }
        return a;
    }
    onVisibleChanged: if (visible) idx = 0
    Keys.onUpPressed: idx = Math.max(0, idx - 1)
    Keys.onDownPressed: idx = Math.min(actions.length - 1, idx + 1)
    Keys.onReturnPressed: pick(actions[idx].id)
    Keys.onEnterPressed: pick(actions[idx].id)
    Keys.onEscapePressed: closed()
    Keys.onBackPressed: closed()
    Keys.onMenuPressed: closed()

    Rectangle { anchors.fill: parent; color: "#b0000000" }
    Rectangle {
        anchors.centerIn: parent
        width: 760 * S.u
        height: col.implicitHeight + 70 * S.u
        radius: 22 * S.u
        color: S.panel
        border.color: S.line
        Column {
            id: col
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 35 * S.u }
            spacing: 10 * S.u
            Row {
                spacing: 22 * S.u
                bottomPadding: 14 * S.u
                Art { width: 100 * S.u; height: width; item: m.item && m.item.kind === "track" ? {kind: "album", name: (m.item.album || {}).name || m.item.name, image: m.item.image} : m.item }
                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 560 * S.u
                    spacing: 6 * S.u
                    Text { width: parent.width; text: (m.item || {}).name || ""; elide: Text.ElideRight; color: S.text; font.family: S.font; font.pixelSize: S.tBody; font.weight: Font.Bold }
                    Text { width: parent.width; text: S.subtitle(m.item); elide: Text.ElideRight; color: S.dim; font.family: S.font; font.pixelSize: S.tMeta }
                }
            }
            Repeater {
                model: m.actions
                delegate: Rectangle {
                    required property var modelData
                    required property int index
                    width: col.width; height: 70 * S.u; radius: 12 * S.u
                    color: m.idx === index ? S.panel2 : "transparent"
                    border.color: m.idx === index ? S.focus : "transparent"; border.width: 3 * S.u
                    Text { anchors { left: parent.left; leftMargin: 24 * S.u; right: parent.right; rightMargin: 24 * S.u; verticalCenter: parent.verticalCenter }
                           text: modelData.label; elide: Text.ElideRight; color: S.text; font.family: S.font; font.pixelSize: S.tBody }
                }
            }
        }
    }
}
