// couchbox-streaming: Dropout as a TV app (started by /usr/lib/couchbox/bin/couchbox-dropout). The website's
// pages, bigger and for the remote: the top bar (Home, Series, My List, Search), the home
// rows, show pages with seasons and episodes, search, and the player (libmpv). Up from a
// page's top reaches the top bar; Back goes back (and leaves the app from Home).
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Window
import QtCore
import CouchKit
import CouchPlayer

ApplicationWindow {
    id: win
    width: 1920
    height: 1080
    visible: true
    visibility: shot ? Window.Windowed : Window.FullScreen
    title: site.name
    color: D.bg
    font.family: D.font

    readonly property var args: Qt.application.arguments
    function arg(name) { const i = args.indexOf(name); return i >= 0 ? args[i + 1] || "" : ""; }
    readonly property string shot: arg("--shot")
    readonly property real u: height / 1080
    onUChanged: D.u = u
    readonly property var sections: site.nav || ["Home", "Series", "My List", "Search"]
    property int section: 0
    property var typed: null
    readonly property bool playing: !!(stack.currentItem && stack.currentItem.videoId !== undefined)

    Settings { id: prefs; category: "player"; property bool subtitles: defaults.subtitles; property string chatMode: defaults.chatMode }
    Connections {
        target: D
        function onSubtitlesChanged() { prefs.subtitles = D.subtitles; }
        function onChatModeChanged() { prefs.chatMode = D.chatMode; }
    }
    Component.onCompleted: {
        D.subtitles = prefs.subtitles;
        D.chatMode = prefs.chatMode;
        D.video = video;
        D.site = site;
        D.u = u;
        D.call("status", {}, r => win.signedIn(r), () => stack.replace(null, win.signInPage, {}, StackView.Immediate));
    }
    function signedIn(r) {
        if (r.state === "ok") showSection(0);
        else if (r.state === "profile") stack.replace(null, profileC, {profiles: r.profiles}, StackView.Immediate);
        else stack.replace(null, win.signInPage, {}, StackView.Immediate);
    }

    // ------------------------------------------------------------------ pages
    Component { id: homeC; HomePage {} }
    Component { id: seriesC; SeriesPage {} }
    Component { id: gridC; GridPage {} }
    Component { id: searchC; SearchPage {} }
    Component { id: playerC; PlayerPage { onFinished: win.back() } }
    Component { id: signInC; SignInPage { onDone: r => win.signedIn(r) } }
    Component { id: profileC; ProfilePage { onDone: r => win.signedIn(r) } }
    Component { id: deviceC; DeviceSignInPage { onDone: r => win.signedIn(r) } }
    readonly property Component signInPage: site.signin === "device" ? deviceC : signInC

    function showSection(i) {
        section = i;
        const pages = [[homeC, {}], [gridC, {title: win.sections[1], op: "allSeries", args: {}, shape: site.series_shape || "poster"}],
                       [gridC, {title: win.sections[2], op: "mylist", args: {}, shape: "wide",
                                empty: site.no_list_button ? "Nothing saved to " + win.sections[2] + " yet." : "Add shows with My List on their page."}],
                       [searchC, {}]];
        stack.clear();
        stack.push(pages[i][0], pages[i][1], StackView.Immediate);
        stack.forceActiveFocus();
    }
    function push(c, props) { stack.push(c, props); stack.forceActiveFocus(); }
    function back() {
        if (keyboard.visible) return;
        if (nav.activeFocus) return stack.forceActiveFocus();
        if (stack.depth > 1) {
            stack.pop();
            stack.forceActiveFocus();
            if (stack.currentItem && stack.currentItem.returned) stack.currentItem.returned();
            return;
        }
        if (section !== 0) return showSection(0);
        Qt.quit();
    }

    Connections {
        target: D
        function onOpen(c) {
            if (c.kind === "category") win.push(gridC, {title: c.title, op: "items", args: {href: c.id}, shape: "wide"});
            else if (c.kind === "video") win.push(seriesC, {cid: c.collectionId, focusVideo: c.id});
            else win.push(seriesC, {cid: c.id, autoplay: !!c.autoplay});
        }
        function onPlay(id) { win.push(playerC, {videoId: id}); }
        function onOpenGrid(title, op, a) { win.push(gridC, {title: title, op: op, args: a}); }
        function onToast(text) { toast.show(text); }
        function onSignInNeeded() {
            const cur = stack.currentItem;
            if (cur && (cur.email !== undefined || cur.info !== undefined)) return;
            stack.replace(null, win.signInPage, {}, StackView.Immediate);
        }
        function onAskText(title, text, password, done) {
            win.typed = done;
            keyboard.title = title;
            keyboard.password = password;
            keyboard.doneLabel = title.indexOf("Search") === 0 ? "Search" : "Done";
            keyboard.open(text, win.activeFocusItem);
        }
    }
    Connections {                             // Twitch signed in after the sign-in page was left
        target: backend
        function onEvent(name, data) { if (name === "signedIn") toast.show("Signed in as " + JSON.parse(data).user + "."); }
    }

    // keys the pages didn't use: Up -> the top bar, Back -> back
    FocusScope {
        id: ui
        anchors.fill: parent
        focus: true
        Keys.onUpPressed: if (!win.playing) nav.forceActiveFocus()
        Keys.onEscapePressed: win.back()
        Keys.onBackPressed: win.back()

        // the video: under the pages, shown while the player page is up
        MpvVideo {
            id: video
            anchors.fill: parent
            anchors.rightMargin: D.videoInset          // Twitch's side chat
            visible: win.playing
        }

        StackView {
            id: stack
            anchors.fill: parent
            focus: true
            pushEnter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 180 } }
            pushExit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 140 } }
            popEnter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 180 } }
            popExit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 140 } }
        }

        // ------------------------------------------------------------------ top bar
        Item {
            id: topBar
            visible: !win.playing && stack.currentItem && stack.currentItem.email === undefined && stack.currentItem.profiles === undefined && stack.currentItem.info === undefined
            width: parent.width
            height: 120 * win.u
            Rectangle {
                anchors.fill: parent
                gradient: Gradient {
                    GradientStop { position: 0.0; color: Qt.rgba(0, 0, 0, 0.9) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }
            Logo {
                id: logo
                x: D.edge
                y: 34 * win.u
                size: 46
            }
            ListView {
                id: nav
                anchors { left: logo.right; leftMargin: 64 * win.u; verticalCenter: logo.verticalCenter }
                width: 900 * win.u
                height: 56 * win.u
                orientation: ListView.Horizontal
                interactive: false
                spacing: 12 * win.u
                model: win.sections
                currentIndex: win.section
                delegate: Rectangle {
                    required property int index
                    required property string modelData
                    readonly property bool cur: ListView.isCurrentItem && nav.activeFocus
                    width: navText.implicitWidth + 40 * win.u
                    height: 56 * win.u
                    radius: 28 * win.u
                    color: cur ? D.accent : "transparent"
                    Text {
                        id: navText
                        anchors.centerIn: parent
                        text: modelData
                        color: parent.cur ? D.accentInk : index === win.section ? D.text : D.dim
                        font.family: D.font
                        font.pixelSize: 25 * win.u
                        font.weight: index === win.section ? Font.Black : Font.DemiBold
                        font.capitalization: Font.AllUppercase
                        font.letterSpacing: 1 * win.u
                    }
                    Rectangle {
                        visible: index === win.section && !parent.cur
                        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 2 * win.u }
                        width: 28 * win.u; height: 4 * win.u; radius: 2 * win.u
                        color: D.accent
                    }
                }
                Keys.onLeftPressed: if (currentIndex > 0) currentIndex--
                Keys.onRightPressed: if (currentIndex < count - 1) currentIndex++
                Keys.onDownPressed: { currentIndex = win.section; stack.forceActiveFocus(); }
                Keys.onReturnPressed: win.showSection(currentIndex)
                Keys.onEnterPressed: win.showSection(currentIndex)
                onActiveFocusChanged: if (!activeFocus) currentIndex = Qt.binding(() => win.section)
            }
        }
    }

    TextEntry {
        id: keyboard
        anchors.fill: parent
        accent: D.accent; bg: D.bg; panel: D.panel; keyColor: D.panel2; line: D.line; ink: D.text; dim: D.dim
        onAccepted: t => { const done = win.typed; win.typed = null; if (done) done(t); }
        onCanceled: win.typed = null
    }

    Rectangle {                                  // notices
        id: toast
        function show(t) { toastText.text = t; opacity = 1; toastTimer.restart(); }
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 60 * win.u }
        width: toastText.implicitWidth + 64 * win.u
        height: 76 * win.u
        radius: 10 * win.u
        color: D.panel2
        border.color: D.line
        opacity: 0
        z: 200
        Behavior on opacity { NumberAnimation { duration: 200 } }
        Text { id: toastText; anchors.centerIn: parent; color: D.text; font.family: D.font; font.pixelSize: 26 * win.u; font.weight: Font.DemiBold }
        Timer { id: toastTimer; interval: 3500; onTriggered: toast.opacity = 0 }
    }

    // ------------------------------------------------------------------ the voice assistant
    // couchbox-voice reaches the app through its control socket (couchbox.appctl): it opens
    // things here, controls the player, and reads what's on screen (pushState).
    function openTarget(o) {
        const idOf = x => isNaN(Number(x)) ? x : Number(x);     // Nebula's and Twitch's ids are text
        if (o.startsWith("series:")) D.open({kind: "series", id: idOf(o.slice(7))});
        else if (o.startsWith("video:")) D.open({kind: "video", id: parseInt(o.split(":")[2] || 0), collectionId: parseInt(o.split(":")[1])});
        else if (o.startsWith("play:")) {
            if (win.playing) stack.popCurrentItem(StackView.Immediate);   // one player at a time
            D.play(idOf(o.slice(5)));
        }
        else if (o.startsWith("search:")) { win.showSection(3); Qt.callLater(() => stack.currentItem.search(o.slice(7))); }
        else if (o === "series") win.showSection(1);
        else if (o === "mylist") win.showSection(2);
        else if (o === "home") win.showSection(0);
    }
    function mediaCommand(a, s) {
        if (!win.playing) return;
        if (a === "play") video.setPaused(false);
        else if (a === "pause") video.setPaused(true);
        else if (a === "toggle") video.togglePause();
        else if (a === "forward") video.seek(s || 30);
        else if (a === "back") video.seek(-(s || 10));
        else if (a === "seek") video.seekTo(s);
        else if (a === "restart") video.seekTo(0);
        Qt.callLater(win.pushState);
    }
    function pushState() {
        const it = stack.currentItem;
        let st = {page: "home", section: win.sections[win.section] || ""};
        if (!it) st.page = "starting";
        else if (it.videoId !== undefined) {
            const v = it.v || {};
            st = {page: "player", id: String(it.videoId), title: v.title || "", series: v.series || "", episode: v.title ? D.epLabel(v) : "",
                  live: !!v.live, position: video.position, duration: video.duration, paused: video.paused};
        }
        else if (it.cid !== undefined) st = {page: "series", id: String(it.cid), title: it.s ? it.s.title || "" : ""};
        else if (it.query !== undefined) st = {page: "search", query: it.query};
        else if (it.op !== undefined) st = {page: "list", title: it.title};
        else if (it.email !== undefined || it.info !== undefined) st = {page: "sign-in"};
        control.setState(JSON.stringify(st));
    }
    Connections {
        target: control
        function onCommand(js) {
            const c = JSON.parse(js);
            if (c.op === "open") win.openTarget(c.target || "home");
            else if (c.op === "media") win.mediaCommand(c.action, c.seconds || 0);
        }
    }
    Connections { target: stack; function onCurrentItemChanged() { Qt.callLater(win.pushState); } }
    Timer { interval: 5000; repeat: true; running: !win.shot; onTriggered: win.pushState() }

    // ------------------------------------------------------------------ idle, off-screen tests
    // Like couchbox-memory does for the other apps: quit after an hour without use (not while playing).
    onActiveFocusItemChanged: idle.restart()
    readonly property bool watching: win.playing && !!stack.currentItem.watching
    Timer { id: idle; interval: 60 * 60 * 1000; running: !win.watching; onTriggered: Qt.quit() }

    // --shot FILE [--open series:ID | video:ID | play:ID | search:TEXT | series | mylist] [--down N] [--keyboard]
    //            [--keys ok,down,right,back,...] [--wait MS]
    property int downs: 0
    property var keys: []                       // --keys up,down,left,right,ok,back,...: pressed one per second
    Timer {
        interval: 1100
        repeat: true
        running: shotTimer.running && win.keys.length > 0
        onTriggered: { const k = win.keys.shift(); win.keys = win.keys; shooter.press(k); }
    }
    Timer {
        running: !!win.shot
        interval: 4000
        onTriggered: {
            win.openTarget(win.arg("--open"));
            if (win.args.indexOf("--keyboard") >= 0) D.askText("Search " + D.name, "game", false, () => {});
            win.downs = parseInt(win.arg("--down") || "0");
            win.keys = win.arg("--keys") ? win.arg("--keys").split(",") : [];
            shotTimer.start();
        }
    }
    Timer {
        interval: 800
        repeat: true
        running: shotTimer.running && win.downs > 0
        onTriggered: if (stack.currentItem && stack.currentItem.move && win.downs > 0 && stack.currentItem.move(1)) win.downs--
    }
    Timer { id: shotTimer; interval: parseInt(win.arg("--wait") || "9000"); onTriggered: { shooter.save(win.shot); Qt.quit(); } }
}
