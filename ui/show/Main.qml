// couchbox-show: the morning show (couchbox.show), started from its tile at the front of the
// home screen. Its parts play one after another, silent, each with its words over a shade at
// the bottom and a bar across the top (a segment a part, as long as the part): yesterday's
// backyard sped up, the night's camera moments, the pets' best of yesterday, the radar with
// today's forecast, the new videos from the YouTube subscriptions. Left/Right: the clip or part
// before or after. OK on a camera moment: the Frigate app at that time; on a video: the YouTube
// app. Back leaves. When the window goes to the back (an app opened, Home), the show pauses;
// back in front it carries on. At the end (the last video part's time, or the last part when
// there are no videos) the show is watched: its tile goes.
// --reels: the Reels app instead (couchbox.reels): the list of kept reels (Library), OK plays one
// here as a show of one part; Back or its end goes back to the list. --open ID: that reel at once
// (Today at home's card on the home screen), and Back or its end leaves.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Window
import CouchPlayer

ApplicationWindow {
    id: win
    width: 1920
    height: 1080
    visible: true
    visibility: shot ? Window.Windowed : Window.FullScreen
    title: reelsMode ? "Reels" : "Morning show"
    color: "black"

    readonly property var args: Qt.application.arguments
    function arg(name) { const i = args.indexOf(name); return i >= 0 ? args[i + 1] || "" : ""; }
    readonly property string shot: arg("--shot")
    readonly property bool reelsMode: args.indexOf("--reels") >= 0
    property bool library: false                 // the Reels app's list in front
    property string reelId: ""                   // the reel playing (the Reels app)
    property bool fromCard: false                // ... opened from the home screen: Back leaves the app
    readonly property real u: height / 1080
    onUChanged: S.u = u

    property var show: null
    readonly property var parts: show ? show.parts : []
    property int pi: -1                          // the part playing
    property int ci: 0                           // its clip
    readonly property var part: parts[pi] || ({})
    readonly property string kind: part.kind || ""
    readonly property bool clips: kind === "night" || kind === "pets" || kind === "clips"
    readonly property var clip: clips ? (part.clips || [])[ci] || ({}) : ({})
    property real elapsed: 0                     // seconds into a timed part (weather, videos)
    property bool finished: false
    property var weather: null
    readonly property bool awake: win.active || noVideo   // (off screen there's no active window)

    Component.onCompleted: {
        S.u = u;
        if (reelsMode) {
            if (arg("--open")) openReel(arg("--open"), true);
            else showLibrary();
            return;
        }
        S.call("show", {}, s => {
            if (!s.parts.length) { Qt.quit(); return; }      // (watched, or past noon, since the tile was pressed)
            win.show = s;
            if (s.parts.some(p => p.kind === "weather")) S.call("weather", {}, w => win.weather = w);
            begin(s.start || 0);
        }, () => Qt.quit());
    }

    // ------------------------------------------------------------------ the Reels app
    function showLibrary() {
        video.stop();
        library = true;
        finished = false;
        lib.load(!!show);
        lib.forceActiveFocus();
        updateState();
    }
    function openReel(id, card) {
        S.call("reel", {id: id}, s => {
            if (!s.parts.length) { if (card) Qt.quit(); else showLibrary(); return; }    // (gone since)
            video.stop();
            win.show = s;
            reelId = id;
            fromCard = card;
            finished = false;
            library = false;
            pi = -1;
            begin(0);
        }, () => { if (card) Qt.quit(); });
    }
    function leave() {                           // Back, or the end of what's playing
        video.stop();
        if (reelsMode && !library && !fromCard) showLibrary();
        else Qt.quit();
    }

    // ------------------------------------------------------------------ playing
    function begin(i, fromEnd) {
        if (i < 0 || i >= parts.length) return;
        video.stop();
        pi = i;
        const p = parts[i];
        ci = fromEnd && p.clips ? p.clips.length - 1 : 0;
        elapsed = 0;
        if (p.kind === "yard") yard.restart();
        if (p.kind === "videos") { videos.index = fromEnd ? Math.max(0, videos.videos.length - 1) : 0; videos.forceActiveFocus(); }
        else keys.forceActiveFocus();
        words.opacity = 0; fadeIn.restart();
        play();
        updateState();
    }
    function play() {                            // the clip in front, from its start (when awake)
        if (!clips || !awake || !clip.file) return;
        if (clip.file === "demo:clip") video.load("demo:clip", 0);
        else video.loadWith(clip.file, 0, "aid=no");          // cameras: never any sound
    }
    function step(d) {
        if (clips) {
            const j = ci + d;
            if (j >= 0 && j < part.clips.length) { ci = j; words.opacity = 0; fadeIn.restart(); play(); return; }
        }
        if (d > 0) nextPart();
        else if (pi > 0) begin(pi - 1, true);
        else begin(0);
    }
    function nextPart() {
        if (pi < parts.length - 1) begin(pi + 1);
        else end();
    }
    function end() {                             // watched: the tile goes; on the videos, stay for a pick
        video.stop();
        if (!finished) { finished = true; S.call(reelsMode ? "reelSeen" : "seen", {id: reelId}); }
        if (kind !== "videos") leave();
    }
    function open(target) {
        if (!target) return;
        video.stop();
        S.call("open", {target: target});
    }
    onAwakeChanged: if (awake && !library) play(); else video.stop()

    Timer {                                      // the timed parts' clock
        interval: 100; repeat: true
        running: win.awake && !win.finished && (win.kind === "weather" || win.kind === "videos")
        onTriggered: {
            win.elapsed += 0.1;
            if (win.elapsed >= (win.part.seconds || 12)) win.nextPart();
        }
    }
    Connections {
        target: video
        function onEndedChanged() { if (win.clips && video.ended && !noVideo) win.step(1); }
    }
    Timer {                                      // off screen there's no end to a video: 5 s each
        interval: 5000; repeat: true
        running: noVideo && win.clips && !win.shot && !win.library
        onTriggered: win.step(1)
    }
    // Left the TV on it: gone after a while (when it's been watched, or set aside for an hour)
    Timer {
        id: idle
        interval: win.finished ? 10 * 60 * 1000 : 60 * 60 * 1000
        running: win.finished || !win.awake
        onTriggered: Qt.quit()
    }

    function updateState() {
        if (library) control.setState(JSON.stringify({page: "reels"}));
        else control.setState(JSON.stringify({page: reelsMode ? "reel" : "morning show", part: part.title || "", clip: clip.what || ""}));
    }
    Connections {
        target: control
        function onCommand(js) {
            win.raise(); win.requestActivate();
            const t = JSON.parse(js).target || "";
            if (win.reelsMode && t && t !== "reels") win.openReel(t, false);
        }
    }

    // ------------------------------------------------------------------ the remote
    Item {
        id: keys
        focus: true
        Keys.onLeftPressed: win.step(-1)
        Keys.onRightPressed: win.step(1)
        Keys.onReturnPressed: if (win.clips) win.open(win.clip.target)
        Keys.onEnterPressed: if (win.clips) win.open(win.clip.target)
        Keys.onUpPressed: (event) => event.accepted = true
        Keys.onDownPressed: (event) => event.accepted = true
        Keys.onEscapePressed: win.leave()
        Keys.onBackPressed: win.leave()
    }
    onActiveFocusItemChanged: idle.restart()

    // ------------------------------------------------------------------ the parts
    MpvVideo {
        id: video
        anchors.fill: parent
        visible: win.clips
    }
    Rectangle {                                  // a clip's still, until its first frame is drawn
        anchors.fill: parent
        color: "black"
        visible: win.clips && (noVideo || !video.hasFrame)
        Image {
            id: still
            anchors.fill: parent
            source: win.clip.poster ? "file://" + win.clip.poster : ""
            fillMode: Image.PreserveAspectFit
            asynchronous: true
        }
        Rectangle {                              // made-up clips (screenshots) have no picture
            anchors.fill: parent
            visible: still.status !== Image.Ready
            gradient: Gradient {
                GradientStop { position: 0; color: "#1c1f26" }
                GradientStop { position: 1; color: "#0b0c0f" }
            }
            Image {
                anchors.centerIn: parent
                width: 220 * win.u; height: width
                opacity: 0.12
                sourceSize: S.sz(width, height)
                source: Qt.resolvedUrl("../frigate/icons/" + (win.clip.kind || "object") + ".svg")
            }
        }
    }
    Yard {
        id: yard
        anchors.fill: parent
        visible: win.kind === "yard"
        part: win.kind === "yard" ? win.part : ({})
        running: visible && win.awake
        onDone: win.nextPart()
    }
    Forecast {
        anchors.fill: parent
        visible: win.kind === "weather"
        info: win.weather
        running: visible && win.awake
    }
    Rectangle {                                  // the videos, over the morning's own dark
        anchors.fill: parent
        visible: win.kind === "videos"
        gradient: Gradient {
            GradientStop { position: 0; color: "#1a1d2b" }
            GradientStop { position: 1; color: "#08090c" }
        }
    }
    Videos {
        id: videos
        anchors.fill: parent
        visible: win.kind === "videos"
        part: win.kind === "videos" ? win.part : ({})
        onOpened: v => win.open(v.target)
        onBefore: win.begin(win.pi - 1, true)
        onLeave: win.leave()
    }

    // ------------------------------------------------------------------ the bar and the part's name
    Rectangle {
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: 220 * win.u
        gradient: Gradient {
            GradientStop { position: 0; color: "#cc000000" }
            GradientStop { position: 1; color: "#00000000" }
        }
    }
    Row {
        id: bar
        x: S.side
        y: 48 * win.u
        width: win.width - 2 * S.side
        spacing: 10 * win.u
        readonly property real total: win.parts.reduce((t, p) => t + (p.seconds || 10), 0) || 1
        Repeater {
            model: win.parts
            Rectangle {
                required property var modelData
                required property int index
                width: (bar.width - bar.spacing * (win.parts.length - 1)) * (modelData.seconds || 10) / bar.total
                height: 6 * win.u
                radius: height / 2
                color: Qt.rgba(1, 1, 1, 0.28)
                Rectangle {
                    height: parent.height
                    radius: parent.radius
                    color: "white"
                    width: parent.width * (win.finished || index < win.pi ? 1 : index > win.pi ? 0 : win.progress())
                }
            }
        }
    }
    function progress() {
        if (kind === "yard") return yard.progress;
        if (clips) {
            const n = (part.clips || []).length || 1;
            const f = noVideo ? 0.4 : video.duration > 0 ? Math.min(1, video.position / video.duration) : 0;
            return (ci + f) / n;
        }
        return Math.min(1, elapsed / (part.seconds || 12));
    }
    Text {
        x: S.side
        y: bar.y + 34 * win.u
        text: win.part.title || ""
        color: S.morning
        font.family: S.font; font.pixelSize: 30 * win.u; font.weight: Font.DemiBold
        style: Text.Raised; styleColor: "#66000000"
    }

    // ------------------------------------------------------------------ the words
    Rectangle {
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: 380 * win.u
        visible: win.kind !== "videos"
        gradient: Gradient {
            GradientStop { position: 0; color: "#00000000" }
            GradientStop { position: 1; color: "#e0000000" }
        }
    }
    Column {
        id: words
        x: S.side
        anchors { bottom: parent.bottom; bottomMargin: 76 * win.u }
        width: win.width - 2 * S.side
        spacing: 12 * win.u
        visible: win.kind !== "videos"
        readonly property var fc: win.weather ? win.weather.forecast : null
        Text {
            width: parent.width
            text: win.kind === "yard" ? (yard.now.when || "")
                : win.clips ? (win.clip.what || "")
                : win.kind === "weather" ? (words.fc ? words.fc.line : win.weather ? "No forecast this morning." : "")
                : ""
            color: "white"
            wrapMode: Text.WordWrap
            maximumLineCount: 2
            elide: Text.ElideRight
            font.family: S.font
            font.pixelSize: (win.kind === "yard" ? 64 : win.kind === "weather" ? 44 : 48) * win.u
            font.weight: Font.DemiBold
            font.features: {"tnum": 1}
            style: Text.Raised; styleColor: "#66000000"
        }
        Text {
            width: parent.width
            text: win.kind === "yard" ? (win.part.cameraLabel || "")
                : win.clips ? [win.clip.when, win.clip.cameraLabel].filter(x => !!x).join("  ·  ")
                : win.kind === "weather" && words.fc ? [words.fc.place].concat(words.fc.alerts || []).filter(x => !!x).join("  ·  ")
                : ""
            color: S.text2
            elide: Text.ElideRight
            font.family: S.font; font.pixelSize: 28 * win.u; font.weight: Font.Medium
        }
    }
    NumberAnimation { id: fadeIn; target: words; property: "opacity"; from: 0; to: 1; duration: 350; easing.type: Easing.OutCubic }

    // ------------------------------------------------------------------ the Reels app's list, over all of it
    Library {
        id: lib
        anchors.fill: parent
        visible: win.library
        onPlayed: r => win.openReel(r.id, false)
        onLeave: Qt.quit()
    }

    // ------------------------------------------------------------------ off-screen tests
    // --shot FILE [--part KIND] [--keys k1,k2,...]
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
