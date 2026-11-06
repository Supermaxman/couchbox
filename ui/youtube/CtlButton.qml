// A round player control: an icon on a faint circle, white with the focus. plain: no circle of
// its own (it sits in a group's pill).
import QtQuick

Rectangle {
    property string icon: ""
    property bool on: false
    property bool big: false
    property bool plain: false
    property real weight: 1.6                // the icon's stroke: YouTube's 2 px rounded outlines
    width: (big ? 96 : 72) * Y.u
    height: width
    radius: width / 2
    color: on ? Y.text : plain ? "transparent" : "#1fffffff"   // unfocused: white at 12%
    Icon {
        anchors.centerIn: parent
        name: parent.icon
        size: (parent.big ? 44 : 38) * Y.u
        color: parent.on ? Y.ink : Y.text
        weight: parent.weight
    }
}
