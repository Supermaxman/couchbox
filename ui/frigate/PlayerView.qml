// A recording (a review item, or the timeline from a point, from Frigate's recordings as HLS).
// OK: pause, Left/Right: 10 s back or forward, Up/Down: the previous or next item, Back: where
// you came from.
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
        if (r.id && !r.reviewed) F.call("viewed", {ids: [r.id]});
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
        height: 250 * F.u
        opacity: view.controls ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 250 } }
        gradient: Gradient {
            GradientStop { position: 0; color: "#00000000" }
            GradientStop { position: 1; color: "#e0000000" }
        }
        Column {
            x: 60 * F.u; y: 40 * F.u
            width: parent.width - 60 * F.u - F.edge
            spacing: 12 * F.u
            Row {
                width: parent.width
                spacing: 14 * F.u
                Repeater {
                    model: (view.r.kinds || []).slice(0, 4)
                    delegate: KindBadge { required property var modelData; anchors.verticalCenter: parent.verticalCenter; kind: modelData.kind; size: 52 * F.u; fill: "#33ffffff" }
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    width: Math.min(implicitWidth, parent.width - 300 * F.u); elide: Text.ElideRight
                    text: (view.r.cameraLabel || "") + (view.r.fromTimeline ? "" : "  ·  " + F.seen(view.r))
                    color: "white"; font.family: F.font; font.pixelSize: 34 * F.u; font.weight: Font.DemiBold
                }
                Rectangle {
                    visible: !!view.r.severity
                    anchors.verticalCenter: parent.verticalCenter
                    width: sevText.implicitWidth + 22 * F.u; height: sevText.implicitHeight + 10 * F.u; radius: 8 * F.u
                    color: F.sevColor(view.r)
                    Text { id: sevText; anchors.centerIn: parent; text: view.r.severity === "alert" ? "ALERT" : "DETECTION"; color: "#09090b"; font.family: F.font; font.pixelSize: F.tSmall - 2 * F.u; font.weight: Font.Bold }
                }
            }
            Text {
                text: (view.r.fromTimeline ? "From " : "") + (view.r.start ? F.when(view.r.start) : "")
                      + (view.list.length > 1 ? "     " + (view.index + 1) + " of " + view.list.length + "  (▲ ▼)" : "")
                color: F.text2; font.family: F.font; font.pixelSize: F.tMeta + 2 * F.u
            }
            Item {
                width: parent.width; height: 34 * F.u
                Rectangle { anchors.verticalCenter: parent.verticalCenter; width: parent.width - 260 * F.u; height: 8 * F.u; radius: 4 * F.u; color: "#55ffffff"
                    Rectangle { width: view.video && view.video.duration > 0 ? parent.width * Math.min(1, view.video.position / view.video.duration) : 0; height: parent.height; radius: 4 * F.u; color: F.accent } }
                Text {
                    anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                    text: view.video ? (view.video.paused ? "❚❚  " : "") + fmt(view.video.position) + " / " + fmt(view.video.duration) : ""
                    color: F.text2; font.family: F.font; font.pixelSize: F.tMeta + 2 * F.u
                    function fmt(s) { s = Math.max(0, Math.floor(s || 0)); const h = Math.floor(s / 3600), m = Math.floor(s / 60) % 60;
                                      return (h ? h + ":" + ("0" + m).slice(-2) : m) + ":" + ("0" + s % 60).slice(-2); }
                }
            }
        }
    }
}
