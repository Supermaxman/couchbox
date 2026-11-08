// A pill button (a channel's Play mix and Subscribe): an optional icon and a label, white with the
// focus, else a faint white over whatever is behind it. OK presses it.
import QtQuick

Rectangle {
    id: pill
    property string icon: ""
    property string label: ""
    signal pressed()
    height: 72 * Y.u
    width: content.implicitWidth + (icon ? 48 : 72) * Y.u
    radius: height / 2
    color: activeFocus ? Y.text : "#26ffffff"   // unfocused: white at 15%
    Row {
        id: content
        anchors.centerIn: parent
        spacing: 12 * Y.u
        Icon {
            visible: !!pill.icon
            anchors.verticalCenter: parent.verticalCenter
            name: pill.icon
            size: 36 * Y.u
            color: pill.activeFocus ? Y.ink : Y.text
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: pill.label
            color: pill.activeFocus ? Y.ink : Y.text
            font.family: Y.font; font.pixelSize: 28 * Y.u; font.weight: Font.Medium
        }
    }
    Keys.onReturnPressed: pressed()
    Keys.onEnterPressed: pressed()
}
