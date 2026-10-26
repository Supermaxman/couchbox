// One number on Today: a glyph, what it is, the value, and a line under it.
import QtQuick

Rectangle {
    id: stat
    property string glyph: ""
    property string label: ""
    property string value: ""
    property string note: ""
    property color tint: W.text
    radius: W.radius
    color: W.panel
    implicitHeight: col.implicitHeight + 40 * W.u

    Column {
        id: col
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 22 * W.u; topMargin: 20 * W.u }
        spacing: 8 * W.u
        Row {
            spacing: 10 * W.u
            Image { width: 26 * W.u; height: width; sourceSize: W.sz(width, height); source: stat.glyph ? W.glyph(stat.glyph) : ""; opacity: 0.75; anchors.verticalCenter: parent.verticalCenter }
            Text { text: stat.label.toUpperCase(); color: W.faint; font.family: W.font; font.pixelSize: 18 * W.u; font.weight: Font.Bold; font.letterSpacing: 1.5 * W.u; anchors.verticalCenter: parent.verticalCenter }
        }
        Text {
            width: parent.width
            text: stat.value
            color: stat.tint; font.family: W.font; font.pixelSize: 36 * W.u; font.weight: Font.DemiBold
            elide: Text.ElideRight
        }
        Text {
            width: parent.width
            visible: text !== ""
            text: stat.note
            color: W.dim; font.family: W.font; font.pixelSize: W.tSmall
            elide: Text.ElideRight
        }
    }
}
