// While you were out (couchbox.away): the home screen card's reel. Short silent clips of what the
// cameras saw, one after another, each with what happened, when and where. Left/Right: the clip
// before or after, OK: the whole recording in the player, Back: leave. At the end it's done (the
// card goes) and the app leaves too.
import QtQuick

FocusScope {
    id: reel
    property var video: null
    property var clips: []
    property int index: 0
    property bool stills: false              // no video (off-screen screenshots): the stills
    readonly property var now: clips[index] || {}
    signal openClip(var clip)
    signal closed()
    signal finished()

    function start(i) {
        index = Math.max(0, Math.min(clips.length - 1, i || 0));
        play();
    }
    function play() {
        if (!video || !now.file) return;
        if (now.file === "demo:clip") video.load("demo:clip", 0);
        else video.loadWith(now.file, 0, "aid=no");          // cameras: never any sound (a local file: opens at once)
    }
    function step(d) {
        const i = index + d;
        if (i < 0) return play();                             // the first clip again
        if (i >= clips.length) return finished();
        index = i;
        play();
    }
    function stop() { if (video) video.stop(); }
    onVisibleChanged: if (!visible) stop()

    Connections {
        target: reel.video
        function onEndedChanged() { if (reel.visible && reel.video.ended && !reel.stills) reel.step(1); }
    }

    Keys.onLeftPressed: step(-1)
    Keys.onRightPressed: step(1)
    Keys.onReturnPressed: openClip(now)
    Keys.onEnterPressed: openClip(now)
    Keys.onEscapePressed: closed()
    Keys.onBackPressed: closed()
    Keys.onUpPressed: (event) => event.accepted = true
    Keys.onDownPressed: (event) => event.accepted = true

    readonly property real side: 96 * F.u

    // The clip's still, until its first frame is drawn (no flash of the clip before)
    Rectangle {
        anchors.fill: parent
        color: "black"
        visible: reel.stills || !reel.video || !reel.video.hasFrame
        Image {
            id: still
            anchors.fill: parent
            source: reel.now.poster ? "file://" + reel.now.poster : ""
            fillMode: Image.PreserveAspectFit
            asynchronous: true
            smooth: true
        }
        Rectangle {                              // made-up clips (screenshots) have no picture
            anchors.fill: parent
            visible: still.status !== Image.Ready
            gradient: Gradient {
                GradientStop { position: 0; color: "#1c1f26" }
                GradientStop { position: 1; color: "#0b0c0f" }
            }
            Image {
                anchors.centerIn: parent
                width: 220 * F.u; height: width
                opacity: 0.12
                sourceSize: F.sz(width, height)
                source: F.icon(reel.now.kind || "object")
            }
        }
    }

    // How far along: a segment a clip, the one playing filling up (over a shade: the cameras
    // print their own date and time up there)
    Rectangle {
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: 190 * F.u
        gradient: Gradient {
            GradientStop { position: 0; color: "#cc000000" }
            GradientStop { position: 1; color: "#00000000" }
        }
    }
    Row {
        id: progress
        x: reel.side
        y: 48 * F.u
        width: reel.width - 2 * reel.side
        spacing: 10 * F.u
        Repeater {
            model: reel.clips.length
            Rectangle {
                required property int index
                width: (progress.width - progress.spacing * (reel.clips.length - 1)) / Math.max(1, reel.clips.length)
                height: 6 * F.u
                radius: height / 2
                color: Qt.rgba(1, 1, 1, 0.28)
                Rectangle {
                    height: parent.height
                    radius: parent.radius
                    color: "white"
                    width: index < reel.index ? parent.width
                         : index > reel.index ? 0
                         : reel.stills ? parent.width * 0.4
                         : reel.video && reel.video.duration > 0 ? parent.width * Math.min(1, reel.video.position / reel.video.duration) : 0
                }
            }
        }
    }

    // What happened, then when and where
    Rectangle {
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: 360 * F.u
        gradient: Gradient {
            GradientStop { position: 0; color: "#00000000" }
            GradientStop { position: 1; color: "#d9000000" }
        }
    }
    Column {
        id: words
        x: reel.side
        anchors { bottom: parent.bottom; bottomMargin: 76 * F.u }
        width: reel.width - 2 * reel.side
        spacing: 12 * F.u
        Text {
            width: parent.width
            text: reel.now.what || ""
            color: "white"
            wrapMode: Text.WordWrap
            maximumLineCount: 2
            elide: Text.ElideRight
            font.family: F.font; font.pixelSize: 48 * F.u; font.weight: Font.DemiBold
            style: Text.Raised; styleColor: "#66000000"
        }
        Text {
            width: parent.width
            text: [reel.now.when, reel.now.cameraLabel].filter(x => !!x).join("  ·  ")
            color: F.text2
            elide: Text.ElideRight
            font.family: F.font; font.pixelSize: 28 * F.u; font.weight: Font.Medium
        }
    }
    // a new clip: its words come in with it
    onIndexChanged: { words.opacity = 0; fadeIn.restart(); }
    NumberAnimation { id: fadeIn; target: words; property: "opacity"; from: 0; to: 1; duration: 350; easing.type: Easing.OutCubic }
}
