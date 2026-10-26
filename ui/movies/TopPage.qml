// The best rated movies (or shows), numbered: TMDB's score among titles with plenty of votes.
// Arrows move, Left at a row's start goes to the sidebar, OK opens.
import QtQuick

FocusScope {
    id: page
    property string kind: "movie"
    property var items: []
    property bool loading: false
    property string problem: ""
    property string loadedKind: ""
    signal toRail()

    function load() {
        if (loadedKind === kind && items.length) return;
        loading = true; problem = ""; items = [];
        const k = kind;
        M.call("top", {kind: k}, r => { if (k !== page.kind) return; items = r.items; loadedKind = k; loading = false; grid.currentIndex = 0; },
               e => { loading = false; problem = e; });
    }
    onKindChanged: load()
    onActiveFocusChanged: if (activeFocus) grid.forceActiveFocus()

    Column {
        id: head
        x: 60 * M.u; y: 56 * M.u
        spacing: 8 * M.u
        Text { text: page.kind === "tv" ? "Top rated shows" : "Top rated movies"; color: M.text; font.family: M.font; font.pixelSize: M.tTitle; font.weight: Font.Bold }
        Text { text: "By TMDB score, among titles with lots of votes"; color: M.dim; font.family: M.font; font.pixelSize: M.tMeta }
    }
    GridView {
        id: grid
        readonly property real pad: 22 * M.u        // room for a focused poster to grow
        anchors { left: parent.left; right: parent.right; top: head.bottom; bottom: parent.bottom; leftMargin: 60 * M.u - pad; topMargin: 36 * M.u - pad }
        leftMargin: pad; topMargin: pad
        readonly property int cols: Math.max(1, Math.floor((width - pad - M.edge) / cellWidth))
        cellWidth: M.posterW + M.gap + 4 * M.u
        cellHeight: M.posterH + 130 * M.u
        clip: true
        focus: true
        model: page.items
        cacheBuffer: 1600
        highlightMoveDuration: 150
        preferredHighlightBegin: 20 * M.u
        preferredHighlightEnd: height - cellHeight
        highlightRangeMode: GridView.ApplyRange
        keyNavigationEnabled: true
        Keys.onLeftPressed: e => { if (currentIndex % cols === 0) { page.toRail(); e.accepted = true; } else e.accepted = false; }
        Keys.onReturnPressed: M.open(page.items[currentIndex])
        Keys.onEnterPressed: M.open(page.items[currentIndex])
        delegate: Item {
            required property var modelData
            required property int index
            readonly property bool cur: GridView.isCurrentItem
            width: grid.cellWidth; height: grid.cellHeight
            Poster { y: 8 * M.u; item: parent.modelData; rank: parent.modelData.rank || 0; on: parent.cur && grid.activeFocus }
        }
    }
    Text {
        anchors.centerIn: parent
        visible: page.loading || !!page.problem
        text: page.problem || "Loading…"
        color: page.problem ? M.text2 : M.faint; font.family: M.font; font.pixelSize: M.tHead
    }
}
