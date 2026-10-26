// couchbox-movies: Movies & TV (started by /usr/lib/couchbox/bin/couchbox-movies). The sidebar
// (Home, Search, Top movies, Top shows) and its pages; titles, people and seasons open on top
// of each other, and Back goes back down (from the pages, Back leaves the app). The back end
// is movies.py, through Backend's threads.
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
    title: "Movies & TV"
    color: M.bg
    font.family: M.font

    readonly property var args: Qt.application.arguments
    function arg(name) { const i = args.indexOf(name); return i >= 0 ? args[i + 1] || "" : ""; }
    readonly property string shot: arg("--shot")
    readonly property real u: height / 1080
    onUChanged: M.u = u

    property string mode: "starting"         // starting | setup | app
    property int section: 0                  // 0 home, 1 search, 2 top movies, 3 top shows

    Component.onCompleted: { M.u = u; start(); }
    function start() {
        M.call("status", {}, s => {
            M.status = s;
            if (!s.ok) { mode = "setup"; setup.problem = s.problem || ""; setup.forceActiveFocus(); return; }
            mode = "app";
            home.load();
            focusPage();
            updateState();
            const o = arg("--open");
            if (o) openTarget(o);
        }, e => { mode = "setup"; setup.problem = e; });
    }

    // ------------------------------------------------------------------ navigation
    function focusPage() {
        if (stack.depth) { stack.currentItem.forceActiveFocus(); return; }
        [home, search, top, top][section].forceActiveFocus();
    }
    function choose(i) {
        clearStack();
        section = i;
        if (i >= 2) { top.kind = i === 2 ? "movie" : "tv"; top.load(); }
        focusPage();
        updateState();
    }
    function clearStack() { stack.clear(StackView.Immediate); }
    Connections {
        target: M
        function onOpen(t) { win.push(t); }
        function onToast(text) { toast.show(text); }
    }
    function push(t) {
        if (!t || !t.type) return;
        if (t.type === "movie" || t.type === "tv") stack.push(titleC, {kind: t.type, tid: t.id}, StackView.Immediate);
        else if (t.type === "person") stack.push(personC, {pid: t.id, startDept: t.dept || ""}, StackView.Immediate);
        else if (t.type === "season") stack.push(seasonC, {tid: t.id, n: t.n, show: t.show || ""}, StackView.Immediate);
        stack.currentItem.forceActiveFocus();
        updateState();
    }
    function back() {
        stack.pop(StackView.Immediate);
        focusPage();
        updateState();
    }
    // --open / the voice assistant / a second launch: movie:ID, tv:ID, person:ID[:DEPT],
    // season:ID:N, search:TEXT, top:movie, top:tv, home
    function openTarget(o) {
        if (mode !== "app") return;
        const [k, a, b] = o.split(":");
        if (k === "movie" || k === "tv") { clearStack(); push({type: k, id: parseInt(a)}); }
        else if (k === "person") { clearStack(); push({type: "person", id: parseInt(a), dept: b || ""}); }
        else if (k === "season") { clearStack(); push({type: "season", id: parseInt(a), n: parseInt(b)}); }
        else if (k === "search") { choose(1); search.search(o.slice(7)); }
        else if (k === "top") choose(a === "tv" ? 3 : 2);
        else if (k === "home") choose(0);
    }
    function updateState() {
        const st = {page: stack.depth ? (stack.currentItem.kind || (stack.currentItem.pid ? "person" : "season")) : ["home", "search", "top movies", "top shows"][section]};
        if (stack.depth && stack.currentItem.label) st.showing = stack.currentItem.label;
        control.setState(JSON.stringify(st));
    }
    Connections {
        target: control
        function onCommand(js) {
            const c = JSON.parse(js);
            if (c.op === "open") { if (c.target) win.openTarget(c.target); win.raise(); win.requestActivate(); }
        }
    }

    // ------------------------------------------------------------------ layout
    Item {
        id: main
        anchors.fill: parent
        visible: win.mode === "app" && stack.depth === 0
        Rail {
            id: rail
            width: M.railW
            anchors { top: parent.top; bottom: parent.bottom }
            section: win.section
            onChosen: i => win.choose(i)
            onToPage: win.focusPage()
            Keys.onEscapePressed: Qt.quit()
            Keys.onBackPressed: Qt.quit()
        }
        HomePage {
            id: home
            anchors { left: rail.right; right: parent.right; top: parent.top; bottom: parent.bottom }
            visible: win.section === 0
            onToRail: rail.forceActiveFocus()
            Keys.onEscapePressed: Qt.quit()
            Keys.onBackPressed: Qt.quit()
        }
        SearchPage {
            id: search
            anchors { left: rail.right; right: parent.right; top: parent.top; bottom: parent.bottom }
            visible: win.section === 1
            onToRail: rail.forceActiveFocus()
            onAsk: current => keyboard.open(current, search)
            Keys.onEscapePressed: win.choose(0)
            Keys.onBackPressed: win.choose(0)
        }
        TopPage {
            id: top
            anchors { left: rail.right; right: parent.right; top: parent.top; bottom: parent.bottom }
            visible: win.section >= 2
            onToRail: rail.forceActiveFocus()
            Keys.onEscapePressed: win.choose(0)
            Keys.onBackPressed: win.choose(0)
        }
    }
    StackView {
        id: stack
        anchors.fill: parent
        visible: depth > 0
    }
    Component { id: titleC; TitlePage { onClosed: win.back() } }
    Component { id: personC; PersonPage { onClosed: win.back() } }
    Component { id: seasonC; SeasonPage { onClosed: win.back() } }

    SetupPage {
        id: setup
        anchors.fill: parent
        visible: win.mode === "setup"
        Keys.onEscapePressed: Qt.quit()
        Keys.onBackPressed: Qt.quit()
    }
    Text {
        anchors.centerIn: parent
        visible: win.mode === "starting"
        text: "Movies & TV"
        color: M.faint; font.family: M.font; font.pixelSize: 40 * M.u
    }

    TextEntry {
        id: keyboard
        anchors.fill: parent
        title: "Search movies, shows and people"
        doneLabel: "Search"
        accent: M.accent; bg: M.bg; panel: M.panel; keyColor: M.panel2; line: M.line; ink: M.text; dim: M.dim
        onAccepted: t => search.search(t)
    }

    Rectangle {                                  // notices
        id: toast
        function show(t) { toastText.text = t; opacity = 1; toastTimer.restart(); }
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 48 * win.u }
        width: Math.min(toastText.implicitWidth + 56 * win.u, parent.width * 0.8)
        height: 72 * win.u
        radius: 14 * win.u
        color: M.panel2
        border.color: M.line
        opacity: 0
        z: 200
        Behavior on opacity { NumberAnimation { duration: 200 } }
        Text { id: toastText; anchors.centerIn: parent; width: parent.width - 40 * win.u; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight
               color: M.text; font.family: M.font; font.pixelSize: 24 * win.u }
        Timer { id: toastTimer; interval: 3500; onTriggered: toast.opacity = 0 }
    }

    // ------------------------------------------------------------------ idle, off-screen tests
    // Quit after half an hour without use (nothing plays here).
    onActiveFocusItemChanged: idle.restart()
    Timer { id: idle; interval: 30 * 60 * 1000; running: !win.shot; onTriggered: Qt.quit() }

    // --shot FILE [--open ...] [--keys k1,k2,...]
    Timer {
        running: !!win.shot
        interval: 2000
        onTriggered: {
            const keys = win.arg("--keys");
            if (keys) for (const k of keys.split(",")) shooter.press(k);
            shotTimer.start();
        }
    }
    Timer { id: shotTimer; interval: 2000; onTriggered: { shooter.save(win.shot); Qt.quit(); } }
}
