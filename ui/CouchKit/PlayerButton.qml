// CouchKit PlayerButton: one of the player controls' buttons (PlayerControls draws a row of
// them): an icon on a faint circle, or a short text in a pill; filled (and ringed, if the app's
// focus is a ring) with the focus. It takes no keys itself: `on` says it's the focused one.
import QtQuick

Rectangle {
    id: b
    property string icon: ""                 // a PlayerIcon name
    property string text: ""                 // ... or a short text instead
    property bool on: false                  // it has the focus
    property bool big: false                 // Play / Pause
    property bool marked: false              // switched on (captions): a short bar under the icon
    property real u: 1
    property string font: "Inter"
    property color ink: "#ffffff"            // the icon, unfocused
    property color fill: "#1fffffff"         // the circle, unfocused
    property color focusFill: "#ffffff"
    property color focusInk: "#0f0f0f"
    property color focusRing: "transparent"

    height: (big ? 96 : 72) * u
    width: text && !icon ? Math.max(height, label.implicitWidth + 56 * u) : height
    radius: height / 2
    color: on ? focusFill : fill
    border.color: on ? focusRing : "transparent"
    border.width: on && focusRing.a > 0 ? 4 * u : 0

    PlayerIcon {
        visible: !!b.icon
        anchors.centerIn: parent
        name: b.icon
        size: (b.big ? 44 : 38) * b.u
        color: b.on ? b.focusInk : b.ink
        weight: 1.6
    }
    Text {
        id: label
        visible: !b.icon
        anchors.centerIn: parent
        text: b.text
        color: b.on ? b.focusInk : b.ink
        font.family: b.font; font.pixelSize: 26 * b.u; font.weight: Font.DemiBold
    }
    Rectangle {
        visible: b.marked
        anchors { horizontalCenter: parent.horizontalCenter; top: parent.verticalCenter; topMargin: (b.big ? 28 : 23) * b.u }
        width: 26 * b.u; height: 4 * b.u; radius: height / 2
        color: b.on ? b.focusInk : b.ink
    }
}
