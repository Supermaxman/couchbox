// The status mark in a poster's top-right corner: check (available), minus (partly),
// clock (requested / pending), cross (deleted or blocklisted).
import QtQuick

Rectangle {
    property int status: 0
    visible: status >= 2
    width: 26 * S.u
    height: width
    radius: width / 2
    color: S.statusColor(status)
    border.color: Qt.lighter(color, 1.4)
    border.width: 1
    Text {
        anchors.centerIn: parent
        visible: parent.status === 4 || parent.status === 5 || parent.status >= 6
        text: parent.status === 5 ? "✓" : parent.status === 4 ? "–" : "✕"
        color: "white"
        font.pixelSize: 16 * S.u
        font.weight: Font.Bold
    }
    Item {                                   // a clock for requested / pending
        anchors.fill: parent
        visible: parent.status === 2 || parent.status === 3
        Rectangle { x: parent.width / 2 - width / 2; y: parent.height * 0.22; width: 2 * S.u; height: parent.height * 0.32; color: "white"; radius: 1 }
        Rectangle { x: parent.width / 2 - 1 * S.u; y: parent.height / 2 - 1 * S.u; width: parent.width * 0.28; height: 2 * S.u; color: "white"; radius: 1 }
    }
}
