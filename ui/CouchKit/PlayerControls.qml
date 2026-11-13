// CouchKit PlayerControls: the controls over a video, the same in every app that plays one (they
// work as the YouTube app's player does). Laid over the video, it takes the remote's keys:
//   OK            with the controls hidden: show them, on Play / Pause (it doesn't pause); on them:
//                 the focused button
//   Left / Right  hidden: back / forward 10 s at once (only the bar shows); on the controls: along
//                 the buttons
//   Up / Down     hidden: the controls. Up from the controls: the bar, scrubbing (Left / Right move
//                 where it would go, faster while held; the video plays on; only OK jumps; Down,
//                 Back or waiting leave it where it was). Down from the controls: the app's own
//                 row under them, if it gave one (below)
//   Back          hides the controls (paused too: a small pause mark stays), then leaves the player
// Everything else that controls the player (MPRIS: the remote's Play / Pause, Rewind and
// Fast-forward; the voice assistant) comes in through media(name, arg) and shows the same as
// the key would. They hide 5 s after the last key, not while paused or loading.
//
//   PlayerControls {
//       anchors.fill: parent; focus: true
//       video: video; title: "…"; subtitle: "…"; u: App.u
//       buttons: [{key: "cc", icon: "cc", label: "Subtitles off", marked: false}, {key: "play"}, {key: "next", icon: "next", label: "Next episode"}]
//       onAction: key => …                 // a button of the app's was pressed (Play / Pause is handled here)
//       onLeave: page.finished()
//   }
//   controls.reset()                       // a new file is coming: the one before stops at once, a cover
//                                          // (the poster, or black) stays until the new one's first picture
//   loading: true                          // … while the app has nothing to give the video yet
//
// video is the app's MpvVideo (CouchPlayer): position, duration, paused, buffering, ended,
// hasFrame, seek(d), seekTo(p), togglePause(), setPaused(p), stop().
import QtQuick

FocusScope {
    id: pc
    objectName: "playerControls"

    property var video: null
    property string title: ""
    property string subtitle: ""
    property bool live: false                 // no bar, no seeking
    property bool loading: false              // the app is still fetching what to play
    property string message: ""               // why it won't play (a card; only Back works)
    property url poster: ""                   // shown until the file's first picture (else black)
    // the buttons, left to right: {key, icon (a PlayerIcon name) or text, label (said under it with
    // the focus), visible, marked}. {key: "play"} places Play / Pause (first when it's left out).
    property var buttons: []
    property Component header: null           // the app's own title block, instead of title and subtitle
    property Item below: null                 // the app's own row under the controls (Down reaches it)
    property real belowLift: 480 * u          // how far the controls move up for it
    // an app's own card over the video (Up next) takes keys first: function (event) -> true when it did
    property var before: null
    property real u: height / 1080            // the app's size unit
    property real edge: 96 * u                // left and right margins
    property real rightInset: 0               // an app's panel over the video's right side (chat): kept clear

    // the look: each app passes its own
    property string font: "Inter"
    property color text: "#ffffff"
    property color dim: "#b4b4bc"
    property color ink: "#ffffff"             // the buttons' icons
    property color accent: "#ffffff"          // the played part of the bar, the knob
    property color focusFill: "#ffffff"       // the focused button
    property color focusInk: "#0f0f0f"
    property color focusRing: "transparent"   // ... and a ring around it, for apps whose focus is one
    property color scrim: "#000000"

    signal action(string key)
    signal leave()

    // ------------------------------------------------------------------ state
    property string mode: "controls"          // hidden | bar | controls | below
    property string focused: "play"           // the focused button's key
    property real scrub: -1                   // scrubbing: where OK would go (-1: nothing pending)
    property bool quickSeek: false            // the bar came up for a seek done at once: Left / Right seek
    property int repeats: 0                   // a held Left / Right while scrubbing
    property bool pictured: false             // this file's first picture has shown
    property real pos: 0
    property real cached: 0                   // how far the video has read ahead (the bar's lighter part)

    readonly property bool active: visible && !!video
    readonly property real duration: video ? video.duration || 0 : 0
    readonly property bool paused: !!video && !!video.paused
    readonly property bool ended: !!video && !!video.ended
    readonly property bool ready: !loading && !message
    readonly property bool seeking: mode === "bar"
    readonly property real shownPos: scrub >= 0 ? scrub : pos
    readonly property bool shown: mode !== "hidden" || !ready
    readonly property bool busy: !message && (loading || !pictured || (!!video && !!video.buffering && !paused))
    readonly property var shownButtons: {
        const list = (buttons || []).filter(b => b && b.visible !== false);
        if (!list.some(b => b.key === "play")) list.unshift({key: "play"});
        return list;
    }
    readonly property int playIndex: Math.max(0, shownButtons.findIndex(b => b.key === "play"))
    // (a focused button that went away, Next episode on the last one: Play / Pause has the focus)
    readonly property int focusIndex: { const i = shownButtons.findIndex(b => b.key === focused); return i >= 0 ? i : playIndex; }
    function focusDetail() { return {mode: mode, button: (shownButtons[focusIndex] || {}).key || "", scrub: Math.round(scrub), quick: quickSeek,
                                     position: Math.round(pos), paused: paused, pictured: pictured, shown: shown, busy: busy}; }

    function clock(s) {                       // 3956 -> "1:05:56", 76 -> "1:16"
        s = Math.max(0, Math.floor(s || 0));
        const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), sec = s % 60;
        const two = n => (n < 10 ? "0" : "") + n;
        return h ? h + ":" + two(m) + ":" + two(sec) : m + ":" + two(sec);
    }

    // A new file is coming (the first, the next episode, another recording): the one before stops
    // now (not its sound on under the next one's cover), the cover is up until the new one's
    // first picture, and the controls start over on Play / Pause (the focus too: set `focused`
    // after it to keep it on a button, stepping on through a list).
    function reset() {
        if (video) video.stop();
        pictured = false;
        pos = 0; cached = 0;
        focused = "play";
        keys.focus = true;                     // (the focus left on a button that's gone, or on the app's row)
        mode = "controls";
        hide.restart();
    }
    readonly property bool framed: !!video && !!video.hasFrame && !loading
    onFramedChanged: if (framed && active) pictured = true
    onPicturedChanged: if (pictured) hide.restart()
    onLoadingChanged: if (!loading) show()

    // ------------------------------------------------------------------ what the keys and media() do
    function show() {                          // the controls, as any key shows them
        if (mode === "hidden") { focused = "play"; mode = "controls"; }
        hide.restart();
    }
    function toggle() {
        if (video.ended) { video.seekTo(0); video.setPaused(false); }   // at the end: again from the start
        else video.togglePause();
    }
    function barUp() {                         // after a seek done at once: only the bar
        if (mode === "hidden" || mode === "bar") { quickSeek = true; mode = "bar"; }
        hide.restart();
    }
    function quick(d) {
        if (live || !(duration > 0)) { show(); return; }
        const again = video.ended && d < 0;    // back from the end: it plays on from there
        cancelScrub();
        video.seek(d);
        if (again) video.setPaused(false);
        barUp();
    }
    function scrubBy(dir, held) {
        repeats = held ? repeats + 1 : 0;
        const step = repeats < 8 ? 10 : repeats < 24 ? 30 : 60;
        scrub = Math.max(0, Math.min(Math.max(0, duration - 1), (scrub >= 0 ? scrub : pos) + dir * step));
        hide.restart();
    }
    function cancelScrub() { scrub = -1; repeats = 0; }
    function press(key) {
        if (key === "play") toggle(); else action(key);
        hide.restart();
    }
    function back() {
        if (mode === "below") { mode = "controls"; hide.restart(); }
        else if (mode !== "hidden" && ready) mode = "hidden";     // (still loading, they can't hide: it leaves)
        else leave();
    }
    // Every other way in: "toggle", "play", "pause", "seek" (arg: seconds from here, 10 when not
    // given), "seekTo" (arg: seconds from the start), "stop" (leaves the player).
    function media(name, arg) {
        if (name === "stop") { leave(); return; }
        if (!video || !ready) return;
        if (name === "seek") { quick(Number(arg) || 10); return; }
        if (name === "seekTo") {
            if (live) { show(); return; }
            const again = video.ended;
            cancelScrub();
            video.seekTo(Math.max(0, Math.min(Math.max(0, duration - 1), Number(arg) || 0)));
            if (again) video.setPaused(false);
            barUp();
            return;
        }
        if (name === "toggle") toggle();
        else if (name === "play") { if (video.ended) toggle(); else video.setPaused(false); }
        else if (name === "pause") video.setPaused(true);
        else return;
        show();
    }

    // 5 s after the last key: hidden. Paused or at the end, the controls stay (a bar left there goes back to
    // them); loading, or on the app's row, nothing hides.
    Timer { id: hide; interval: 5000; onTriggered: pc.rest() }
    function rest() {
        if (!ready || !pictured || mode === "below") return;
        if (paused || ended) { if (mode === "bar") mode = "controls"; return; }
        mode = "hidden";
    }
    onModeChanged: {
        if (mode !== "bar") { quickSeek = false; cancelScrub(); }     // (a scrub left to time out doesn't jump)
        if (mode === "below" && below) below.forceActiveFocus(); else keys.focus = true;
    }
    onBelowChanged: if (below) below.parent = belowSlot

    // the position, read four times a second as well as on the video's notices: the clock and the
    // bar follow from the first frame
    Timer {
        interval: 250; repeat: true; running: pc.active
        onTriggered: {
            pc.pos = pc.video.position;
            if (pc.mode !== "hidden" && typeof pc.video.cacheTime === "function") pc.cached = pc.video.cacheTime();
        }
    }
    Connections {
        target: pc.video
        enabled: pc.active
        ignoreUnknownSignals: true
        function onPositionChanged() { pc.pos = pc.video.position; }
        function onPausedChanged() { if (pc.video.paused && pc.ready) pc.show(); else hide.restart(); }   // paused by any route: the controls
        function onEndedChanged() { if (pc.video.ended && pc.ready) pc.show(); }     // the end: the controls, Play starts it again
    }
    onActiveChanged: if (!active) { hide.stop(); pictured = false; }

    // subtitles move up while the controls show, so they don't sit under them
    readonly property int subtitlesAt: active && shown ? Math.floor(100 * (sheet.rowY - 116 * u) / Math.max(1, height)) : 100
    onSubtitlesAtChanged: if (video && typeof video.setSubtitlePosition === "function") video.setSubtitlePosition(subtitlesAt)
    Component.onDestruction: if (video && typeof video.setSubtitlePosition === "function") video.setSubtitlePosition(100)

    // ------------------------------------------------------------------ the keys
    Item { id: keys; focus: true }             // the keys land here and are handled below, whatever shows
    Keys.onPressed: e => {
        if (before && before(e)) { e.accepted = true; return; }
        const k = e.key;
        const ok = k === Qt.Key_Return || k === Qt.Key_Enter || k === Qt.Key_Select;
        const left = k === Qt.Key_Left, right = k === Qt.Key_Right, up = k === Qt.Key_Up, down = k === Qt.Key_Down;
        if (k === Qt.Key_Escape || k === Qt.Key_Back) {
            if (!e.isAutoRepeat) back();
        } else if (k === Qt.Key_MediaTogglePlayPause || k === Qt.Key_MediaPlay || k === Qt.Key_MediaPause || k === Qt.Key_Space) {
            if (!e.isAutoRepeat) media("toggle");
        } else if (k === Qt.Key_AudioRewind || k === Qt.Key_MediaPrevious) {
            media("seek", -10);
        } else if (k === Qt.Key_AudioForward || k === Qt.Key_MediaNext) {
            media("seek", 10);
        } else if (!(ok || left || right || up || down)) {
            return;
        } else if (!ready || !video || (ok && e.isAutoRepeat)) {
            // loading, or it can't be played: only Back; a held OK presses once
        } else if (mode === "below") {         // (what the app's row didn't take) Up: back to the controls
            if (up) { mode = "controls"; hide.restart(); }
        } else if (mode === "hidden") {
            if (left || right) quick(left ? -10 : 10); else show();
        } else if (mode === "bar") {
            if (left || right) { if (quickSeek) quick(left ? -10 : 10); else scrubBy(left ? -1 : 1, e.isAutoRepeat); }
            else if (ok && scrub >= 0) { const to = scrub; cancelScrub(); video.seekTo(to); mode = "hidden"; }   // there, playing
            else if (ok) { toggle(); hide.restart(); }
            else if (down) { mode = "controls"; hide.restart(); }
            else mode = "hidden";              // Up: back to the video, where it was
        } else {
            hide.restart();
            if (left || right) focused = shownButtons[Math.max(0, Math.min(shownButtons.length - 1, focusIndex + (left ? -1 : 1)))].key;
            else if (up) { if (!live && duration > 0) mode = "bar"; }     // the bar: scrubbing
            else if (down) { if (below) mode = "below"; }
            else press(shownButtons[focusIndex].key);
        }
        e.accepted = true;
    }

    // ------------------------------------------------------------------ the cover
    // What stands in for the video until this file's own first picture is drawn (never the one
    // before's last picture), then fading out.
    Item {
        id: cover
        anchors.fill: parent
        readonly property bool want: !pc.pictured
        opacity: 1
        visible: opacity > 0
        onWantChanged: { coverFade.stop(); if (want) opacity = 1; else coverFade.start(); }
        NumberAnimation { id: coverFade; target: cover; property: "opacity"; to: 0; duration: 240; easing.type: Easing.OutCubic }
        Rectangle { anchors.fill: parent; color: "black" }
        Image {
            anchors.fill: parent
            source: pc.poster
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            sourceSize: Qt.size(960, 540)
        }
    }

    // ------------------------------------------------------------------ the overlay
    Item {
        id: overlay
        anchors.fill: parent
        opacity: pc.shown ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 220 } }

        Rectangle {                            // the app's row is up: all of the video dimmed
            anchors.fill: parent
            color: Qt.rgba(pc.scrim.r, pc.scrim.g, pc.scrim.b, 0.78)
            opacity: pc.mode === "below" ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 220 } }
        }
        Rectangle {
            anchors { left: parent.left; right: parent.right; top: parent.top }
            height: 280 * pc.u
            opacity: pc.seeking ? 0 : 1
            Behavior on opacity { NumberAnimation { duration: 180 } }
            gradient: Gradient {
                GradientStop { position: 0; color: Qt.rgba(pc.scrim.r, pc.scrim.g, pc.scrim.b, 0.85) }
                GradientStop { position: 1; color: Qt.rgba(pc.scrim.r, pc.scrim.g, pc.scrim.b, 0) }
            }
        }
        Rectangle {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            height: 460 * pc.u
            gradient: Gradient {
                GradientStop { position: 0; color: Qt.rgba(pc.scrim.r, pc.scrim.g, pc.scrim.b, 0) }
                GradientStop { position: 0.5; color: Qt.rgba(pc.scrim.r, pc.scrim.g, pc.scrim.b, 0.7) }
                GradientStop { position: 1; color: Qt.rgba(pc.scrim.r, pc.scrim.g, pc.scrim.b, 0.96) }
            }
        }

        Item {
            id: sheet
            width: parent.width - pc.rightInset
            height: parent.height
            y: pc.mode === "below" ? -pc.belowLift : 0
            Behavior on y { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
            // where the buttons sit: near the foot, or higher with a row of the app's under them
            readonly property real rowY: pc.below ? 741 * pc.u : height - 192 * pc.u

            Item {                             // the title
                x: pc.edge; y: 60 * pc.u
                width: parent.width - 2 * pc.edge
                opacity: pc.mode === "below" || pc.seeking ? 0 : 1
                Behavior on opacity { NumberAnimation { duration: 180 } }
                Loader { width: parent.width; sourceComponent: pc.header }
                Column {
                    visible: !pc.header
                    width: parent.width
                    spacing: 10 * pc.u
                    Text {
                        width: Math.min(parent.width, implicitWidth)
                        text: pc.title
                        color: pc.text
                        font.family: pc.font; font.pixelSize: 42 * pc.u; font.weight: Font.DemiBold
                        elide: Text.ElideRight
                    }
                    Text {
                        width: Math.min(parent.width, implicitWidth)
                        visible: !!text
                        text: pc.subtitle
                        color: pc.dim
                        font.family: pc.font; font.pixelSize: 24 * pc.u; font.weight: Font.Medium
                        elide: Text.ElideRight
                    }
                }
            }

            // ---------------------------------------------------------------- time and bar
            Item {
                id: barArea
                x: pc.edge; y: sheet.rowY - 86 * pc.u
                width: parent.width - 2 * pc.edge
                height: 70 * pc.u
                visible: !pc.live && pc.ready
                opacity: pc.mode === "below" ? 0 : 1
                Behavior on opacity { NumberAnimation { duration: 180 } }
                readonly property real frac: pc.duration > 0 ? Math.max(0, Math.min(1, pc.shownPos / pc.duration)) : 0
                Text {                         // where it's playing (scrubbing too: the time over the knob says where it'd go)
                    y: 5 * pc.u
                    visible: !(pc.seeking && pc.quickSeek)     // (after a skip the knob's time says it: once)
                    text: pc.clock(pc.pos)
                    color: pc.text
                    font.family: pc.font; font.pixelSize: 24 * pc.u; font.weight: Font.Medium
                }
                Text {
                    anchors.right: parent.right
                    y: 5 * pc.u
                    text: pc.clock(pc.duration)
                    color: pc.dim
                    font.family: pc.font; font.pixelSize: 24 * pc.u; font.weight: Font.Medium
                }
                Item {
                    id: bar
                    y: 55 * pc.u
                    width: parent.width
                    height: 8 * pc.u
                    Rectangle { anchors.fill: parent; radius: height / 2; color: "#5affffff" }
                    Rectangle {                // read ahead: lighter, after the playhead
                        width: pc.duration > 0 ? Math.max(0, Math.min(1, pc.cached / pc.duration)) * parent.width : 0
                        height: parent.height; radius: height / 2
                        color: "#59ffffff"
                    }
                    Rectangle {
                        width: barArea.frac * parent.width
                        height: parent.height; radius: height / 2
                        color: pc.accent
                    }
                    Rectangle {                // the knob, while seeking
                        visible: pc.seeking
                        x: barArea.frac * parent.width - width / 2
                        anchors.verticalCenter: parent.verticalCenter
                        width: 32 * pc.u; height: width; radius: width / 2
                        color: pc.accent
                    }
                }
                Rectangle {                    // the time over the knob, while seeking
                    visible: opacity > 0
                    opacity: pc.seeking ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: pc.seeking ? 180 : 140 } }
                    x: Math.max(0, Math.min(parent.width - width, barArea.frac * parent.width - width / 2))
                    y: -height - 2 * pc.u
                    width: seekT.implicitWidth + 36 * pc.u; height: 56 * pc.u; radius: height / 2
                    color: Qt.rgba(pc.scrim.r, pc.scrim.g, pc.scrim.b, 0.7)
                    Text {
                        id: seekT
                        anchors.centerIn: parent
                        text: pc.clock(pc.shownPos)
                        color: pc.text
                        font.family: pc.font; font.pixelSize: 30 * pc.u; font.weight: Font.DemiBold
                    }
                }
            }

            // ---------------------------------------------------------------- the buttons
            Item {
                id: row
                x: pc.edge; y: sheet.rowY
                width: parent.width - 2 * pc.edge
                height: 96 * pc.u
                visible: pc.ready
                opacity: pc.mode === "below" || pc.seeking ? 0 : 1
                Behavior on opacity { NumberAnimation { duration: 180 } }
                readonly property bool live: pc.mode === "controls" && pc.activeFocus
                Row {
                    id: buttonRow
                    anchors.centerIn: parent
                    spacing: 18 * pc.u
                    Repeater {
                        id: buttonRep
                        model: pc.shownButtons.length        // (a count: the buttons stay as their labels and marks change)
                        PlayerButton {
                            required property int index
                            readonly property var b: pc.shownButtons[index] || ({})
                            readonly property bool play: b.key === "play"
                            anchors.verticalCenter: parent.verticalCenter
                            icon: play ? (pc.ended ? "replay" : pc.paused ? "play" : "pause") : b.icon || ""
                            text: b.text || ""
                            big: play
                            marked: !!b.marked
                            on: row.live && pc.focusIndex === index
                            u: pc.u; font: pc.font
                            ink: pc.ink; focusFill: pc.focusFill; focusInk: pc.focusInk; focusRing: pc.focusRing
                        }
                    }
                }
                Text {                         // what the focused button is (not Play / Pause: its picture says it)
                    readonly property Item at: { pc.shownButtons; return buttonRep.count > pc.focusIndex ? buttonRep.itemAt(pc.focusIndex) : null; }
                    readonly property string said: row.live ? (pc.shownButtons[pc.focusIndex] || {}).label || "" : ""
                    property string last: ""
                    onSaidChanged: if (said) last = said
                    text: said || last
                    opacity: said ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: 140 } }
                    x: at ? Math.max(0, Math.min(row.width - width, buttonRow.x + at.x + at.width / 2 - width / 2)) : 0
                    y: row.height + 12 * pc.u
                    color: pc.text
                    font.family: pc.font; font.pixelSize: 22 * pc.u; font.weight: Font.Medium
                }
            }

            Item {                             // the app's own row (below)
                id: belowSlot
                y: 948 * pc.u
                width: parent.width
                height: 532 * pc.u
                visible: !!pc.below && pc.mode !== "hidden" && !pc.seeking && pc.ready
            }
        }

        Rectangle {                            // why it won't play: a card over the picture
            visible: !!pc.message
            anchors.centerIn: parent
            anchors.horizontalCenterOffset: -pc.rightInset / 2
            width: Math.min((parent.width - pc.rightInset) * 0.66, whyText.implicitWidth + 120 * pc.u)
            height: whyText.implicitHeight + 90 * pc.u
            radius: 24 * pc.u
            color: "#e6121212"
            border.color: "#33ffffff"; border.width: 2 * pc.u
            Text {
                id: whyText
                anchors.centerIn: parent
                width: Math.min(implicitWidth, (overlay.width - pc.rightInset) * 0.66 - 120 * pc.u)
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                text: pc.message
                color: pc.text
                font.family: pc.font; font.pixelSize: 32 * pc.u
            }
        }
    }

    Rectangle {                                // paused with the controls put away (Back): a small mark
        readonly property bool on: pc.paused && !pc.shown && pc.pictured
        x: pc.edge; y: 60 * pc.u
        width: 72 * pc.u; height: width; radius: width / 2
        color: Qt.rgba(pc.scrim.r, pc.scrim.g, pc.scrim.b, 0.7)
        opacity: on ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 180 } }
        PlayerIcon { anchors.centerIn: parent; name: "pause"; size: 34 * pc.u; color: pc.text }
    }
    Rectangle {                                // loading, buffering: a ring
        id: ring
        visible: pc.active && pc.busy
        x: (parent.width - pc.rightInset - width) / 2
        anchors.verticalCenter: parent.verticalCenter
        width: 96 * pc.u; height: width; radius: width / 2
        color: "#80000000"
        border.color: pc.text; border.width: 6 * pc.u
        RotationAnimation on rotation { running: ring.visible; from: 0; to: 360; duration: 1200; loops: Animation.Infinite }
        Rectangle { width: 22 * pc.u; height: width; radius: width / 2; color: pc.accent; x: parent.width / 2 - width / 2; y: -4 * pc.u }
    }
}
