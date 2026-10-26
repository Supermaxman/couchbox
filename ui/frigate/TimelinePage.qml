// Timeline: the last 24 hours of a camera (or of every camera in the group, one lane each),
// like Frigate's history view. Motion is drawn faintly, alerts red and detections amber; the
// picture shows the recording at the cursor.
//   Left/Right   move the cursor (hold to go faster: a minute, then 5, then 15 at a time)
//   Up/Down      the previous or next alert or detection
//   OK           play the recording from the cursor
//   Back         the camera chooser (top row), then out
import QtQuick

FocusScope {
    id: page
    property int group: 0
    property string only: ""                 // one camera, or "" for the whole group
    property var tl: null                  // frigate.py timeline(): start, end, step, items, motion
    property bool loading: false
    property string problem: ""
    property real cursor: 0
    property string cam: ""                  // the camera in the picture
    property int zone: 1                     // 0 camera chooser, 1 timeline
    property int chip: 0                     // 0 the whole group, n: cams[n - 1]
    property int repeats: 0
    readonly property var cams: F.groupCams(group)
    readonly property var lanes: only ? [F.camera(only)] : cams
    readonly property var events: tl ? tl.items.slice().sort((a, b) => a.start - b.start) : []
    readonly property var here: eventAt(cursor, cam)
    readonly property real span: tl ? tl.end - tl.start : 86400
    signal play(var item)
    signal toRail()
    signal leave()

    function show(camera) {                  // from a camera full screen: its timeline
        only = camera || "";
        chip = camera ? Math.max(0, cams.findIndex(c => c.name === camera) + 1) : 0;
        cursor = 0; zone = 1;
        load();
    }
    property int req: 0
    function load() {
        loading = true; problem = "";
        const names = lanes.map(c => c.name), n = ++req;
        F.call("timeline", {cameras: names}, r => {
            if (n !== req) return;               // the cameras changed since: a newer answer is coming
            tl = r; loading = false;
            if (!cursor || cursor < r.start || cursor > r.end) {
                const last = events.length ? events[events.length - 1] : null;
                cursor = last ? last.start : r.end - 60;
                cam = last ? last.camera : names[0] || "";
            }
            if (lanes.findIndex(c => c.name === cam) < 0) cam = names[0] || "";
        }, e => { if (n === req) { problem = e; loading = false; } });
    }
    onGroupChanged: { only = ""; chip = 0; if (visible) load(); }
    onVisibleChanged: if (visible && !tl) load()

    function eventAt(t, camera) {
        let best = null;
        for (const e of events)
            if ((!camera || e.camera === camera) && e.start - 2 <= t && t <= (e.end || tl.end) + 2) best = e;
        return best;
    }
    function scrub(dir, held) {
        repeats = held ? repeats + 1 : 0;
        const step = repeats < 8 ? 60 : repeats < 24 ? 300 : 900;
        cursor = Math.max(tl.start, Math.min(tl.end - 5, cursor + dir * step));
        if (!only) { const e = eventAt(cursor, ""); if (e) cam = e.camera; }
    }
    function jump(dir) {
        const list = events;
        if (dir > 0) { for (const e of list) if (e.start > cursor + 1) { cursor = e.start; cam = e.camera; return; } }
        else { for (let i = list.length - 1; i >= 0; i--) if (list[i].start < cursor - 1) { cursor = list[i].start; cam = list[i].camera; return; } }
        F.toast(dir > 0 ? "Nothing later." : "Nothing earlier in the last day.");
    }
    function playHere() {
        if (!tl || !cam) return;
        const e = here;
        play({id: "", camera: cam, cameraLabel: F.camera(cam).label, severity: e ? e.severity : "", live: false, reviewed: true,
              start: cursor, end: Math.min(tl.end, cursor + 3600), kinds: e ? e.kinds : [], names: e ? e.names : [], fromTimeline: true});
    }
    function choose() {
        only = chip === 0 ? "" : cams[chip - 1].name;
        if (only) cam = only;
        zone = 1;
        load();
    }

    Keys.onLeftPressed: e => {
        if (zone === 0) { if (chip > 0) chip--; else toRail(); }
        else if (tl) scrub(-1, e.isAutoRepeat);
    }
    Keys.onRightPressed: e => {
        if (zone === 0) chip = Math.min(cams.length, chip + 1);
        else if (tl) scrub(1, e.isAutoRepeat);
    }
    Keys.onUpPressed: { if (zone === 1 && tl) jump(-1); }
    Keys.onDownPressed: { if (zone === 0) choose(); else if (tl) jump(1); }
    Keys.onReturnPressed: zone === 0 ? choose() : playHere()
    Keys.onEnterPressed: zone === 0 ? choose() : playHere()
    Keys.onEscapePressed: { if (zone === 1) zone = 0; else leave(); }
    Keys.onBackPressed: { if (zone === 1) zone = 0; else leave(); }

    // ------------------------------------------------------------------ top: title, cameras
    Column {
        id: head
        x: 56 * F.u; y: 48 * F.u
        width: page.width - x - F.edge
        spacing: 22 * F.u
        Row {
            spacing: 20 * F.u
            Text { id: heading; text: "Timeline"; color: F.text; font.family: F.font; font.pixelSize: F.tTitle; font.weight: Font.Bold }
            Text { anchors.baseline: heading.baseline; text: "Last 24 hours"; color: F.dim; font.family: F.font; font.pixelSize: F.tMeta + 2 * F.u }
        }
        ListView {
            id: chips
            width: parent.width
            height: 64 * F.u
            orientation: ListView.Horizontal
            spacing: 12 * F.u
            interactive: false
            clip: false
            model: [{name: "", label: (F.groups[page.group] || {name: "All cameras"}).name}].concat(page.cams)
            currentIndex: page.chip
            highlightRangeMode: ListView.ApplyRange
            preferredHighlightBegin: 0
            preferredHighlightEnd: width - 320 * F.u
            highlightMoveDuration: 160
            delegate: Rectangle {
                required property var modelData
                required property int index
                readonly property bool on: (index === 0 && !page.only) || (index > 0 && page.only === modelData.name)
                readonly property bool cur: page.activeFocus && page.zone === 0 && page.chip === index
                width: Math.min(chipText.implicitWidth + 48 * F.u + (index === 0 ? 40 * F.u : 0), 340 * F.u)
                height: chips.height; radius: height / 2
                color: on ? F.panel2 : "transparent"
                border.color: cur ? F.focus : F.line; border.width: (cur ? 3 : 1) * F.u
                scale: cur ? F.lift : 1
                Behavior on scale { NumberAnimation { duration: 120 } }
                Image {
                    visible: index === 0
                    x: 22 * F.u; anchors.verticalCenter: parent.verticalCenter
                    width: 28 * F.u; height: width; sourceSize: F.sz(width, height)
                    source: F.icon("timeline"); opacity: 0.8
                }
                Text {
                    id: chipText
                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter
                              leftMargin: (index === 0 ? 62 : 24) * F.u; rightMargin: 24 * F.u }
                    text: modelData.label; elide: Text.ElideRight
                    color: parent.on || parent.cur ? F.text : F.dim
                    font.family: F.font; font.pixelSize: F.tMeta + 1 * F.u; font.weight: parent.on ? Font.DemiBold : Font.Normal
                }
            }
        }
    }

    // ------------------------------------------------------------------ the picture at the cursor, and what's there
    Item {
        id: middle
        anchors { left: head.left; right: head.right; top: head.bottom; topMargin: 30 * F.u }
        height: Math.round(Math.min(page.lanes.length > 4 ? 370 * F.u : 430 * F.u, page.height - 560 * F.u))
        Rectangle {
            id: frameBox
            width: Math.round(parent.height * 16 / 9); height: parent.height
            radius: F.radius; color: "#111114"
            clip: true
            property bool showA: true
            property string want: ""
            function next(url) {                 // load into the hidden picture; it flips in when ready
                if (!url) return;
                const shown = showA ? a : b, hidden = showA ? b : a;
                if (shown.source.toString() === url) return;
                if (hidden.source.toString() === url && hidden.status === Image.Ready) { showA = !showA; return; }  // back to the last one
                hidden.source = url;
            }
            Image {
                anchors.centerIn: parent
                visible: a.status !== Image.Ready && b.status !== Image.Ready
                width: 80 * F.u; height: width; sourceSize: F.sz(width, height)
                source: F.icon("timeline"); opacity: 0.12
            }
            Image { id: a; anchors.fill: parent; fillMode: Image.PreserveAspectFit; asynchronous: true; cache: false; visible: frameBox.showA
                    sourceSize.height: F.px(frameBox.height)
                    onStatusChanged: if (status === Image.Ready && !frameBox.showA) frameBox.showA = true }
            Image { id: b; anchors.fill: parent; fillMode: Image.PreserveAspectFit; asynchronous: true; cache: false; visible: !frameBox.showA
                    sourceSize.height: F.px(frameBox.height)
                    onStatusChanged: if (status === Image.Ready && frameBox.showA) frameBox.showA = false }
            Timer {                              // after the cursor stops: the recorded picture there
                id: settle
                interval: 280
                onTriggered: if (!demo && page.cam && page.tl) frameBox.next(backend.frame(page.cam, page.cursor, Math.round(frameBox.height)))
            }
            Rectangle {
                anchors { left: parent.left; top: parent.top; margins: 14 * F.u }
                width: Math.min(camName.implicitWidth + 28 * F.u, frameBox.width - 28 * F.u); height: camName.implicitHeight + 12 * F.u; radius: 8 * F.u
                color: "#b3000000"
                Text { id: camName; anchors { fill: parent; leftMargin: 14 * F.u; rightMargin: 14 * F.u } verticalAlignment: Text.AlignVCenter
                       text: F.camera(page.cam).label || ""; elide: Text.ElideRight
                       color: "white"; font.family: F.font; font.pixelSize: F.tSmall; font.weight: Font.DemiBold }
            }
        }
        Column {                                 // the time, the camera, what's going on there
            anchors { left: frameBox.right; leftMargin: 40 * F.u; right: parent.right; top: parent.top; topMargin: 6 * F.u }
            spacing: 14 * F.u
            Text { text: page.tl ? Qt.formatTime(new Date(page.cursor * 1000), "h:mm:ss AP") : ""; color: F.text; font.family: F.font; font.pixelSize: 56 * F.u; font.weight: Font.Bold }
            Text { text: page.tl ? page.day(page.cursor) : ""; color: F.dim; font.family: F.font; font.pixelSize: F.tMeta + 2 * F.u }
            Item { width: 1; height: 8 * F.u }
            Row {
                visible: !!page.here
                spacing: 12 * F.u
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: sevText.implicitWidth + 24 * F.u; height: sevText.implicitHeight + 10 * F.u; radius: 8 * F.u
                    color: page.here ? F.sevColor(page.here) : "transparent"
                    Text { id: sevText; anchors.centerIn: parent; text: page.here && page.here.severity === "alert" ? "ALERT" : "DETECTION"
                           color: "#09090b"; font.family: F.font; font.pixelSize: F.tSmall - 2 * F.u; font.weight: Font.Bold }
                }
                Text { anchors.verticalCenter: parent.verticalCenter; text: page.here ? F.length(page.here) : ""; color: F.dim; font.family: F.font; font.pixelSize: F.tMeta }
            }
            Row {
                visible: !!page.here
                spacing: 10 * F.u
                Repeater {
                    model: page.here ? page.here.kinds.slice(0, 4) : []
                    delegate: KindBadge { required property var modelData; kind: modelData.kind; size: 52 * F.u; fill: F.panel2 }
                }
            }
            Text {
                visible: !!page.here
                width: parent.width
                text: page.here ? F.seen(page.here) : ""
                elide: Text.ElideRight
                color: F.text; font.family: F.font; font.pixelSize: F.tBody; font.weight: Font.DemiBold
            }
            Text {
                visible: !page.here && !!page.tl
                width: parent.width; wrapMode: Text.WordWrap
                text: "No alerts or detections here."
                color: F.faint; font.family: F.font; font.pixelSize: F.tMeta
            }
        }
    }
    function day(t) {
        const d = new Date(t * 1000), now = new Date();
        if (d.toDateString() === now.toDateString()) return "Today";
        if (d.toDateString() === new Date(now.getTime() - 86400000).toDateString()) return "Yesterday";
        return Qt.formatDate(d, "dddd d MMMM");
    }
    onCursorChanged: settle.restart()
    onCamChanged: settle.restart()

    // ------------------------------------------------------------------ the lanes
    Item {
        id: lanesBox
        anchors { left: head.left; right: head.right; top: middle.bottom; topMargin: 44 * F.u; bottom: hints.top; bottomMargin: 60 * F.u }
        readonly property real labelW: page.only ? 0 : 230 * F.u
        readonly property real trackX: labelW
        readonly property real trackW: width - labelW
        readonly property real laneH: Math.min(page.only ? 130 * F.u : 56 * F.u, height / Math.max(1, page.lanes.length))
        function xAt(t) { return trackX + (t - page.tl.start) / page.span * trackW; }

        Repeater {
            model: page.lanes
            delegate: Item {
                id: lane
                required property var modelData
                required property int index
                y: index * lanesBox.laneH
                width: lanesBox.width; height: lanesBox.laneH
                readonly property bool cur: page.cam === modelData.name
                Text {
                    visible: !page.only
                    width: lanesBox.labelW - 20 * F.u; anchors.verticalCenter: parent.verticalCenter
                    text: lane.modelData.label; elide: Text.ElideRight
                    color: lane.cur ? F.text : F.dim; font.family: F.font
                    font.pixelSize: Math.min(F.tMeta, lanesBox.laneH * 0.62); font.weight: lane.cur ? Font.DemiBold : Font.Normal
                }
                Rectangle {
                    x: lanesBox.trackX; width: lanesBox.trackW
                    y: 3 * F.u; height: parent.height - 6 * F.u; radius: 6 * F.u
                    color: lane.cur ? "#1f1f23" : F.panel
                }
                Canvas {                         // motion (faint) under alerts and detections
                    id: canvas
                    x: lanesBox.trackX; width: lanesBox.trackW
                    y: 3 * F.u; height: parent.height - 6 * F.u
                    renderStrategy: Canvas.Immediate
                    readonly property var src: page.tl
                    onSrcChanged: requestPaint()
                    onWidthChanged: requestPaint()
                    onPaint: {
                        const g = getContext("2d");
                        g.reset();
                        const d = page.tl;
                        if (!d) return;
                        const k = width / page.span, h = height;
                        g.fillStyle = "#3f3f46";
                        for (const m of d.motion[lane.modelData.name] || []) {
                            const mh = Math.max(2, m[1] * h * 0.8);
                            g.fillRect((m[0] - d.start) * k, h - mh, Math.max(1, d.step * k - 1), mh);
                        }
                        for (const sev of ["detection", "alert"]) {
                            g.fillStyle = sev === "alert" ? String(F.alert) : String(F.detection);
                            for (const e of page.events) {
                                if (e.camera !== lane.modelData.name || e.severity !== sev) continue;
                                const x0 = (e.start - d.start) * k, x1 = ((e.end || d.end) - d.start) * k;
                                g.fillRect(x0, h * 0.18, Math.max(5, x1 - x0), h * 0.64);
                            }
                        }
                    }
                }
            }
        }
        Repeater {                               // the hours, every three
            model: page.tl ? page.ticks() : []
            delegate: Item {
                required property var modelData
                x: lanesBox.xAt(modelData); y: 0
                height: page.lanes.length * lanesBox.laneH + 14 * F.u
                Rectangle { width: 1; height: parent.height; color: "#2a2a30" }
                Text { y: parent.height + 4 * F.u; anchors.horizontalCenter: parent.left
                       text: Qt.formatTime(new Date(parent.modelData * 1000), "h AP"); color: F.faint; font.family: F.font; font.pixelSize: F.tSmall }
            }
        }
        Rectangle {                              // the event under the cursor
            visible: !!page.here && !!page.tl
            readonly property int li: page.here ? page.lanes.findIndex(c => c.name === page.here.camera) : -1
            x: page.here && page.tl ? lanesBox.xAt(page.here.start) - 5 * F.u : 0
            width: page.here && page.tl ? Math.max(5 * F.u, lanesBox.xAt(page.here.end || page.tl.end) - lanesBox.xAt(page.here.start)) + 10 * F.u : 0
            y: li * lanesBox.laneH; height: lanesBox.laneH
            radius: 6 * F.u; color: "transparent"
            border.color: "white"; border.width: 3 * F.u
        }
        Item {                                   // the cursor
            visible: !!page.tl
            x: page.tl ? lanesBox.xAt(page.cursor) : 0
            y: -34 * F.u
            height: page.lanes.length * lanesBox.laneH + 34 * F.u
            Rectangle { x: -1.5 * F.u; y: 30 * F.u; width: 3 * F.u; height: parent.height - 30 * F.u; color: page.activeFocus && page.zone === 1 ? F.focus : F.dim }
            Rectangle {
                x: page.tl ? Math.max(-lanesBox.xAt(page.cursor), Math.min(lanesBox.width - lanesBox.xAt(page.cursor) - width, -width / 2)) : 0
                width: curText.implicitWidth + 22 * F.u; height: curText.implicitHeight + 8 * F.u; radius: height / 2
                color: page.activeFocus && page.zone === 1 ? F.focus : F.panel2
                Text { id: curText; anchors.centerIn: parent; text: page.tl ? F.clock(page.cursor) : ""; color: page.activeFocus && page.zone === 1 ? "#09090b" : F.text
                       font.family: F.font; font.pixelSize: F.tSmall; font.weight: Font.DemiBold }
            }
        }
        Text {
            anchors.centerIn: parent
            visible: page.loading || !!page.problem
            text: page.problem || "Loading the last day…"
            color: F.dim; font.family: F.font; font.pixelSize: F.tBody
        }
    }
    function ticks() {
        const out = [], d = new Date(tl.start * 1000);
        d.setMinutes(0, 0, 0);
        d.setHours(d.getHours() + 1);
        while (d.getTime() / 1000 < tl.end) {
            if (d.getHours() % 3 === 0) out.push(d.getTime() / 1000);
            d.setHours(d.getHours() + 1);
        }
        return out;
    }

    Row {
        id: hints
        anchors { left: head.left; bottom: parent.bottom; bottomMargin: 36 * F.u }
        spacing: 34 * F.u
        Repeater {
            model: page.zone === 0 ? [["◀ ▶", "camera"], ["OK", "show its timeline"], ["Back", "leave"]]
                                   : [["◀ ▶", "move (hold: faster)"], ["▲ ▼", "earlier / later event"], ["OK", "play from here"], ["Back", "cameras"]]
            delegate: Row {
                required property var modelData
                spacing: 10 * F.u
                Rectangle {
                    width: keyText.implicitWidth + 18 * F.u; height: keyText.implicitHeight + 8 * F.u; radius: 6 * F.u
                    color: F.panel2
                    Text { id: keyText; anchors.centerIn: parent; text: modelData[0]; color: F.text2; font.family: F.font; font.pixelSize: F.tSmall - 1 * F.u; font.weight: Font.DemiBold }
                }
                Text { anchors.verticalCenter: parent.verticalCenter; text: modelData[1]; color: F.faint; font.family: F.font; font.pixelSize: F.tSmall }
            }
        }
    }
}
