// A recording (a review item, from Frigate's recordings as HLS). OK: pause, Left/Right: 10 s
// back or forward, Up/Down: the previous or next item, Back: where you came from.
import QtQuick

FocusScope {
    id: view
    property var video: null
    property var list: []
    property int index: 0
    readonly property var r: list[index] || {}
    property bool controls: true
    property bool loading: true
    property string problem: ""
    signal closed()

    function start() {
        loading = true; problem = ""; controls = true; hide.restart();
        if (!r.id) return;
        F.call("recording", {camera: r.camera, start: r.start, end: r.end}, x => { if (view.visible) video.load(x.url, 0); },
               e => { problem = e; loading = false; });
        if (!r.reviewed) F.call("viewed", {ids: [r.id]});
    }
    function stop() { if (video) video.stop(); }
    function step(d) {
        const i = index + d;
        if (i < 0 || i >= list.length) return;
        index = i;
        start();
    }
    function poke() { controls = true; hide.restart(); }
    onVisibleChanged: if (!visible) stop()
    Timer { id: hide; interval: 4000; onTriggered: if (!view.video || !view.video.paused) view.controls = false }

    Connections {
        target: view.video
        function onPositionChanged() { if (view.visible && view.video.position > 0) view.loading = false; }
        function onErrorChanged() { if (view.visible && view.video.error) { view.problem = "This recording couldn't be played."; view.loading = false; } }
    }

    Keys.onReturnPressed: { video.togglePause(); poke(); }
    Keys.onEnterPressed: { video.togglePause(); poke(); }
    Keys.onSpacePressed: { video.togglePause(); poke(); }
    Keys.onLeftPressed: { video.seek(-10); poke(); }
    Keys.onRightPressed: { video.seek(10); poke(); }
    Keys.onUpPressed: step(-1)
    Keys.onDownPressed: step(1)
    Keys.onEscapePressed: closed()
    Keys.onBackPressed: closed()

    Text {
        anchors.centerIn: parent
        visible: view.loading || !!view.problem
        text: view.problem || "Loading the recording…"
        color: F.dim; font.family: F.font; font.pixelSize: 30 * F.u
    }
    Rectangle {
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: 230 * F.u
        opacity: view.controls ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 250 } }
        gradient: Gradient {
            GradientStop { position: 0; color: "#00000000" }
            GradientStop { position: 1; color: "#e0000000" }
        }
        Column {
            x: 60 * F.u; y: 46 * F.u
            width: parent.width - 60 * F.u - F.edge
            spacing: 12 * F.u
            Row {
                spacing: 16 * F.u
                Rectangle { anchors.verticalCenter: parent.verticalCenter; width: 14 * F.u; height: width; radius: width / 2; color: view.r.severity === "alert" ? F.alert : F.detection }
                Text { text: (view.r.cameraLabel || "") + "  ·  " + ((view.r.objects || []).join(", ") || "Motion"); color: "white"; font.family: F.font; font.pixelSize: 34 * F.u; font.weight: Font.DemiBold }
            }
            Text { text: (view.r.start ? F.when(view.r.start) : "") + "   " + (view.list.length > 1 ? (view.index + 1) + " of " + view.list.length + "  (▲▼)" : ""); color: F.text2; font.family: F.font; font.pixelSize: 24 * F.u }
            Item {
                width: parent.width; height: 34 * F.u
                Rectangle { anchors.verticalCenter: parent.verticalCenter; width: parent.width - 260 * F.u; height: 8 * F.u; radius: 4 * F.u; color: "#55ffffff"
                    Rectangle { width: view.video && view.video.duration > 0 ? parent.width * Math.min(1, view.video.position / view.video.duration) : 0; height: parent.height; radius: 4 * F.u; color: F.accent } }
                Text {
                    anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                    text: view.video ? (view.video.paused ? "❚❚  " : "") + fmt(view.video.position) + " / " + fmt(view.video.duration) : ""
                    color: F.text2; font.family: F.font; font.pixelSize: 24 * F.u
                    function fmt(s) { s = Math.max(0, Math.floor(s || 0)); return Math.floor(s / 60) + ":" + ("0" + s % 60).slice(-2); }
                }
            }
        }
    }
}
