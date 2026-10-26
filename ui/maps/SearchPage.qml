// Search: what to look for (the keyboard pop-up or a phone), then places near Home. OK on a
// result opens its actions, or, when choosing a place (Set Home, Add a place), picks it.
import QtQuick

FocusScope {
    id: page
    property string query: ""
    property var results: []
    property bool busy: false
    property string problem: ""
    property string picking: ""              // "" | home | work | place | to: what OK on a result does
    property string pickTitle: ""
    property int idx: 0                      // 0 the search box, 1.. the results
    signal ask(string current)
    signal activate(var place)
    signal picked(var place)
    signal toRail()

    function run(q) {
        query = q.trim();
        if (!query) return;
        busy = true; problem = ""; results = [];
        M.call("search", {query: query}, r => {
            page.busy = false; page.results = r.results;
            page.problem = r.results.length ? "" : "Nothing found for “" + page.query + "”.";
            if (r.results.length) page.idx = 1;
        }, e => { page.busy = false; page.problem = e; });
    }
    function startPicking(kind, title) { picking = kind; pickTitle = title; idx = 0; results = []; query = ""; problem = ""; }

    Keys.onUpPressed: idx = Math.max(0, idx - 1)
    Keys.onDownPressed: idx = Math.min(results.length, idx + 1)
    Keys.onLeftPressed: toRail()
    Keys.onReturnPressed: press()
    Keys.onEnterPressed: press()
    function press() {
        if (idx === 0) ask(query);
        else if (picking) picked(results[idx - 1]);
        else activate(results[idx - 1]);
    }
    onIdxChanged: if (idx > 0) list.positionViewAtIndex(idx - 1, ListView.Contain)

    Column {
        id: head
        anchors { left: parent.left; right: parent.right; top: parent.top; leftMargin: 60 * M.u; rightMargin: M.edge; topMargin: 56 * M.u }
        spacing: 26 * M.u
        Row {
            spacing: 20 * M.u
            Text { text: page.picking ? page.pickTitle : "Search"; color: M.text; font.family: M.font; font.pixelSize: M.tTitle; font.weight: Font.Bold }
            Text {
                anchors.baseline: parent.children[0].baseline
                text: page.picking ? "Search, then pick it" : (M.status.google ? "Places from Google" : "Places from OpenStreetMap")
                color: M.dim; font.family: M.font; font.pixelSize: M.tBody
            }
        }
        Rectangle {                                // the search box
            width: parent.width; height: 92 * M.u; radius: 46 * M.u
            color: page.activeFocus && page.idx === 0 ? M.panel2 : M.panel
            border.color: page.activeFocus && page.idx === 0 ? M.focus : M.line
            border.width: page.activeFocus && page.idx === 0 ? M.ring : 1 * M.u
            Image { id: sic; x: 34 * M.u; anchors.verticalCenter: parent.verticalCenter; width: 36 * M.u; height: width; sourceSize: Qt.size(width, height); source: M.icon("search") }
            Text {
                anchors { left: sic.right; leftMargin: 22 * M.u; right: parent.right; rightMargin: 34 * M.u; verticalCenter: parent.verticalCenter }
                text: page.query || "A place, an address or a kind of place (coffee, gas, pharmacy)"
                color: page.query ? M.text : M.faint
                font.family: M.font; font.pixelSize: 30 * M.u; elide: Text.ElideRight
            }
        }
        Text {
            visible: page.busy || !!page.problem
            text: page.busy ? "Searching…" : page.problem
            color: M.dim; font.family: M.font; font.pixelSize: M.tBody
        }
    }
    ListView {
        id: list
        anchors { left: head.left; right: head.right; top: head.bottom; topMargin: 24 * M.u; bottom: parent.bottom; bottomMargin: 30 * M.u }
        clip: true
        spacing: 12 * M.u
        model: page.results
        interactive: false
        highlightMoveDuration: 150
        delegate: Rectangle {
            required property var modelData
            required property int index
            readonly property bool cur: page.activeFocus && page.idx === index + 1
            width: list.width; height: 108 * M.u; radius: 14 * M.u
            color: cur ? M.panel2 : M.panel
            border.color: cur ? M.focus : M.line; border.width: cur ? M.ring : 1 * M.u
            Rectangle {
                id: rb
                x: 24 * M.u; anchors.verticalCenter: parent.verticalCenter
                width: 60 * M.u; height: width; radius: width / 2; color: parent.modelData.saved ? "#14352b" : M.panel2
                Image { anchors.centerIn: parent; width: 32 * M.u; height: width; sourceSize: Qt.size(width, height); source: M.icon(parent.parent.modelData.saved ? (parent.parent.modelData.kind === "home" ? "home" : parent.parent.modelData.kind === "work" ? "work" : "star") : "pin") }
            }
            Column {
                anchors { left: rb.right; leftMargin: 22 * M.u; right: dist.left; rightMargin: 20 * M.u; verticalCenter: parent.verticalCenter }
                spacing: 4 * M.u
                Text { width: parent.width; text: parent.parent.modelData.name; color: M.text; font.family: M.font; font.pixelSize: 29 * M.u; font.weight: Font.DemiBold; elide: Text.ElideRight }
                Text {
                    width: parent.width
                    text: [parent.parent.modelData.type, parent.parent.modelData.address].filter(x => !!x).join("  ·  ")
                    color: M.dim; font.family: M.font; font.pixelSize: M.tMeta; elide: Text.ElideRight
                }
            }
            Text {
                id: dist
                anchors { right: parent.right; rightMargin: 30 * M.u; verticalCenter: parent.verticalCenter }
                text: parent.modelData.distance_text || ""
                color: M.text2; font.family: M.font; font.pixelSize: M.tBody
            }
        }
    }
}
