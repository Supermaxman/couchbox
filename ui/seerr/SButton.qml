// A website-style button: gray (default), indigo (primary) or yellow (warning).
import QtQuick

Rectangle {
    id: b
    property alias text: label.text
    property string icon: ""
    property string kind: ""                // "", "primary", "success", "warning", "danger"
    property bool enabled2: true
    signal clicked()
    implicitWidth: row.implicitWidth + 44 * S.u
    implicitHeight: 60 * S.u
    radius: 10 * S.u
    color: kind === "primary" ? (activeFocus ? S.indigo : S.indigoDark)
         : kind === "warning" ? (activeFocus ? "#facc15" : "#ca8a04")
         : kind === "danger" ? (activeFocus ? "#ef4444" : S.red)
         : kind === "success" ? (activeFocus ? "#22c55e" : "#16a34a")
         : activeFocus ? S.panel2 : Qt.rgba(0.12, 0.16, 0.22, 0.85)
    border.color: activeFocus ? S.focus : kind ? Qt.lighter(color, 1.2) : S.line
    border.width: activeFocus ? 3 * S.u : 1
    opacity: enabled2 ? 1 : 0.5
    scale: activeFocus ? 1.04 : 1
    Behavior on scale { NumberAnimation { duration: 90 } }
    Row {
        id: row
        anchors.centerIn: parent
        spacing: 10 * S.u
        Text {
            visible: b.icon !== ""
            text: b.icon
            color: label.color
            font.pixelSize: 24 * S.u
            anchors.verticalCenter: parent.verticalCenter
        }
        Text {
            id: label
            color: b.kind === "warning" ? "#111827" : S.text
            font.family: S.font
            font.pixelSize: 22 * S.u
            font.weight: Font.Medium
            anchors.verticalCenter: parent.verticalCenter
        }
    }
    Keys.onReturnPressed: if (enabled2) clicked()
    Keys.onEnterPressed: if (enabled2) clicked()
}
