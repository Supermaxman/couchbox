// The focus ring around whatever has the remote's focus.
import QtQuick

Rectangle {
    property bool on: false
    property real radiusOf: 12
    anchors.fill: parent
    anchors.margins: -6 * S.u
    radius: radiusOf * S.u + 6 * S.u
    color: "transparent"
    border.color: S.focus
    border.width: 4 * S.u
    visible: on
    z: 10
}
