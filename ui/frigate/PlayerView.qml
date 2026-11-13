// A recording (a review item, or the timeline from a point, from Frigate's recordings as HLS),
// with the controls every Couchbox player has (CouchKit's PlayerControls): OK shows them,
// Left/Right go 10 s back or forward, Up from them scrubs along the bar (an hour's recording:
// hold to go faster), Back hides them and then goes back where you came from. In a list of
// review items, the buttons beside Play/Pause go to the one before or after.
import QtQuick
import CouchKit

FocusScope {
    id: view
    property var video: null
    property var list: []
    property int index: 0
    readonly property var r: list[index] || {}
    property bool loading: true
    property string problem: ""
    property int asked: 0                    // which start() the answer is for (a late one is dropped)
    signal closed()

    // keepFocus: the button that was pressed keeps the focus (stepping on through the list)
    function start(keepFocus) {
        loading = true; problem = "";
        const on = controls.focused;
        controls.reset();                        // the one before stops now; its picture is covered until this one's
        if (keepFocus) controls.focused = on;
        const n = ++asked;
        if (!r.camera) return;                   // the timeline plays from a point: no review id
        F.call("recording", {camera: r.camera, start: r.start, end: r.end},
               x => { if (view.visible && n === view.asked) { view.loading = false; video.load(x.url, 0); } },
               e => { if (n === view.asked) { view.problem = e; view.loading = false; } });
        if (r.id && !r.reviewed) F.call("viewed", {ids: [r.id]});
    }
    function stop() { asked++; if (video) video.stop(); }
    function step(d) {
        const i = index + d;
        if (i < 0 || i >= list.length) return;
        index = i;
        start(true);
    }
    // Play/Pause, Rewind and Fast-forward (MPRIS), the voice assistant: "toggle", "play", "pause",
    // "seek" (seconds from here), "seekTo" (seconds from the start), "stop". Shown as the keys are.
    function media(name, arg) { controls.media(name, arg); }
    onVisibleChanged: if (!visible) stop()

    Connections {
        target: view.video
        enabled: view.visible
        function onErrorChanged() { if (view.video.error) { view.problem = "This recording couldn't be played."; view.loading = false; } }
    }

    PlayerControls {
        id: controls
        anchors.fill: parent
        focus: true
        video: view.video
        loading: view.loading
        message: view.problem
        poster: view.r.thumb || ""
        u: F.u
        edge: 60 * F.u
        font: F.font; text: F.text; dim: F.text2; ink: F.text
        accent: F.accent; focusFill: F.accent; focusInk: "#ffffff"; focusRing: F.focus; scrim: "#000000"
        buttons: [
            {key: "prev", icon: "prev", label: "Previous recording", visible: view.index > 0},
            {key: "play"},
            {key: "next", icon: "next", label: "Next recording", visible: view.index < view.list.length - 1}
        ]
        onAction: key => view.step(key === "prev" ? -1 : 1)
        onLeave: view.closed()
        header: Column {
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
                      + (view.list.length > 1 ? "     " + (view.index + 1) + " of " + view.list.length : "")
                color: F.text2; font.family: F.font; font.pixelSize: F.tMeta + 2 * F.u
            }
        }
    }
}
