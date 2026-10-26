// A button or a row you can select with the remote (OK presses it).
import QtQuick

Rectangle {
    id: b
    property string text: ""
    property string sub: ""
    property bool primary: false
    signal pressed()
    height: (sub ? 92 : 72) * F.u
    radius: 12 * F.u
    color: primary ? (activeFocus ? F.accent : "#1d4ed8") : activeFocus ? F.panel2 : F.panel
    border.color: activeFocus ? F.focus : F.line
    border.width: (activeFocus ? 3 : 1) * F.u
    Keys.onReturnPressed: pressed()
    Keys.onEnterPressed: pressed()
    Column {
        anchors { left: parent.left; right: parent.right; leftMargin: 28 * F.u; rightMargin: 28 * F.u; verticalCenter: parent.verticalCenter }
        spacing: 4 * F.u
        Text { width: parent.width; text: b.text; color: F.text; font.family: F.font; font.pixelSize: 28 * F.u; font.weight: Font.DemiBold; elide: Text.ElideRight; horizontalAlignment: b.primary ? Text.AlignHCenter : Text.AlignLeft }
        Text { width: parent.width; visible: !!b.sub; text: b.sub; color: F.dim; font.family: F.font; font.pixelSize: 22 * F.u; elide: Text.ElideRight }
    }
}
