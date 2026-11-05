// The end of a video: what plays next (the queue first, else YouTube's Up next) after a countdown,
// as YouTube's TV app shows it. OK plays it now, Right goes to Cancel; Back cancels.
import QtQuick

FocusScope {
    id: end
    property var next: null                   // the card that plays next
    property int seconds: 5
    property int remaining: seconds
    property bool queued: false               // it's from the queue
    property int button: 0                    // 0 Play now, 1 Cancel
    signal playNow()
    signal cancel()
    function begin() { remaining = seconds; button = 0; tick.restart(); }
    Timer { id: tick; interval: 1000; repeat: true; running: end.visible && !!end.next && !Y.shot
            onTriggered: { end.remaining--; if (end.remaining <= 0) { stop(); end.playNow(); } } }
    Keys.onLeftPressed: button = 0
    Keys.onRightPressed: button = 1
    Keys.onReturnPressed: { tick.stop(); if (button === 0) playNow(); else cancel(); }
    Keys.onEnterPressed: { tick.stop(); if (button === 0) playNow(); else cancel(); }
    Keys.onEscapePressed: { tick.stop(); cancel(); }
    Keys.onBackPressed: { tick.stop(); cancel(); }

    Rectangle { anchors.fill: parent; color: "#e60f0f0f" }
    Text {
        x: 156 * Y.u; y: 150 * Y.u
        text: end.queued ? "Next in your queue" : "Up next"
        color: Y.dim; font.family: Y.font; font.pixelSize: 32 * Y.u; font.weight: Font.Medium
    }
    Item {
        x: 156 * Y.u; y: 220 * Y.u
        width: 960 * Y.u; height: 540 * Y.u
        Rectangle {
            anchors.fill: parent; radius: Y.radius
            gradient: Gradient {
                GradientStop { position: 0; color: Qt.hsla(Y.hue(end.next ? end.next.title : ""), 0.5, 0.3, 1) }
                GradientStop { position: 1; color: Qt.hsla((Y.hue(end.next ? end.next.title : "") + 0.15) % 1, 0.55, 0.12, 1) }
            }
        }
        Image { anchors.fill: parent; source: end.next ? end.next.thumb || "" : ""; fillMode: Image.PreserveAspectCrop; sourceSize: Y.sz(width, height); asynchronous: true }
        Corners { anchors.fill: parent; color: "#0f0f0f"; visible: false }
        Rectangle {                            // the countdown
            anchors.centerIn: parent
            width: 150 * Y.u; height: width; radius: width / 2
            color: "#b3000000"
            border.color: Y.text; border.width: 6 * Y.u
            Text { anchors.centerIn: parent; text: end.remaining; color: Y.text; font.family: Y.font; font.pixelSize: 64 * Y.u; font.weight: Font.Bold }
        }
    }
    Column {
        x: 1160 * Y.u; y: 220 * Y.u
        width: 640 * Y.u
        spacing: 16 * Y.u
        Text {
            width: parent.width
            text: end.next ? end.next.title : ""
            color: Y.text; font.family: Y.font; font.pixelSize: 44 * Y.u; font.weight: Font.Bold
            wrapMode: Text.WordWrap; maximumLineCount: 3; elide: Text.ElideRight
        }
        Text {
            width: parent.width
            text: end.next ? (end.next.lines || []).join(" • ") : ""
            color: Y.dim; font.family: Y.font; font.pixelSize: 28 * Y.u
            wrapMode: Text.WordWrap
        }
        Item { width: 1; height: 30 * Y.u }
        Row {
            spacing: 24 * Y.u
            Repeater {
                model: ["Play now", "Cancel"]
                Rectangle {
                    required property string modelData
                    required property int index
                    readonly property bool on: end.button === index && end.activeFocus
                    width: bt.implicitWidth + 72 * Y.u; height: 72 * Y.u; radius: height / 2
                    color: on ? Y.text : Y.raised
                    Text { id: bt; anchors.centerIn: parent; text: parent.modelData; color: parent.on ? Y.ink : Y.text; font.family: Y.font; font.pixelSize: 28 * Y.u; font.weight: Font.Medium }
                }
            }
        }
    }
}
