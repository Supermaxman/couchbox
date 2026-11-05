// A page's rows, top to bottom: shelves, a row of chips (searches) or YouTube's "sign in" note.
// The current row moves up to the top, as YouTube's TV app does; Up from the first row leaves
// the feed (atTop: the search pill above), near the end more shelves are fetched (page "more").
import QtQuick

FocusScope {
    id: feed
    property var rows: []                    // [{kind: "shelf" | "chips" | "nudge", ...}]
    property string more: ""                 // the page's continuation: more shelves
    property bool grow: false                // the current shelf's cards grow (Home, the tabs)
    property bool boxed: false               // a channel page's boxed cards
    property color behind: Y.bg
    property real indent: Y.left             // where rows start (the feed itself spans the page)
    property alias index: list.currentIndex
    property alias count: list.count
    property real bottomRoom: 0
    property real cardW: Y.cardW
    property bool fixed: false
    property int perRow: 3                   // a grid (History, Watch later) in rows of this many
    property bool gridScroll: false          // its rows scroll under the focus like shelves (Subscriptions)
    property bool gridMore: false            // "more" continues a grid (items), not the page (shelves)
    property real topRoom: 12 * Y.u              // room above the current row (its focus ring)
    signal atTop()
    signal open(var item)

    function setPage(page, extra) {
        const out = [];
        if (page.nudge) out.push({kind: "nudge", title: page.nudge.title, subtitle: page.nudge.subtitle});
        for (const s of page.shelves || []) {
            if (!s.grid) { out.push(Object.assign({kind: "shelf"}, s)); continue; }
            for (let i = 0; i < s.items.length; i += perRow)         // a grid: rows that don't scroll
                out.push({kind: "shelf", title: i ? "" : s.title, subtitle: "", items: s.items.slice(i, i + perRow), more: "", fixedRow: !gridScroll});
        }
        for (const e of extra || []) out.splice(e.at, 0, e.row);
        rows = out;
        more = page.more || "";
        // a long grid (Watch later, History) goes on from its own continuation
        const grid = (page.shelves || []).find(s => s.grid && s.more);
        gridMore = !more && !!grid;
        if (gridMore) more = grid.more;
        list.currentIndex = 0;
        list.positionViewAtBeginning();
    }

    ListView {
        id: list
        anchors.fill: parent
        focus: true
        clip: true
        model: feed.rows
        spacing: 50 * Y.u
        cacheBuffer: Math.round(1600 * Y.u)
        highlightRangeMode: ListView.StrictlyEnforceRange
        preferredHighlightBegin: feed.topRoom
        preferredHighlightEnd: feed.topRoom + 200 * Y.u
        highlightMoveDuration: 220
        highlightMoveVelocity: -1
        boundsBehavior: Flickable.StopAtBounds
        interactive: false
        footer: Item { width: 1; height: feed.bottomRoom }
        Keys.onUpPressed: e => { if (currentIndex === 0) feed.atTop(); else decrementCurrentIndex(); }
        Keys.onDownPressed: incrementCurrentIndex()
        onCurrentIndexChanged: if (count && currentIndex >= count - 3) feed.loadMore()
        delegate: Loader {
            id: cell
            required property var modelData
            required property int index
            readonly property bool current: ListView.isCurrentItem
            width: list.width
            focus: current
            // rows above the current one are gone (as on YouTube), and their cards' corners
            // (Shapes) mustn't draw past the list's clip
            visible: index >= list.currentIndex
            sourceComponent: ({chips: chipsC, nudge: nudgeC, tiles: tilesC})[modelData.kind] || shelfC
            Component {
                id: shelfC
                Shelf {
                    row: cell.modelData
                    current: cell.current
                    grow: feed.grow
                    boxed: feed.boxed
                    behind: feed.behind
                    indent: feed.indent
                    baseW: feed.cardW
                    fixed: feed.fixed || !!cell.modelData.fixedRow
                    focus: true
                    onOpen: it => feed.open(it)
                }
            }
            Component {
                id: chipsC
                Chips { chips: cell.modelData.chips || []; indent: feed.indent; focus: true }
            }
            Component {
                id: tilesC
                Tiles { tiles: cell.modelData.tiles || []; indent: feed.indent; focus: true }
            }
            Component {
                id: nudgeC
                Nudge { title: cell.modelData.title; subtitle: cell.modelData.subtitle; indent: feed.indent; focus: true }
            }
        }
    }

    property bool loading: false
    function loadMore() {
        if (loading || !more) return;
        loading = true;
        const token = more;
        Y.call("more", {token: token}, r => {
            loading = false;
            if (more !== token) return;
            const i = list.currentIndex;
            if (gridMore) {
                const add = [], items = r.items || [];
                for (let k = 0; k < items.length; k += perRow)
                    add.push({kind: "shelf", title: "", subtitle: "", items: items.slice(k, k + perRow), more: "", fixedRow: !gridScroll});
                rows = rows.concat(add);
            } else rows = rows.concat((r.shelves || []).map(s => Object.assign({kind: "shelf"}, s)));
            more = r.more || "";
            list.currentIndex = i;
            list.positionViewAtIndex(i, ListView.Beginning);
        }, () => loading = false);
    }
}
