// One song in a list: number (or bars when it's playing), art, name, artists, album, a heart
// when it's in Liked Songs, and its length.
import QtQuick

Rectangle {
    id: row
    property var t: ({})
    property int num: 0
    property bool current: false
    property bool showArt: true
    property bool showAlbum: true
    readonly property bool isNow: !!t.uri && S.nowUri === t.uri
    height: 96 * S.u
    radius: 10 * S.u
    color: current ? S.panel2 : "transparent"
    border.color: current ? S.focus : "transparent"
    border.width: 3 * S.u

    Item {
        id: numBox
        x: 18 * S.u; width: 50 * S.u; height: parent.height
        Text { anchors.centerIn: parent; visible: !row.isNow; text: row.num; color: S.dim; font.family: S.font; font.pixelSize: S.tMeta }
        Image { anchors.centerIn: parent; visible: row.isNow; width: 30 * S.u; height: width; sourceSize: Qt.size(width, height); source: S.icon(S.playing ? "bars-green" : "note-green") }
    }
    Art {
        id: art
        visible: row.showArt
        anchors { left: numBox.right; leftMargin: 14 * S.u; verticalCenter: parent.verticalCenter }
        width: row.showArt ? 66 * S.u : 0; height: width
        item: ({kind: "album", name: (row.t.album || {}).name || row.t.name, image: row.t.image})
    }
    Column {
        anchors { left: art.right; leftMargin: row.showArt ? 22 * S.u : 0; right: albumText.left; rightMargin: 24 * S.u; verticalCenter: parent.verticalCenter }
        spacing: 4 * S.u
        Text { width: parent.width; text: row.t.name || ""; elide: Text.ElideRight
               color: row.isNow ? S.accent : row.t.playable === false ? S.faint : S.text; font.family: S.font; font.pixelSize: S.tBody; font.weight: Font.DemiBold }
        Row {
            width: parent.width
            spacing: 8 * S.u
            Rectangle { visible: !!row.t.explicit; width: 24 * S.u; height: 24 * S.u; radius: 4 * S.u; color: S.dim; anchors.verticalCenter: parent.verticalCenter
                        Text { anchors.centerIn: parent; text: "E"; color: S.bg; font.family: S.font; font.pixelSize: 15 * S.u; font.weight: Font.Bold } }
            Text { width: parent.width - (row.t.explicit ? 32 * S.u : 0); text: S.artists(row.t); elide: Text.ElideRight; color: S.dim; font.family: S.font; font.pixelSize: S.tMeta }
        }
    }
    Text {
        id: albumText
        visible: row.showAlbum
        anchors { right: heart.left; rightMargin: 30 * S.u; verticalCenter: parent.verticalCenter }
        width: row.showAlbum ? Math.min(420 * S.u, row.width * 0.28) : 0
        text: (row.t.album || {}).name || ""; elide: Text.ElideRight
        color: S.dim; font.family: S.font; font.pixelSize: S.tMeta
    }
    Image {
        id: heart
        anchors { right: dur.left; rightMargin: 26 * S.u; verticalCenter: parent.verticalCenter }
        width: 30 * S.u; height: width; sourceSize: Qt.size(width, height)
        source: S.icon("heart-filled")
        opacity: S.liked[row.t.uri] ? 1 : 0
    }
    Text {
        id: dur
        anchors { right: parent.right; rightMargin: 28 * S.u; verticalCenter: parent.verticalCenter }
        width: 76 * S.u; horizontalAlignment: Text.AlignRight
        text: S.mmss(row.t.duration); color: S.dim; font.family: S.font; font.pixelSize: S.tMeta
    }
}
