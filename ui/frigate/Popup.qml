// couchbox-frigate-popup's window: a camera's live picture in a corner of the TV, over whatever
// is on, when Frigate sees something (bin/couchbox-frigate-popup decides what and for how long;
// this draws it). A layer-shell overlay like the voice indicator: it never takes the keyboard
// from the app below (OK and Back reach the service through couchbox-input instead), and it's
// unmapped while nothing shows. The video is mpv's, muted, stopped as soon as it hides. Set to
// snapshots (or when live video doesn't come through) it shows the camera's picture every second.
import QtQuick
import QtQuick.Window
import CouchPlayer
import org.kde.layershell 1.0 as LayerShell

Window {
    id: win
    readonly property bool still: shot !== ""            // --shot: drawn over a stand-in for the TV
    readonly property real u: (still ? 1080 : Screen.height) / 1080
    property var p: ({})                     // what shows: the service's present() (camera, label, seen, video, test...)
    property var look: ({position: "top-right", size: "medium", picture: "live"})
    property bool shown: false
    property bool connected: false           // live frames are coming in
    property bool stills: false              // pictures instead of video
    property real lastPos: -1
    property real frac: 1                    // the countdown bar
    property string snapBase: ""
    readonly property bool atTop: look.position.indexOf("top") === 0
    readonly property bool atLeft: look.position.indexOf("left") > 0
    readonly property real cardW: ({small: 420, medium: 560, large: 760}[look.size] || 560) * u
    readonly property real mx: 56 * u        // clear of the TV's overscan, like the apps' F.edge
    readonly property real my: 44 * u
    readonly property color sevColor: p.test ? F.accent : p.severity === "alert" ? F.alert : F.detection

    width: still ? 1920 : cardW + 2 * mx
    height: still ? 1080 : card.height + 2 * my
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus
    visible: still
    title: "Frigate pop-up"

    LayerShell.Window.scope: "couchbox-frigate-popup"
    LayerShell.Window.layer: LayerShell.Window.LayerOverlay
    LayerShell.Window.anchors: (win.atTop ? LayerShell.Window.AnchorTop : LayerShell.Window.AnchorBottom)
                               | (win.atLeft ? LayerShell.Window.AnchorLeft : LayerShell.Window.AnchorRight)
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityNone
    LayerShell.Window.exclusionZone: -1

    Component.onCompleted: F.u = u
    onUChanged: F.u = u

    Connections {
        target: popup
        function onPresent(js) { win.open(JSON.parse(js)); }
        function onExtend(id, left, total) { if (id === win.p.id) win.countdown(left, total); }
        function onDismiss() { win.close(); }
        function onLook(js) { win.look = JSON.parse(js); }
    }

    function open(x) {
        const same = shown && p.camera === x.camera && p.video === x.video;  // a newer event, same camera: keep the picture
        p = x;
        if (x.look) look = x.look;
        if (!same) {
            stopVideo();
            stills = !x.video;
            snapBase = popup.snapshot(x.camera, F.px(cardW * 9 / 16));
            pics.reset();
            if (x.video) {
                player.active = true;
                player.item.loadLive(x.video);
                watchdog.restart();
            }
        }
        shown = true;
        hideTimer.stop();
        win.visible = true;
        countdown(x.left, x.total);
    }
    function close() {
        shown = false;
        ends.stop(); bar.stop();
        stopVideo();
        hideTimer.restart();
    }
    function stopVideo() {
        watchdog.stop();
        if (player.item) player.item.stop();
        connected = false; lastPos = -1;
    }
    function countdown(left, total) {
        ends.interval = Math.max(100, left * 1000);
        ends.restart();
        bar.stop();
        frac = total > 0 ? Math.min(1, left / total) : 0;
        bar.duration = Math.max(1, left * 1000);
        bar.start();
    }
    Timer { id: ends; onTriggered: popup.expired(win.p.id || "") }
    NumberAnimation { id: bar; target: win; property: "frac"; to: 0 }
    Timer { id: hideTimer; interval: 320; onTriggered: if (!win.shown && !win.still) { win.visible = false; win.snapBase = ""; pics.reset(); } }
    // no frames for 12 s: pictures instead
    Timer { id: watchdog; interval: 12000; onTriggered: if (win.shown && !win.connected) { win.stopVideo(); win.stills = true; } }

    // ------------------------------------------------------------------ --shot: a stand-in for what's on the TV
    Rectangle {
        anchors.fill: parent
        visible: win.still
        gradient: Gradient {
            GradientStop { position: 0; color: "#2b3a4a" }
            GradientStop { position: 1; color: "#0d1117" }
        }
        Text { x: 120; y: 820; text: "Whatever is on the TV"; color: "#40ffffff"; font.family: F.font; font.pixelSize: 64; font.weight: Font.Bold }
    }

    // ------------------------------------------------------------------ the card
    Rectangle {
        id: card
        property real lift: win.shown ? 0 : (win.atTop ? -18 : 18) * win.u
        x: win.still ? (win.atLeft ? win.mx : win.width - width - win.mx) : win.mx
        y: (win.still ? (win.atTop ? win.my : win.height - height - win.my) : win.my) + lift
        width: win.cardW
        height: col.height + 2 * pad
        readonly property real pad: 18 * win.u
        radius: F.radius
        color: Qt.rgba(0.094, 0.094, 0.106, 0.96)          // F.panel, nearly opaque
        border.color: Qt.rgba(win.sevColor.r, win.sevColor.g, win.sevColor.b, 0.85)
        border.width: 2 * win.u
        opacity: win.shown ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
        Behavior on lift { NumberAnimation { duration: 260; easing.type: Easing.OutCubic } }

        Column {
            id: col
            x: card.pad; y: card.pad
            width: card.width - 2 * card.pad
            spacing: 14 * win.u

            Item {                                   // the camera, what was seen, LIVE or TEST
                width: parent.width
                height: 56 * win.u
                KindBadge {
                    id: badge
                    anchors.verticalCenter: parent.verticalCenter
                    kind: win.p.kind || "object"
                    size: 52 * win.u
                    fill: Qt.rgba(win.sevColor.r, win.sevColor.g, win.sevColor.b, 0.85)
                }
                Column {
                    anchors { left: badge.right; leftMargin: 16 * win.u; right: pill.left; rightMargin: 14 * win.u; verticalCenter: parent.verticalCenter }
                    spacing: 2 * win.u
                    Text { width: parent.width; text: win.p.label || ""; color: F.text; font.family: F.font; font.pixelSize: 28 * win.u; font.weight: Font.Bold; elide: Text.ElideRight }
                    Text { width: parent.width; text: win.p.seen || ""; color: F.text2; font.family: F.font; font.pixelSize: 21 * win.u; elide: Text.ElideRight }
                }
                Rectangle {
                    id: pill
                    anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                    width: pillRow.implicitWidth + 24 * win.u; height: pillRow.implicitHeight + 12 * win.u; radius: 8 * win.u
                    color: win.p.test ? F.accent : win.connected ? F.alert : F.panel2
                    Row {
                        id: pillRow
                        anchors.centerIn: parent
                        spacing: 7 * win.u
                        Rectangle { anchors.verticalCenter: parent.verticalCenter; width: 9 * win.u; height: width; radius: width / 2; color: "white"; visible: !win.p.test && !win.stills }
                        Text { text: win.p.test ? "TEST" : win.stills ? "PICTURE" : "LIVE"; color: "white"; font.family: F.font; font.pixelSize: 17 * win.u; font.weight: Font.Bold }
                    }
                }
            }

            Rectangle {                              // the picture: 16:9 (mpv and the pictures letterbox others)
                id: picture
                width: parent.width
                height: Math.round(width * 9 / 16)
                color: "black"
                clip: true
                Image {                              // nothing yet
                    anchors.centerIn: parent
                    visible: !win.connected && a.status !== Image.Ready && b.status !== Image.Ready
                    width: 64 * win.u; height: width; sourceSize: F.sz(width, height)
                    source: F.icon("object"); opacity: 0.18
                }
                Item {                               // pictures: two in turn, so it never blanks while the next loads
                    id: pics
                    anchors.fill: parent
                    visible: !win.connected
                    property bool showA: true
                    function reset() { a.source = ""; b.source = ""; showA = true; next(); }
                    function next() {
                        if (!win.snapBase) return;
                        const url = win.snapBase + "&t=" + Date.now();
                        if (showA) b.source = url; else a.source = url;
                    }
                    Image { id: a; anchors.fill: parent; fillMode: Image.PreserveAspectFit; asynchronous: true; cache: false; visible: pics.showA
                            sourceSize.width: F.px(picture.width)
                            onStatusChanged: if (status === Image.Ready && !pics.showA) pics.showA = true }
                    Image { id: b; anchors.fill: parent; fillMode: Image.PreserveAspectFit; asynchronous: true; cache: false; visible: !pics.showA
                            sourceSize.width: F.px(picture.width)
                            onStatusChanged: if (status === Image.Ready && pics.showA) pics.showA = false }
                    Timer { interval: 1000; repeat: true; running: win.shown && !win.connected && !!win.snapBase; onTriggered: pics.next() }
                }
                Loader {                             // made on the first live pop-up, kept (stopped) after
                    id: player
                    anchors.fill: parent
                    active: false
                    visible: win.connected && !win.stills
                    sourceComponent: Component { MpvVideo {} }
                }
                Text {
                    anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 14 * win.u }
                    visible: win.shown && !win.connected && !win.stills
                    text: "Connecting…"
                    color: F.dim; font.family: F.font; font.pixelSize: 19 * win.u
                    style: Text.Outline; styleColor: "#80000000"
                }
            }
            Connections {
                target: player.item
                ignoreUnknownSignals: true
                function onPositionChanged() {
                    const v = player.item;
                    if (win.shown && !win.stills && v.position > 0 && v.position !== win.lastPos) { win.connected = true; watchdog.stop(); }
                    win.lastPos = v.position;
                }
                function onErrorChanged() { if (win.shown && player.item.error) { win.stopVideo(); win.stills = true; } }
            }

            Rectangle {                              // how long it stays
                width: parent.width
                height: 4 * win.u
                radius: height / 2
                color: F.panel2
                Rectangle { width: parent.width * win.frac; height: parent.height; radius: parent.radius; color: win.sevColor }
            }

            Row {                                    // the remote's keys
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 10 * win.u
                KeyCap { text: "OK" }
                Hint { text: "Open camera" }
                Hint { text: "·"; color: F.faint }
                KeyCap { text: "Back" }
                Hint { text: "Dismiss" }
            }
        }
    }

    component KeyCap: Rectangle {
        property alias text: capText.text
        anchors.verticalCenter: parent ? parent.verticalCenter : undefined
        width: capText.implicitWidth + 18 * win.u; height: capText.implicitHeight + 8 * win.u; radius: 6 * win.u
        color: F.panel2
        border.color: F.line; border.width: 1
        Text { id: capText; anchors.centerIn: parent; color: F.text; font.family: F.font; font.pixelSize: 17 * win.u; font.weight: Font.Bold }
    }
    component Hint: Text {
        anchors.verticalCenter: parent ? parent.verticalCenter : undefined
        color: F.dim; font.family: F.font; font.pixelSize: 19 * win.u
    }

    // --shot FILE: save once the pop-up is up
    Timer { running: win.still; interval: 3000; onTriggered: { shooter.save(shot); Qt.quit(); } }
}
