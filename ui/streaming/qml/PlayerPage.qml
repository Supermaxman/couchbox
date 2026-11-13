// Playing a video, with the controls every Couchbox player has (CouchKit's PlayerControls, which
// work as the YouTube app's). The remote:
//   OK            show the controls, on Play / Pause (it doesn't pause); on them: the focused button
//   Left / Right  back / forward 10 s at once (only the bar shows)   Rewind / Fast-forward: the same
//   Up / Down     show the controls: Subtitles, Play / Pause, Next episode (Twitch: Chat, Follow,
//                 Say something). Up from them: the bar, scrubbing (only OK jumps)
//   Back          hide the controls, then leave the player
// It starts where Dropout says you left off, and tells Dropout the position every 10 s (as the
// website's player does), so Continue Watching matches everywhere. Near the end an "Up next"
// card plays the next episode after a countdown (OK on it plays it now, Back keeps the credits).
// Live (Twitch): no seeking; chat beside the video, over it, or off (the Chat button), and
// sending a message (Say something: the keyboard pop-up, a phone, or the mic).
import QtQuick
import CouchKit

FocusScope {
    id: player
    property var videoId: 0
    property var v: null                       // playback info (vhx.playback)
    property var coming: null                  // the next episode's card while it loads (its title and picture)
    property string session: ""
    property bool loading: true                // asking what to play (the video before has stopped)
    property bool started: false
    property bool upNextDismissed: false
    property real lastReport: 0
    property string message: ""                // why it won't play
    // The one video player (Main.qml): it lives as long as the app, since tearing libmpv down
    // with the page crashed (its callbacks outlived the item).
    readonly property var video: D.video
    readonly property bool watching: !!v && !video.paused && !video.ended   // keeps the app from idling out
    readonly property bool live: !!(v && v.live)
    readonly property bool hasChat: !!(v && (v.chat || v.vodChat))
    readonly property bool replay: !!(v && v.vodChat)          // a video's chat, replayed in time
    readonly property string channel: v ? (v.chat || v.collectionId || "") : ""
    property bool following: false
    property int tick: 0                       // uptime: once a second
    Timer { interval: 1000; repeat: true; running: player.live; onTriggered: player.tick++ }
    Timer {                                    // viewers, title, tags: once a minute
        interval: 60000; repeat: true; running: player.live
        onTriggered: D.call("streamInfo", {login: player.v.chat}, r => {
            if (!r.live || !player.v) return;
            const c = Object.assign({}, player.v);
            c.viewers = r.viewers; c.started = r.started; c.title = r.title; c.description = r.category; c.category = r.category; c.tags = r.tags;
            player.v = c;
        })
    }
    readonly property real chatW: 500 * D.u
    readonly property real inset: hasChat && D.chatMode === "side" ? chatW : 0
    property bool canSend: false
    property string chatStatus: ""
    property bool adBreak: false               // Twitch: an ad break is being left out
    ListModel { id: chatModel }
    Binding { target: D; property: "videoInset"; value: player.inset }
    readonly property bool showUpNext: !!(v && v.next) && video.duration > 0 && !upNextDismissed &&
                                       video.position > video.duration - Math.max(20, v.upNext || 0)
    // The Up next card takes OK and Back only while the video plays with the controls away: its
    // button shows the focus then. Paused, or with the controls up, OK is theirs (it resumes).
    readonly property bool upNextArmed: showUpNext && controls.mode === "hidden" && !video.paused

    signal finished()

    function start(id) {
        if (v && started && !video.ended) report("timeupdate");      // where the one before was left
        coming = v && v.next && v.next.id === id ? v.next : null;
        videoId = id;
        v = null; started = false; upNextDismissed = false; lastReport = 0; message = ""; loading = true;
        controls.reset();                      // the one before stops now, covered until this one's first picture
        session = Math.random().toString(16).slice(2) + Math.random().toString(16).slice(2);
        D.call("playback", {id: id}, r => {
            if (player.videoId !== id) return;                       // (another one was asked for meanwhile)
            v = r;
            chatModel.clear();
            replayQueue = []; replayFrom = -1;
            following = false;
            if (r.chat || r.vodChat)
                D.call("onWatchlist", {id: r.chat || r.collectionId}, w => player.following = w.on, () => {});
            if (r.chat) {
                chatStatus = "Connecting to chat…";
                D.call("chatJoin", {login: r.chat, channelId: r.channelId || ""}, j => {
                    player.canSend = j.canSend;
                    player.chatStatus = "";
                }, err => player.chatStatus = err);
            }
            loading = false;
            video.load(r.url, r.start || 0);
        }, err => {
            if (player.videoId !== id) return;
            console.log("playback " + id + ": " + err);
            loading = false; message = "This video couldn't be loaded.";
        });
    }
    Component.onCompleted: start(videoId)
    // Leaving: the video stops whatever else fails (a paused, loaded video keeps the TV's
    // refresh rate matched to it). The position is read before: stop() clears it.
    Component.onDestruction: {
        const ended = video.ended;
        try {
            report(ended ? "ended" : "timeupdate");
            if (hasChat) D.call("chatPart", {});
            D.videoInset = 0;
        } finally {
            video.stop();
            if (typeof mpris !== "undefined" && mpris) mpris.update(false, false, "", "", 0, 0);
        }
    }

    // what Plasma shows as playing (and the remote's media keys come back over it)
    function mprisUpdate() {
        if (typeof mpris === "undefined" || !mpris) return;
        mpris.update(!!v && video.duration > 0, video.paused, v ? v.title : "", v ? [v.series, D.epLabel(v)].filter(x => x).join(" · ") : "",
                     video.duration, video.position);
    }
    // Play / Pause, Rewind and Fast-forward (MPRIS: Plasma sends the remote's media keys there),
    // the voice assistant (Main's mediaCommand): "toggle", "play", "pause", "seek" (seconds from
    // here), "seekTo" (seconds from the start), "stop". Shown on screen as the keys are.
    function media(name, arg) { controls.media(name, arg); }
    Connections {
        target: typeof mpris !== "undefined" ? mpris : null
        ignoreUnknownSignals: true
        function onCommand(name, arg) {
            if (name === "playpause") player.media("toggle");
            else if (name === "play" || name === "pause" || name === "stop") player.media(name);
            else if (name === "seek" || name === "previous") player.media("seek", arg);
            else if (name === "seekto") player.media("seekTo", arg);
            else if (name === "next" && player.v && player.v.next) player.start(player.v.next.id);
        }
    }
    Timer { interval: 5000; repeat: true; running: !!player.v; onTriggered: player.mprisUpdate() }

    function report(name) {
        if (!v || !video.duration) return;
        backend.report(name, String(v.id), String(v.collectionId || ""), video.position, video.duration, session,
                       video.subtitle > 0 ? "English" : "none");
    }
    Connections {
        target: video
        function onSubtitlesChanged() { player.defaultSubtitles(); }
        function onPositionChanged() {
            if (!player.v) return;
            if (!player.started && video.position > 0) { player.started = true; player.report("firstplay"); }
            if (!video.paused && Math.abs(video.position - player.lastReport) >= 10) { player.lastReport = video.position; player.report("timeupdate"); }
        }
        function onPausedChanged() { if (player.started) player.report(video.paused ? "pause" : "play"); player.mprisUpdate(); }
        function onDurationChanged() { player.mprisUpdate(); }
        function onEndedChanged() {            // the end: the next episode, else the controls (Play starts it again)
            if (!video.ended || !player.v) return;
            player.report("ended");
            if (player.v.next && !player.upNextDismissed) player.start(player.v.next.id);
        }
    }

    // ------------------------------------------------------------------ chat (Twitch)
    Connections {
        target: backend
        ignoreUnknownSignals: true
        function onEvent(name, data) {
            if (name === "ads") { player.adBreak = JSON.parse(data).on; return; }
            if (!player.hasChat) return;
            if (name === "chat") {
                chatModel.append({j: data});
                if (chatModel.count > 60) chatModel.remove(0, chatModel.count - 60);
                chatList.positionViewAtEnd();
            } else if (name === "chatState") {
                const st = JSON.parse(data);
                player.chatStatus = st.state === "connected" ? "" : "Reconnecting to chat…";
                if (st.state === "connected") player.canSend = st.canSend;
            }
        }
    }
    // a video's chat: fetched a page at a time from where the video is, shown as it reaches each
    property var replayQueue: []
    property real replayFrom: -1               // where the fetched comments start (-1: none)
    property real replayTo: -1                 // ... and end
    property bool replayLoading: false
    property real replayLast: 0
    function replayFetch(at) {
        if (replayLoading) return;
        replayLoading = true;
        D.call("vodComments", {id: v.vodChat, offset: Math.max(0, Math.floor(at)), login: v.collectionId || ""}, r => {
            replayLoading = false;
            const items = (r.items || []).filter(m => m.t >= Math.floor(at));
            if (replayFrom < 0) replayFrom = at;
            replayQueue = replayQueue.concat(items.filter(m => m.t > replayTo || replayTo < 0));
            replayTo = items.length ? items[items.length - 1].t : at + 30;
        }, () => replayLoading = false);
    }
    Timer {
        interval: 500
        repeat: true
        running: player.replay && !video.paused
        onTriggered: {
            const pos = video.position;
            if (Math.abs(pos - player.replayLast) > 8) {        // a seek: start over from there
                chatModel.clear();
                player.replayQueue = []; player.replayFrom = -1; player.replayTo = -1;
            }
            player.replayLast = pos;
            if (player.replayTo < pos + 10) player.replayFetch(player.replayTo < 0 ? pos : player.replayTo + 1);
            let q = player.replayQueue, shown = 0;
            while (q.length && q[0].t <= pos) {
                chatModel.append({j: JSON.stringify(q.shift())});
                shown++;
            }
            if (shown) {
                if (chatModel.count > 60) chatModel.remove(0, chatModel.count - 60);
                player.replayQueue = q;
            }
        }
    }
    function toggleFollow() {
        const on = following;
        D.call("watchlist", {op: on ? "remove" : "add", kind: "series", id: channel}, () => {
            following = !on;                   // (the button says it: its heart, "Following")
        }, err => D.toast(err));
    }
    function cycleChat() { D.chatMode = ({overlay: "side", side: "off", off: "overlay"})[D.chatMode] || "overlay"; }
    function say() {
        if (!canSend) { D.toast("Sign in to chat."); D.signInNeeded(); return; }
        D.askText("Chat in " + v.series, "", false, t => {
            if (t.trim()) D.call("chatSend", {text: t}, () => {}, err => D.toast(err));
        });
    }
    // subtitles on unless they were turned off (D.subtitles, kept across runs)
    property var subsFor: 0
    function defaultSubtitles() {
        const subs = video.subtitles;
        if (!subs.length || subsFor === videoId) return;
        subsFor = videoId;
        const en = subs.find(t => /^en/.test(t.lang)) || subs[0];
        video.setSubtitle(D.subtitles ? en.id : 0);
    }
    function cycleSubtitles() {
        const subs = video.subtitles;
        if (!subs.length) return D.toast("No subtitles for this one.");
        const i = subs.findIndex(t => t.id === video.subtitle);
        const nextId = i < 0 ? subs[0].id : i + 1 < subs.length ? subs[i + 1].id : 0;
        video.setSubtitle(nextId);
        D.subtitles = nextId > 0;                    // remembered for the next videos
    }

    // ------------------------------------------------------------------ the controls
    PlayerControls {
        id: controls
        anchors.fill: parent
        anchors.rightMargin: player.inset      // (chat beside the video: the video ends there)
        rightInset: player.hasChat && D.chatMode === "overlay" ? player.chatW : 0   // chat over it: kept clear
        focus: true
        video: player.video
        live: player.live
        loading: player.loading
        message: player.message || video.error
        poster: player.coming ? D.img(player.coming.landscape, 960, 540) : ""
        u: D.u
        edge: D.edge
        font: D.font; text: D.text; dim: D.text2; ink: D.text
        accent: D.accent; focusFill: D.accent; focusInk: D.accentInk
        buttons: [
            {key: "cc", icon: "cc", marked: video.subtitle > 0,
             label: video.subtitle > 0 ? "Subtitles: " + ((video.subtitles.find(t => t.id === video.subtitle) || {}).title || "On") : "Subtitles off"},
            {key: "play"},
            {key: "next", icon: "next", label: "Next episode", visible: !!(player.v && player.v.next)},
            {key: "chat", icon: "chat", visible: player.hasChat, marked: D.chatMode !== "off",
             label: ({side: "Chat beside the video", overlay: "Chat over the video", off: "Chat hidden"})[D.chatMode] || ""},
            {key: "follow", icon: player.following ? "heart-filled" : "heart", label: player.following ? "Following" : "Follow",
             visible: !!player.channel && D.site.backend === "twitch"},
            {key: "say", icon: "write", label: "Say something", visible: player.hasChat && !player.replay}
        ]
        onAction: key => {
            if (key === "cc") player.cycleSubtitles();
            else if (key === "next") player.start(player.v.next.id);
            else if (key === "chat") player.cycleChat();
            else if (key === "follow") player.toggleFollow();
            else if (key === "say") player.say();
        }
        onLeave: player.finished()
        before: e => {                         // the Up next card, while it has the say
            if (!player.upNextArmed) return false;
            const k = e.key;
            if (k === Qt.Key_Return || k === Qt.Key_Enter || k === Qt.Key_Select) { if (!e.isAutoRepeat) player.start(player.v.next.id); return true; }
            if (k === Qt.Key_Escape || k === Qt.Key_Back) { if (!e.isAutoRepeat) player.upNextDismissed = true; return true; }
            return false;
        }
        header: Column {
            readonly property var h: player.v || player.coming || ({})
            spacing: 8 * D.u
            Text {
                text: [h.series, D.epLabel(h)].filter(x => x).join("  ·  ")
                visible: !!text
                color: D.accent
                font.family: D.font
                font.pixelSize: 24 * D.u
                font.weight: Font.Bold
                font.capitalization: Font.AllUppercase
                font.letterSpacing: 1.5 * D.u
            }
            Text {
                width: parent.width
                text: h.title || ""
                elide: Text.ElideRight
                color: D.text
                font.family: D.font
                font.pixelSize: 44 * D.u
                font.weight: Font.Black
            }
            Row {                                // LIVE  5:28:17  550 watching  category
                visible: player.live
                spacing: 18 * D.u
                Rectangle {
                    width: liveT.implicitWidth + 18 * D.u; height: liveT.implicitHeight + 8 * D.u; radius: 4 * D.u; color: "#eb0400"
                    anchors.verticalCenter: parent.verticalCenter
                    Text { id: liveT; anchors.centerIn: parent; text: "LIVE"; color: "white"; font.family: D.font; font.pixelSize: 20 * D.u; font.weight: Font.Black }
                }
                Text {
                    text: h.started ? D.uptime(h.started, player.tick) : ""
                    visible: !!text
                    color: D.text; font.family: D.font; font.pixelSize: 23 * D.u; font.weight: Font.DemiBold
                    anchors.verticalCenter: parent.verticalCenter
                }
                Text {
                    text: h.viewerCount !== undefined ? Number(h.viewerCount || 0).toLocaleString(Qt.locale("en_US"), "f", 0) + " watching" : h.viewers || ""
                    visible: !!text
                    color: D.text; font.family: D.font; font.pixelSize: 23 * D.u; font.weight: Font.DemiBold
                    anchors.verticalCenter: parent.verticalCenter
                }
                Text {
                    text: h.category || h.description || ""
                    visible: !!text
                    color: D.accent; font.family: D.font; font.pixelSize: 23 * D.u; font.weight: Font.Bold
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
            Flow {                               // tags and content labels
                visible: player.live && ((h.tags || []).length + (h.labels || []).length) > 0
                width: parent.width
                spacing: 10 * D.u
                Repeater {
                    model: (h.labels || []).map(l => ({t: l, label: true})).concat((h.tags || []).slice(0, 8).map(t => ({t: t})))
                    Rectangle {
                        required property var modelData
                        width: tagText.implicitWidth + 24 * D.u
                        height: tagText.implicitHeight + 10 * D.u
                        radius: height / 2
                        color: modelData.label ? Qt.rgba(0.92, 0.02, 0, 0.35) : Qt.rgba(1, 1, 1, 0.14)
                        Text { id: tagText; anchors.centerIn: parent; text: modelData.t; color: D.text; font.family: D.font; font.pixelSize: 18 * D.u; font.weight: Font.Medium }
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------------ chat panel
    Rectangle {
        id: chatPanel
        visible: player.hasChat && D.chatMode !== "off"
        anchors { right: parent.right; top: parent.top; bottom: parent.bottom }
        width: player.chatW
        color: D.chatMode === "side" ? "#18181b" : Qt.rgba(0, 0, 0, 0.42)
        Rectangle { visible: D.chatMode === "side"; width: 1; height: parent.height; color: "#2f2f35" }
        Text {
            id: chatHead
            visible: !!player.chatStatus
            x: 24 * D.u; y: 24 * D.u
            text: player.chatStatus
            color: D.chatMode === "side" ? D.text2 : Qt.rgba(1, 1, 1, 0.8)
            font.family: D.font; font.pixelSize: 19 * D.u; font.weight: Font.Bold; font.letterSpacing: 1.5 * D.u
        }
        ListView {
            id: chatList
            anchors { left: parent.left; right: parent.right; top: chatHead.visible ? chatHead.bottom : parent.top; bottom: chatFoot.visible ? chatFoot.top : parent.bottom; margins: 18 * D.u }
            clip: true
            interactive: false
            spacing: 10 * D.u
            model: chatModel
            verticalLayoutDirection: ListView.TopToBottom
            onCountChanged: positionViewAtEnd()
            delegate: Item {
                required property string j
                readonly property var m: JSON.parse(j)
                readonly property var tokens: {
                    const out = [];
                    for (const p of m.parts || []) {
                        if (p.e) out.push({e: p.e});
                        else for (const w of p.t.split(/(\s+)/)) if (w.trim()) out.push({t: w});
                    }
                    return out;
                }
                width: chatList.width
                height: flow.height
                Flow {
                    id: flow
                    width: parent.width
                    spacing: 6 * D.u
                    Text {
                        visible: !parent.parent.m.notice
                        text: parent.parent.m.name + ":"
                        color: parent.parent.m.color || ["#ff7f50", "#9acd32", "#1e90ff", "#ff69b4", "#daa520", "#00ff7f", "#bf94ff", "#ff4500"][Math.abs(parent.parent.m.name.split("").reduce((a, c) => a * 31 + c.charCodeAt(0) | 0, 7)) % 8]
                        font.family: D.font; font.pixelSize: 22 * D.u; font.weight: Font.Bold
                        style: D.chatMode === "overlay" ? Text.Outline : Text.Normal; styleColor: "black"
                    }
                    Repeater {
                        model: parent.parent.tokens
                        Loader {
                            required property var modelData
                            sourceComponent: modelData.e ? emoteC : wordC
                            Component {
                                id: wordC
                                Text {
                                    text: modelData.t
                                    color: D.text
                                    font.family: D.font; font.pixelSize: 22 * D.u
                                    style: D.chatMode === "overlay" ? Text.Outline : Text.Normal; styleColor: "black"
                                }
                            }
                            Component {
                                id: emoteC
                                AnimatedImage {
                                    source: modelData.e
                                    height: 36 * D.u
                                    width: implicitHeight ? implicitWidth * height / implicitHeight : height
                                    fillMode: Image.PreserveAspectFit
                                    asynchronous: true
                                    cache: true
                                    // some animated WebP doesn't load here: 7TV has a GIF of each, BTTV its original
                                    onStatusChanged: if (status === Image.Error && String(source).endsWith(".webp"))
                                        source = String(source).indexOf("7tv.app") >= 0 ? String(source).replace(/\.webp$/, ".gif")
                                                                                     : String(source).replace(/\/2x\.webp$/, "/2x")
                                }
                            }
                        }
                    }
                }
            }
        }
        Text {
            id: chatFoot
            anchors { left: parent.left; bottom: parent.bottom; margins: 22 * D.u }
            width: parent.width - 44 * D.u
            wrapMode: Text.WordWrap
            visible: !player.canSend && !player.replay
            text: "Sign in to chat"
            color: D.dim; font.family: D.font; font.pixelSize: 17 * D.u
        }
    }

    // ------------------------------------------------------------------ Twitch's ad break
    Rectangle {
        anchors.centerIn: controls
        visible: player.adBreak && !controls.message
        width: adText.implicitWidth + 80 * D.u
        height: 90 * D.u
        radius: 12 * D.u
        color: Qt.rgba(0, 0, 0, 0.75)
        Text {
            id: adText
            anchors.centerIn: parent
            text: "Ad break · the stream will be right back"
            color: D.text
            font.family: D.font
            font.pixelSize: 28 * D.u
            font.weight: Font.DemiBold
        }
    }

    // ------------------------------------------------------------------ up next
    // Above the controls' bar (it never moves as they come and go). Its button has the focus
    // while the video plays with the controls away (upNextArmed): OK plays the next episode now,
    // Back keeps the credits; left alone, the next one plays at the end.
    Rectangle {
        anchors { right: controls.right; bottom: parent.bottom; rightMargin: D.edge + controls.rightInset; bottomMargin: 340 * D.u }
        visible: player.showUpNext
        width: 620 * D.u
        height: upCol.height + 48 * D.u
        radius: 10 * D.u
        color: Qt.rgba(0.08, 0.08, 0.08, 0.95)
        border.color: D.line
        Column {
            id: upCol
            x: 24 * D.u; y: 24 * D.u
            width: parent.width - 48 * D.u
            spacing: 16 * D.u
            Text {
                text: "UP NEXT  ·  " + Math.max(0, Math.ceil(video.duration - video.position)) + "s"
                color: D.accent
                font.family: D.font; font.pixelSize: 21 * D.u; font.weight: Font.Bold; font.letterSpacing: 1.5 * D.u
            }
            Row {
                spacing: 18 * D.u
                Image {
                    width: 220 * D.u; height: 124 * D.u
                    source: player.v && player.v.next ? D.img(player.v.next.landscape, 440, 248) : ""
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                }
                Column {
                    width: upCol.width - 238 * D.u
                    spacing: 6 * D.u
                    Text { text: player.v && player.v.next ? D.epLabel(player.v.next) : ""; color: D.dim; font.family: D.font; font.pixelSize: 19 * D.u }
                    Text {
                        width: parent.width
                        text: player.v && player.v.next ? player.v.next.title : ""
                        wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
                        color: D.text; font.family: D.font; font.pixelSize: 25 * D.u; font.weight: Font.Bold
                    }
                }
            }
            DButton { icon: "next"; text: "Next Episode"; lit: player.upNextArmed }
        }
    }
}
