// A rounded status label, like the website's badges ("Available", "Requested", "10 Episodes").
import QtQuick

Rectangle {
    property alias text: label.text
    property real size: 15
    property color fg: S.text
    implicitWidth: label.implicitWidth + 20 * S.u
    implicitHeight: label.implicitHeight + 8 * S.u
    radius: height / 2
    color: S.green
    Text {
        id: label
        anchors.centerIn: parent
        color: parent.fg
        font.family: S.font
        font.pixelSize: parent.size * S.u
        font.weight: Font.DemiBold
    }
}
