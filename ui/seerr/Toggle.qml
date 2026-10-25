// The website's switch.
import QtQuick

Rectangle {
    property bool on: false
    property bool enabled2: true
    width: 54 * S.u
    height: 30 * S.u
    radius: height / 2
    color: on ? S.indigo : S.line
    opacity: enabled2 ? 1 : 0.45
    Rectangle {
        x: parent.on ? parent.width - width - 3 * S.u : 3 * S.u
        anchors.verticalCenter: parent.verticalCenter
        width: 23 * S.u; height: width; radius: width / 2
        color: "white"
        Behavior on x { NumberAnimation { duration: 120 } }
    }
}
