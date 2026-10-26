// Leave by: pick where and when to arrive; it works out when to set off (with the traffic
// expected then, when Google is in use) and keeps the answer up to date as you change them.
// Up/Down move between the rows; Left/Right change the mode or the time (15 minutes a press).
import QtQuick

FocusScope {
    id: page
    property var to: null
    property string mode: "drive"
    property real arrive: 0                  // epoch seconds
    property var plan: null                  // maps.py leave_by()
    property bool busy: false
    property string problem: ""
    property int row: 0                      // 0 where, 1 how, 2 when, 3 show the route
    readonly property var modes: ["drive", "transit", "walk", "bike"]
    signal pickDestination()
    signal showRoute(var to, string mode, real depart)
    signal toRail()

    function defaultArrive() {                   // the next full hour, at least 45 minutes away
        const t = Date.now() / 1000 + 45 * 60;
        return Math.ceil(t / 3600) * 3600;
    }
    function setup(dest, when, how) {
        if (dest) to = dest;
        if (when) arrive = when; else if (!arrive || arrive < Date.now() / 1000) arrive = defaultArrive();
        if (how) mode = how;
        row = to ? 2 : 0;
        replan.restart();
    }
    Timer { id: replan; interval: 500; onTriggered: page.compute() }
    function compute() {
        if (!to || !arrive) { plan = null; return; }
        busy = true; problem = "";
        const want = {to: to, arrive: arrive, mode: mode};
        M.call("leave_by", want, r => { if (want.to === page.to && want.arrive === page.arrive && want.mode === page.mode) { page.plan = r; page.busy = false; } },
               e => { page.busy = false; page.plan = null; page.problem = e; });
    }

    Keys.onUpPressed: row = Math.max(0, row - 1)
    Keys.onDownPressed: row = Math.min(plan ? 3 : 2, row + 1)
    Keys.onLeftPressed: {
        if (row === 1 && modes.indexOf(mode) > 0) { mode = modes[modes.indexOf(mode) - 1]; replan.restart(); }
        else if (row === 2 && arrive - 900 > Date.now() / 1000) { arrive -= 900; replan.restart(); }
        else if (row === 0 || row === 3) toRail();
    }
    Keys.onRightPressed: {
        if (row === 1 && modes.indexOf(mode) < modes.length - 1) {
            const next = modes[modes.indexOf(mode) + 1];
            if (M.status.modes && M.status.modes.indexOf(next) < 0) M.toast("Transit needs a Google Maps key (Settings → Apps → Maps).");
            mode = M.status.modes && M.status.modes.indexOf(next) < 0 ? modes[modes.indexOf(mode) + 2] || mode : next;
            replan.restart();
        } else if (row === 2) { arrive += 900; replan.restart(); }
    }
    Keys.onReturnPressed: press()
    Keys.onEnterPressed: press()
    function press() {
        if (row === 0) pickDestination();
        else if (row === 3 && plan) showRoute(to, mode, plan.leave);
    }

    Column {
        id: col
        anchors { left: parent.left; top: parent.top; leftMargin: 60 * M.u; topMargin: 56 * M.u }
        width: 760 * M.u
        spacing: 24 * M.u
        Row {
            spacing: 20 * M.u
            Text { text: "Leave by"; color: M.text; font.family: M.font; font.pixelSize: M.tTitle; font.weight: Font.Bold }
            Text { anchors.baseline: parent.children[0].baseline; text: "When to set off to be there on time"; color: M.dim; font.family: M.font; font.pixelSize: M.tBody }
        }
        Item { width: 1; height: 6 * M.u }
        MButton {
            width: parent.width
            icon: page.to ? (page.to.kind === "home" ? "home" : page.to.kind === "work" ? "work" : "pin") : "search"
            text: page.to ? page.to.name : "Where to?"
            sub: page.to ? (page.to.address || "") : "Press OK to choose a place"
            border.color: page.activeFocus && page.row === 0 ? M.focus : M.line
            border.width: (page.activeFocus && page.row === 0 ? 3 : 1) * M.u
            color: page.activeFocus && page.row === 0 ? M.panel2 : M.panel
        }
        Rectangle {                                  // how
            width: parent.width; height: 92 * M.u; radius: 12 * M.u
            color: page.activeFocus && page.row === 1 ? M.panel2 : M.panel
            border.color: page.activeFocus && page.row === 1 ? M.focus : M.line; border.width: (page.activeFocus && page.row === 1 ? 3 : 1) * M.u
            Text { x: 28 * M.u; anchors.verticalCenter: parent.verticalCenter; text: "By"; color: M.dim; font.family: M.font; font.pixelSize: M.tBody }
            Row {
                anchors { right: parent.right; rightMargin: 24 * M.u; verticalCenter: parent.verticalCenter }
                spacing: 10 * M.u
                Repeater {
                    model: page.modes
                    delegate: Rectangle {
                        required property string modelData
                        readonly property bool sel: page.mode === modelData
                        readonly property bool off: !!M.status.modes && M.status.modes.indexOf(modelData) < 0
                        width: 132 * M.u; height: 60 * M.u; radius: 30 * M.u
                        color: sel ? "#123a2e" : "transparent"
                        border.color: sel ? M.accent : M.line
                        opacity: off ? 0.35 : 1
                        Row {
                            anchors.centerIn: parent; spacing: 8 * M.u
                            Image { anchors.verticalCenter: parent.verticalCenter; width: 26 * M.u; height: width; sourceSize: M.sz(width, height); source: M.icon(M.modeIcon(parent.parent.modelData)) }
                            Text { anchors.verticalCenter: parent.verticalCenter; text: M.modeName(parent.parent.modelData); color: M.text; font.family: M.font; font.pixelSize: 21 * M.u }
                        }
                    }
                }
            }
        }
        Rectangle {                                  // when
            width: parent.width; height: 132 * M.u; radius: 12 * M.u
            color: page.activeFocus && page.row === 2 ? M.panel2 : M.panel
            border.color: page.activeFocus && page.row === 2 ? M.focus : M.line; border.width: (page.activeFocus && page.row === 2 ? 3 : 1) * M.u
            Text { x: 28 * M.u; anchors.verticalCenter: parent.verticalCenter; text: "Arrive by"; color: M.dim; font.family: M.font; font.pixelSize: M.tBody }
            Row {
                anchors { right: parent.right; rightMargin: 28 * M.u; verticalCenter: parent.verticalCenter }
                spacing: 22 * M.u
                Text { anchors.verticalCenter: parent.verticalCenter; text: "◀"; color: page.activeFocus && page.row === 2 ? M.text : M.faint; font.pixelSize: 26 * M.u }
                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    Text { anchors.horizontalCenter: parent.horizontalCenter; text: page.arrive ? M.clock(page.arrive) : "—"; color: M.text; font.family: M.font; font.pixelSize: 52 * M.u; font.weight: Font.Bold }
                    Text { anchors.horizontalCenter: parent.horizontalCenter; text: page.arrive ? M.day(page.arrive) : ""; color: M.dim; font.family: M.font; font.pixelSize: M.tMeta }
                }
                Text { anchors.verticalCenter: parent.verticalCenter; text: "▶"; color: page.activeFocus && page.row === 2 ? M.text : M.faint; font.pixelSize: 26 * M.u }
            }
        }
        MButton {
            visible: !!page.plan
            width: parent.width
            icon: "route"
            text: "Show the route"
            border.color: page.activeFocus && page.row === 3 ? M.focus : M.line
            border.width: (page.activeFocus && page.row === 3 ? 3 : 1) * M.u
            color: page.activeFocus && page.row === 3 ? M.panel2 : M.panel
        }
    }

    // ------------------------------------------------------------------ the answer
    Rectangle {
        anchors { left: col.right; leftMargin: 50 * M.u; right: parent.right; rightMargin: M.edge; top: col.top; topMargin: 110 * M.u }
        height: answer.implicitHeight + 90 * M.u
        radius: 22 * M.u
        color: M.panel; border.color: M.line
        Column {
            id: answer
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 45 * M.u }
            spacing: 14 * M.u
            Text {
                width: parent.width; wrapMode: Text.WordWrap
                visible: !page.plan || page.busy
                text: page.busy ? "Working it out…" : page.problem ? page.problem : !page.to ? "Choose where you're going." : ""
                color: M.text2; font.family: M.font; font.pixelSize: M.tBody
            }
            Text { visible: !!page.plan && !page.busy; text: page.plan && page.plan.late ? "Leave now" : "Leave by"; color: M.dim; font.family: M.font; font.pixelSize: M.tHead }
            Text {
                visible: !!page.plan && !page.busy
                text: page.plan ? M.clock(Math.max(page.plan.leave, Date.now() / 1000)) : ""
                color: page.plan && page.plan.late ? M.heavy : M.accent
                font.family: M.font; font.pixelSize: 110 * M.u; font.weight: Font.Bold
            }
            Text {
                visible: !!page.plan && !page.busy
                width: parent.width; wrapMode: Text.WordWrap
                text: !page.plan ? "" : page.plan.late ? "You'd arrive at " + M.clock(page.plan.route.arrive) + ", " + M.mins(page.plan.late_by) + " late."
                      : M.day(page.plan.leave) + "  ·  " + page.plan.route.duration_text + " " + {drive: "drive", transit: "by transit", walk: "walk", bike: "ride"}[page.plan.mode]
                        + (page.plan.traffic ? " with expected traffic" : "") + "  ·  arrive " + M.clock(page.plan.route.arrive)
                color: M.text2; font.family: M.font; font.pixelSize: M.tBody
            }
            Text {
                visible: !!page.plan && !page.busy && !!page.plan.route.summary
                width: parent.width; elide: Text.ElideRight
                text: page.plan ? "via " + page.plan.route.summary + "  ·  " + page.plan.route.distance_text : ""
                color: M.dim; font.family: M.font; font.pixelSize: M.tMeta
            }
            Text {
                visible: !!page.plan && !page.busy && !page.plan.traffic && page.plan.mode === "drive"
                width: parent.width; wrapMode: Text.WordWrap
                text: "Without traffic: allow extra time at busy hours. A Google Maps key adds traffic (Settings → Apps → Maps)."
                color: M.faint; font.family: M.font; font.pixelSize: M.tSmall
            }
        }
    }
}
