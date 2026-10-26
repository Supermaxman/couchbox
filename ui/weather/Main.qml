// couchbox-weather: the weather where the TV is (started by /usr/lib/couchbox/bin/couchbox-weather):
// the sidebar (Today, the next 14 days, the radar, alerts), Today, the fortnight, the radar loop,
// a day hour by hour, and the alerts in full. Remote: arrows move, OK opens, Back goes back (and leaves the app from a
// page). The forecast refreshes every 15 minutes while the app is open.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Window

ApplicationWindow {
    id: win
    width: 1920
    height: 1080
    visible: true
    visibility: shot ? Window.Windowed : Window.FullScreen
    title: "Weather"
    color: W.bg
    font.family: W.font

    readonly property var args: Qt.application.arguments
    function arg(name) { const i = args.indexOf(name); return i >= 0 ? args[i + 1] || "" : ""; }
    readonly property string shot: arg("--shot")
    readonly property real u: height / 1080
    onUChanged: W.u = u

    property string mode: "starting"         // starting | problem | app
    property string problem: ""
    property int section: 0                  // 0 today, 1 week, 2 radar
    property string overlay: ""              // "" | day | alerts
    property string pending: arg("--open")    // a target to open once the forecast is in

    Component.onCompleted: { W.u = u; load(false); }
    function load(force) {
        W.call("forecast", {force: force}, d => {
            W.data = d;
            if (mode !== "app") { mode = "app"; focusPage(); }
            if (pending) { const p = pending; pending = ""; openTarget(p); }
            W.call("glance", {}, g => W.glance = g.text || "", () => {});
            updateState();
        }, e => {
            if (W.data) { toast.show(e); return; }   // keep showing the last forecast
            problem = e; mode = "problem"; retry.forceActiveFocus();
        });
    }
    Timer { interval: 15 * 60 * 1000; repeat: true; running: win.mode === "app"; onTriggered: win.load(true) }

    // ------------------------------------------------------------------ navigation
    function focusPage() { [today, week, radar][section].forceActiveFocus(); updateState(); }
    function choose(e) {
        if (e.kind === "today") { section = 0; focusPage(); }
        else if (e.kind === "week") { section = 1; focusPage(); }
        else if (e.kind === "radar") { section = 2; focusPage(); }
        else if (e.kind === "alerts") openAlerts();
    }
    function openDay(date, hour) {
        day.show(date, hour);
        overlay = "day";
        day.forceActiveFocus();
        updateState();
    }
    function openAlerts() {
        if (!W.data || !W.data.alerts.length) return;
        alerts.index = 0;
        overlay = "alerts";
        alerts.forceActiveFocus();
        updateState();
    }
    function closeOverlay() {
        if (overlay === "day" && section === 1) week.di = day.index;  // come back to the day last looked at
        overlay = "";
        focusPage();
    }
    function findDay(spec) {
        const s = (spec || "").toLowerCase();
        const days = W.data ? W.data.days : [];
        for (const x of days) if (x.date === s || x.name.toLowerCase() === s) return x.date;
        for (const x of days) if (x.name.toLowerCase().startsWith(s.slice(0, 3)) && s.length >= 3) return x.date;
        return "";
    }
    function openTarget(o) {
        if (mode !== "app") { pending = o; return; }
        if (o === "today" || o === "") { overlay = ""; section = 0; focusPage(); }
        else if (o === "week") { overlay = ""; section = 1; focusPage(); }
        else if (o === "radar") { overlay = ""; section = 2; focusPage(); }
        else if (o === "alerts") openAlerts();
        else if (o.startsWith("day:")) {
            const date = findDay(o.slice(4));
            if (date) openDay(date, -1);
            else toast.show("No forecast for " + o.slice(4) + ".");
        }
    }
    function updateState() {
        const st = {page: overlay || ["today", "week", "radar"][section]};
        if (overlay === "day" && day.day) st.day = day.day.name + " " + day.day.date;
        control.setState(JSON.stringify(st));
    }
    Connections {
        target: control
        function onCommand(js) {
            const c = JSON.parse(js);
            if (c.op === "open") { win.openTarget(c.target || "today"); win.raise(); win.requestActivate(); }
        }
    }

    // ------------------------------------------------------------------ layout
    Item {
        anchors.fill: parent
        visible: win.mode === "app" && win.overlay === ""
        Rail {
            id: rail
            width: W.railW
            anchors { top: parent.top; bottom: parent.bottom }
            section: win.section
            onChosen: e => win.choose(e)
            onToPage: win.focusPage()
            Keys.onEscapePressed: Qt.quit()
            Keys.onBackPressed: Qt.quit()
        }
        TodayPage {
            id: today
            anchors { left: rail.right; right: parent.right; top: parent.top; bottom: parent.bottom }
            visible: win.section === 0
            onOpenDay: (date, hour) => win.openDay(date, hour)
            onOpenAlerts: win.openAlerts()
            onToRail: rail.forceActiveFocus()
            Keys.onEscapePressed: Qt.quit()
            Keys.onBackPressed: Qt.quit()
        }
        WeekPage {
            id: week
            anchors { left: rail.right; right: parent.right; top: parent.top; bottom: parent.bottom }
            visible: win.section === 1
            onOpenDay: date => win.openDay(date, -1)
            onToRail: rail.forceActiveFocus()
            Keys.onEscapePressed: { win.section = 0; win.focusPage(); }
            Keys.onBackPressed: { win.section = 0; win.focusPage(); }
        }
        RadarPage {
            id: radar
            anchors { left: rail.right; right: parent.right; top: parent.top; bottom: parent.bottom }
            visible: win.section === 2
            Keys.onEscapePressed: rail.forceActiveFocus()
            Keys.onBackPressed: rail.forceActiveFocus()
        }
    }
    DayPage {
        id: day
        anchors.fill: parent
        visible: win.overlay === "day"
        onClosed: win.closeOverlay()
        onIndexChanged: win.updateState()
    }
    AlertView {
        id: alerts
        anchors.fill: parent
        visible: win.overlay === "alerts"
        onClosed: win.closeOverlay()
    }

    Column {                                     // starting, or no forecast
        anchors.centerIn: parent
        visible: win.mode !== "app"
        spacing: 30 * win.u
        Image { anchors.horizontalCenter: parent.horizontalCenter; width: 160 * win.u; height: width; sourceSize: Qt.size(width, height); source: W.icon(win.mode === "problem" ? "cloudy" : "partly-day"); opacity: 0.8 }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.min(implicitWidth, 1100 * win.u)
            horizontalAlignment: Text.AlignHCenter
            text: win.mode === "problem" ? win.problem : "Getting the forecast…"
            color: win.mode === "problem" ? W.text : W.faint; font.family: W.font; font.pixelSize: 34 * win.u
            wrapMode: Text.WordWrap
        }
        Rectangle {
            id: retry
            visible: win.mode === "problem"
            anchors.horizontalCenter: parent.horizontalCenter
            width: retryText.implicitWidth + 80 * win.u; height: 76 * win.u; radius: 38 * win.u
            color: activeFocus ? W.accent : W.panel2
            border.color: activeFocus ? W.focus : "transparent"; border.width: W.ring
            Text { id: retryText; anchors.centerIn: parent; text: "Try again"; color: retry.activeFocus ? W.bg : W.text; font.family: W.font; font.pixelSize: 28 * win.u; font.weight: Font.DemiBold }
            Keys.onReturnPressed: { win.mode = "starting"; win.load(true); }
            Keys.onEnterPressed: { win.mode = "starting"; win.load(true); }
            Keys.onEscapePressed: Qt.quit()
            Keys.onBackPressed: Qt.quit()
        }
    }

    Rectangle {
        id: toast
        function show(t) { toastText.text = t; opacity = 1; toastTimer.restart(); }
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 48 * win.u }
        width: toastText.implicitWidth + 56 * win.u
        height: 72 * win.u
        radius: 14 * win.u
        color: W.panel2
        border.color: W.line
        opacity: 0
        z: 200
        Behavior on opacity { NumberAnimation { duration: 200 } }
        Text { id: toastText; anchors.centerIn: parent; color: W.text; font.family: W.font; font.pixelSize: 24 * win.u }
        Timer { id: toastTimer; interval: 3500; onTriggered: toast.opacity = 0 }
    }

    // ------------------------------------------------------------------ idle, off-screen tests
    onActiveFocusItemChanged: idle.restart()
    Timer { id: idle; interval: 30 * 60 * 1000; running: true; onTriggered: Qt.quit() }

    // --shot FILE [--open today | week | radar | day:... | alerts] [--keys k1,k2,...]
    Timer {
        running: !!win.shot
        interval: 2000
        onTriggered: {
            const keys = win.arg("--keys");
            if (keys) for (const k of keys.split(",")) shooter.press(k);
            shotTimer.start();
        }
    }
    Timer { id: shotTimer; interval: 1500; onTriggered: { shooter.save(win.shot); Qt.quit(); } }
}
