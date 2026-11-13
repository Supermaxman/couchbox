// The end of a video, laid out as YouTube's TV app's end screen (measured in VacuumTube): Replay
// top left; UP NEXT, the next video's title and channel; its picture on the right half, fading
// into the page, with a play button (the focus starts there); a row of three more videos below.
// With autoplay on, a ring around the play button runs down and the next video plays (ours: the
// old app on this TV has autoplay off). Every key is this screen's: Left / Right / Up / Down move,
// OK plays (the next video, a tile) or replays, Back leaves the player, as YouTube's does.
import QtQuick
import QtQuick.Shapes

FocusScope {
    id: end
    property var next: null                   // the card that plays next
    property var more: []                     // three more cards (the row below)
    property var current: ({})                // the video that ended: {title, thumb} (Replay's picture)
    property int seconds: 5
    property int remaining: seconds
    property bool queued: false               // it's from the queue
    property string at: "play"                // where the focus is: play | replay | tiles
    property int tile: 0
    property real run: 0                      // the ring: 0 full, 1 run down
    property bool counting: false
    signal playNow()
    signal replay()
    signal openItem(var item)
    signal leave()
    function begin() {
        remaining = seconds; at = "play"; tile = 0; run = 0;
        counting = auto;
        if (counting) { tick.restart(); runDown.duration = seconds * 1000; runDown.restart(); }
    }
    function stopCount() { counting = false; tick.stop(); runDown.stop(); }
    // (Autoplay next video off: no countdown, unless it's from the queue)
    readonly property bool auto: queued || Y.settings.autoplay !== false
    Timer { id: tick; interval: 1000; repeat: true
            onTriggered: { end.remaining--; if (end.remaining <= 0) { end.stopCount(); end.playNow(); } } }
    NumberAnimation { id: runDown; target: end; property: "run"; from: 0; to: 1; easing.type: Easing.Linear }
    function focusDetail() { return {at: at, tile: tile, counting: counting, remaining: remaining, more: more.length}; }
    // the remote's keys, all of them (the player hands them here too while this shows)
    function key(e) {
        const k = e.key, ok = k === Qt.Key_Return || k === Qt.Key_Enter;
        e.accepted = true;
        if (e.isAutoRepeat && (ok || k === Qt.Key_Escape || k === Qt.Key_Back)) return;
        if (k === Qt.Key_Escape || k === Qt.Key_Back) { stopCount(); leave(); return; }
        if (at === "play") {
            if (k === Qt.Key_Left) { stopCount(); at = "replay"; }
            else if (k === Qt.Key_Down && more.length) { stopCount(); at = "tiles"; }
            else if (ok) { stopCount(); playNow(); }
        } else if (at === "replay") {
            if (k === Qt.Key_Right) at = "play";
            else if (k === Qt.Key_Down && more.length) at = "tiles";
            else if (ok) replay();
        } else {
            if (k === Qt.Key_Left) tile = Math.max(0, tile - 1);
            else if (k === Qt.Key_Right) tile = Math.min(more.length - 1, tile + 1);
            else if (k === Qt.Key_Up) at = "play";
            else if (ok && more[tile]) openItem(more[tile]);
        }
    }
    Keys.onPressed: e => key(e)

    opacity: visible ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: Y.tPanel; easing.type: Easing.OutCubic } }

    Rectangle { anchors.fill: parent; color: Y.bg }

    // the next video's picture, the right half, fading into the page left and below; dimmed while
    // the focus is elsewhere
    Item {
        id: art
        x: 960 * Y.u; width: 960 * Y.u; height: 540 * Y.u
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0; color: Qt.hsla(Y.hue(end.next ? end.next.title : ""), 0.5, 0.3, 1) }
                GradientStop { position: 1; color: Qt.hsla((Y.hue(end.next ? end.next.title : "") + 0.15) % 1, 0.55, 0.12, 1) }
            }
        }
        Image { anchors.fill: parent; source: end.next ? end.next.thumb || "" : ""; fillMode: Image.PreserveAspectCrop; sourceSize: Y.sz(width, height); asynchronous: true }
        Rectangle { anchors.fill: parent; color: "black"; opacity: end.at === "play" ? 0 : 0.55; Behavior on opacity { NumberAnimation { duration: Y.tFocus } } }
        Rectangle {
            width: 420 * Y.u; height: parent.height
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: Y.bg }
                GradientStop { position: 1; color: "transparent" }
            }
        }
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width; height: 220 * Y.u
            gradient: Gradient {
                GradientStop { position: 0; color: "transparent" }
                GradientStop { position: 1; color: Y.bg }
            }
        }
        Item {                                 // the play button (and the countdown's ring around it)
            id: playBtn
            readonly property bool on: end.at === "play"
            x: 426 * Y.u; y: 210 * Y.u; width: 72 * Y.u; height: width
            Rectangle {
                anchors.fill: parent; radius: width / 2
                color: playBtn.on ? Y.text : "#66000000"
                Behavior on color { ColorAnimation { duration: Y.tFocus } }
            }
            Icon { anchors.centerIn: parent; anchors.horizontalCenterOffset: 2 * Y.u; name: "play"; size: 34 * Y.u; color: playBtn.on ? Y.ink : Y.text }
            Shape {
                visible: end.counting
                x: -14 * Y.u; y: -14 * Y.u; width: 100 * Y.u; height: width
                antialiasing: true
                ShapePath {
                    strokeColor: "#4dffffff"; strokeWidth: 5 * Y.u; fillColor: "transparent"
                    PathAngleArc { centerX: 50 * Y.u; centerY: 50 * Y.u; radiusX: 47 * Y.u; radiusY: 47 * Y.u; startAngle: 0; sweepAngle: 360 }
                }
                ShapePath {
                    strokeColor: Y.text; strokeWidth: 5 * Y.u; fillColor: "transparent"; capStyle: ShapePath.RoundCap
                    PathAngleArc { centerX: 50 * Y.u; centerY: 50 * Y.u; radiusX: 47 * Y.u; radiusY: 47 * Y.u; startAngle: -90; sweepAngle: 360 * (1 - end.run) }
                }
            }
        }
    }

    // UP NEXT, the title, the channel (dim while the focus is elsewhere)
    Column {
        x: 99 * Y.u; y: 156 * Y.u
        width: 735 * Y.u
        spacing: 0
        opacity: end.at === "play" ? 1 : 0.3
        Behavior on opacity { NumberAnimation { duration: Y.tFocus } }
        Text {
            height: 72 * Y.u
            text: end.queued ? "NEXT IN YOUR QUEUE" : end.counting ? "UP NEXT IN " + Math.max(0, end.remaining) : "UP NEXT"
            color: Y.text; font.family: Y.font; font.pixelSize: 36 * Y.u; font.weight: Font.Bold
            // Autoplay next video off (the player's settings menu, or Settings): said beside it
            Text {
                visible: !end.auto
                x: parent.contentWidth + 24 * Y.u; height: parent.height
                text: "AUTOPLAY IS OFF"
                color: "#909090"; font: parent.font
            }
        }
        Text {
            width: parent.width
            text: end.next ? end.next.title : ""
            color: Y.text; font.family: Y.font; font.pixelSize: 54 * Y.u; font.weight: Font.Bold
            wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
            lineHeight: 75 * Y.u; lineHeightMode: Text.FixedHeight
        }
        Text {
            width: parent.width
            topPadding: 6 * Y.u
            text: end.next ? ((end.next.lines || [])[0] || "") : ""
            color: "#909090"; font.family: Y.font; font.pixelSize: 36 * Y.u; font.weight: Font.Bold
            elide: Text.ElideRight
        }
    }

    // Replay: an icon; focused, a card with the video's picture and REPLAY
    Item {
        x: 100 * Y.u; y: 52 * Y.u
        readonly property bool on: end.at === "replay"
        Icon { x: 0; y: 10 * Y.u; name: "replay"; size: 46 * Y.u; color: Y.dim; visible: !parent.on }
        Rectangle {
            visible: parent.on
            width: 304 * Y.u; height: 180 * Y.u; radius: 20 * Y.u
            color: Y.text
            Rectangle {
                x: 8 * Y.u; y: 8 * Y.u; width: parent.width - 16 * Y.u; height: parent.height - 16 * Y.u; radius: 14 * Y.u
                color: "#272727"; clip: true
                RoundImage { anchors.fill: parent; radius: 14 * Y.u; cover: true; source: end.current.thumb || "" }
                Rectangle {
                    anchors.bottom: parent.bottom; width: parent.width; height: 66 * Y.u; radius: 14 * Y.u
                    color: "#d9161616"
                    Row {
                        anchors.centerIn: parent
                        spacing: 10 * Y.u
                        Icon { name: "replay"; size: 34 * Y.u; color: Y.text; anchors.verticalCenter: parent.verticalCenter }
                        Text { text: "REPLAY"; color: Y.text; font.family: Y.font; font.pixelSize: 30 * Y.u; font.weight: Font.Bold; anchors.verticalCenter: parent.verticalCenter }
                    }
                }
            }
        }
    }

    // three more videos
    Row {
        x: 96 * Y.u; y: 537 * Y.u
        spacing: 36 * Y.u
        Repeater {
            model: end.more
            VideoCard {
                required property var modelData
                required property int index
                item: modelData
                w: 552 * Y.u
                on: end.at === "tiles" && end.tile === index
            }
        }
    }
}
