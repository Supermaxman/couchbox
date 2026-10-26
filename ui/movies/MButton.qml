// A button you select with the remote (OK presses it): an icon and a label.
import QtQuick

Rectangle {
    id: b
    property string text: ""
    property string icon: ""
    property bool primary: false
    signal pressed()
    width: row.implicitWidth + 56 * M.u
    height: 72 * M.u
    radius: 12 * M.u
    color: primary ? (activeFocus ? M.focus : M.accent) : activeFocus ? M.panel2 : M.panel
    border.color: activeFocus ? (primary ? "white" : M.focus) : primary ? "transparent" : M.line
    border.width: (activeFocus ? 3 : 1) * M.u
    scale: activeFocus ? 1.04 : 1
    Behavior on scale { NumberAnimation { duration: 120 } }
    Keys.onReturnPressed: pressed()
    Keys.onEnterPressed: pressed()
    Row {
        id: row
        anchors.centerIn: parent
        spacing: 14 * M.u
        Image {
            visible: !!b.icon
            anchors.verticalCenter: parent.verticalCenter
            width: 30 * M.u; height: width; sourceSize: Qt.size(width, height)
            source: b.icon ? "icons/" + b.icon + (b.primary ? "-dark" : "") + ".svg" : ""
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: b.text; color: b.primary ? M.accentDark : M.text
            font.family: M.font; font.pixelSize: 27 * M.u; font.weight: Font.DemiBold
        }
    }
}
