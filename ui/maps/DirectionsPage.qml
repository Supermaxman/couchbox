// Directions: where to (and from), how (Drive, Transit, Walk, Bike), the route alternatives with
// their times, the turns of the chosen one, and the map. Left column: Up/Down between the modes
// row, the routes and the turns; Right goes to the map (arrows move it, OK zooms); Left goes
// to the sidebar.
import QtQuick

FocusScope {
    id: page
    property var trip: null                  // maps.py directions(): {from, to, mode, routes, traffic, provider}
    property bool busy: false
    property string problem: ""
    property int chosen: 0
    property int zone: 1                     // 0 modes row, 1 routes, 2 turns
    property int midx: 0
    property int sidx: 0
    readonly property var modes: ["drive", "transit", "walk", "bike"]
    readonly property var chips: modes.concat(["leave"])
    readonly property var route: trip && trip.routes ? trip.routes[chosen] || null : null
    signal changeMode(string mode)
    signal leaveBy()
    signal toRail()

    function shown(t) {
        trip = t; chosen = 0; sidx = 0; busy = false; problem = "";
        zone = t && t.routes && t.routes.length ? 1 : 0;
        midx = Math.max(0, modes.indexOf(t ? t.mode : "drive"));
        fitSoon.restart();
    }
    function loading(to, mode) {
        busy = true; problem = "";
        trip = {to: to, from: trip && trip.from || null, mode: mode, routes: []};
        midx = Math.max(0, modes.indexOf(mode));
    }
    function failed(e) { busy = false; problem = e; zone = 0; }
    Timer { id: fitSoon; interval: 30; onTriggered: page.fit() }
    function fit() {
        if (route && route.bbox) map.fit(route.bbox);
        else if (trip && trip.to) map.show(trip.to.lat, trip.to.lon, 14);
    }
    onChosenChanged: fit()

    Keys.onUpPressed: {
        if (zone === 2) { if (sidx > 0) sidx--; else zone = 1; }
        else if (zone === 1) { if (chosen > 0) chosen--; else zone = 0; }
    }
    Keys.onDownPressed: {
        if (zone === 0) { if (trip && trip.routes && trip.routes.length) zone = 1; }
        else if (zone === 1) { if (trip && chosen < trip.routes.length - 1) chosen++; else if (route && route.steps.length) { zone = 2; sidx = 0; } }
        else if (zone === 2 && route) sidx = Math.min(route.steps.length - 1, sidx + 1);
    }
    Keys.onLeftPressed: { if (zone === 0 && midx > 0) midx--; else toRail(); }
    Keys.onRightPressed: { if (zone === 0 && midx < chips.length - 1) midx++; else map.forceActiveFocus(); }
    Keys.onReturnPressed: press()
    Keys.onEnterPressed: press()
    function press() {
        if (zone === 0) {
            const c = chips[midx];
            if (c === "leave") leaveBy();
            else if (M.status.modes && M.status.modes.indexOf(c) < 0) M.toast("Transit directions need a Google Maps key (Settings → Apps → Maps).");
            else changeMode(c);
        } else map.forceActiveFocus();
    }
    onSidxChanged: steps.positionViewAtIndex(sidx, ListView.Contain)

    // ------------------------------------------------------------------ left: the trip
    Item {
        id: left
        anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
        width: 690 * M.u
        Column {
            id: head
            anchors { left: parent.left; right: parent.right; top: parent.top; leftMargin: 50 * M.u; rightMargin: 36 * M.u; topMargin: 50 * M.u }
            spacing: 8 * M.u
            Text { width: parent.width; text: page.trip && page.trip.to ? page.trip.to.name : "Directions"; color: M.text; font.family: M.font; font.pixelSize: 42 * M.u; font.weight: Font.Bold; elide: Text.ElideRight }
            Text {
                width: parent.width
                text: page.trip && page.trip.to ? [page.trip.to.address, "From " + (page.trip.from ? page.trip.from.name : "Home")].filter(x => !!x).join("  ·  ") : ""
                color: M.dim; font.family: M.font; font.pixelSize: M.tMeta; elide: Text.ElideRight
            }
            Item { width: 1; height: 12 * M.u }
            Row {                                    // Drive · Transit · Walk · Bike · Leave by
                spacing: 10 * M.u
                Repeater {
                    model: page.chips
                    delegate: Rectangle {
                        required property string modelData
                        required property int index
                        readonly property bool cur: page.activeFocus && page.zone === 0 && page.midx === index
                        readonly property bool sel: !!page.trip && page.trip.mode === modelData
                        readonly property bool off: modelData !== "leave" && !!M.status.modes && M.status.modes.indexOf(modelData) < 0
                        width: modelData === "leave" ? 160 * M.u : 98 * M.u; height: 70 * M.u; radius: 35 * M.u
                        color: sel ? "#123a2e" : cur ? M.panel2 : M.panel
                        border.color: cur ? M.focus : sel ? M.accent : M.line; border.width: cur ? 3 * M.u : 1 * M.u
                        opacity: off ? 0.4 : 1
                        Row {
                            anchors.centerIn: parent
                            spacing: 8 * M.u
                            Image { anchors.verticalCenter: parent.verticalCenter; width: 30 * M.u; height: width; sourceSize: M.sz(width, height); source: M.icon(parent.parent.modelData === "leave" ? "clock" : M.modeIcon(parent.parent.modelData)) }
                            Text { anchors.verticalCenter: parent.verticalCenter; visible: parent.parent.modelData === "leave"; text: "Leave by"; color: M.text; font.family: M.font; font.pixelSize: M.tMeta }
                        }
                    }
                }
            }
            Text {
                text: page.zone === 0 && page.activeFocus ? (page.chips[page.midx] === "leave" ? "When to leave to be there on time" : M.modeName(page.chips[page.midx])) : ""
                color: M.dim; font.family: M.font; font.pixelSize: M.tSmall; height: 26 * M.u
            }
        }
        Column {
            id: routesCol
            anchors { left: head.left; right: head.right; top: head.bottom; topMargin: 6 * M.u }
            spacing: 12 * M.u
            Text { visible: page.busy || !!page.problem; width: parent.width; wrapMode: Text.WordWrap; text: page.busy ? "Finding routes…" : page.problem; color: M.text2; font.family: M.font; font.pixelSize: M.tBody }
            Repeater {
                model: page.trip && page.trip.routes ? page.trip.routes : []
                delegate: Rectangle {
                    id: rc
                    required property var modelData
                    required property int index
                    readonly property bool sel: page.chosen === index
                    readonly property bool cur: page.activeFocus && page.zone === 1 && sel
                    width: routesCol.width; height: rcCol.implicitHeight + 34 * M.u
                    radius: 14 * M.u
                    color: sel ? M.panel2 : M.panel
                    border.color: cur ? M.focus : sel ? "#3f3f46" : M.line; border.width: cur ? M.ring : 1 * M.u
                    Rectangle { visible: rc.sel; x: 0; anchors.verticalCenter: parent.verticalCenter; width: 6 * M.u; height: parent.height - 30 * M.u; radius: 3 * M.u; color: M.route }
                    Column {
                        id: rcCol
                        anchors { left: parent.left; right: parent.right; top: parent.top; leftMargin: 28 * M.u; rightMargin: 24 * M.u; topMargin: 17 * M.u }
                        spacing: 4 * M.u
                        Row {
                            width: parent.width
                            spacing: 16 * M.u
                            Text {
                                text: rc.modelData.duration_text
                                color: rc.modelData.traffic ? M.trafficColor(rc.modelData.traffic) : M.text
                                font.family: M.font; font.pixelSize: 40 * M.u; font.weight: Font.Bold
                            }
                            Text {
                                anchors.baseline: parent.children[0].baseline
                                text: (page.trip.mode === "transit" ? M.clock(rc.modelData.depart) + " – " : "Arrive ") + M.clock(rc.modelData.arrive)
                                color: M.text2; font.family: M.font; font.pixelSize: M.tBody
                            }
                            Text {
                                anchors.baseline: parent.children[0].baseline
                                visible: (rc.modelData.labels || []).indexOf("DEFAULT_ROUTE") >= 0 || (rc.modelData.labels || []).indexOf("Fastest") >= 0 || (rc.index === 0 && page.trip.routes.length > 1)
                                text: "Best"; color: M.accent; font.family: M.font; font.pixelSize: M.tSmall; font.weight: Font.Bold
                            }
                        }
                        Row {                            // transit: the lines to take
                            visible: (rc.modelData.transit || []).length > 0
                            spacing: 8 * M.u
                            Repeater {
                                model: rc.modelData.transit || []
                                delegate: Rectangle {
                                    required property var modelData
                                    height: 36 * M.u; width: lt.implicitWidth + 24 * M.u; radius: 8 * M.u
                                    color: modelData.color || M.route
                                    Text { id: lt; anchors.centerIn: parent; text: parent.modelData.line || parent.modelData.vehicle; color: "white"; font.family: M.font; font.pixelSize: 20 * M.u; font.weight: Font.Bold }
                                }
                            }
                        }
                        Text {
                            width: parent.width
                            text: [rc.modelData.distance_text, rc.modelData.summary ? "via " + rc.modelData.summary : ""].filter(x => !!x).join("  ·  ")
                            color: M.dim; font.family: M.font; font.pixelSize: M.tMeta; elide: Text.ElideRight
                        }
                        Text {
                            visible: !!rc.modelData.delay_text
                            text: "+" + rc.modelData.delay_text + " for traffic"
                            color: M.trafficColor(rc.modelData.traffic); font.family: M.font; font.pixelSize: M.tSmall
                        }
                    }
                }
            }
        }
        Text {
            id: stepsHead
            visible: !!page.route && page.route.steps.length > 0
            anchors { left: head.left; top: routesCol.bottom; topMargin: 26 * M.u }
            text: "Steps"; color: M.text2; font.family: M.font; font.pixelSize: M.tBody; font.weight: Font.DemiBold
        }
        ListView {
            id: steps
            anchors { left: head.left; right: head.right; top: stepsHead.bottom; topMargin: 10 * M.u; bottom: parent.bottom; bottomMargin: 30 * M.u }
            clip: true
            interactive: false
            spacing: 4 * M.u
            model: page.route ? page.route.steps : []
            delegate: Rectangle {
                required property var modelData
                required property int index
                readonly property bool cur: page.activeFocus && page.zone === 2 && page.sidx === index
                width: steps.width; height: Math.max(70 * M.u, stx.implicitHeight + 26 * M.u); radius: 10 * M.u
                color: cur ? M.panel2 : "transparent"
                border.color: cur ? M.focus : "transparent"; border.width: 3 * M.u
                Image { id: sti; x: 14 * M.u; anchors.verticalCenter: parent.verticalCenter; width: 34 * M.u; height: width; sourceSize: M.sz(width, height); source: M.icon(parent.modelData.icon) }
                Text {
                    id: stx
                    anchors { left: sti.right; leftMargin: 18 * M.u; right: sd.left; rightMargin: 12 * M.u; verticalCenter: parent.verticalCenter }
                    text: parent.modelData.text; color: M.text; font.family: M.font; font.pixelSize: 24 * M.u; wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
                }
                Text { id: sd; anchors { right: parent.right; rightMargin: 14 * M.u; verticalCenter: parent.verticalCenter } text: parent.modelData.distance_text || ""; color: M.dim; font.family: M.font; font.pixelSize: M.tSmall }
            }
        }
    }

    // ------------------------------------------------------------------ right: the map
    MapView {
        id: map
        anchors { left: left.right; right: parent.right; top: parent.top; bottom: parent.bottom }
        routes: page.trip && page.trip.routes ? page.trip.routes.map((r, i) => ({points: r.points, chosen: i === page.chosen})) : []
        pins: page.trip && page.trip.to ? [{lat: page.trip.from ? page.trip.from.lat : page.trip.to.lat, lon: page.trip.from ? page.trip.from.lon : page.trip.to.lon, kind: page.trip.from ? "start" : "end"},
                                          {lat: page.trip.to.lat, lon: page.trip.to.lon, kind: "end"}] : []
        onLeave: { map.focus = false; page.forceActiveFocus(); }   // else the page hands focus straight back
        onWidthChanged: if (width > 0) fitSoon.restart()
    }
}
