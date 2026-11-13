// Dropout's button: yellow with black text when focused (the website's call-to-action look),
// dark otherwise. icon: a drawn one by name (CouchKit's PlayerIcon: "play", "next"; "▶" is drawn
// too, as fonts differ on it), else a character.
import QtQuick
import CouchKit

Rectangle {
    id: b
    property alias text: label.text
    property string icon: ""
    property bool primary: false
    property bool lit: false                   // shown as focused (a card's button that takes OK without the focus)
    readonly property bool on: activeFocus || lit
    readonly property string drawn: icon === "▶" ? "play" : /^[a-z-]+$/.test(icon) ? icon : ""
    signal clicked()
    implicitWidth: row.implicitWidth + 56 * D.u
    implicitHeight: 68 * D.u
    radius: 6 * D.u
    color: on ? D.accent : primary ? Qt.rgba(1, 1, 1, 0.92) : Qt.rgba(1, 1, 1, 0.14)
    border.color: on ? D.accent : Qt.rgba(1, 1, 1, 0.18)
    border.width: 1
    scale: activeFocus ? 1.05 : 1
    Behavior on scale { NumberAnimation { duration: 100 } }
    Row {
        id: row
        anchors.centerIn: parent
        spacing: 14 * D.u
        PlayerIcon {
            visible: !!b.drawn
            name: b.drawn
            size: 28 * D.u
            color: label.color
            anchors.verticalCenter: parent.verticalCenter
        }
        Text {
            visible: b.icon !== "" && !b.drawn
            text: b.icon
            color: label.color
            font.pixelSize: 26 * D.u
            anchors.verticalCenter: parent.verticalCenter
        }
        Text {
            id: label
            color: b.on ? D.accentInk : b.primary ? "#111111" : D.text
            font.family: D.font
            font.pixelSize: 25 * D.u
            font.weight: Font.Bold
            font.letterSpacing: 1 * D.u
            font.capitalization: Font.AllUppercase
            anchors.verticalCenter: parent.verticalCenter
        }
    }
    Keys.onReturnPressed: clicked()
    Keys.onEnterPressed: clicked()
}
