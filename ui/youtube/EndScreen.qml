// The end of a video: what plays next (the queue first, else YouTube's Up next) after a countdown,
// as YouTube's TV app shows it: the video's last picture dimmed, the next one's thumbnail with a
// ring that runs down, its title and channel, Play now and Cancel. Every key is this screen's
// (the player's controls behind it are hidden and get none): Left / Right between the buttons, OK
// presses, Back cancels.
import QtQuick
import QtQuick.Shapes

FocusScope {
    id: end
    property var next: null                   // the card that plays next
    property int seconds: 5
    property int remaining: seconds
    property bool queued: false               // it's from the queue
    property int button: 0                    // 0 Play now, 1 Cancel
    property real run: 0                      // the ring: 0 full, 1 run down
    signal playNow()
    signal cancel()
    function begin() {
        remaining = seconds; button = 0; run = 0;
        tick.restart();
        if (auto) { runDown.duration = seconds * 1000; runDown.restart(); }
    }
    function stopCount() { tick.stop(); runDown.stop(); }
    // (Autoplay next video off: no countdown, unless it's from the queue)
    readonly property bool auto: queued || Y.settings.autoplay !== false
    Timer { id: tick; interval: 1000; repeat: true; running: end.visible && !!end.next && !Y.shot && end.auto
            onTriggered: { end.remaining--; if (end.remaining <= 0) { end.stopCount(); end.playNow(); } } }
    NumberAnimation { id: runDown; target: end; property: "run"; from: 0; to: 1; easing.type: Easing.Linear }
    // the remote's keys, all of them (the player hands them here too while this shows)
    function key(e) {
        const k = e.key;
        if (k === Qt.Key_Left) button = 0;
        else if (k === Qt.Key_Right) button = 1;
        else if ((k === Qt.Key_Return || k === Qt.Key_Enter) && !e.isAutoRepeat) { stopCount(); if (button === 0) playNow(); else cancel(); }
        else if ((k === Qt.Key_Escape || k === Qt.Key_Back) && !e.isAutoRepeat) { stopCount(); cancel(); }
        e.accepted = true;
    }
    Keys.onPressed: e => key(e)

    // in: a quick fade
    opacity: visible ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: Y.tPanel; easing.type: Easing.OutCubic } }

    Rectangle { anchors.fill: parent; color: "#d90f0f0f" }
    Rectangle {
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: parent.height * 0.6
        gradient: Gradient {
            GradientStop { position: 0; color: "#000f0f0f" }
            GradientStop { position: 1; color: "#ff0f0f0f" }
        }
    }

    Item {                                     // the thumbnail and the words beside it, mid-screen
        id: group
        width: 1640 * Y.u
        height: thumbBox.height
        anchors.centerIn: parent
        anchors.verticalCenterOffset: -20 * Y.u

        Item {
            id: thumbBox
            width: 880 * Y.u; height: width * 9 / 16
            Rectangle {
                anchors.fill: parent; radius: Y.radius
                gradient: Gradient {
                    GradientStop { position: 0; color: Qt.hsla(Y.hue(end.next ? end.next.title : ""), 0.5, 0.3, 1) }
                    GradientStop { position: 1; color: Qt.hsla((Y.hue(end.next ? end.next.title : "") + 0.15) % 1, 0.55, 0.12, 1) }
                }
            }
            RoundImage { anchors.fill: parent; radius: Y.radius; cover: true; source: end.next ? end.next.thumb || "" : "" }
            Rectangle { anchors.fill: parent; radius: Y.radius; color: "#59000000"; visible: end.auto }
            Item {                             // the countdown: a ring that runs down, the seconds inside
                visible: end.auto
                anchors.centerIn: parent
                width: 152 * Y.u; height: width
                Rectangle { anchors.fill: parent; radius: width / 2; color: "#99000000" }
                Shape {
                    anchors.fill: parent
                    antialiasing: true
                    ShapePath {
                        strokeColor: "#4dffffff"; strokeWidth: 6 * Y.u; fillColor: "transparent"
                        PathAngleArc { centerX: 76 * Y.u; centerY: 76 * Y.u; radiusX: 70 * Y.u; radiusY: 70 * Y.u; startAngle: 0; sweepAngle: 360 }
                    }
                    ShapePath {
                        strokeColor: Y.text; strokeWidth: 6 * Y.u; fillColor: "transparent"; capStyle: ShapePath.RoundCap
                        PathAngleArc { centerX: 76 * Y.u; centerY: 76 * Y.u; radiusX: 70 * Y.u; radiusY: 70 * Y.u; startAngle: -90; sweepAngle: 360 * (1 - end.run) }
                    }
                }
                Text { anchors.centerIn: parent; text: Math.max(0, end.remaining); color: Y.text; font.family: Y.font; font.pixelSize: 60 * Y.u; font.weight: Font.Bold }
            }
            Rectangle {                        // its length, as on its card
                visible: !!(end.next && end.next.duration)
                anchors { right: parent.right; bottom: parent.bottom; margins: 14 * Y.u }
                width: dur.implicitWidth + 16 * Y.u; height: 34 * Y.u; radius: 6 * Y.u
                color: "#cc000000"
                Text { id: dur; anchors.centerIn: parent; text: end.next && end.next.duration ? (typeof end.next.duration === "number" ? Y.clock(end.next.duration) : end.next.duration) : ""
                       color: Y.text; font.family: Y.font; font.pixelSize: 22 * Y.u; font.weight: Font.Medium }
            }
        }

        Column {
            anchors { left: thumbBox.right; leftMargin: 56 * Y.u; verticalCenter: thumbBox.verticalCenter }
            width: group.width - thumbBox.width - 56 * Y.u
            spacing: 14 * Y.u
            Text {
                text: end.queued ? "Next in your queue" : end.auto ? "Up next in " + Math.max(0, end.remaining) : "Up next"
                color: Y.dim; font.family: Y.font; font.pixelSize: 28 * Y.u; font.weight: Font.Medium
            }
            Text {
                width: parent.width
                text: end.next ? end.next.title : ""
                color: Y.text; font.family: Y.font; font.pixelSize: 44 * Y.u; font.weight: Font.Bold
                wrapMode: Text.WordWrap; maximumLineCount: 3; elide: Text.ElideRight
                lineHeight: 1.08
            }
            Text {
                width: parent.width
                text: end.next ? (end.next.lines || []).join(" • ") : ""
                color: Y.dim; font.family: Y.font; font.pixelSize: 28 * Y.u
                wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
            }
            Item { width: 1; height: 26 * Y.u }
            Row {
                spacing: 24 * Y.u
                Repeater {
                    model: ["Play now", "Cancel"]
                    Rectangle {
                        required property string modelData
                        required property int index
                        readonly property bool on: end.button === index
                        width: bt.implicitWidth + 72 * Y.u; height: 72 * Y.u; radius: height / 2
                        color: on ? Y.text : Y.raised
                        Behavior on color { ColorAnimation { duration: Y.tFocus } }
                        Text { id: bt; anchors.centerIn: parent; text: parent.modelData; color: parent.on ? Y.ink : Y.text; font.family: Y.font; font.pixelSize: 28 * Y.u; font.weight: Font.Medium }
                    }
                }
            }
        }
    }
}
