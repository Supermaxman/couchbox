// The player, laid out as YouTube's TV app's: the title and channel top left; the time and
// chapter, the progress bar (cut into the video's chapters) and the length; the controls (the
// channel, Description, the bell | previous, play/pause, next | like, dislike, comments, Ask,
// save, Thanks | captions, settings); and the related videos under them, rows of three.
// The remote:
//   OK            pause / play (and show the controls)
//   Left / Right  back / forward 10 s (the bar shows)      Rewind / Fast-forward: the same (MPRIS)
//   Up / Down     show the controls; Down again: the related videos; Up from the controls: the bar
//   Back          from the related videos to the controls, then hide them, then leave the player
// Streams: ytstream.py (yt-dlp), H.264 up to 1080p60; at the end the next video plays.
import QtQuick

FocusScope {
    id: player
    property string videoId: ""
    property real startAt: 0
    property var seed: ({})                    // the card it was opened from (title while loading)
    property var meta: ({})                    // watch: {video, related, next}
    property var s: null                       // stream: {url, live, duration, chapters, ...}
    property string message: ""
    property string mode: "controls"           // hidden | bar | controls | related
    property int button: 4                     // the focused control (index into controls)
    readonly property var video: Y.video
    readonly property var v: meta.video || {}
    readonly property bool live: !!(s && s.live) || !!v.live || seed.type === "live"
    readonly property var chapters: s ? s.chapters || [] : []
    readonly property real duration: video.duration || (s ? s.duration : 0) || 0
    readonly property int chapter: Y.chapterAt(chapters, video.position)
    readonly property bool watching: !!s && !video.paused && !video.ended   // keeps the app from idling out
    readonly property string label: v.title || (s ? s.title : "") || seed.title || ""
    signal finished()
    signal openChannel(string id)

    function start(id, at) {
        videoId = id;
        startAt = at || 0;
        s = null; meta = {}; message = ""; waitLeft = 0;
        mode = "controls"; button = 4;
        showControls();
        Y.call("stream", {id: id}, r => {
            if (player.videoId !== id) return;
            s = r;
            waitLeft = r.wait || 0;            // YouTube holds some streams back for as long as their ads
            if (waitLeft <= 0) begin();
            showControls();
        }, e => { if (player.videoId === id) message = e || "This video can't be played."; });
        Y.call("watch", {id: id}, r => {
            if (player.videoId !== id) return;
            meta = r;
            const rows = [];
            const rel = r.related || [];
            for (let i = 0; i < rel.length; i += 3) rows.push({kind: "shelf", title: "", items: rel.slice(i, i + 3), more: ""});
            related.rows = rows;
            mprisUpdate();
        }, () => {});
    }
    function begin() {
        if (s.url.indexOf("demo://") === 0) video.load(s.url, startAt);
        else video.loadWith(s.url, startAt, s.opts || "");
    }
    property int waitLeft: 0
    Timer {
        interval: 1000; repeat: true; running: player.waitLeft > 0
        onTriggered: { player.waitLeft--; if (player.waitLeft <= 0) player.begin(); }
    }
    Component.onCompleted: start(videoId, startAt)
    Component.onDestruction: {
        video.stop();
        if (typeof mpris !== "undefined" && mpris) mpris.update(false, false, "", "", 0, 0);
    }
    function playNext() {
        const n = meta.next || (meta.related && meta.related.length ? meta.related[0].id : "");
        if (n) start(n, 0); else finished();
    }

    // ------------------------------------------------------------------ the remote's media keys (MPRIS)
    function mprisUpdate() {
        if (typeof mpris === "undefined" || !mpris) return;
        mpris.update(!!s && player.duration > 0, video.paused, player.label, v.channel || (s ? s.channel : ""), player.duration, video.position);
    }
    Connections {
        target: typeof mpris !== "undefined" ? mpris : null
        ignoreUnknownSignals: true
        function onCommand(name, arg) {
            if (name === "playpause") video.togglePause();
            else if (name === "play") video.setPaused(false);
            else if (name === "pause") video.setPaused(true);
            else if (name === "seek" || name === "previous") player.skip(arg);
            else if (name === "seekto") video.seekTo(arg);
            else if (name === "next") player.playNext();
            else if (name === "stop") player.finished();
            player.showControls();
        }
    }
    Timer { interval: 5000; repeat: true; running: !!player.s; onTriggered: player.mprisUpdate() }
    Connections {
        target: video
        function onPausedChanged() { player.mprisUpdate(); if (video.paused) player.showControls(); }
        function onEndedChanged() { if (video.ended && !player.live) player.playNext(); }
        function onErrorChanged() { if (video.error) player.message = video.error; }
    }

    // ------------------------------------------------------------------ the overlay
    readonly property bool shown: mode !== "hidden" || video.paused || !!message || !s
    function showControls() {
        if (mode === "hidden") { mode = "controls"; }
        hide.restart();
    }
    Timer { id: hide; interval: 5000; onTriggered: if (!video.paused && player.mode !== "related" && !!player.s) player.mode = "hidden" }
    function skip(d) {
        if (live || !s) return;
        video.seek(d);
        if (mode === "hidden") mode = "bar";
        hide.restart();
    }
    function back() {
        if (mode === "related") { mode = "controls"; hide.restart(); return; }
        if (mode !== "hidden" && s && !message) { mode = "hidden"; return; }
        finished();
    }
    onModeChanged: {
        if (mode === "related") related.forceActiveFocus();
        else player.forceActiveFocus();
    }
    Connections {
        target: related
        function onAtTop() { player.mode = "controls"; hide.restart(); }
    }

    // the controls, left to right
    readonly property var controls: [
        {key: "channel"}, {key: "description", label: "Description"}, {key: "bell", icon: "bell"},
        {key: "prev", icon: "prev"}, {key: "play"}, {key: "next", icon: "next"},
        {key: "like", icon: "like"}, {key: "dislike", icon: "dislike"}, {key: "comments", icon: "comments"},
        {key: "ask", icon: "sparkle"}, {key: "save", icon: "save"}, {key: "thanks", icon: "thanks"},
        {key: "cc", icon: "cc"}, {key: "settings", icon: "settings"}
    ]
    function act(key) {
        if (key === "play") video.togglePause();
        else if (key === "prev") { if (video.position > 5 || !s) video.seekTo(0); }
        else if (key === "next") playNext();
        else if (key === "channel") { if (v.channelId || (s && s.channelId)) { video.setPaused(true); player.openChannel(v.channelId || s.channelId); } }
        else if (key === "like" || key === "dislike" || key === "save" || key === "bell")
            Y.toast("Sign in to " + ({like: "like videos", dislike: "dislike videos", save: "save videos", bell: "subscribe"})[key] + ": signing in comes in the next update.");
        else if (key === "settings" && s)
            Y.toast((s.height ? s.height + "p" + (s.fps > 30 ? Math.round(s.fps) : "") + " " : "") + (s.vcodec === "avc1" ? "H.264" : s.vcodec.toUpperCase())
                    + (s.acodec ? " · " + (s.acodec === "mp4a" ? "AAC" : s.acodec) : "") + (s.live ? " · live" : "") + ". Quality and speed menus come in a later update.");
        else Y.toast(({description: "The description", comments: "Comments", ask: "Ask", thanks: "Thanks", cc: "Captions", settings: "The settings menu"})[key] + " comes in a later update.");
    }

    Keys.onPressed: e => {
        const k = e.key;
        if (k === Qt.Key_Escape || k === Qt.Key_Back) { back(); e.accepted = true; return; }
        if (k === Qt.Key_MediaTogglePlayPause || k === Qt.Key_MediaPlay || k === Qt.Key_MediaPause || k === Qt.Key_Space) {
            video.togglePause(); showControls();
        } else if (k === Qt.Key_AudioRewind || k === Qt.Key_MediaPrevious) {
            skip(-10);
        } else if (k === Qt.Key_AudioForward || k === Qt.Key_MediaNext) {
            skip(10);
        } else if (mode === "hidden") {
            if (k === Qt.Key_Return || k === Qt.Key_Enter) { video.togglePause(); mode = "controls"; button = 4; hide.restart(); }
            else if (k === Qt.Key_Left) skip(-10);
            else if (k === Qt.Key_Right) skip(10);
            else if (k === Qt.Key_Up) { mode = "bar"; hide.restart(); }
            else if (k === Qt.Key_Down) { mode = "controls"; button = 4; hide.restart(); }
            else return;
        } else if (mode === "bar") {
            if (k === Qt.Key_Left) skip(-10);
            else if (k === Qt.Key_Right) skip(10);
            else if (k === Qt.Key_Return || k === Qt.Key_Enter) { video.togglePause(); hide.restart(); }
            else if (k === Qt.Key_Down) { mode = "controls"; hide.restart(); }
            else if (k === Qt.Key_Up) hide.restart();
            else return;
        } else if (mode === "controls") {
            hide.restart();
            if (k === Qt.Key_Left) button = Math.max(0, button - 1);
            else if (k === Qt.Key_Right) button = Math.min(controls.length - 1, button + 1);
            else if (k === Qt.Key_Up) { if (!live) mode = "bar"; }
            else if (k === Qt.Key_Down) { if (related.count) mode = "related"; }
            else if (k === Qt.Key_Return || k === Qt.Key_Enter) act(controls[button].key);
            else return;
        } else {
            return;
        }
        e.accepted = true;
    }

    // the stand-in for the video while it loads (and off screen, the demo): its thumbnail
    Image {
        anchors.fill: parent
        visible: !player.s || !hasVideo
        source: player.seed.thumb || ""
        fillMode: Image.PreserveAspectCrop
        sourceSize: Y.sz(width, height)
        asynchronous: true
    }
    Rectangle {
        anchors.fill: parent
        visible: !hasVideo && !(player.seed.thumb)
        gradient: Gradient {
            GradientStop { position: 0; color: Qt.hsla(Y.hue(player.label), 0.35, 0.22, 1) }
            GradientStop { position: 1; color: Qt.hsla((Y.hue(player.label) + 0.2) % 1, 0.45, 0.08, 1) }
        }
    }

    Item {
        id: overlay
        anchors.fill: parent
        opacity: player.shown ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 220 } }

        Rectangle {                            // scrims: the top for the title, the bottom for the controls
            anchors { left: parent.left; right: parent.right; top: parent.top }
            height: 320 * Y.u
            opacity: player.mode === "related" ? 0 : 1
            gradient: Gradient {
                GradientStop { position: 0; color: "#cc000000" }
                GradientStop { position: 1; color: "transparent" }
            }
        }
        Rectangle {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            height: player.mode === "related" ? parent.height : 560 * Y.u
            gradient: Gradient {
                GradientStop { position: 0; color: "transparent" }
                GradientStop { position: player.mode === "related" ? 0.35 : 0.45; color: "#b3000008" }
                GradientStop { position: 1; color: "#f0050512" }
            }
        }

        Item {
            id: sheet
            width: parent.width
            height: parent.height
            y: player.mode === "related" ? -480 * Y.u : 0
            Behavior on y { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }

            Column {                           // the title and channel
                x: 96 * Y.u; y: 96 * Y.u
                width: parent.width - 2 * x
                spacing: 12 * Y.u
                opacity: player.mode === "related" ? 0 : 1
                Behavior on opacity { NumberAnimation { duration: 180 } }
                Text {
                    width: Math.min(parent.width, implicitWidth)
                    text: player.label
                    color: Y.text
                    font.family: Y.font; font.pixelSize: 44 * Y.u; font.weight: Font.Medium
                    elide: Text.ElideRight
                    style: Text.Raised; styleColor: "#40000000"
                }
                Row {
                    spacing: 12 * Y.u
                    Rectangle {
                        visible: player.live
                        width: liveT.implicitWidth + 16 * Y.u; height: liveT.implicitHeight + 4 * Y.u; radius: 4 * Y.u
                        color: "#cc0000"
                        anchors.verticalCenter: parent.verticalCenter
                        Text { id: liveT; anchors.centerIn: parent; text: "LIVE"; color: "white"; font.family: Y.font; font.pixelSize: 22 * Y.u; font.weight: Font.Bold }
                    }
                    Text {
                        text: [player.v.channel || (player.s ? player.s.channel : "") || (player.seed.lines || [])[0] || "",
                               player.v.views || "", player.v.date || ""].filter(x => !!x).join(" • ")
                        color: Y.text
                        font.family: Y.font; font.pixelSize: Y.tMeta
                    }
                }
            }

            // ---------------------------------------------------------------- time, chapter, bar
            Item {
                id: barArea
                x: 96 * Y.u; y: 655 * Y.u
                width: parent.width - 192 * Y.u
                height: 70 * Y.u
                opacity: player.mode === "related" ? 0 : 1
                visible: !player.message
                Behavior on opacity { NumberAnimation { duration: 180 } }
                Text {
                    text: player.live ? "" : Y.clock(video.position) + (player.chapter >= 0 ? " • " + player.chapters[player.chapter].title : "")
                    color: Y.text
                    font.family: Y.font; font.pixelSize: 24 * Y.u; font.weight: Font.Medium
                }
                Text {
                    anchors.right: parent.right
                    text: player.live ? "" : Y.clock(player.duration)
                    color: Y.text
                    font.family: Y.font; font.pixelSize: 24 * Y.u; font.weight: Font.Medium
                }
                Item {                         // the bar, cut at the chapters
                    id: bar
                    visible: !player.live
                    y: 55 * Y.u
                    width: parent.width
                    height: (player.mode === "bar" ? 12 : 8) * Y.u
                    readonly property real frac: player.duration > 0 ? Math.min(1, video.position / player.duration) : 0
                    readonly property var cuts: {
                        const d = player.duration, c = player.chapters;
                        if (!(d > 0) || c.length < 2) return [{a: 0, b: 1}];
                        const out = [];
                        for (let i = 0; i < c.length; i++)
                            out.push({a: Math.min(1, Math.max(0, c[i].start / d)), b: Math.min(1, i + 1 < c.length ? c[i + 1].start / d : 1)});
                        return out;
                    }
                    Repeater {
                        model: bar.cuts
                        Item {
                            required property var modelData
                            readonly property real gapPx: 5 * Y.u
                            x: modelData.a * bar.width
                            width: Math.max(1, (modelData.b - modelData.a) * bar.width - gapPx)
                            height: bar.height
                            Rectangle { anchors.fill: parent; radius: height / 2; color: "#5affffff" }
                            Rectangle {
                                width: Math.max(0, Math.min(parent.width, bar.frac * bar.width - parent.x))
                                height: parent.height
                                radius: height / 2
                                color: player.mode === "bar" ? Y.red : Y.text
                            }
                        }
                    }
                    Rectangle {                // the playhead while seeking
                        visible: player.mode === "bar"
                        x: bar.frac * bar.width - width / 2
                        anchors.verticalCenter: parent.verticalCenter
                        width: 26 * Y.u; height: width; radius: width / 2
                        color: Y.red
                    }
                }
            }

            // ---------------------------------------------------------------- the controls
            Item {
                id: row
                x: 96 * Y.u; y: 741 * Y.u
                width: parent.width - 192 * Y.u
                height: 96 * Y.u
                opacity: player.mode === "related" ? 0 : 1
                Behavior on opacity { NumberAnimation { duration: 180 } }
                readonly property bool live: player.mode === "controls" && player.activeFocus
                function on(i) { return live && player.button === i; }

                Row {                          // the channel, Description, the bell
                    spacing: 12 * Y.u
                    anchors.verticalCenter: parent.verticalCenter
                    Rectangle {
                        width: 72 * Y.u; height: width; radius: width / 2
                        color: row.on(0) ? Y.text : "#33ffffff"
                        RoundImage {
                            anchors { fill: parent; margins: row.on(0) ? 5 * Y.u : 0 }
                            source: player.v.avatar || ""
                            fallback: player.v.channel || ""
                        }
                    }
                    Rectangle {
                        width: descT.implicitWidth + 72 * Y.u; height: 72 * Y.u; radius: height / 2
                        color: row.on(1) ? Y.text : "#33ffffff"
                        Text { id: descT; anchors.centerIn: parent; text: "Description"; color: row.on(1) ? Y.ink : Y.text; font.family: Y.font; font.pixelSize: 28 * Y.u; font.weight: Font.Medium }
                    }
                    CtlButton { icon: "bell"; on: row.on(2) }
                }
                Row {                          // previous, play/pause, next
                    anchors.centerIn: parent
                    spacing: 18 * Y.u
                    CtlButton { icon: "prev"; on: row.on(3); anchors.verticalCenter: parent.verticalCenter }
                    CtlButton {
                        icon: video.paused || !player.s ? "play" : "pause"
                        big: true
                        on: row.on(4) || !row.live
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    CtlButton { icon: "next"; on: row.on(5); anchors.verticalCenter: parent.verticalCenter }
                }
                Row {                          // like ... Thanks | captions, settings
                    anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                    spacing: 14 * Y.u
                    Rectangle {
                        width: actions.implicitWidth; height: 72 * Y.u; radius: height / 2
                        color: "#33ffffff"
                        Row {
                            id: actions
                            Repeater {
                                model: ["like", "dislike", "comments", "sparkle", "save", "thanks"]
                                CtlButton { required property string modelData; required property int index; icon: modelData; on: row.on(6 + index); plain: true }
                            }
                        }
                    }
                    Rectangle {
                        width: tools.implicitWidth; height: 72 * Y.u; radius: height / 2
                        color: "#33ffffff"
                        Row {
                            id: tools
                            CtlButton { icon: "cc"; on: row.on(12); plain: true }
                            CtlButton { icon: "settings"; on: row.on(13); plain: true }
                        }
                    }
                }
            }

            // ---------------------------------------------------------------- related videos
            Feed {
                id: related
                y: 948 * Y.u
                width: parent.width
                height: player.height - 440 * Y.u
                indent: 96 * Y.u
                cardW: 552 * Y.u
                fixed: true
                behind: "transparent"
                visible: player.mode !== "hidden"
                onOpen: it => Y.open(it)
            }
        }

        Text {                                 // loading, or why it won't play
            visible: !player.s || !!player.message || player.waitLeft > 0
            anchors.centerIn: parent
            width: parent.width * 0.6
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: player.message ? player.message + "\nBack to go back."
                : player.waitLeft > 0 ? "Starting in " + player.waitLeft + " s (YouTube holds it back as long as its ads would play)" : "Loading…"
            color: Y.text
            font.family: Y.font; font.pixelSize: 32 * Y.u
            style: Text.Raised; styleColor: "#80000000"
        }
    }
    Rectangle {                                // buffering
        visible: !!player.s && video.buffering && !video.paused
        anchors.centerIn: parent
        width: 96 * Y.u; height: width; radius: width / 2
        color: "#80000000"
        border.color: Y.text; border.width: 6 * Y.u
        RotationAnimation on rotation { running: parent.visible; from: 0; to: 360; duration: 1200; loops: Animation.Infinite }
        Rectangle { width: 22 * Y.u; height: width; radius: width / 2; color: Y.red; x: parent.width / 2 - width / 2; y: -4 * Y.u }
    }
}
