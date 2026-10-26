// The bar along the bottom while browsing: what's playing on this TV and how far along.
import QtQuick

Rectangle {
    id: bar
    readonly property var info: S.nowInfo || ({})
    readonly property real dur: info.duration || 0
    property real pos: 0
    visible: !!S.nowUri
    height: S.barH
    color: "#f2121214"
    Rectangle { anchors { left: parent.left; right: parent.right; top: parent.top } height: 1; color: S.line }
    Timer { interval: 1000; repeat: true; running: bar.visible; triggeredOnStart: true
            onTriggered: { const n = S.now; bar.pos = !n.timestamp_ms ? (n.position_ms || 0) / 1000 : (n.position_ms + Math.max(0, Date.now() - n.timestamp_ms) * (n.speed || 0)) / 1000; } }
    Art { id: art; x: 26 * S.u; anchors.verticalCenter: parent.verticalCenter; width: 76 * S.u; height: width
          item: ({kind: "album", name: (bar.info.album || {}).name || bar.info.name || "", image: bar.info.image || ""}) }
    Column {
        anchors { left: art.right; leftMargin: 22 * S.u; right: hint.left; rightMargin: 30 * S.u; verticalCenter: parent.verticalCenter }
        spacing: 4 * S.u
        Text { width: parent.width; text: bar.info.name || ((((S.now.item || {}).decorations || {}).identity || {}).name) || ""; elide: Text.ElideRight
               color: S.text; font.family: S.font; font.pixelSize: S.tBody; font.weight: Font.DemiBold }
        Text { width: parent.width; text: S.artists(bar.info); elide: Text.ElideRight; color: S.dim; font.family: S.font; font.pixelSize: S.tMeta }
    }
    Row {
        id: hint
        anchors { right: parent.right; rightMargin: S.edge; verticalCenter: parent.verticalCenter }
        spacing: 16 * S.u
        Image { anchors.verticalCenter: parent.verticalCenter; width: 34 * S.u; height: width; sourceSize: Qt.size(width, height); source: S.icon(S.playing ? "bars-green" : "pause") }
        Text { anchors.verticalCenter: parent.verticalCenter; text: S.mmss(bar.pos) + " / " + S.mmss(bar.dur); color: S.dim; font.family: S.font; font.pixelSize: S.tMeta }
    }
    Rectangle { anchors { left: parent.left; bottom: parent.bottom } height: 4 * S.u; color: S.accent
                width: bar.dur > 0 ? parent.width * Math.min(1, bar.pos / bar.dur) : 0 }
}
