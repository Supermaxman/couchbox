// What was seen, as an icon in a round badge: a person, a car, a package, a sound...
import QtQuick

Rectangle {
    id: b
    property string kind: "object"
    property real size: 40 * F.u
    property color fill: "#99000000"
    width: size; height: size; radius: size / 2
    color: fill
    Image {
        anchors.centerIn: parent
        width: b.size * 0.62; height: width
        sourceSize: F.sz(width, height)
        source: F.icon(b.kind)
        smooth: true
    }
}
