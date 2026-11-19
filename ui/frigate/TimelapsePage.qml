// Timelapse: a camera's recordings sped up (couchbox.timelapse): which camera, over when (the
// last hour, the last 3 hours, today so far, yesterday) and how fast (2x to 1200x, the speeds
// that make a sensible length for that time). Frigate makes it; it plays here when it's ready.
// Up/Down move. Left/Right (or OK) step a choice; OK on Make starts it, and again stops it.
// Left on Make, and Back, go to the sidebar.
import QtQuick

FocusScope {
    id: page
    property var spans: []                   // timelapse.spans(): [{key, label, start, end, speeds, best}]
    property bool loading: true
    property string problem: ""
    property int camIdx: 0
    property int spanIdx: 0
    property int speedIdx: 0
    property int idx: 0
    property int job: 0                      // the one being made (0: none)
    property var st: ({})                    // its state: {state, percent, file, error}
    property var madeOver: ({})              // the times it covers
    property var done: null                  // made while this page was out of sight: played from Make
    signal toRail()
    signal play(var item)

    readonly property var cam: F.cameras[camIdx] || {name: "", label: ""}
    readonly property var span: spans[spanIdx] || null
    readonly property var speeds: span ? span.speeds : []
    readonly property var speed: speeds[speedIdx] || null
    readonly property bool making: job > 0
    readonly property var rows: [
        {key: "camera", label: "Camera", value: cam.label},
        {key: "span", label: "When", value: span ? span.label : ""},
        {key: "speed", label: "Speed", value: speed ? speed.label : "", sub: speed ? speed.lengthLabel + " of video" : ""},
        {key: "make", label: making ? "Making the timelapse" : done ? "Play the timelapse" : "Make timelapse",
         value: making ? Math.floor(st.percent || 0) + "%" : "",
         sub: making ? (st.state === "fetching" ? "Bringing it to the TV" : "Frigate is speeding it up")
                     : done ? done.cameraLabel + "  ·  " + done.when
                     : speed ? "Ready in about " + ready(speed.ready) : ""}
    ]

    function ready(s) { return s < 50 ? "a minute" : Math.round(s / 60) + " min"; }

    function load() {
        loading = true; problem = "";
        F.call("timelapseChoices", {}, r => {
            const key = span ? span.key : "", sp = speed ? speed.speed : 0;
            spans = r.spans;
            const i = spans.findIndex(s => s.key === key);
            spanIdx = i >= 0 ? i : Math.min(1, spans.length - 1);
            const j = speeds.findIndex(s => s.speed === sp);
            speedIdx = j >= 0 ? j : (span ? span.best : 0);
            loading = false;
        }, e => { problem = e; loading = false; });
    }
    onVisibleChanged: if (visible && !making) load()
    function show(camera) {                  // from a camera full screen: that camera
        const i = F.cameras.findIndex(c => c.name === camera);
        if (i >= 0) camIdx = i;
        idx = 0;
    }

    function step(key, d) {
        if (making) return;
        done = null;
        if (key === "camera") camIdx = (camIdx + d + F.cameras.length) % Math.max(1, F.cameras.length);
        else if (key === "span" && spans.length) { spanIdx = (spanIdx + d + spans.length) % spans.length; speedIdx = span.best; }
        else if (key === "speed" && speeds.length) speedIdx = Math.max(0, Math.min(speeds.length - 1, speedIdx + d));
    }
    function make() {
        if (making) { stop(); F.toast("Stopped."); return; }
        if (done) { const d = done; done = null; play(d); return; }
        if (!cam.name || !speed) return;
        st = {state: "making", percent: 0};
        F.call("timelapseMake", {camera: cam.name, span: span.key, speed: speed.speed},
               r => { job = r.job; madeOver = {start: r.start, end: r.end, label: span.label, hours: span.hours, speed: speed.label}; poll.start(); },
               e => { st = {}; F.toast(e); });
    }
    function stop() { poll.stop(); job = 0; st = {}; F.call("timelapseCancel", {}); }
    Timer {
        id: poll
        interval: 1000; repeat: true
        onTriggered: {
            const n = page.job;
            F.call("timelapseState", {job: n}, r => {
                if (n !== page.job) return;
                page.st = r;
                if (r.state === "ready") {
                    poll.stop(); page.job = 0;
                    page.done = ({id: "", camera: "", file: r.file, cameraLabel: page.cam.label, fromTimeline: true, live: false, reviewed: true,
                               kinds: [], names: [], severity: "", start: page.madeOver.start, end: page.madeOver.end,
                               timelapse: "Timelapse, " + page.madeOver.speed, when: page.madeOver.label + "  ·  " + page.madeOver.hours});
                    page.st = {};
                    if (page.visible && page.activeFocus) { const d = page.done; page.done = null; page.play(d); }
                    else F.toast("The timelapse is ready: it's under Timelapse.");
                } else if (r.state === "failed") { poll.stop(); page.job = 0; page.st = {}; F.toast(r.error || "That didn't work."); }
            });
        }
    }

    Keys.onUpPressed: idx = Math.max(0, idx - 1)
    Keys.onDownPressed: idx = Math.min(rows.length - 1, idx + 1)
    Keys.onLeftPressed: { if (rows[idx].key === "make") toRail(); else step(rows[idx].key, -1); }
    Keys.onRightPressed: if (rows[idx].key !== "make") step(rows[idx].key, 1)
    Keys.onReturnPressed: rows[idx].key === "make" ? make() : step(rows[idx].key, 1)
    Keys.onEnterPressed: rows[idx].key === "make" ? make() : step(rows[idx].key, 1)

    Column {                                     // the title
        id: head
        x: 56 * F.u; y: 48 * F.u
        width: page.width - x - F.edge
        spacing: 14 * F.u
        Row {
            spacing: 20 * F.u
            Text { id: heading; text: "Timelapse"; color: F.text; font.family: F.font; font.pixelSize: F.tTitle; font.weight: Font.Bold }
            Text { anchors.baseline: heading.baseline; text: "A camera sped up"; color: F.dim; font.family: F.font; font.pixelSize: F.tMeta + 2 * F.u }
        }
        Text {
            width: parent.width
            visible: !!page.problem
            wrapMode: Text.WordWrap
            text: page.problem
            color: F.detection; font.family: F.font; font.pixelSize: F.tMeta
        }
    }

    Column {                                     // the choices
        id: list
        x: 56 * F.u
        y: head.y + head.height + 40 * F.u
        width: 640 * F.u
        spacing: 12 * F.u
        opacity: page.loading ? 0 : 1
        Repeater {
            model: page.rows
            delegate: Rectangle {
                id: row
                required property var modelData
                required property int index
                readonly property bool cur: page.activeFocus && page.idx === index
                readonly property bool primary: modelData.key === "make"
                width: list.width
                height: (modelData.sub ? 96 : 78) * F.u
                radius: 12 * F.u
                clip: true
                color: primary ? (cur ? F.accent : "#1d4ed8") : cur ? F.panel2 : F.panel
                border.color: cur ? F.focus : F.line
                border.width: (cur ? 3 : 1) * F.u
                opacity: page.making && !primary ? 0.55 : 1
                Rectangle {                          // making: how far along
                    visible: row.primary && page.making
                    width: parent.width * Math.max(0.02, (page.st.percent || 0) / 100); height: parent.height
                    color: "#ffffff"; opacity: 0.16
                    Behavior on width { NumberAnimation { duration: 900; easing.type: Easing.OutCubic } }
                }
                Rectangle {                          // and that it's moving
                    visible: row.primary && page.making
                    width: 160 * F.u; height: parent.height
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0; color: "#00ffffff" }
                        GradientStop { position: 0.5; color: "#26ffffff" }
                        GradientStop { position: 1; color: "#00ffffff" }
                    }
                    NumberAnimation on x { running: row.primary && page.making && page.visible; from: -160 * F.u; to: row.width; duration: 1600; loops: Animation.Infinite }
                }
                Column {
                    anchors { left: parent.left; leftMargin: 28 * F.u; right: value.left; rightMargin: 20 * F.u; verticalCenter: parent.verticalCenter }
                    spacing: 4 * F.u
                    Text { width: parent.width; text: row.modelData.label; color: F.text; font.family: F.font; font.pixelSize: 28 * F.u; font.weight: Font.DemiBold; elide: Text.ElideRight }
                    Text { width: parent.width; visible: !!row.modelData.sub; text: row.modelData.sub || ""; color: row.primary ? "#dbeafe" : F.dim; font.family: F.font; font.pixelSize: 21 * F.u; elide: Text.ElideRight }
                }
                Row {                                // ◀ value ▶ (the arrows while it has focus; their room always, so the value stays put)
                    id: value
                    anchors { right: parent.right; rightMargin: 28 * F.u; verticalCenter: parent.verticalCenter }
                    spacing: 16 * F.u
                    readonly property bool arrows: !row.primary && row.cur && !page.making
                    Text { visible: !row.primary; opacity: value.arrows ? 1 : 0; text: "◀"; color: F.text; font.family: F.font; font.pixelSize: 26 * F.u }
                    Text {
                        width: Math.min(implicitWidth, row.width * 0.5)
                        text: row.modelData.value || ""
                        elide: Text.ElideRight
                        color: row.primary ? "white" : row.cur ? F.text : F.text2
                        font.family: F.font; font.pixelSize: 26 * F.u; font.weight: row.primary ? Font.DemiBold : Font.Normal
                    }
                    Text { visible: !row.primary; opacity: value.arrows ? 1 : 0; text: "▶"; color: F.text; font.family: F.font; font.pixelSize: 26 * F.u }
                }
            }
        }
    }

    Column {                                     // the camera then (the middle of the time chosen)
        anchors { left: list.right; leftMargin: 40 * F.u; right: parent.right; rightMargin: F.edge; top: list.top }
        spacing: 16 * F.u
        Rectangle {
            id: picBox
            width: parent.width; height: Math.round(width * 9 / 16)
            radius: F.radius; color: "#111114"
            clip: true
            readonly property string want: page.cam.name && page.span
                ? backend.frame(page.cam.name, Math.round((page.span.start + page.span.end) / 2 / 60) * 60, Math.round(F.px(height))) : ""
            Image {
                anchors.centerIn: parent
                visible: pic.status !== Image.Ready
                width: 80 * F.u; height: width; sourceSize: F.sz(width, height)
                source: F.icon("timelapse"); opacity: 0.12
            }
            Image { id: pic; anchors.fill: parent; fillMode: Image.PreserveAspectFit; asynchronous: true; cache: false; source: picBox.want }
        }
        Text { text: page.cam.label; color: F.text; font.family: F.font; font.pixelSize: F.tHead; font.weight: Font.DemiBold }
        Text { text: page.span ? page.span.label + "  ·  " + page.span.hours : ""; color: F.text2; font.family: F.font; font.pixelSize: F.tMeta + 2 * F.u }
    }

    Text {
        anchors.centerIn: parent
        visible: page.loading
        text: "Loading…"
        color: F.dim; font.family: F.font; font.pixelSize: 30 * F.u
    }
}
