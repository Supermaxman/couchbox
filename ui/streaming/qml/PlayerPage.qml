// Playing a video. The remote:
//   OK            pause / play (and show the controls)
//   Left / Right  back / forward 10 s (hold to keep going)    Rewind / Fast-forward: 30 s
//   Up / Down     show the controls: Back 10, Play/Pause, Forward 10, Subtitles, Next episode
//   Back          hide the controls, else leave the player
// It starts where Dropout says you left off, and tells Dropout the position every 10 s (as the
// website's player does), so Continue Watching matches everywhere. Near the end an "Up next"
// card plays the next episode after a countdown.
// Live (Twitch): no seeking; chat beside the video, over it, or off (the Chat button), and
// sending a message (Say Something: the keyboard pop-up, a phone, or the mic).
import QtQuick

FocusScope {
    id: player
    property var videoId: 0
    property var v: null                       // playback info (vhx.playback)
    property string session: ""
    property bool controls: true
    property bool started: false
    property bool upNextDismissed: false
    property real lastReport: 0
    property string message: ""
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

    signal finished()

    function start(id) {
        videoId = id;
        v = null; started = false; upNextDismissed = false; message = "Loading…";
        session = Math.random().toString(16).slice(2) + Math.random().toString(16).slice(2);
        D.call("playback", {id: id}, r => {
            v = r;
            message = "";
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
            video.load(r.url, r.start || 0);
            showControls();
        }, err => { console.log("playback " + id + ": " + err); message = "This video couldn't be loaded. Back to go back."; });
    }
    Component.onCompleted: start(videoId)
    Component.onDestruction: {
        if (hasChat) D.call("chatPart", {});
        D.videoInset = 0;
        report(video.ended ? "ended" : "timeupdate");
        video.stop();
        if (typeof mpris !== "undefined" && mpris) mpris.update(false, false, "", "", 0, 0);
    }

    // the remote's media keys (Plasma sends them over MPRIS) and what Plasma shows as playing
    function mprisUpdate() {
        if (typeof mpris === "undefined" || !mpris) return;
        mpris.update(!!v && video.duration > 0, video.paused, v ? v.title : "", v ? [v.series, D.epLabel(v)].filter(x => x).join(" · ") : "",
                     video.duration, video.position);
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
            else if (name === "next" && player.v && player.v.next) player.start(player.v.next.id);
            else if (name === "stop") player.finished();
            player.showControls();
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
            if (!player.started && video.position > 0) { player.started = true; player.report("firstplay"); }
            if (!video.paused && video.position - player.lastReport >= 10) { player.lastReport = video.position; player.report("timeupdate"); }
        }
        function onPausedChanged() { if (player.started) player.report(video.paused ? "pause" : "play"); if (video.paused) player.showControls(); player.mprisUpdate(); }
        function onDurationChanged() { player.mprisUpdate(); }
        function onEndedChanged() {
            if (!video.ended) return;
            player.report("ended");
            if (player.v && player.v.next && !player.upNextDismissed) player.start(player.v.next.id);
            else player.showControls();
        }
    }

    // subtitles move up while the controls are showing, so they don't sit under the buttons
    readonly property bool overlayShown: controls || video.paused || !!message
    onOverlayShownChanged: video.setSubtitlePosition(overlayShown ? 70 : 100)

    function showControls() {
        controls = true;
        hide.restart();
    }
    Timer { id: hide; interval: 5000; onTriggered: if (!video.paused && !bar.activeFocus) player.controls = false }

    function skip(s) { if (!live) video.seek(s); showControls(); }

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
            following = !on;
            D.toast((on ? "Unfollowed " : "Following ") + (v.series || channel) + ".");
        }, err => D.toast(err));
    }
    function cycleChat() {
        D.chatMode = ({overlay: "side", side: "off", off: "overlay"})[D.chatMode] || "overlay";
        D.toast(({side: "Chat beside the video", overlay: "Chat over the video", off: "Chat hidden"})[D.chatMode]);
    }
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
        D.toast(nextId ? "Subtitles: " + (subs.find(t => t.id === nextId).title || "On") : "Subtitles off");
    }


    // ------------------------------------------------------------------ keys
    Keys.onPressed: event => {
        const k = event.key;
        if (k === Qt.Key_Escape || k === Qt.Key_Back) {
            if (player.showUpNext) player.upNextDismissed = true;
            else if (bar.activeFocus) { player.forceActiveFocus(); controls = false; }
            else player.finished();
        } else if (k === Qt.Key_MediaTogglePlayPause || k === Qt.Key_MediaPlay || k === Qt.Key_MediaPause || k === Qt.Key_Space) {
            video.togglePause(); showControls();
        } else if (k === Qt.Key_AudioRewind || k === Qt.Key_MediaPrevious) {
            skip(-30);
        } else if (k === Qt.Key_AudioForward || k === Qt.Key_MediaNext) {
            skip(30);
        } else if (bar.activeFocus) {
            return;
        } else if (k === Qt.Key_Return || k === Qt.Key_Enter) {
            if (player.showUpNext) upNextPlay.clicked(); else { video.togglePause(); showControls(); }
        } else if (k === Qt.Key_Left) {
            skip(-10);
        } else if (k === Qt.Key_Right) {
            skip(10);
        } else if (k === Qt.Key_Up || k === Qt.Key_Down) {
            showControls(); playPause.forceActiveFocus();
        } else {
            return;
        }
        event.accepted = true;
    }

    // ------------------------------------------------------------------ overlay
    Item {
        anchors.fill: parent
        anchors.rightMargin: player.inset
        opacity: player.controls || video.paused || player.message ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 250 } }

        Rectangle {
            anchors { left: parent.left; right: parent.right; top: parent.top }
            height: 260 * D.u
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(0, 0, 0, 0.85) }
                GradientStop { position: 1.0; color: "transparent" }
            }
        }
        Column {
            x: D.edge
            y: 60 * D.u
            spacing: 8 * D.u
            Text {
                text: player.v ? [player.v.series, D.epLabel(player.v)].filter(x => x).join("  ·  ") : ""
                visible: !!text
                color: D.accent
                font.family: D.font
                font.pixelSize: 24 * D.u
                font.weight: Font.Bold
                font.capitalization: Font.AllUppercase
                font.letterSpacing: 1.5 * D.u
            }
            Text {
                width: player.width - (player.hasChat && D.chatMode !== "off" ? player.chatW : 0) - 2 * D.edge
                text: player.v ? player.v.title : ""
                elide: Text.ElideRight
                color: D.text
                font.family: D.font
                font.pixelSize: 44 * D.u
                font.weight: Font.Black
            }
            Row {                                // LIVE  ● 5:28:17  👤 550 viewers  ·  category
                visible: player.live
                spacing: 18 * D.u
                Rectangle {
                    width: liveT.implicitWidth + 18 * D.u; height: liveT.implicitHeight + 8 * D.u; radius: 4 * D.u; color: "#eb0400"
                    anchors.verticalCenter: parent.verticalCenter
                    Text { id: liveT; anchors.centerIn: parent; text: "LIVE"; color: "white"; font.family: D.font; font.pixelSize: 20 * D.u; font.weight: Font.Black }
                }
                Text {
                    text: player.v && player.v.started ? "◷ " + D.uptime(player.v.started, player.tick) : ""
                    color: D.text; font.family: D.font; font.pixelSize: 23 * D.u; font.weight: Font.DemiBold
                    anchors.verticalCenter: parent.verticalCenter
                }
                Text {
                    text: player.v && player.v.viewerCount !== undefined ? "👤 " + Number(player.v.viewerCount || 0).toLocaleString(Qt.locale("en_US"), "f", 0) : (player.v ? player.v.viewers || "" : "")
                    color: D.text; font.family: D.font; font.pixelSize: 23 * D.u; font.weight: Font.DemiBold
                    anchors.verticalCenter: parent.verticalCenter
                }
                Text {
                    text: player.v ? (player.v.category || player.v.description || "") : ""
                    visible: !!text
                    color: D.accent; font.family: D.font; font.pixelSize: 23 * D.u; font.weight: Font.Bold
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
            Flow {                               // tags and content labels
                visible: player.live && !!player.v && ((player.v.tags || []).length + (player.v.labels || []).length) > 0
                width: player.width - (player.hasChat && D.chatMode !== "off" ? player.chatW : 0) - 2 * D.edge
                spacing: 10 * D.u
                Repeater {
                    model: player.v ? (player.v.labels || []).map(l => ({t: l, label: true})).concat((player.v.tags || []).slice(0, 8).map(t => ({t: t}))) : []
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

        Rectangle {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            height: 420 * D.u
            gradient: Gradient {
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.45; color: Qt.rgba(0, 0, 0, 0.65) }
                GradientStop { position: 1.0; color: Qt.rgba(0, 0, 0, 0.95) }
            }
        }
        Column {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom; leftMargin: D.edge; rightMargin: D.edge; bottomMargin: 60 * D.u }
            spacing: 26 * D.u

            Item {                               // progress
                visible: !player.live
                width: parent.width
                height: 40 * D.u
                Rectangle {
                    id: track
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - times.width - 30 * D.u
                    height: 8 * D.u
                    radius: 4 * D.u
                    color: Qt.rgba(1, 1, 1, 0.25)
                    Rectangle {
                        width: video.duration ? parent.width * video.position / video.duration : 0
                        height: parent.height
                        radius: parent.radius
                        color: D.accent
                    }
                    Rectangle {
                        x: (video.duration ? parent.width * video.position / video.duration : 0) - width / 2
                        anchors.verticalCenter: parent.verticalCenter
                        width: 22 * D.u; height: width; radius: width / 2
                        color: D.accent
                    }
                }
                Text {
                    id: times
                    anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                    text: D.clock(video.position) + "  /  " + D.clock(video.duration)
                    color: D.text
                    font.family: D.font
                    font.pixelSize: 24 * D.u
                    font.weight: Font.DemiBold
                }
            }

            FocusScope {                         // the buttons (Up/Down from the video)
                id: bar
                width: barRow.width
                height: barRow.height
                anchors.horizontalCenter: parent.horizontalCenter
                Row {
                    id: barRow
                    spacing: 18 * D.u
                    DButton { id: back10; visible: !player.live; icon: "↺"; text: "10"; onClicked: player.skip(-10) }
                    DButton {
                        id: playPause
                        icon: video.paused ? "▶" : "❚❚"
                        text: video.paused ? "Play" : "Pause"
                        onClicked: { video.togglePause(); player.showControls(); }
                    }
                    DButton { id: fwd10; visible: !player.live; icon: "↻"; text: "10"; onClicked: player.skip(10) }
                    DButton {
                        id: chatBtn
                        visible: player.hasChat
                        icon: "💬"
                        text: ({side: "Chat: Side", overlay: "Chat: Over", off: "Chat: Off"})[D.chatMode]
                        onClicked: { player.cycleChat(); player.showControls(); }
                    }
                    DButton {
                        id: followBtn
                        visible: !!player.channel && D.site.backend === "twitch"
                        icon: player.following ? "♥" : "♡"
                        text: player.following ? "Following" : "Follow"
                        onClicked: { player.toggleFollow(); player.showControls(); }
                    }
                    DButton {
                        id: sayBtn
                        visible: player.hasChat && !player.replay
                        icon: "✎"
                        text: "Say Something"
                        onClicked: player.say()
                    }
                    DButton {
                        id: subs
                        icon: "CC"
                        text: video.subtitle > 0 ? "On" : "Off"
                        onClicked: { player.cycleSubtitles(); player.showControls(); }
                    }
                    DButton {
                        id: nextBtn
                        visible: !!(player.v && player.v.next)
                        icon: "⏭"
                        text: "Next Episode"
                        onClicked: player.start(player.v.next.id)
                    }
                }
                function shown() { return barRow.children.filter(b => b.visible && b.clicked !== undefined); }
                function step(d) {
                    const b = shown(), i = b.findIndex(x => x.activeFocus);
                    if (i + d >= 0 && i + d < b.length) b[i + d].forceActiveFocus();
                }
                Keys.onLeftPressed: step(-1)
                Keys.onRightPressed: step(1)
                Keys.onUpPressed: { player.forceActiveFocus(); player.showControls(); }
                Keys.onDownPressed: { player.forceActiveFocus(); player.showControls(); }
                onActiveFocusChanged: { if (activeFocus) hide.stop(); else hide.restart(); }
            }
        }
    }

    // ------------------------------------------------------------------ chat panel
    Rectangle {
        id: chatPanel
        visible: player.hasChat && D.chatMode !== "off"
        anchors { right: parent.right; top: parent.top; bottom: parent.bottom }
        // over the video, chat stops above the buttons while they're showing
        anchors.bottomMargin: D.chatMode === "overlay" && player.overlayShown ? 190 * D.u : 0
        Behavior on anchors.bottomMargin { NumberAnimation { duration: 200 } }
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

    // ------------------------------------------------------------------ buffering / messages
    Rectangle {
        anchors.centerIn: parent
        visible: video.buffering || !!player.message || !!video.error || player.adBreak
        width: busyText.implicitWidth + 80 * D.u
        height: 90 * D.u
        radius: 12 * D.u
        color: Qt.rgba(0, 0, 0, 0.75)
        Text {
            id: busyText
            anchors.centerIn: parent
            text: video.error || player.message || (player.adBreak ? "Ad break · the stream will be right back" : "Buffering…")
            color: D.text
            font.family: D.font
            font.pixelSize: 28 * D.u
            font.weight: Font.DemiBold
        }
    }

    // ------------------------------------------------------------------ up next
    Rectangle {
        anchors { right: parent.right; bottom: parent.bottom; rightMargin: D.edge; bottomMargin: 200 * D.u }
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
            Text { text: "OK to play now  ·  Back to keep watching the credits"; color: D.dim; font.family: D.font; font.pixelSize: 18 * D.u }
        }
        DButton { id: upNextPlay; visible: false; onClicked: player.start(player.v.next.id) }
    }
}
