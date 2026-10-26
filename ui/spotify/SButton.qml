// A round or pill button for the remote: an icon and/or a word. `current` draws the focus ring.
import QtQuick

Rectangle {
    id: b
    property string icon: ""
    property string text: ""
    property bool primary: false
    property bool current: false
    property bool on: false                  // a toggle that's on (shuffle, liked)
    height: (primary ? 96 : 76) * S.u
    width: text ? row.implicitWidth + 2 * 30 * S.u : height
    radius: height / 2
    color: primary ? (current ? Qt.lighter(S.accent, 1.12) : S.accent) : current ? S.panel2 : "transparent"
    border.color: current ? S.focus : primary ? "transparent" : S.line
    border.width: (current ? S.ring : 2 * S.u)
    scale: current ? 1.06 : 1
    Behavior on scale { NumberAnimation { duration: 100 } }
    Row {
        id: row
        anchors.centerIn: parent
        spacing: 12 * S.u
        Image {
            visible: !!b.icon
            anchors.verticalCenter: parent.verticalCenter
            width: (b.primary ? 42 : 34) * S.u; height: width; sourceSize: Qt.size(width, height)
            source: b.icon ? S.icon(b.icon) : ""
        }
        Text {
            visible: !!b.text
            anchors.verticalCenter: parent.verticalCenter
            text: b.text
            color: b.primary ? "#000000" : b.on ? S.accent : S.text
            font.family: S.font; font.pixelSize: S.tBody; font.weight: Font.DemiBold
        }
    }
    Rectangle { visible: b.on && !b.text; width: 8 * S.u; height: width; radius: width / 2; color: S.accent
                anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 8 * S.u } }
}
