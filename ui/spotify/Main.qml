// couchbox-spotify: Spotify as a TV app (started by /usr/lib/couchbox/bin/couchbox-spotify).
// The sidebar (Home, Search, Your Library, Now Playing, Setup), pages of shelves and songs,
// albums, playlists and artists, Now Playing, and a bar with what's playing. Music plays on
// this TV through Spotify's player (couchbox-spotify --connect), so it keeps playing after
// the app closes. Remote: arrows move, OK opens or plays, Menu shows actions, Back goes back.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Window
import CouchKit

ApplicationWindow {
    id: win
    width: 1920
    height: 1080
    visible: true
    visibility: shot ? Window.Windowed : Window.FullScreen
    title: "Spotify"
    color: S.bg
    font.family: S.font

    readonly property var args: Qt.application.arguments
    function arg(name) { const i = args.indexOf(name); return i >= 0 ? args[i + 1] || "" : ""; }
    readonly property string shot: arg("--shot")
    readonly property real u: height / 1080
    onUChanged: S.u = u

    property string mode: "starting"         // starting | setup | app
    property int section: 0                  // 0 home, 1 search, 2 library
    property var stack: []                   // opened albums, playlists, artists (Back pops)
    property bool nowOpen: false
    property var typed: null                 // the keyboard pop-up types for this
    property var menuFocus: null

    Component.onCompleted: { S.u = u; start(); }
    onModeChanged: if (mode === "setup") control.setState(JSON.stringify({page: "setup"}))
    function start() {
        S.call("status", {}, s => {
            S.status = s;
            if (win.args.indexOf("--setup") >= 0 || !s.configured || !s.signedIn) { mode = "setup"; setup.forceActiveFocus(); }
            else load();
        }, e => toast.show(e));
    }
    function load() {
        mode = "app";
        home.load();
        openFromArgs();
        if (!stack.length && !nowOpen) focusPage();
    }

    Connections {
        target: S
        function onSignInNeeded(why) {
            S.call("status", {}, s => { S.status = s; win.mode = "setup"; win.nowOpen = false; setup.forceActiveFocus(); });
            toast.show(why);
        }
        function onToast(text) { toast.show(text); }
        function onMenu(item, context) { if (item) win.showMenu(item, context || {}); }
    }

    // ------------------------------------------------------------------ navigation
    readonly property var pages: [home, search, library]
    function focusPage() {
        if (stack.length) return (topIsArtist ? artist : detail).forceActiveFocus();
        pages[section].forceActiveFocus();
    }
    readonly property bool topIsArtist: stack.length > 0 && stack[stack.length - 1].kind === "artist"
    function choose(id) {
        if (id === "now") return openNow();
        if (id === "setup") { mode = "setup"; setup.forceActiveFocus(); return; }
        stack = [];
        section = {home: 0, search: 1, library: 2}[id];
        if (section === 2) library.load();
        if (section === 0) home.load();
        focusPage();
        updateState();
    }
    function open(item) {
        if (!item) return;
        if (item.kind === "track") {                 // a song card: play it, in its album
            if (item.album && item.album.uri) S.play({context: item.album.uri, offset: item.uri});
            else S.play({uris: [item.uri]});
            return;
        }
        stack = stack.concat([item]);
        if (item.kind === "artist") { artist.item = item; artist.forceActiveFocus(); }
        else { detail.item = item; detail.forceActiveFocus(); }
        updateState();
    }
    function back() {
        if (stack.length) {
            const s = stack.slice(0, -1);
            stack = s;
            if (s.length) { const top = s[s.length - 1]; if (top.kind === "artist") artist.item = top; else detail.item = top; }
            focusPage();
        } else if (section !== 0) { section = 0; focusPage(); }
        else Qt.quit();
        updateState();
    }
    function openNow() { nowOpen = true; nowPlaying.forceActiveFocus(); updateState(); }
    function closeNow() { nowOpen = false; focusPage(); updateState(); }

    function showMenu(item, context) {
        menuFocus = win.activeFocusItem;
        actions.item = item; actions.context = context;
        actions.visible = true;
        actions.forceActiveFocus();
    }
    function closeMenu() { actions.visible = false; if (menuFocus) menuFocus.forceActiveFocus(); }
    function act(id) {
        const x = actions.item, ctx = actions.context || {};
        actions.visible = false;
        if (id === "play") {
            if (x.kind === "track") S.play(ctx.context ? {context: ctx.context, offset: x.uri} : {uris: [x.uri]});
            else S.play({context: x.context || x.uri});
        } else if (id === "shuffle") S.play({context: x.context || x.uri, shuffle: true});
        else if (id === "queue") S.call("media", {action: "queue", uri: x.uri}, () => toast.show("Plays next: " + x.name + "."));
        else if (id === "like" || id === "save") {
            const on = !S.liked[x.uri];
            S.call("save", {uris: [x.uri], on: on}, () => { S.setLiked(x.uri, on); toast.show(on ? (id === "like" ? "Added to Liked Songs." : "Saved to Your Library.") : "Removed."); });
        } else if (id === "add" || id === "addall") {
            picker.uris = id === "add" ? [x.uri] : x.tracksUris;
            picker.what = id === "add" ? "“" + x.name + "”" : picker.uris.length + " songs";
            picker.visible = true; picker.load(); picker.forceActiveFocus();
            return;
        } else if (id === "album") { nowOpen = false; open({kind: "album", id: x.album.id, uri: x.album.uri, name: x.album.name}); return; }
        else if (id.startsWith("artist:")) { nowOpen = false; open({kind: "artist", id: id.slice(7), uri: "spotify:artist:" + id.slice(7), name: ""}); return; }
        else if (id === "open") { open(x); return; }
        if (menuFocus) menuFocus.forceActiveFocus();
    }
    function openFromArgs() {
        const o = arg("--open");
        if (o) openTarget(o);
    }
    function openTarget(o) {                         // a second launch, the voice assistant, tests
        if (mode !== "app") return;
        if (o === "now") openNow();
        else if (o === "search") { choose("search"); }
        else if (o.startsWith("search:")) { choose("search"); search.search(o.slice(7)); }
        else if (o === "library") choose("library");
        else if (o === "home") choose("home");
        else if (o.startsWith("album:")) { nowOpen = false; open({kind: "album", id: o.slice(6), uri: "spotify:album:" + o.slice(6), name: ""}); }
        else if (o.startsWith("playlist:")) { nowOpen = false; open({kind: "playlist", id: o.slice(9), uri: "spotify:playlist:" + o.slice(9), name: ""}); }
        else if (o.startsWith("artist:")) { nowOpen = false; open({kind: "artist", id: o.slice(7), uri: "spotify:artist:" + o.slice(7), name: ""}); }
        else if (o === "liked") { nowOpen = false; open({kind: "liked", id: "liked", uri: "liked", name: "Liked Songs"}); }
        else if (o === "menu") { const t = demo ? {kind: "track", uri: "spotify:track:demo1", name: "Northern Lights", artists: [{id: "ar1", name: "The Midnight Arcade"}], album: {id: "al0", uri: "spotify:album:al0", name: "Neon Harbor"}} : null; if (t) showMenu(t, {}); }
        else if (o === "picker") { picker.uris = ["spotify:track:demo1"]; picker.what = "“Northern Lights”"; picker.visible = true; picker.load(); picker.forceActiveFocus(); }
    }
    function updateState() {
        const top = stack.length ? stack[stack.length - 1] : null;
        control.setState(JSON.stringify({page: nowOpen ? "now playing" : top ? top.kind + ": " + (top.name || "") : ["home", "search", "library"][section]}));
    }
    Connections {
        target: control
        function onCommand(js) {
            const c = JSON.parse(js);
            if (c.op === "open") { if (c.target) win.openTarget(c.target); win.raise(); win.requestActivate(); }
            else if (c.op === "status") S.call("status", {}, s => { S.status = s; if (win.mode === "setup" && s.signedIn && s.configured) toast.show("Signed in as " + s.user + "."); });
        }
    }

    // ------------------------------------------------------------------ layout
    Item {
        id: main
        anchors.fill: parent
        visible: win.mode === "app" && !win.nowOpen
        Rail {
            id: rail
            width: S.railW
            anchors { top: parent.top; bottom: parent.bottom }
            section: win.section
            onChosen: id => win.choose(id)
            onToPage: win.focusPage()
            Keys.onEscapePressed: Qt.quit()
            Keys.onBackPressed: Qt.quit()
        }
        Item {
            id: content
            anchors { left: rail.right; leftMargin: 60 * S.u; right: parent.right; top: parent.top; bottom: bar.visible ? bar.top : parent.bottom }
            HomePage {
                id: home
                anchors.fill: parent
                visible: win.section === 0 && !win.stack.length
                onToRail: rail.forceActiveFocus()
                onChosen: item => win.open(item)
                Keys.onEscapePressed: win.back()
                Keys.onBackPressed: win.back()
            }
            SearchPage {
                id: search
                anchors.fill: parent
                visible: win.section === 1 && !win.stack.length
                onToRail: rail.forceActiveFocus()
                onChosen: item => win.open(item)
                onAsk: current => {
                    keyboard.title = "Search Spotify"; keyboard.doneLabel = "Search"; keyboard.password = false;
                    win.typed = t => search.search(t.trim());
                    keyboard.open(current, search);
                }
                Keys.onEscapePressed: win.back()
                Keys.onBackPressed: win.back()
            }
            LibraryPage {
                id: library
                anchors.fill: parent
                visible: win.section === 2 && !win.stack.length
                onToRail: rail.forceActiveFocus()
                onChosen: item => win.open(item)
                Keys.onEscapePressed: win.back()
                Keys.onBackPressed: win.back()
            }
            DetailPage {
                id: detail
                anchors.fill: parent
                visible: win.stack.length > 0 && !win.topIsArtist
                onLeftEdge: rail.forceActiveFocus()
                Keys.onEscapePressed: win.back()
                Keys.onBackPressed: win.back()
            }
            ArtistPage {
                id: artist
                anchors.fill: parent
                visible: win.topIsArtist
                onLeftEdge: rail.forceActiveFocus()
                onChosen: item => win.open(item)
                Keys.onEscapePressed: win.back()
                Keys.onBackPressed: win.back()
            }
        }
        MiniPlayer {
            id: bar
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        }
    }
    NowPlaying {
        id: nowPlaying
        anchors.fill: parent
        visible: win.mode === "app" && win.nowOpen
        onClosed: win.closeNow()
        onAddToPlaylist: t => {
            picker.uris = [t.uri]; picker.what = "“" + (t.name || "this song") + "”";
            win.menuFocus = nowPlaying;
            picker.visible = true; picker.load(); picker.forceActiveFocus();
        }
        Keys.onMenuPressed: if (S.nowInfo && S.nowInfo.uri) win.showMenu(Object.assign({kind: "track"}, S.nowInfo), {})
    }
    SetupPage {
        id: setup
        anchors.fill: parent
        visible: win.mode === "setup"
        onAsk: (what, current, secret, op) => {
            keyboard.title = what; keyboard.doneLabel = "Save"; keyboard.password = secret;
            win.typed = t => S.call(op, {value: t.trim()}, s => { S.status = s; toast.show(op === "login_paste" ? "Signed in as " + s.user + "." : "Saved."); });
            keyboard.open(current, setup);
        }
        onDone: { if (S.status.signedIn) win.load(); else Qt.quit(); }
        Keys.onEscapePressed: { if (S.status.signedIn) win.load(); else Qt.quit(); }
        Keys.onBackPressed: { if (S.status.signedIn) win.load(); else Qt.quit(); }
    }
    Text {
        anchors.centerIn: parent
        visible: win.mode === "starting"
        text: "Spotify"
        color: S.faint; font.family: S.font; font.pixelSize: 40 * S.u
    }
    ActionMenu {
        id: actions
        anchors.fill: parent
        visible: false
        z: 50
        onClosed: win.closeMenu()
        onPick: id => win.act(id)
    }
    PlaylistPicker {
        id: picker
        anchors.fill: parent
        visible: false
        z: 60
        onClosed: { picker.visible = false; if (win.menuFocus) win.menuFocus.forceActiveFocus(); else win.focusPage(); }
        onAskName: {
            keyboard.title = "New playlist name"; keyboard.doneLabel = "Create"; keyboard.password = false;
            win.typed = t => picker.create(t.trim());
            keyboard.open("", picker);
        }
    }

    TextEntry {
        id: keyboard
        anchors.fill: parent
        z: 100
        title: "Search"
        accent: S.accent; bg: S.bg; panel: S.panel; keyColor: S.panel2; line: S.line; ink: S.text; dim: S.dim
        onAccepted: t => { if (win.typed) { const done = win.typed; win.typed = null; done(t); } }
        onCanceled: win.typed = null
    }

    Rectangle {                                  // notices ("Added to Liked Songs")
        id: toast
        function show(t) { toastText.text = t; opacity = 1; toastTimer.restart(); }
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: (bar.visible && main.visible ? S.barH : 0) + 40 * win.u }
        width: Math.min(parent.width - 200 * win.u, toastText.implicitWidth + 60 * win.u)
        height: 76 * win.u
        radius: height / 2
        color: "#f0f0f0"
        opacity: 0
        z: 200
        Behavior on opacity { NumberAnimation { duration: 200 } }
        Text { id: toastText; anchors.centerIn: parent; width: parent.width - 60 * win.u; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight
               color: "#000000"; font.family: S.font; font.pixelSize: 25 * win.u; font.weight: Font.DemiBold }
        Timer { id: toastTimer; interval: 3500; onTriggered: toast.opacity = 0 }
    }

    // ------------------------------------------------------------------ idle, off-screen tests
    // The app quits after an hour without use; the music keeps playing (couchbox-spotify --connect).
    onActiveFocusItemChanged: idle.restart()
    Timer { id: idle; interval: 60 * 60 * 1000; running: true; onTriggered: Qt.quit() }
    Timer {                                  // not a Spotify speaker yet: watch for a refused key or a login
        interval: 5000; repeat: true; running: win.mode === "app" && !S.now.logged_in
        onTriggered: S.call("status", {}, s => S.status = s)
    }

    // --shot FILE [--open now | search:TEXT | album:ID | artist:ID | playlist:ID | liked | library | menu | picker] [--setup] [--keys k1,k2,...]
    Timer {
        running: !!win.shot
        interval: 2500
        onTriggered: {
            const keys = win.arg("--keys");
            if (keys) for (const k of keys.split(",")) shooter.press(k);
            shotTimer.start();
        }
    }
    Timer { id: shotTimer; interval: 2000; onTriggered: { shooter.save(win.shot); Qt.quit(); } }
}
