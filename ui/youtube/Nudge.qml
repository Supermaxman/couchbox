// YouTube's note at the top of Home when nobody's signed in ("Make YouTube your own"), with its
// Sign in button.
import QtQuick

FocusScope {
    id: nudge
    property string title: ""
    property string subtitle: ""
    width: parent ? parent.width : 0
    height: 250 * Y.u
    property real indent: Y.left
    Rectangle {
        x: nudge.indent
        width: Math.min(parent.width - nudge.indent - 108 * Y.u, 1180 * Y.u)
        height: parent.height
        radius: 24 * Y.u
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: "#3a1020" }
            GradientStop { position: 1; color: "#1a1a2a" }
        }
        Column {
            anchors { left: parent.left; leftMargin: 48 * Y.u; verticalCenter: parent.verticalCenter }
            width: parent.width - 96 * Y.u
            spacing: 14 * Y.u
            Text { text: nudge.title; color: Y.text; font.family: Y.font; font.pixelSize: 40 * Y.u; font.weight: Font.Medium }
            Text { width: parent.width; text: nudge.subtitle; color: Y.dim; font.family: Y.font; font.pixelSize: Y.tMeta; wrapMode: Text.WordWrap }
            Item { width: 1; height: 6 * Y.u }
            Rectangle {
                id: button
                readonly property bool on: nudge.activeFocus
                width: signIn.implicitWidth + 64 * Y.u
                height: 64 * Y.u
                radius: height / 2
                color: on ? Y.text : Y.glass
                Text { id: signIn; anchors.centerIn: parent; text: "Sign in"; color: parent.on ? Y.ink : Y.text; font.family: Y.font; font.pixelSize: 26 * Y.u; font.weight: Font.Medium }
            }
        }
    }
    Keys.onReturnPressed: Y.signIn()
    Keys.onEnterPressed: Y.signIn()
    Keys.onLeftPressed: Y.toGuide()
}
