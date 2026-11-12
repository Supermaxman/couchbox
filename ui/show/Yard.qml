// The morning show's first part: yesterday at the backyard camera, sunrise to sunset, as a
// flipbook of the stills couchbox-morning downloaded (12 a second). Two pictures take turns:
// one shows while the next one loads, so a frame never shows half-drawn. done() at the end.
import QtQuick

Item {
    id: yard
    property var part: ({})
    property bool running: false
    readonly property var frames: part.frames || []
    readonly property real seconds: part.seconds || 20
    property int step: 0                     // the frame showing
    readonly property real progress: frames.length > 1 ? step / (frames.length - 1) : 0
    readonly property var now: frames[step] || {}
    signal done()

    function restart() { step = 0; }
    function src(i) {
        const f = frames[Math.min(i, frames.length - 1)];
        return f && f.file && f.file !== "demo:yard" ? "file://" + f.file : "";
    }
    Timer {
        interval: Math.max(40, yard.seconds * 1000 / Math.max(1, yard.frames.length))
        repeat: true
        running: yard.running && yard.visible
        onTriggered: {
            if (yard.step >= yard.frames.length - 1) { yard.done(); return; }
            const next = yard.step % 2 === 0 ? b : a;      // the one loading the next frame
            if (next.status === Image.Ready || String(next.source) === "") yard.step++;
        }
    }
    Rectangle { anchors.fill: parent; color: "black" }
    // even steps show a, odd ones b; the other already loads the next frame
    Image {
        id: a
        anchors.fill: parent
        source: yard.src(yard.step % 2 === 0 ? yard.step : yard.step + 1)
        visible: yard.step % 2 === 0
        fillMode: Image.PreserveAspectFit
        asynchronous: true
        cache: false
        smooth: true
    }
    Image {
        id: b
        anchors.fill: parent
        source: yard.src(yard.step % 2 === 1 ? yard.step : yard.step + 1)
        visible: yard.step % 2 === 1
        fillMode: Image.PreserveAspectFit
        asynchronous: true
        cache: false
        smooth: true
    }
    // made-up stills (screenshots): the sky through the day, the sun going over
    Item {
        id: madeUp
        anchors.fill: parent
        visible: !!yard.now.file && yard.now.file === "demo:yard"
        readonly property real t: yard.progress
        readonly property real day: Math.sin(Math.PI * t)
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0; color: Qt.hsla(0.6, 0.5, 0.12 + 0.42 * madeUp.day, 1) }
                GradientStop { position: 0.6; color: Qt.hsla(0.06 + 0.5 * madeUp.day, 0.5, 0.3 + 0.4 * madeUp.day, 1) }
                GradientStop { position: 0.61; color: "#2f4a2a" }
                GradientStop { position: 1; color: "#1a2a17" }
            }
        }
        Rectangle {
            width: 120 * S.u; height: width; radius: width / 2
            color: "#ffe2a1"
            x: parent.width * (0.1 + 0.8 * madeUp.t) - width / 2
            y: parent.height * (0.58 - 0.45 * madeUp.day) - height / 2
        }
    }
}
