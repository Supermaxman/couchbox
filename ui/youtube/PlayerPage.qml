// The player, laid out as YouTube's TV app's: the title and channel top left; the time and
// chapter, the progress bar (cut into the video's chapters) and the length; the controls (the
// channel, Description, the bell | previous, play/pause, next | like, dislike, comments, Ask,
// save, Thanks | captions, settings); and the related videos under them, rows of three.
// The remote:
//   OK            pause / play (and show the controls)
//   Left / Right  back / forward 10 s (the bar shows)      Rewind / Fast-forward: the same (MPRIS)
//   Up / Down     show the controls; Down again: the related videos; Up from the controls: the bar,
//                 with the chapters' pictures above it; Up again picks a chapter (Left / Right, OK)
//   Back          from the related videos to the controls, then hide them, then leave the player
// Description and comments open beside the video; the settings menu has quality, speed and
// captions (CC turns captions on and off). At the end, Up next (the queue first) after a countdown.
// Streams: ytstream.py (yt-dlp), H.264 up to 1080p60; at the end the next video plays.
// Signed in: like and dislike, the channel's panel (Subscribe / Subscribed, Go to channel), the
// bell's notification levels, Save (Watch later, playlists); it starts where YouTube says this
// profile left off, and reports what's watched (History, resume on every device).
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
    // the chapters: the watch page's (with pictures) or yt-dlp's
    readonly property var chapters: meta.chapters && meta.chapters.length ? meta.chapters : s ? s.chapters || [] : []
    property int chapterPick: 0                // the chapter picked in the strip (Up from the bar)
    property real speed: 1
    property string captionsOn: ""             // the captions shown (their name), "" none
    property bool ending: false                // the end screen is up
    readonly property real duration: video.duration || (s ? s.duration : 0) || 0
    readonly property int chapter: Y.chapterAt(chapters, video.position)
    readonly property bool watching: !!s && !video.paused && !video.ended   // keeps the app from idling out
    readonly property string label: v.title || (s ? s.title : "") || seed.title || ""
    property string panel: ""                  // "" | channel | notify | save: a panel beside the video
    property var saveOptions: []
    property string cpn: ""                    // this playback's id in YouTube's reports
    property bool reported: false
    property real lastReport: 0
    signal finished()
    signal openChannel(string id)

    function start(id, at) {
        if (s && reported) report(video.ended ? "end" : "pause");     // the one before
        videoId = id;
        startAt = at || 0;
        s = null; meta = {}; message = ""; waitLeft = 0; panel = ""; reported = false; lastReport = 0;
        cpn = "";
        const abc = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
        for (let i = 0; i < 16; i++) cpn += abc[Math.floor(Math.random() * 64)];
        mode = "controls"; button = 4; ending = false; captionsOn = "";
        if (speed !== 1) video.setSpeed(speed);
        showControls();
        Y.call("stream", {id: id}, r => {
            if (player.videoId !== id) return;
            s = r;
            // where this profile left off: the card's (a part-watched card's red bar) unless told
            const p = player.seed.progress || 0;
            if (!player.startAt && p > 0.02 && p < 0.95 && r.duration && !r.live) player.startAt = Math.max(0, p * r.duration - 3);
            waitLeft = r.wait || 0;            // YouTube holds some streams back for as long as their ads
            if (waitLeft <= 0) begin();
            showControls();
        }, e => { if (player.videoId === id) message = e || "This video can't be played."; });
        Y.call("watch", {id: id}, r => {
            if (player.videoId !== id) return;
            meta = r;
            // YouTube's own resume point for this profile, when the card didn't have one
            if (r.start > 0 && !player.startAt) {
                player.startAt = r.start;
                if (player.s && video.position < r.start - 5) video.seekTo(r.start);
            }
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
        if (s && reported) report(video.ended ? "end" : "pause");
        Y.videoSide = false;
        video.stop();
        if (typeof mpris !== "undefined" && mpris) mpris.update(false, false, "", "", 0, 0);
    }
    // what plays next: the queue first (a card's menu: Play next, Add to queue), then YouTube's Up next
    function upNext() {
        if (Y.queue.length) return {item: Y.queue[0], queued: true};
        const rel = meta.related || [];
        const n = rel.find(x => x.id === meta.next) || rel[0];
        return n ? {item: n, queued: false} : null;
    }
    function playNext() {
        const n = upNext();
        if (!n) { finished(); return; }
        if (n.queued) Y.queue = Y.queue.slice(1);
        seed = n.item;
        start(n.item.id, 0);
    }
    function showEnd() {
        const n = upNext();
        if (!n) { mode = "controls"; showControls(); return; }
        endScreen.next = n.item;
        endScreen.queued = n.queued;
        endScreen.seconds = meta.countdown || 5;
        ending = true;
        endScreen.begin();
        endScreen.forceActiveFocus();
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
        function onEndedChanged() { if (video.ended && !player.live) player.showEnd(); }
        function onErrorChanged() { if (video.error) player.message = video.error; }
    }

    // ------------------------------------------------------------------ history (signed in)
    function report(event) {
        if (!Y.signedIn || !s || s.live) return;
        Y.call("report", {id: videoId, cpn: cpn, event: event, position: video.position, duration: player.duration}, () => {}, () => {});
    }
    Connections {
        target: video
        function onPositionChanged() {
            if (!player.s) return;
            if (!player.reported && video.position > Math.max(1, player.startAt)) { player.reported = true; player.lastReport = video.position; player.report("start"); }
            else if (player.reported && !video.paused && Math.abs(video.position - player.lastReport) >= 10) { player.lastReport = video.position; player.report("progress"); }
        }
        function onPausedChanged() { if (player.reported) player.report(video.paused ? "pause" : "progress"); }
    }

    // ------------------------------------------------------------------ signed in: like, subscribe, save
    function signInFirst(what) { Y.toast("Sign in to " + what + ": the guide's picture, then Add account."); }
    function rate(status) {
        if (!Y.signedIn) return signInFirst("rate videos");
        const now = v.like === status ? "none" : status;
        Y.call("like", {id: videoId, status: now}, () => {
            meta = Object.assign({}, meta, {video: Object.assign({}, v, {like: now})});
            Y.toast(now === "like" ? "Added to Liked videos" : now === "dislike" ? "You dislike this video" : "Rating removed");
        });
    }
    function subscribe(on) {
        if (!Y.signedIn) return signInFirst("subscribe");
        Y.call("subscribe", {id: v.channelId, on: on}, () => {
            meta = Object.assign({}, meta, {video: Object.assign({}, v, {subscribed: on, notify: on ? (v.notify || "personalized") : ""})});
            Y.toast(on ? "Subscribed to " + v.channel : "Unsubscribed from " + v.channel);
            if (!on && panel === "notify") panel = "";
        });
    }
    function openPanel(which) {
        if (which === "save") {
            if (!Y.signedIn) return signInFirst("save videos");
            Y.call("saveOptions", {id: videoId}, r => { player.saveOptions = r.playlists || []; player.panel = "save"; });
            return;
        }
        if (which === "notify" && !Y.signedIn) return signInFirst("choose notifications");
        panel = which;
        if (which === "comments") { comments.token = (meta.details || {}).commentsToken || ""; comments.count = (meta.details || {}).comments || ""; comments.load(); }
    }
    onPanelChanged: {
        Y.videoSide = !!panel;
        const checked = panelOptions.findIndex(o => o.checked);     // the current choice, as YouTube's does
        sidePanel.index = checked >= 0 && panel !== "save" ? checked : 0;
        if (panel === "description") { description.index = 0; description.forceActiveFocus(); }
        else if (panel === "comments") comments.forceActiveFocus();
        else if (panel) sidePanel.forceActiveFocus();
        else { player.forceActiveFocus(); mode = "controls"; hide.restart(); }
    }
    readonly property var notifyLevels: [
        {level: "all", label: "All", icon: "bell-all"}, {level: "personalized", label: "Personalized", icon: "bell"},
        {level: "none", label: "None", icon: "bell-off"}
    ]
    readonly property var panelOptions: {
        if (panel === "channel")
            return [{label: v.subscribed ? "Subscribed" : "Subscribe", trailing: v.subscribed ? ({all: "bell-all", none: "bell-off"})[v.notify] || "bell" : ""},
                    {label: "Go to channel"}];
        if (panel === "notify") {
            const have = (v.notifyOptions || []).map(o => o.level);
            return notifyLevels.filter(l => have.length === 0 || have.indexOf(l.level) >= 0)
                .map(l => ({label: l.label, icon: l.icon, checked: v.notify === l.level, level: l.level}))
                .concat([{label: "Unsubscribe", icon: "unsubscribe", level: "unsubscribe"}]);
        }
        if (panel === "save")
            return saveOptions.map(o => ({label: o.title, icon: o.id === "WL" ? "history" : "list", checked: o.saved, id: o.id}));
        if (panel === "settings")
            return [{label: "Quality", value: qualityLabel, icon: "settings"}, {label: "Playback speed", value: speed === 1 ? "Normal" : speed + "×", icon: "speed"},
                    {label: "Captions", value: captionsOn || "Off", icon: "cc"}];
        if (panel === "quality")
            return [{label: "Auto", checked: !s || !s.maxHeight || s.maxHeight >= 1080, h: 1080}]
                .concat(((s && s.heights) || []).map(h => ({label: h + "p", checked: s.maxHeight === h && h < 1080, h: h})));
        if (panel === "speed")
            return [0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2].map(x => ({label: x === 1 ? "Normal" : x + "×", checked: speed === x, x: x}));
        if (panel === "captions")
            return [{label: "Off", checked: !captionsOn}].concat(((s && s.captions) || []).map(c => ({label: c.name, checked: captionsOn === c.name, c: c})));
        return [];
    }
    readonly property string qualityLabel: s && s.height ? "Auto (" + Math.min(s.height, s.width || s.height) + "p" + (s.fps > 30 ? Math.round(s.fps) : "") + ")" : "Auto"
    function setQuality(h) {
        const id = videoId, at = video.position;
        Y.call("stream", {id: id, max_height: h}, r => {
            if (player.videoId !== id) return;
            s = r;
            if (r.url.indexOf("demo://") === 0) video.load(r.url, at); else video.loadWith(r.url, at, r.opts || "");
            if (captionsOn) { const c = (r.captions || []).find(x => x.name === captionsOn); if (c) video.addSubtitleTrack(c.url, c.name); }
        }, e => Y.toast(e));
    }
    function setCaptions(c) {
        if (!c) { video.setSubtitle(0); captionsOn = ""; return; }
        const have = video.subtitles.find(t => t.title === c.name);
        if (have) video.setSubtitle(have.id); else video.addSubtitleTrack(c.url, c.name);
        captionsOn = c.name;
    }
    function toggleCaptions() {
        if (captionsOn) return setCaptions(null);
        const c = (s && s.captions) || [];
        if (!c.length) return Y.toast("No captions for this video.");
        setCaptions(c[0]);
        Y.toast("Captions: " + c[0].name);
    }
    function panelPick(i) {
        const o = panelOptions[i];
        if (panel === "channel") {
            if (i === 0) { if (v.subscribed) openPanel("notify"); else subscribe(true); }
            else { panel = ""; video.setPaused(true); player.openChannel(v.channelId); }
        } else if (panel === "notify") {
            if (o.level === "unsubscribe") { subscribe(false); return; }
            const opt = (v.notifyOptions || []).find(x => x.level === o.level);
            if (!opt) return;
            Y.call("notify", {params: opt.params, level: o.level}, () => {
                meta = Object.assign({}, meta, {video: Object.assign({}, v, {notify: o.level})});
            });
        } else if (panel === "settings") {
            panel = ["quality", "speed", "captions"][i];
        } else if (panel === "quality") {
            setQuality(o.h); panel = "";
        } else if (panel === "speed") {
            speed = o.x; video.setSpeed(o.x); panel = "";
        } else if (panel === "captions") {
            setCaptions(o.c || null); panel = "";
        } else if (panel === "save") {
            const add = !o.checked;
            Y.call("save", {id: videoId, playlist: o.id, add: add}, () => {
                saveOptions = saveOptions.map(x => x.id === o.id ? Object.assign({}, x, {saved: add}) : x);
                Y.toast((add ? "Saved to " : "Removed from ") + o.label);
            });
        }
    }

    // ------------------------------------------------------------------ the overlay
    readonly property bool shown: mode !== "hidden" || video.paused || !!message || !s
    function showControls() {
        if (mode === "hidden") { mode = "controls"; }
        hide.restart();
    }
    Timer { id: hide; interval: 5000; onTriggered: if (!video.paused && player.mode !== "related" && player.mode !== "chapters" && !!player.s && !player.ending) player.mode = "hidden" }
    function skip(d) {
        if (live || !s) return;
        video.seek(d);
        if (mode === "hidden") mode = "bar";
        hide.restart();
    }
    function back() {
        if (panel === "quality" || panel === "speed" || panel === "captions") { panel = "settings"; return; }
        if (panel) { panel = ""; return; }
        if (mode === "chapters") { mode = "bar"; hide.restart(); return; }
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
        else if (key === "channel") { if (v.channelId || (s && s.channelId)) openPanel("channel"); }
        else if (key === "like" || key === "dislike") rate(key);
        else if (key === "save") openPanel("save");
        else if (key === "bell") { if (!Y.signedIn) signInFirst("subscribe"); else if (v.subscribed) openPanel("notify"); else subscribe(true); }
        else if (key === "settings") openPanel("settings");
        else if (key === "description") openPanel("description");
        else if (key === "comments") openPanel("comments");
        else if (key === "cc") toggleCaptions();
        else Y.toast(({ask: "Ask", thanks: "Thanks"})[key] + " isn't on TVs yet.");
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
            else if (k === Qt.Key_Up) { if (chapters.length > 1) { chapterPick = Math.max(0, chapter); mode = "chapters"; } hide.restart(); }
            else return;
        } else if (mode === "chapters") {
            hide.restart();
            if (k === Qt.Key_Left) chapterPick = Math.max(0, chapterPick - 1);
            else if (k === Qt.Key_Right) chapterPick = Math.min(chapters.length - 1, chapterPick + 1);
            else if (k === Qt.Key_Return || k === Qt.Key_Enter) { video.seekTo(chapters[chapterPick].start); mode = "bar"; }
            else if (k === Qt.Key_Down) mode = "bar";
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

    // the video's place: the whole screen, or left of a panel
    readonly property rect place: Y.videoSide ? Qt.rect(54 * Y.u, 218 * Y.u, 1146 * Y.u, 646 * Y.u) : Qt.rect(0, 0, width, height)
    // the stand-in for the video while it loads (and off screen, the demo): its thumbnail
    Image {
        x: player.place.x; y: player.place.y; width: player.place.width; height: player.place.height
        visible: !player.s || !hasVideo
        source: player.seed.thumb || ""
        fillMode: Image.PreserveAspectCrop
        sourceSize: Y.sz(width, height)
        asynchronous: true
    }
    Rectangle {
        x: player.place.x; y: player.place.y; width: player.place.width; height: player.place.height
        visible: !hasVideo && !(player.seed.thumb)
        gradient: Gradient {
            GradientStop { position: 0; color: Qt.hsla(Y.hue(player.label), 0.35, 0.22, 1) }
            GradientStop { position: 1; color: Qt.hsla((Y.hue(player.label) + 0.2) % 1, 0.45, 0.08, 1) }
        }
    }

    Corners {                                  // the inset video's rounded corners
        visible: Y.videoSide
        x: player.place.x; y: player.place.y; width: player.place.width; height: player.place.height
        r: 28 * Y.u
    }
    DescriptionPanel {
        id: description
        visible: player.panel === "description"
        v: player.v
        d: player.meta.details || {}
        chapters: player.chapters
        onOpenChannel: { player.panel = ""; video.setPaused(true); player.openChannel(player.v.channelId); }
        onOpenComments: player.openPanel("comments")
        onSeekTo: t => { video.seekTo(t); player.panel = ""; }
        onClosed: player.panel = ""
    }
    CommentsPanel {
        id: comments
        visible: player.panel === "comments"
        onClosed: player.panel = ""
    }
    PlayerPanel {
        id: sidePanel
        visible: !!player.panel && player.panel !== "description" && player.panel !== "comments"
        options: player.panelOptions
        avatar: player.panel === "channel" ? player.v.avatar || "" : ""
        name: player.panel === "channel" ? player.v.channel || "" : ""
        line: player.panel === "channel" ? [player.v.handle || "", player.v.subscribers || ""].filter(x => !!x).join(" · ") : ""
        title: ({notify: "Notifications", save: "Save video to…", settings: "Settings", quality: "Quality", speed: "Playback speed", captions: "Captions"})[player.panel] || ""
        subtitle: player.panel === "notify" ? "You'll get notified in the mobile app or on YouTube.com based on your account settings"
                : player.panel === "quality" ? "H.264, the Pi's best: Auto picks up to 1080p60" : ""
        onPicked: i => player.panelPick(i)
        onClosed: player.panel = ""
    }

    Item {
        id: overlay
        anchors.fill: parent
        opacity: player.shown && !player.panel ? 1 : 0
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
                Rectangle {                    // live: the red badge where the time would be
                    visible: player.live
                    width: liveBar.implicitWidth + 20 * Y.u; height: 34 * Y.u; radius: 6 * Y.u
                    color: "#cc0000"
                    Text { id: liveBar; anchors.centerIn: parent; text: "LIVE"; color: "white"; font.family: Y.font; font.pixelSize: 22 * Y.u; font.weight: Font.Bold }
                }
                Rectangle {
                    visible: player.live
                    y: 59 * Y.u; width: parent.width; height: 6 * Y.u; radius: 3 * Y.u
                    color: Y.red
                }
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
                    height: (player.mode === "bar" || player.mode === "chapters" ? 12 : 8) * Y.u
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
                                color: player.mode === "bar" || player.mode === "chapters" ? Y.red : Y.text
                            }
                        }
                    }
                    Rectangle {                // the playhead while seeking
                        visible: player.mode === "bar" || player.mode === "chapters"
                        x: bar.frac * bar.width - width / 2
                        anchors.verticalCenter: parent.verticalCenter
                        width: 30 * Y.u; height: width; radius: width / 2
                        color: Y.text
                    }
                }
            }

            // ---------------------------------------------------------------- the chapters, while seeking
            Item {
                id: strip
                visible: (player.mode === "bar" || player.mode === "chapters") && player.chapters.length > 1
                y: 296 * Y.u
                width: parent.width
                height: 330 * Y.u
                readonly property int cur: player.mode === "chapters" ? player.chapterPick : Math.max(0, player.chapter)
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: player.mode === "chapters" ? "OK plays from the chapter" : "Press up to view chapters"
                    color: Y.text; font.family: Y.font; font.pixelSize: 24 * Y.u; font.weight: Font.Medium
                    style: Text.Raised; styleColor: "#80000000"
                }
                ListView {
                    id: stripList
                    y: 57 * Y.u
                    width: parent.width
                    height: 270 * Y.u
                    orientation: ListView.Horizontal
                    interactive: false
                    spacing: 18 * Y.u
                    model: player.chapters
                    currentIndex: strip.cur
                    // the current chapter sits over the playhead
                    highlightRangeMode: ListView.StrictlyEnforceRange
                    preferredHighlightBegin: Math.max(0, Math.min(width - 336 * Y.u, 96 * Y.u + bar.frac * bar.width - 168 * Y.u))
                    preferredHighlightEnd: preferredHighlightBegin + 336 * Y.u
                    highlightMoveDuration: 160
                    delegate: Item {
                        id: chap
                        required property var modelData
                        required property int index
                        readonly property bool cur: index === strip.cur
                        width: 336 * Y.u; height: 270 * Y.u
                        Rectangle {
                            width: parent.width; height: 189 * Y.u; radius: 12 * Y.u
                            color: Qt.hsla(Y.hue(chap.modelData.title), 0.45, 0.28, 1)
                            border.color: chap.cur && player.mode === "chapters" ? Y.text : "transparent"
                            border.width: 6 * Y.u
                            Image {
                                anchors { fill: parent; margins: chap.cur && player.mode === "chapters" ? 6 * Y.u : 0 }
                                source: chap.modelData.thumb || ""
                                fillMode: Image.PreserveAspectCrop
                                sourceSize: Y.sz(width, height)
                                asynchronous: true
                            }
                        }
                        Text {
                            y: 206 * Y.u; width: parent.width
                            horizontalAlignment: chap.cur ? Text.AlignHCenter : Text.AlignLeft
                            text: chap.modelData.title
                            color: chap.cur ? Y.text : Y.dim
                            font.family: Y.font; font.pixelSize: 24 * Y.u; font.weight: chap.cur ? Font.Bold : Font.Medium
                            elide: Text.ElideRight
                        }
                        Text {
                            visible: chap.cur
                            y: 240 * Y.u; width: parent.width
                            horizontalAlignment: Text.AlignHCenter
                            text: Y.clock(player.mode === "chapters" ? chap.modelData.start : video.position)
                            color: Y.text; font.family: Y.font; font.pixelSize: 24 * Y.u
                        }
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
                    CtlButton {                // the bell when subscribed (its level), else Subscribe
                        visible: !Y.signedIn || !!player.v.subscribed
                        icon: ({all: "bell-all", none: "bell-off"})[player.v.notify] || "bell"
                        on: row.on(2)
                    }
                    Rectangle {
                        visible: Y.signedIn && !player.v.subscribed
                        width: subT.implicitWidth + 64 * Y.u; height: 72 * Y.u; radius: height / 2
                        color: row.on(2) ? Y.text : "#33ffffff"
                        Text { id: subT; anchors.centerIn: parent; text: "Subscribe"; color: row.on(2) ? Y.ink : Y.text; font.family: Y.font; font.pixelSize: 28 * Y.u; font.weight: Font.Medium }
                    }
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
                                CtlButton {
                                    required property string modelData
                                    required property int index
                                    icon: modelData === "like" && player.v.like === "like" ? "like-filled"
                                        : modelData === "dislike" && player.v.like === "dislike" ? "dislike-filled" : modelData
                                    on: row.on(6 + index)
                                    plain: true
                                }
                            }
                        }
                    }
                    Rectangle {
                        width: tools.implicitWidth; height: 72 * Y.u; radius: height / 2
                        color: "#33ffffff"
                        Row {
                            id: tools
                            CtlButton { icon: player.captionsOn ? "cc-filled" : "cc"; on: row.on(12); plain: true }
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
                behind: "#08070d"              // about the scrim's colour there
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
    EndScreen {
        id: endScreen
        anchors.fill: parent
        visible: player.ending
        onPlayNow: { player.ending = false; player.playNext(); }
        onCancel: { player.ending = false; player.mode = "controls"; player.button = 3; player.forceActiveFocus(); player.showControls(); }
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
