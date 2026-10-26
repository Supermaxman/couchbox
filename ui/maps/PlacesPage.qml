// Places: Home, Work and the other saved places, each with the drive time from Home right now
// (refreshed every few minutes while it's on screen), an Add card, and the recent destinations.
// Arrows move, OK opens a place's actions, Left from the first column goes to the sidebar.
import QtQuick

FocusScope {
    id: page
    property var etas: ({})                  // place id -> {duration_text, arrive, traffic, ...}
    property int etaAt: 0
    property int zone: 0                     // 0 the places, 1 recent
    property int idx: 0
    property int ridx: 0
    readonly property int cols: 3
    readonly property var cards: M.places.concat([{add: true}])
    readonly property var home: M.places.find(p => p.kind === "home") || null
    signal activate(var place, bool saved)
    signal add()
    signal toRail()

    function refresh() {
        M.call("places", {}, r => M.setPlaces(r));
        M.call("etas", {}, r => {
            const e = {};
            for (const x of r.etas) e[x.id] = x;
            page.etas = e; page.etaAt = r.at;
        }, err => {});
    }
    Timer { interval: 4 * 60 * 1000; repeat: true; running: page.visible; onTriggered: page.refresh() }
    property int tick: 0
    Timer { interval: 30000; repeat: true; running: page.visible; onTriggered: page.tick++ }   // "updated N min ago"
    onVisibleChanged: if (visible) refresh()

    Keys.onLeftPressed: { if (zone === 0) { if (idx % cols === 0) toRail(); else idx--; } else { if (ridx === 0) toRail(); else ridx--; } }
    Keys.onRightPressed: { if (zone === 0) idx = Math.min(cards.length - 1, idx + 1); else ridx = Math.min(M.recent.length - 1, ridx + 1); }
    Keys.onUpPressed: { if (zone === 1) zone = 0; else if (idx >= cols) idx -= cols; }
    Keys.onDownPressed: {
        if (zone === 0) {
            if (idx + cols < cards.length) idx += cols;
            else if (Math.floor(idx / cols) < Math.floor((cards.length - 1) / cols)) idx = cards.length - 1;
            else if (M.recent.length) { zone = 1; ridx = Math.min(ridx, M.recent.length - 1); }
        }
    }
    Keys.onReturnPressed: press()
    Keys.onEnterPressed: press()
    function press() {
        if (zone === 0) { const c = cards[idx]; if (c.add) add(); else activate(c, true); }
        else if (M.recent[ridx]) activate(M.recent[ridx], false);
    }
    onIdxChanged: flick.show(cardRep.itemAt(idx))
    onZoneChanged: if (zone === 1) flick.show(recentRow); else flick.show(cardRep.itemAt(idx))

    Flickable {
        id: flick
        readonly property real pad: 18 * M.u        // room for a focused card to grow at the sides
        anchors { fill: parent; leftMargin: 60 * M.u - pad; rightMargin: M.edge - pad }
        contentHeight: body.implicitHeight + 80 * M.u
        clip: true
        interactive: false
        function show(item) {
            if (!item) return;
            const p = item.mapToItem(body, 0, 0);
            if (p.y - 40 * M.u < contentY) contentY = Math.max(0, p.y - 140 * M.u);
            else if (p.y + item.height + 60 * M.u > contentY + height) contentY = Math.min(contentHeight - height, p.y + item.height + 60 * M.u - height);
        }
        Behavior on contentY { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

        Column {
            id: body
            x: flick.pad
            width: flick.width - 2 * flick.pad
            topPadding: 56 * M.u
            spacing: 22 * M.u
            Row {
                spacing: 20 * M.u
                Text { text: "Places"; color: M.text; font.family: M.font; font.pixelSize: M.tTitle; font.weight: Font.Bold }
                Text {
                    anchors.baseline: parent.children[0].baseline
                    text: page.tick >= 0 && page.home ? "Drive times from Home, now" + (page.etaAt ? " · updated " + Math.max(0, Math.round((Date.now() / 1000 - page.etaAt) / 60)) + " min ago" : "") : "Set Home to see drive times"
                    color: M.dim; font.family: M.font; font.pixelSize: M.tBody
                }
            }
            Grid {
                id: grid
                columns: page.cols
                spacing: M.gap
                Repeater {
                    id: cardRep
                    model: page.cards
                    delegate: Rectangle {
                        id: card
                        required property var modelData
                        required property int index
                        readonly property bool cur: page.activeFocus && page.zone === 0 && page.idx === index
                        readonly property var eta: modelData.add ? null : page.etas[modelData.id]
                        width: (body.width - (page.cols - 1) * M.gap) / page.cols
                        height: 250 * M.u
                        radius: M.radius
                        color: modelData.add ? "transparent" : M.panel
                        border.color: cur ? M.focus : M.line
                        border.width: cur ? M.ring : (modelData.add ? 2 * M.u : 1 * M.u)
                        scale: cur ? M.lift : 1
                        z: cur ? 2 : 1
                        Behavior on scale { NumberAnimation { duration: 120 } }
                        Column {                             // Add a place
                            visible: card.modelData.add === true
                            anchors.centerIn: parent
                            spacing: 14 * M.u
                            Image { anchors.horizontalCenter: parent.horizontalCenter; width: 52 * M.u; height: width; sourceSize: Qt.size(width, height); source: M.icon("plus"); opacity: 0.8 }
                            Text { anchors.horizontalCenter: parent.horizontalCenter; text: "Add a place"; color: M.text2; font.family: M.font; font.pixelSize: M.tBody }
                        }
                        Item {
                            visible: !card.modelData.add
                            anchors { fill: parent; margins: 26 * M.u }
                            Rectangle {
                                id: badge
                                width: 64 * M.u; height: width; radius: width / 2
                                color: card.modelData.kind === "home" ? "#1e3a5f" : card.modelData.kind === "work" ? "#3b2a4a" : "#14352b"
                                Image { anchors.centerIn: parent; width: 34 * M.u; height: width; sourceSize: Qt.size(width, height); source: M.icon(card.modelData.kind === "home" ? "home" : card.modelData.kind === "work" ? "work" : "star") }
                            }
                            Column {
                                anchors { left: badge.right; leftMargin: 20 * M.u; right: parent.right; verticalCenter: badge.verticalCenter }
                                spacing: 2 * M.u
                                Text { width: parent.width; text: card.modelData.name || ""; color: M.text; font.family: M.font; font.pixelSize: M.tHead; font.weight: Font.DemiBold; elide: Text.ElideRight }
                                Text {
                                    width: parent.width
                                    text: card.modelData.approx ? "Set your address" : (card.modelData.address || "")
                                    color: card.modelData.approx ? M.moderate : M.dim
                                    font.family: M.font; font.pixelSize: M.tMeta; elide: Text.ElideRight
                                }
                            }
                            Column {
                                anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                                spacing: 4 * M.u
                                Row {
                                    spacing: 14 * M.u
                                    Image {
                                        visible: card.modelData.kind !== "home"
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: 34 * M.u; height: width; sourceSize: Qt.size(width, height); source: M.icon("car"); opacity: 0.8
                                    }
                                    Text {
                                        text: card.modelData.kind === "home" ? (card.modelData.approx ? "Drive times start from your town" : "Drive times start here")
                                              : card.eta ? (card.eta.duration_text || "No route") : "…"
                                        color: card.modelData.kind === "home" ? M.dim : card.eta && card.eta.traffic ? M.trafficColor(card.eta.traffic) : M.text
                                        font.family: M.font; font.pixelSize: card.modelData.kind === "home" ? M.tBody : 44 * M.u; font.weight: Font.Bold
                                    }
                                }
                                Text {
                                    width: parent.width
                                    visible: card.modelData.kind !== "home"
                                    text: card.eta && card.eta.duration ? "Arrive " + M.clock(card.eta.arrive) + "  ·  " + card.eta.distance_text + (card.eta.delay_text ? "  ·  +" + card.eta.delay_text + " traffic" : "")
                                          : card.eta && card.eta.error ? card.eta.error : ""
                                    color: M.dim; font.family: M.font; font.pixelSize: M.tMeta; elide: Text.ElideRight
                                }
                            }
                        }
                    }
                }
            }
            Item { width: 1; height: 10 * M.u; visible: M.recent.length > 0 }
            Text { visible: M.recent.length > 0; text: "Recent"; color: M.text2; font.family: M.font; font.pixelSize: M.tHead; font.weight: Font.DemiBold }
            Row {
                id: recentRow
                visible: M.recent.length > 0
                spacing: 18 * M.u
                Repeater {
                    model: M.recent.slice(0, 4)
                    delegate: Rectangle {
                        required property var modelData
                        required property int index
                        readonly property bool cur: page.activeFocus && page.zone === 1 && page.ridx === index
                        width: (body.width - 3 * 18 * M.u) / 4; height: 116 * M.u
                        radius: 12 * M.u
                        color: M.panel
                        border.color: cur ? M.focus : M.line; border.width: cur ? M.ring : 1 * M.u
                        scale: cur ? M.lift : 1
                        Image { id: rpin; x: 20 * M.u; anchors.verticalCenter: parent.verticalCenter; width: 30 * M.u; height: width; sourceSize: Qt.size(width, height); source: M.icon("recent"); opacity: 0.75 }
                        Column {
                            anchors { left: rpin.right; leftMargin: 16 * M.u; right: parent.right; rightMargin: 18 * M.u; verticalCenter: parent.verticalCenter }
                            spacing: 2 * M.u
                            Text { width: parent.width; text: parent.parent.modelData.name; color: M.text; font.family: M.font; font.pixelSize: M.tBody; font.weight: Font.DemiBold; elide: Text.ElideRight }
                            Text { width: parent.width; text: parent.parent.modelData.address || ""; color: M.dim; font.family: M.font; font.pixelSize: M.tSmall; elide: Text.ElideRight }
                        }
                    }
                }
            }
        }
    }
}
