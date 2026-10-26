// couchbox-frigate: Frigate as a TV app (started by /usr/lib/couchbox/bin/couchbox-frigate),
// laid out like Frigate's web UI: the sidebar (Live with the camera groups, Review), the live
// dashboard, a camera full screen, the review grid and recordings. Remote: arrows move, OK
// opens, Back goes back (and, on the dashboard, leaves the app). Frigate is reached through
// frigate.py's relay on 127.0.0.1, which holds the sign-in.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Window
import CouchKit
import CouchPlayer

ApplicationWindow {
    id: win
    width: 1920
    height: 1080
    visible: true
    visibility: shot ? Window.Windowed : Window.FullScreen
    title: "Frigate"
    color: F.bg
    font.family: F.font

    readonly property var args: Qt.application.arguments
    function arg(name) { const i = args.indexOf(name); return i >= 0 ? args[i + 1] || "" : ""; }
    readonly property string shot: arg("--shot")
    readonly property real u: height / 1080
    onUChanged: F.u = u

    property string mode: "starting"         // starting | signin | app
    property int section: 0                  // 0 live, 1 review
    property int group: 0
    property var alerts: []
    property string overlay: ""              // "" | camera | player
    property string playerFrom: ""           // where Back from a recording goes
    property var typed: null                 // the keyboard pop-up types for this

    Component.onCompleted: { F.u = u; start(); }
    function start() {
        F.call("status", {}, s => {
            F.status = s;
            if (!s.configured || !s.signedIn || win.args.indexOf("--signin") >= 0) { mode = "signin"; signin.forceActiveFocus(); }
            else load();
        }, e => toast.show(e));
    }
    function load() {
        mode = "app";
        F.call("config", {}, c => { F.cameras = c.cameras; F.groups = c.groups; win.refresh(); openFromArgs(); });
        focusPage();
    }
    function refresh() {
        if (mode !== "app") return;
        F.call("active", {}, r => F.activeCams = r.cameras);
        F.call("reviews", {severity: "alert", hours: 24, unreviewed: true, limit: 16}, r => win.alerts = r.items);
    }
    Timer { interval: 10000; repeat: true; running: win.mode === "app" && win.overlay === ""; onTriggered: win.refresh() }

    Connections {
        target: F
        function onSignInNeeded(why) {
            win.stopVideo();
            win.overlay = "";
            F.call("status", {}, s => { F.status = s; win.mode = "signin"; signin.problem = why; signin.forceActiveFocus(); });
        }
        function onToast(text) { toast.show(text); }
    }

    // ------------------------------------------------------------------ navigation
    function focusPage() { (section === 0 ? live : review).forceActiveFocus(); }
    function choose(e) {
        if (e.kind === "group") { group = e.index; section = 0; focusPage(); }
        else if (e.kind === "review") { section = 1; focusPage(); }
        else if (e.kind === "signout") F.call("signout", {}, s => { F.status = s; mode = "signin"; signin.user = ""; signin.forceActiveFocus(); });
    }
    function openCamera(cams, i) {
        camera.cams = cams; camera.index = i;
        overlay = "camera";
        camera.forceActiveFocus();
        camera.start();
        updateState();
    }
    function openReview(r, list, from) {
        playerFrom = from;
        player.list = list && list.length ? list : [r];
        player.index = Math.max(0, player.list.indexOf(r));
        if (overlay === "camera") camera.stop();
        overlay = "player";
        player.forceActiveFocus();
        player.start();
        updateState();
    }
    function closePlayer() {
        player.stop();
        if (playerFrom === "camera") { overlay = "camera"; camera.forceActiveFocus(); camera.start(); }
        else { overlay = ""; focusPage(); refresh(); if (section === 1) review.load(); }
        updateState();
    }
    function closeCamera() { camera.stop(); overlay = ""; focusPage(); refresh(); updateState(); }
    function stopVideo() { camera.stop(); player.stop(); }
    function openFromArgs() {
        const o = arg("--open");
        if (o) openTarget(o);
    }
    function openTarget(o) {
        if (mode !== "app") return;
        if (o.startsWith("camera:")) {
            const name = o.slice(7);
            const all = F.cameras;
            for (let i = 0; i < all.length; i++)
                if (all[i].name === name || all[i].label.toLowerCase() === name.toLowerCase()) { group = 0; section = 0; stopVideo(); return openCamera(all, i); }
            toast.show("There's no camera called " + name + ".");
        } else if (o === "review" || o === "alerts" || o === "detections") {
            stopVideo(); overlay = ""; section = 1; review.tab = o === "detections" ? 1 : 0; focusPage();
        } else if (o === "live") { stopVideo(); overlay = ""; section = 0; focusPage(); }
    }
    function updateState() {
        const st = {page: overlay === "camera" ? "camera" : overlay === "player" ? "recording" : section === 1 ? "review" : "live",
                    group: (F.groups[group] || {}).name || ""};
        if (overlay === "camera") st.camera = camera.cam.label;
        if (overlay === "player") st.recording = (player.r.cameraLabel || "") + ": " + (player.r.objects || []).join(", ");
        control.setState(JSON.stringify(st));
        if (mpris) {
            const on = overlay !== "";
            mpris.update(on, on && video.paused, overlay === "camera" ? camera.cam.label || "" : (player.r.cameraLabel || ""),
                         "Frigate", overlay === "player" ? video.duration : 0, overlay === "player" ? video.position : 0);
        }
    }
    Connections {
        target: control
        function onCommand(js) {
            const c = JSON.parse(js);
            if (c.op === "open") { if (c.target) win.openTarget(c.target); win.raise(); win.requestActivate(); }
            else if (c.op === "media") win.media(c.action);
        }
    }
    Connections {
        target: mpris
        ignoreUnknownSignals: true
        function onCommand(action, seconds) { win.media(action, seconds); }
    }
    function media(action, seconds) {               // the remote's media keys, Home (pause-all), the voice assistant
        if (overlay === "player") {
            if (action === "playpause") video.togglePause();
            else if (action === "pause" || action === "stop") video.setPaused(true);
            else if (action === "play") video.setPaused(false);
            else if (action === "seek") video.seek(seconds || 10);
        } else if (overlay === "camera" && (action === "pause" || action === "stop")) closeCamera();
        updateState();
    }

    // ------------------------------------------------------------------ layout
    MpvVideo {                                   // one player, behind the camera and recording views
        id: video
        anchors.fill: parent
        visible: win.overlay !== ""
        onPausedChanged: win.updateState()
    }
    Item {
        id: main
        anchors.fill: parent
        visible: win.mode === "app" && win.overlay === ""
        Rail {
            id: rail
            width: F.railW
            anchors { top: parent.top; bottom: parent.bottom }
            section: win.section
            group: win.group
            unreviewed: win.alerts.length
            onChosen: e => win.choose(e)
            onToPage: win.focusPage()
            Keys.onEscapePressed: Qt.quit()
            Keys.onBackPressed: Qt.quit()
        }
        LivePage {
            id: live
            anchors { left: rail.right; right: parent.right; top: parent.top; bottom: parent.bottom }
            visible: win.section === 0
            group: win.group
            alerts: win.alerts
            onOpenCamera: i => win.openCamera(F.groupCams(win.group), i)
            onOpenReview: r => win.openReview(r, win.alerts, "live")
            onToRail: rail.forceActiveFocus()
            Keys.onEscapePressed: Qt.quit()
            Keys.onBackPressed: Qt.quit()
        }
        ReviewPage {
            id: review
            anchors { left: rail.right; right: parent.right; top: parent.top; bottom: parent.bottom }
            visible: win.section === 1
            group: win.group
            onOpenReview: (r, list) => win.openReview(r, list, "review")
            onToRail: rail.forceActiveFocus()
            Keys.onEscapePressed: { win.section = 0; win.focusPage(); }
            Keys.onBackPressed: { win.section = 0; win.focusPage(); }
        }
    }
    CameraView {
        id: camera
        anchors.fill: parent
        visible: win.overlay === "camera"
        video: video
        onClosed: win.closeCamera()
        onOpenReview: (r, list) => win.openReview(r, list, "camera")
        onIndexChanged: win.updateState()
    }
    PlayerView {
        id: player
        anchors.fill: parent
        visible: win.overlay === "player"
        video: video
        onClosed: win.closePlayer()
    }
    SignInPage {
        id: signin
        anchors.fill: parent
        visible: win.mode === "signin"
        onAsk: (what, current, secret) => {
            keyboard.title = what; keyboard.doneLabel = "Done"; keyboard.password = secret;
            win.typed = t => { if (secret) signin.password = t; else signin.user = t.trim(); if (!secret) signin.idx = 1; else signin.idx = 2; };
            keyboard.open(current, signin);
        }
        onSignedIn: { toast.show("Signed in as " + F.status.user + "."); win.load(); }
        Keys.onEscapePressed: Qt.quit()
        Keys.onBackPressed: Qt.quit()
    }
    Text {
        anchors.centerIn: parent
        visible: win.mode === "starting"
        text: "Frigate"
        color: F.faint; font.family: F.font; font.pixelSize: 40 * F.u
    }

    TextEntry {
        id: keyboard
        anchors.fill: parent
        title: "User name"
        accent: F.accent; bg: F.bg; panel: F.panel; keyColor: F.panel2; line: F.line; ink: F.text; dim: F.dim
        onAccepted: t => { if (win.typed) { const done = win.typed; win.typed = null; done(t); } }
        onCanceled: win.typed = null
    }

    Rectangle {                                  // notices ("Signed in as …")
        id: toast
        function show(t) { toastText.text = t; opacity = 1; toastTimer.restart(); }
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 48 * win.u }
        width: toastText.implicitWidth + 56 * win.u
        height: 72 * win.u
        radius: 14 * win.u
        color: F.panel2
        border.color: F.line
        opacity: 0
        z: 200
        Behavior on opacity { NumberAnimation { duration: 200 } }
        Text { id: toastText; anchors.centerIn: parent; color: F.text; font.family: F.font; font.pixelSize: 24 * win.u }
        Timer { id: toastTimer; interval: 3500; onTriggered: toast.opacity = 0 }
    }

    // ------------------------------------------------------------------ idle, off-screen tests
    // Quit after an hour without use, unless a camera or a recording is up.
    onActiveFocusItemChanged: idle.restart()
    Timer { id: idle; interval: 60 * 60 * 1000; running: win.overlay === ""; onTriggered: Qt.quit() }

    // --shot FILE [--open camera:NAME | review | detections] [--signin] [--keys k1,k2,...]
    Timer {
        running: !!win.shot
        interval: 2500
        onTriggered: {
            const keys = win.arg("--keys");
            if (keys) for (const k of keys.split(",")) shooter.press(k);
            shotTimer.start();
        }
    }
    Timer { id: shotTimer; interval: 2500; onTriggered: { shooter.save(win.shot); Qt.quit(); } }
}
