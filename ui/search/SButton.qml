// A toolbar button or a row you can select with the remote (OK presses it).
import QtQuick

Rectangle {
    id: b
    property string text: ""
    property string glyph: ""                // a symbol before the text
    property bool ai: false                  // the assistant's (violet)
    property bool on: true            // can be pressed now
    signal pressed()
    implicitWidth: row.implicitWidth + 40 * S.u
    implicitHeight: 64 * S.u
    radius: 12 * S.u
    opacity: on ? 1 : 0.4
    color: activeFocus ? (ai ? "#3b2f63" : S.panel2) : S.panel
    border.color: activeFocus ? (ai ? S.ai : S.focus) : S.line
    border.width: (activeFocus ? 3 : 1) * S.u
    Keys.onReturnPressed: if (on) pressed()
    Keys.onEnterPressed: if (on) pressed()
    Row {
        id: row
        anchors.centerIn: parent
        spacing: 10 * S.u
        Text { visible: !!b.glyph; text: b.glyph; color: b.ai ? S.ai : S.text2; font.family: S.font; font.pixelSize: 26 * S.u; anchors.verticalCenter: parent.verticalCenter }
        Text { visible: !!b.text; text: b.text; color: S.text; font.family: S.font; font.pixelSize: 24 * S.u; font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter }
    }
}
