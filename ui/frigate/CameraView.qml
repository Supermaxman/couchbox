// A camera full screen: live video (through the relay's MSE bridge, in mpv). Left/Right: the
// previous or next camera in the group. Down: this camera's timeline and recent activity (OK
// opens the timeline or plays the item).
// Back: the strip, then the dashboard. If live video doesn't start, its picture refreshes
// every second instead.
import QtQuick

FocusScope {
    id: view
    property var video: null
    property var cams: []
    property int index: 0
    readonly property var cam: cams[index] || {}
    property bool connecting: true
    property bool stills: false              // live video failed: pictures instead
    property real lastPos: -1
    property var recent: []
    property bool strip: false
    property int si: 0
    signal closed()
    signal openReview(var r, var list)
    signal openTimeline(string name)

    function start() {
        connecting = true; stills = false; lastPos = -1; strip = false; recent = [];
        if (!cam.name) return;
        F.call("live", {stream: cam.stream}, r => { if (view.visible && r.url) video.loadLive(r.url); else if (!r.url) stalled.fail(); },
               () => stalled.fail());
        F.call("reviews", {severity: "all", cameras: [cam.name], limit: 12}, r => { if (r.items) recent = r.items; });
        watchdog.restart();
    }
    function stop() { watchdog.stop(); if (video) video.stop(); }
    function step(d) {
        if (cams.length < 2) return;
        index = (index + d + cams.length) % cams.length;
        start();
    }
    onVisibleChanged: if (!visible) stop()

    QtObject {
        id: stalled
        function fail() { view.connecting = false; view.stills = true; view.video.stop(); }
    }
    // frames arriving = connected; none for 15 s = fall back to pictures
    Connections {
        target: view.video
        function onPositionChanged() {
            if (!view.visible) return;
            if (view.video.position > 0 && view.video.position !== view.lastPos) { view.connecting = false; watchdog.restart(); }
            view.lastPos = view.video.position;
        }
        function onErrorChanged() { if (view.visible && view.video.error) stalled.fail(); }
    }
    Timer { id: watchdog; interval: 15000; onTriggered: if (view.visible && !demo) stalled.fail() }

    // the strip: 0 is the timeline, then the recent items
    function activate() { if (si === 0) openTimeline(cam.name); else openReview(recent[si - 1], recent); }
    Keys.onLeftPressed: { if (strip) si = Math.max(0, si - 1); else step(-1); }
    Keys.onRightPressed: { if (strip) si = Math.min(recent.length, si + 1); else step(1); }
    Keys.onDownPressed: { strip = true; si = recent.length ? 1 : 0; }
    Keys.onUpPressed: strip = false
    Keys.onReturnPressed: { if (strip) activate(); else { strip = true; si = recent.length ? 1 : 0; } }
    Keys.onEnterPressed: { if (strip) activate(); else { strip = true; si = recent.length ? 1 : 0; } }
    Keys.onEscapePressed: { if (strip) strip = false; else closed(); }
    Keys.onBackPressed: { if (strip) strip = false; else closed(); }

    Rectangle { anchors.fill: parent; color: "black"; visible: view.stills || view.connecting }
    Image {                                      // stills: the latest picture, every second
        id: still
        anchors.fill: parent
        fillMode: Image.PreserveAspectFit
        visible: view.stills
        cache: false
        property int n: 0
        source: view.stills && view.cam.name && !demo ? backend.snapshot(view.cam.name, 1080) + "&t=" + n : ""
        Timer { interval: 1000; repeat: true; running: view.stills && view.visible; onTriggered: still.n++ }
    }
    Column {
        anchors.centerIn: parent
        visible: view.connecting && !view.stills
        spacing: 20 * F.u
        BusyDots { anchors.horizontalCenter: parent.horizontalCenter }
        Text { text: "Connecting to " + (view.cam.label || "") + "…"; color: F.dim; font.family: F.font; font.pixelSize: 30 * F.u }
    }

    Rectangle {                                  // top: name, LIVE, position in the group
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: 150 * F.u
        gradient: Gradient {
            GradientStop { position: 0; color: "#c0000000" }
            GradientStop { position: 1; color: "#00000000" }
        }
        Row {
            x: 60 * F.u; y: 44 * F.u
            spacing: 20 * F.u
            Text { width: Math.min(implicitWidth, view.width - 700 * F.u); elide: Text.ElideRight
                   text: view.cam.label || ""; color: "white"; font.family: F.font; font.pixelSize: 44 * F.u; font.weight: Font.Bold }
            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: liveRow.implicitWidth + 28 * F.u; height: liveRow.implicitHeight + 14 * F.u; radius: 8 * F.u
                color: view.stills ? F.panel2 : view.connecting ? F.panel2 : F.alert
                Row {
                    id: liveRow
                    anchors.centerIn: parent
                    spacing: 8 * F.u
                    Rectangle { anchors.verticalCenter: parent.verticalCenter; width: 10 * F.u; height: width; radius: width / 2; color: "white"; visible: !view.stills }
                    Text { text: view.stills ? "PICTURES" : "LIVE"; color: "white"; font.family: F.font; font.pixelSize: 20 * F.u; font.weight: Font.Bold }
                }
            }
            Repeater {                           // what's there right now
                model: (F.activeKinds[view.cam.name] || []).slice(0, 4)
                delegate: KindBadge { required property var modelData; anchors.verticalCenter: parent.verticalCenter; kind: modelData; size: 48 * F.u; fill: "#cc" + F.alert.toString().slice(1) }
            }
        }
        Text {
            anchors { right: parent.right; rightMargin: F.edge; top: parent.top; topMargin: 50 * F.u }
            text: view.cams.length > 1 ? "◀  " + (view.index + 1) + " of " + view.cams.length + "  ▶" : ""
            color: F.text2; font.family: F.font; font.pixelSize: 26 * F.u
        }
    }
    Text {
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 34 * F.u }
        visible: !view.strip
        text: view.stills ? "Live video isn't coming through: showing a picture every second." : "▼  Timeline and recent activity"
        color: F.text2; font.family: F.font; font.pixelSize: 24 * F.u
        style: Text.Outline; styleColor: "#80000000"
    }

    Rectangle {                                  // Down: this camera's recent activity
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: stripList.height + 150 * F.u
        visible: view.strip
        gradient: Gradient {
            GradientStop { position: 0; color: "#00000000" }
            GradientStop { position: 0.25; color: "#d0000000" }
            GradientStop { position: 1; color: "#f0000000" }
        }
        Text { x: 60 * F.u; y: 40 * F.u; text: "Timeline and recent activity"; color: F.text; font.family: F.font; font.pixelSize: F.tHead - 2 * F.u; font.weight: Font.DemiBold }
        ReviewCard { id: probe; visible: false; width: 330 * F.u; showCamera: false }
        ListView {
            id: stripList
            x: 60 * F.u; y: 100 * F.u
            width: parent.width - 60 * F.u - F.edge
            height: probe.implicitHeight
            orientation: ListView.Horizontal
            spacing: F.gap
            interactive: false
            model: [null].concat(view.recent)
            currentIndex: view.si
            highlightRangeMode: ListView.ApplyRange
            preferredHighlightBegin: 0
            preferredHighlightEnd: width - 340 * F.u
            highlightMoveDuration: 180
            delegate: Loader {
                required property var modelData
                required property int index
                width: 330 * F.u; height: probe.implicitHeight
                sourceComponent: index === 0 ? timelineCard : itemCard
                Component {
                    id: itemCard
                    ReviewCard { r: modelData; showCamera: false; current: view.si === index }
                }
                Component {
                    id: timelineCard
                    Item {
                        Rectangle {
                            anchors.fill: parent; radius: F.radius
                            color: view.si === 0 ? F.panel2 : F.panel
                            Column {
                                anchors.centerIn: parent
                                spacing: 16 * F.u
                                Image { anchors.horizontalCenter: parent.horizontalCenter; width: 84 * F.u; height: width; sourceSize: Qt.size(width, height); source: F.icon("timeline") }
                                Text { anchors.horizontalCenter: parent.horizontalCenter; text: "Timeline"; color: F.text; font.family: F.font; font.pixelSize: F.tBody; font.weight: Font.DemiBold }
                                Text { anchors.horizontalCenter: parent.horizontalCenter; text: "The last 24 hours"; color: F.dim; font.family: F.font; font.pixelSize: F.tMeta }
                            }
                        }
                        Rectangle { anchors.fill: parent; anchors.margins: -F.ring; radius: F.radius + F.ring; color: "transparent"
                                    border.color: F.focus; border.width: F.ring; visible: view.si === 0 }
                        scale: view.si === 0 ? F.lift : 1
                        Behavior on scale { NumberAnimation { duration: 120 } }
                    }
                }
            }
        }
    }

    component BusyDots: Row {
        spacing: 14 * F.u
        Repeater {
            model: 3
            delegate: Rectangle {
                required property int index
                width: 18 * F.u; height: width; radius: width / 2; color: F.dim
                SequentialAnimation on opacity { loops: Animation.Infinite; running: view.connecting
                    PauseAnimation { duration: index * 200 } NumberAnimation { to: 0.2; duration: 400 } NumberAnimation { to: 1; duration: 400 } PauseAnimation { duration: (2 - index) * 200 } }
            }
        }
    }
}
