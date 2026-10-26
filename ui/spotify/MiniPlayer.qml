// The bar along the bottom while browsing: what's playing on this TV (cover, song, artists and
// album), whether it's playing, and how far along.
import QtQuick

Rectangle {
    id: bar
    readonly property var info: S.nowInfo.uri === S.nowUri ? S.nowInfo : ({})
    readonly property real dur: S.nowDur
    property real pos: 0
    visible: !!S.nowUri
    height: S.barH
    color: "#f2121214"
    Timer { interval: 500; repeat: true; running: bar.visible; triggeredOnStart: true; onTriggered: bar.pos = S.nowPos() }
    Rectangle {                                  // progress, along the top edge
        id: progress
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: 6 * S.u
        color: S.line
        Rectangle { height: parent.height; color: S.accent; width: bar.dur > 0 ? parent.width * Math.min(1, bar.pos / bar.dur) : 0 }
    }
    Art { id: art; x: 26 * S.u; anchors.verticalCenter: parent.verticalCenter; anchors.verticalCenterOffset: progress.height / 2
          width: 84 * S.u; height: width
          item: ({kind: "album", name: (bar.info.album || {}).name || bar.info.name || "", image: bar.info.image || "", imageLarge: bar.info.imageLarge || ""}) }
    Column {
        anchors { left: art.right; leftMargin: 22 * S.u; right: hint.left; rightMargin: 30 * S.u; verticalCenter: art.verticalCenter }
        spacing: 4 * S.u
        Text { width: parent.width; text: bar.info.name || ((((S.now.item || {}).decorations || {}).identity || {}).name) || ""; elide: Text.ElideRight
               color: S.text; font.family: S.font; font.pixelSize: S.tBody; font.weight: Font.DemiBold }
        Text { width: parent.width; elide: Text.ElideRight; color: S.dim; font.family: S.font; font.pixelSize: S.tMeta
               visible: text !== ""
               text: [S.artists(bar.info), (bar.info.album || {}).name || ""].filter(x => x).join("  ·  ") }
    }
    Row {
        id: hint
        anchors { right: parent.right; rightMargin: S.edge; verticalCenter: art.verticalCenter }
        spacing: 16 * S.u
        Image { anchors.verticalCenter: parent.verticalCenter; width: 34 * S.u; height: width; sourceSize: Qt.size(width, height); source: S.icon(S.playing ? "bars-green" : "pause") }
        Text { anchors.verticalCenter: parent.verticalCenter; text: S.mmss(bar.pos) + (bar.dur > 0 ? " / " + S.mmss(bar.dur) : ""); color: S.dim; font.family: S.font; font.pixelSize: S.tMeta }
    }
}
