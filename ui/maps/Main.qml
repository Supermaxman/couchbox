// couchbox-maps: maps on the TV (started by /usr/lib/couchbox/bin/couchbox-maps). The sidebar
// (Places, Search, Directions, Leave by) and the page beside it. Remote: arrows move, OK opens,
// Back goes back (and, on Places, leaves the app). maps.py does the work on threads; the map
// tiles come through its relay on 127.0.0.1.
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
    title: "Maps"
    color: M.bg
    font.family: M.font

    readonly property var args: Qt.application.arguments
    function arg(name) { const i = args.indexOf(name); return i >= 0 ? args[i + 1] || "" : ""; }
    readonly property string shot: arg("--shot")
    readonly property real u: height / 1080
    onUChanged: M.u = u

    property int section: 0                  // 0 places, 1 search, 2 directions, 3 leave by
    property int from: 0                     // where Back from Directions goes
    property var typed: null                 // the keyboard pop-up types for this

    Component.onCompleted: { M.u = u; start(); }
    function start() {
        M.call("status", {}, s => {
            M.status = s;
            M.call("places", {}, r => { M.setPlaces(r); places.refresh(); win.openFromArgs(); });
        });
        places.forceActiveFocus();
    }
    Connections { target: M; function onToast(text) { toast.show(text); } }

    // ------------------------------------------------------------------ navigation
    function page(i) { return [places, search, directions, leave][i]; }
    function go(i) {
        if (i === 2 && !directions.trip) return;
        if (i === 2 && section !== 2) from = section;
        section = i;
        page(i).forceActiveFocus();
        if (i === 1 && !search.picking && !search.query) search.idx = 0;
        updateState();
    }
    function back() {
        if (section === 0) Qt.quit();
        else if (section === 1 && search.picking) { search.picking = ""; go(search.pickFrom); }
        else if (section === 2) go(from === 2 ? 0 : from);
        else go(0);
    }

    function openDirections(to, mode, depart) {
        mode = mode || "drive";
        if (M.status.modes && M.status.modes.indexOf(mode) < 0) mode = "drive";
        go2(to, mode);
        M.call("directions", {to: to, mode: mode, depart: depart || 0}, t => { if (directions.trip && directions.trip.to === to) directions.shown(t); },
               e => directions.failed(e));
    }
    function go2(to, mode) {
        directions.loading(to, mode);
        if (section !== 2) from = section;
        section = 2;
        directions.forceActiveFocus();
        updateState();
    }
    function openLeave(to, arrive, mode) { leave.setup(to, arrive, mode); go(3); }
    function pick(kind, title, then) {           // search for a place, for Home, Work, a new place, a trip
        search.pickFrom = section;
        search.startPicking(kind, title);
        win.picked = then;
        go(1);
        askSearch();
    }
    property var picked: null
    function askSearch() {
        keyboard.title = search.picking ? search.pickTitle : "Search";
        keyboard.doneLabel = "Search"; keyboard.password = false;
        win.typed = t => search.run(t);
        keyboard.open(search.query, search);
    }
    function askName(current, then) {
        keyboard.title = "Name this place"; keyboard.doneLabel = "Save"; keyboard.password = false;
        win.typed = t => { if (t.trim()) then(t.trim()); };
        keyboard.open(current, page(section));
    }
    function save(place, kind, name) {
        M.call("save", {place: place, kind: kind, name: name || ""}, r => {
            M.setPlaces(r);
            toast.show(kind === "home" ? "Home is set." : kind === "work" ? "Work is set." : "Saved " + (name || place.name) + ".");
            places.refresh();
        });
    }

    // what you can do with a place
    function placeActions(p, saved) {
        const a = [{label: "Directions", icon: "route", act: () => win.openDirections(p)},
                   {label: "Leave by…", icon: "clock", act: () => win.openLeave(p)}];
        if (saved) {
            if (p.kind === "home" || p.kind === "work")
                a.push({label: p.approx ? "Set the address" : "Change the address", icon: "search",
                        act: () => win.pick(p.kind, p.kind === "home" ? "Set Home" : "Set Work", r => { win.save(r, p.kind); win.go(0); })});
            if (p.kind === "place") {
                a.push({label: "Rename", icon: "edit", act: () => win.askName(p.name, n => M.call("rename", {id: p.id, name: n}, r => M.setPlaces(r)))});
                a.push({label: "Remove", icon: "remove", danger: true, act: () => M.call("remove", {id: p.id}, r => { M.setPlaces(r); places.idx = 0; })});
            }
            if (p.kind === "work")
                a.push({label: "Remove", icon: "remove", danger: true, act: () => M.call("remove", {id: p.id}, r => { M.setPlaces(r); places.idx = 0; })});
            if (p.kind === "home") a.splice(0, 2);
        } else {
            a.push({label: "Save as a place", icon: "star", act: () => win.askName(p.name, n => win.save(p, "place", n))});
            a.push({label: "Save as Home", icon: "home", act: () => win.save(p, "home")});
            a.push({label: "Save as Work", icon: "work", act: () => win.save(p, "work")});
        }
        sheet.open(p.name, p.address || "", a, page(section));
    }
    function chooseDestination() {
        const a = M.places.filter(p => p.kind !== "home").concat(M.recent).slice(0, 7)
                   .map(p => ({label: p.name, icon: p.kind === "work" ? "work" : p.kind === "place" ? "star" : "recent", act: () => leave.setup(p)}));
        a.push({label: "Search for a place…", icon: "search", act: () => win.pick("to", "Where to?", r => { win.go(3); leave.setup(r); })});
        sheet.open("Where to?", "", a, leave);
    }

    // --open places | search[:QUERY] | to:{"place": ..., "mode": ...} | leave:{"place": ..., "arrive": ...}
    function openFromArgs() { const o = arg("--open"); if (o) openTarget(o); }
    function openTarget(o) {
        try {
            if (o === "places") go(0);
            else if (o === "search") { go(1); askSearch(); }
            else if (o.startsWith("search:")) { search.picking = ""; go(1); search.run(o.slice(7)); }
            else if (o.startsWith("to:")) { const j = JSON.parse(o.slice(3)); openDirections(j.place, j.mode, j.depart); }
            else if (o.startsWith("leave:")) { const j = JSON.parse(o.slice(6)); openLeave(j.place, j.arrive, j.mode); }
            else if (o === "leave") go(3);
        } catch (e) { toast.show("Couldn't open that."); }
    }
    function updateState() {
        const st = {page: ["places", "search", "directions", "leave_by"][section]};
        if (section === 2 && directions.trip && directions.trip.to) {
            st.to = directions.trip.to.name; st.mode = directions.trip.mode;
            const r = directions.route;
            if (r) { st.duration = r.duration_text; st.arrive = M.clock(r.arrive); }
        }
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
    Rail {
        id: rail
        width: M.railW
        anchors { top: parent.top; bottom: parent.bottom }
        section: win.section
        hasTrip: !!directions.trip
        onChosen: i => { if (i === 1) { search.picking = ""; win.go(1); if (!search.query) win.askSearch(); } else win.go(i); }
        onToPage: win.page(win.section).forceActiveFocus()
        Keys.onEscapePressed: win.back()
        Keys.onBackPressed: win.back()
    }
    Item {
        id: content
        anchors { left: rail.right; right: parent.right; top: parent.top; bottom: parent.bottom }
        PlacesPage {
            id: places
            anchors.fill: parent
            visible: win.section === 0
            onActivate: (p, saved) => win.placeActions(p, saved)
            onAdd: win.pick("place", "Add a place", r => win.askName(r.name, n => { win.save(r, "place", n); win.go(0); }))
            onToRail: rail.forceActiveFocus()
            Keys.onEscapePressed: win.back()
            Keys.onBackPressed: win.back()
        }
        SearchPage {
            id: search
            property int pickFrom: 0
            anchors.fill: parent
            visible: win.section === 1
            onAsk: win.askSearch()
            onActivate: p => win.placeActions(p, !!p.saved)
            onPicked: p => { const then = win.picked; search.picking = ""; win.picked = null; if (then) then(p); }
            onToRail: rail.forceActiveFocus()
            Keys.onEscapePressed: win.back()
            Keys.onBackPressed: win.back()
        }
        DirectionsPage {
            id: directions
            anchors.fill: parent
            visible: win.section === 2
            onChangeMode: mode => win.openDirections(directions.trip.to, mode)
            onLeaveBy: win.openLeave(directions.trip.to, 0, directions.trip.mode)
            onToRail: rail.forceActiveFocus()
            onChosenChanged: win.updateState()
            Keys.onEscapePressed: win.back()
            Keys.onBackPressed: win.back()
        }
        LeaveByPage {
            id: leave
            anchors.fill: parent
            visible: win.section === 3
            onPickDestination: win.chooseDestination()
            onShowRoute: (to, mode, depart) => win.openDirections(to, mode, depart)
            onToRail: rail.forceActiveFocus()
            Keys.onEscapePressed: win.back()
            Keys.onBackPressed: win.back()
        }
    }
    ActionSheet { id: sheet; anchors.fill: parent }

    TextEntry {
        id: keyboard
        anchors.fill: parent
        title: "Search"
        placeholder: "Type with the keys below or on your phone"
        accent: M.accent; bg: M.bg; panel: M.panel; keyColor: M.panel2; line: M.line; ink: M.text; dim: M.dim
        onAccepted: t => { if (win.typed) { const done = win.typed; win.typed = null; done(t); } }
        onCanceled: { win.typed = null; if (search.picking && !search.query) win.back(); }
    }

    Rectangle {                                  // notices
        id: toast
        function show(t) { toastText.text = t; opacity = 1; toastTimer.restart(); }
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 48 * win.u }
        width: Math.min(parent.width - 200 * win.u, toastText.implicitWidth + 56 * win.u)
        height: 72 * win.u
        radius: 14 * win.u
        color: M.panel2
        border.color: M.line
        opacity: 0
        z: 200
        Behavior on opacity { NumberAnimation { duration: 200 } }
        Text { id: toastText; anchors.centerIn: parent; width: parent.width - 56 * win.u; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight; color: M.text; font.family: M.font; font.pixelSize: 24 * win.u }
        Timer { id: toastTimer; interval: 4000; onTriggered: toast.opacity = 0 }
    }

    // ------------------------------------------------------------------ idle, off-screen tests
    onActiveFocusItemChanged: idle.restart()
    Timer { id: idle; interval: 60 * 60 * 1000; running: true; onTriggered: Qt.quit() }

    // --shot FILE [--open ...] [--keys k1,k2,...]
    Timer {
        running: !!win.shot
        interval: 2500
        onTriggered: {
            const keys = win.arg("--keys");
            if (keys) for (const k of keys.split(",")) shooter.press(k);
            shotTimer.start();
        }
    }
    Timer { id: shotTimer; interval: 2500; onTriggered: { try { shooter.save(win.shot); } finally { Qt.quit(); } } }
}
