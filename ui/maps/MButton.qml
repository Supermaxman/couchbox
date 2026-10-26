// A button or a row you can select with the remote (OK presses it), with an optional icon.
import QtQuick

Rectangle {
    id: b
    property string text: ""
    property string sub: ""
    property string icon: ""
    property bool primary: false
    signal pressed()
    height: (sub ? 92 : 72) * M.u
    radius: 12 * M.u
    color: primary ? (activeFocus ? "#059669" : "#047857") : activeFocus ? M.panel2 : M.panel
    border.color: activeFocus ? M.focus : M.line
    border.width: (activeFocus ? 3 : 1) * M.u
    Keys.onReturnPressed: pressed()
    Keys.onEnterPressed: pressed()
    Image {
        id: ic
        visible: !!b.icon
        anchors { left: parent.left; leftMargin: 26 * M.u; verticalCenter: parent.verticalCenter }
        width: 34 * M.u; height: width; sourceSize: M.sz(width, height)
        source: b.icon ? M.icon(b.icon) : ""
    }
    Column {
        anchors { left: ic.visible ? ic.right : parent.left; right: parent.right; leftMargin: ic.visible ? 20 * M.u : 28 * M.u; rightMargin: 28 * M.u; verticalCenter: parent.verticalCenter }
        spacing: 4 * M.u
        Text { width: parent.width; text: b.text; color: M.text; font.family: M.font; font.pixelSize: 28 * M.u; font.weight: Font.DemiBold; elide: Text.ElideRight; horizontalAlignment: b.primary && !b.icon ? Text.AlignHCenter : Text.AlignLeft }
        Text { width: parent.width; visible: !!b.sub; text: b.sub; color: M.dim; font.family: M.font; font.pixelSize: 22 * M.u; elide: Text.ElideRight }
    }
}
