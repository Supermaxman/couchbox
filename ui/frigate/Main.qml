// couchbox-frigate: Frigate as a TV app (started by /usr/lib/couchbox/bin/couchbox-frigate),
// laid out like Frigate's web UI: the sidebar (Live with the camera groups, Review, Timeline,
// Pop-ups), the live dashboard, a camera full screen, the review grid and recordings. Remote: arrows move, OK
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
    property int section: 0                  // 0 live, 1 review, 2 timeline, 3 pop-ups
    property int group: 0
    property var alerts: []
    property string overlay: ""              // "" | camera | player | reel
    property string playerFrom: ""           // where Back from a recording goes
    property var typed: null                 // the keyboard pop-up types for this
    readonly property bool front: win.active || noVideo   // in front (off screen there's no active window)
    property bool camLetGo: false            // the camera's stream was let go while the window was at the back

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
        F.call("config", {}, c => { F.cameras = c.cameras; F.groups = c.groups; F.labels = c.labels || []; win.refresh(); openFromArgs(); });
        focusPage();
    }
    function refresh() {
        if (mode !== "app") return;
        // only what changed: an unchanged list would rebuild the alert strip (its pictures blink, its scroll resets)
        F.call("active", {}, r => {
            if (JSON.stringify(r.kinds || {}) !== JSON.stringify(F.activeKinds)) F.activeKinds = r.kinds || {};
            if (JSON.stringify(r.cameras) !== JSON.stringify(F.activeCams)) F.activeCams = r.cameras;
        });
        F.call("reviews", {severity: "alert", hours: 24, unreviewed: true, limit: 16},
               r => { if (JSON.stringify(r.items) !== JSON.stringify(win.alerts)) win.alerts = r.items; });
    }
    Timer { interval: 10000; repeat: true; running: win.mode === "app" && win.overlay === ""; onTriggered: win.refresh() }

    Connections {
        target: F
        function onSignInNeeded(why) {
            const was = win.mode;                    // signed out while in use: say why
            win.stopVideo();
            win.overlay = "";
            F.call("status", {}, s => { F.status = s; win.mode = "signin"; signin.problem = was === "app" ? why : ""; signin.forceActiveFocus(); });
        }
        function onToast(text) { toast.show(text); }
    }

    // ------------------------------------------------------------------ navigation
    function focusPage() { [live, review, timeline, popups][section].forceActiveFocus(); }
    function choose(e) {
        if (e.kind === "group") { group = e.index; section = 0; focusPage(); }
        else if (e.kind === "review") { section = 1; focusPage(); }
        else if (e.kind === "timeline") { section = 2; focusPage(); }
        else if (e.kind === "popups") { section = 3; focusPage(); }
        else if (e.kind === "signout") F.call("signout", {}, s => { F.status = s; mode = "signin"; signin.user = ""; signin.forceActiveFocus(); });
    }
    function openCamera(cams, i) {
        camLetGo = false;
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
        if (playerFrom === "reel") { overlay = "reel"; reel.forceActiveFocus(); reel.play(); }
        else if (playerFrom === "target") { Qt.quit(); return; }             // opened from elsewhere: back there
        else if (playerFrom === "camera") { overlay = "camera"; camera.forceActiveFocus(); camera.start(); }
        else if (playerFrom === "timeline") { overlay = ""; timeline.forceActiveFocus(); }
        else { overlay = ""; focusPage(); refresh(); if (section === 1) review.load(); }
        updateState();
    }
    function closeCamera() { camera.stop(); overlay = ""; focusPage(); refresh(); updateState(); }
    function openTimeline(name) {
        stopVideo(); overlay = ""; section = 2;
        timeline.show(name);
        timeline.forceActiveFocus();
        updateState();
    }
    function stopVideo() { camera.stop(); player.stop(); reel.stop(); }
    // While you were out: the home screen card's reel; leaving it (or its end) goes back home
    function openReel() {
        F.call("reel", {}, r => {
            if (!r.clips.length) { toast.show("Nothing new from the cameras."); return; }
            stopVideo();
            reel.clips = r.clips;
            overlay = "reel";
            reel.forceActiveFocus();
            reel.start(0);
            updateState();
        }, e => toast.show(e));
    }
    function leaveReel(watched) {
        reel.stop();
        if (watched) F.call("reelSeen", {}, () => Qt.quit(), () => Qt.quit());
        else Qt.quit();
    }
    // At the back (Home, another app): nothing plays on unseen. The reel holds (ReelPage.away: it
    // used to play on, mark itself watched at its end and quit) and a live camera's stream is let
    // go; in front again the reel carries on and the camera connects again. A recording stays as
    // it is: Home pauses it (couchbox-pause-all) and Play/Pause brings it back.
    onFrontChanged: {
        if (overlay === "camera" && !front) camera.letGo();
        else if (overlay === "camera" && camLetGo) camera.live();
        camLetGo = overlay === "camera" && !front;
        updateState();
    }
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
        else if (o === "popups") { stopVideo(); overlay = ""; section = 3; focusPage(); }
        else if (o === "reel") openReel();
        else if (o.startsWith("recording:")) {               // a camera's recording then (the morning show's moments)
            const m = o.slice(10).match(/^(.+)@([\d.]+)-([\d.]+)$/);
            const c = m && F.cameras.find(x => x.name === m[1]);
            if (!c) return toast.show("There's no camera called " + (m ? m[1] : o.slice(10)) + ".");
            stopVideo(); overlay = ""; group = 0;
            openReview({camera: c.name, cameraLabel: c.label, start: parseFloat(m[2]), end: parseFloat(m[3]),
                        fromTimeline: true, kinds: [], live: false, reviewed: true}, [], "target");
        }
        else if (o === "timeline" || o.startsWith("timeline:")) {
            const name = o.slice(9).toLowerCase();
            const c = F.cameras.find(x => x.name === name || x.label.toLowerCase() === name);
            if (name && !c) return toast.show("There's no camera called " + o.slice(9) + ".");
            if (c) group = 0;
            openTimeline(c ? c.name : "");
        }
    }
    function updateState() {
        const st = {page: overlay === "camera" ? "camera" : overlay === "player" ? "recording" : overlay === "reel" ? "while you were out"
                          : ["live", "review", "timeline", "popups"][section],
                    group: (F.groups[group] || {}).name || ""};
        if (overlay === "camera") st.camera = camera.cam.label;
        if (overlay === "player") st.recording = (player.r.cameraLabel || "") + ": " + F.seen(player.r);
        control.setState(JSON.stringify(st));
        if (mpris) {                             // (a camera or the reel at the back plays nothing: not a player then)
            const on = overlay === "player" || overlay !== "" && front;
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
        if (overlay === "player" && player.media) {     // the recording's player does it, and shows it on screen
            if (action === "playpause") player.media("toggle");
            else if (action === "pause" || action === "stop") player.media("pause");
            else if (action === "play") player.media("play");
            else if (action === "seek" || action === "previous") player.media("seek", seconds || 10);
            else if (action === "seekto") player.media("seekTo", seconds || 0);
        } else if (overlay === "player") {
            if (action === "playpause") video.togglePause();
            else if (action === "pause" || action === "stop") video.setPaused(true);
            else if (action === "play") video.setPaused(false);
            else if (action === "seek" || action === "previous") video.seek(seconds || 10);
        } else if (overlay === "reel" && front) {       // Rewind / Fast-forward: the clip before or after
            if (action === "playpause") reel.togglePause();
            else if (action === "pause" || action === "stop") reel.paused = true;
            else if (action === "play") reel.paused = false;
            else if (action === "next" || action === "seek" && seconds > 0) reel.step(1);
            else if (action === "previous" || action === "seek") reel.step(-1);
        } else if (overlay === "camera" && action === "stop") closeCamera();   // (a live camera has nothing to pause)
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
        TimelinePage {
            id: timeline
            anchors { left: rail.right; right: parent.right; top: parent.top; bottom: parent.bottom }
            visible: win.section === 2
            group: win.group
            onPlay: item => win.openReview(item, [item], "timeline")
            onToRail: rail.forceActiveFocus()
            onLeave: { win.section = 0; win.focusPage(); }
        }
        PopupsPage {
            id: popups
            anchors { left: rail.right; right: parent.right; top: parent.top; bottom: parent.bottom }
            visible: win.section === 3
            onToRail: rail.forceActiveFocus()
            Keys.onEscapePressed: rail.forceActiveFocus()
            Keys.onBackPressed: rail.forceActiveFocus()
        }
    }
    CameraView {
        id: camera
        anchors.fill: parent
        visible: win.overlay === "camera"
        video: video
        onClosed: win.closeCamera()
        onOpenReview: (r, list) => win.openReview(r, list, "camera")
        onOpenTimeline: name => win.openTimeline(name)
        onIndexChanged: win.updateState()
    }
    ReelPage {
        id: reel
        anchors.fill: parent
        visible: win.overlay === "reel"
        video: video
        stills: noVideo
        away: !win.front
        onOpenClip: c => win.openReview(c.r, [c.r], "reel")
        onClosed: win.leaveReel(false)
        onFinished: win.leaveReel(true)
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
    // Quit after an hour without use, unless a camera or a recording is up (a camera or the reel
    // left at the back for an hour goes too).
    onActiveFocusItemChanged: idle.restart()
    Timer { id: idle; interval: 60 * 60 * 1000; running: win.overlay === "" || !win.front && win.overlay !== "player"; onTriggered: Qt.quit() }

    // --shot FILE [--open camera:NAME | review | detections | popups] [--signin] [--keys k1,wait:SECONDS,k2,...]
    property var shotKeys: []
    function nextKey() {
        while (shotKeys.length) {
            const k = shotKeys.shift();
            if (k.startsWith("wait:")) { keyWait.interval = parseFloat(k.slice(5)) * 1000; keyWait.start(); return; }
            shooter.press(k);
        }
        shotTimer.start();
    }
    Timer {
        running: !!win.shot
        interval: 2500
        onTriggered: { win.shotKeys = win.arg("--keys").split(",").filter(k => !!k); win.nextKey(); }
    }
    Timer { id: keyWait; onTriggered: win.nextKey() }
    Timer { id: shotTimer; interval: 2500; onTriggered: { shooter.save(win.shot); Qt.quit(); } }
}
