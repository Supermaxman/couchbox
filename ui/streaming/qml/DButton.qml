// Dropout's button: yellow with black text when focused (the website's call-to-action look),
// dark otherwise.
import QtQuick

Rectangle {
    id: b
    property alias text: label.text
    property string icon: ""
    property bool primary: false
    signal clicked()
    implicitWidth: row.implicitWidth + 56 * D.u
    implicitHeight: 68 * D.u
    radius: 6 * D.u
    color: activeFocus ? D.accent : primary ? Qt.rgba(1, 1, 1, 0.92) : Qt.rgba(1, 1, 1, 0.14)
    border.color: activeFocus ? D.accent : Qt.rgba(1, 1, 1, 0.18)
    border.width: 1
    scale: activeFocus ? 1.05 : 1
    Behavior on scale { NumberAnimation { duration: 100 } }
    Row {
        id: row
        anchors.centerIn: parent
        spacing: 14 * D.u
        Text {
            visible: b.icon !== ""
            text: b.icon
            color: label.color
            font.pixelSize: 26 * D.u
            anchors.verticalCenter: parent.verticalCenter
        }
        Text {
            id: label
            color: b.activeFocus ? D.accentInk : b.primary ? "#111111" : D.text
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
