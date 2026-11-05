// A shelf: its title (or a pill: a channel's picture and name, or a search), then a row of cards
// that scrolls under a focus that stays at the left, as YouTube's TV app does. On a growing
// feed (Home, the guide's tabs) the current shelf's cards are larger. Left at the first card goes
// to the guide; OK opens the card; near the end, more cards are fetched (the shelf's "more").
import QtQuick

FocusScope {
    id: shelf
    property var row: ({})                    // {title, subtitle, items, more, pill?}
    property bool current: false              // the feed's current row
    property bool grow: false                 // the current row's cards are larger
    property bool boxed: false
    property color behind: Y.bg
    property real indent: Y.left              // where the header and the focused card sit
    property alias index: list.currentIndex
    property alias count: list.count
    property real baseW: Y.cardW
    property bool fixed: false                // a row that doesn't scroll (the player's rows of three)
    readonly property real cardW: grow && current ? Y.bigW : baseW
    readonly property bool hasHead: !!(row.title || row.pill)
    readonly property real headH: row.pill ? 96 * Y.u : hasHead ? (row.subtitle ? 100 : 70) * Y.u : 0
    signal open(var item)
    signal search(string query)
    width: parent ? parent.width : 0
    height: headH + list.height
    Behavior on height { enabled: shelf.grow; NumberAnimation { duration: 160 } }

    // ------------------------------------------------------------------ header
    Column {
        x: shelf.indent
        visible: !shelf.row.pill && shelf.hasHead
        spacing: 4 * Y.u
        Text {
            text: shelf.row.title || ""
            color: Y.text
            font.family: Y.font; font.pixelSize: Y.tShelf; font.weight: Font.Medium
        }
        Text {
            visible: !!shelf.row.subtitle
            text: shelf.row.subtitle || ""
            color: Y.text
            font.family: Y.font; font.pixelSize: Y.tSmall
        }
    }
    Rectangle {                               // a cluster's pill: the channel (or a search) it's from
        x: shelf.indent
        visible: !!shelf.row.pill
        height: 72 * Y.u
        width: pillRow.implicitWidth + 44 * Y.u
        radius: height / 2
        color: Y.raised
        Row {
            id: pillRow
            anchors { left: parent.left; leftMargin: shelf.row.pill && shelf.row.pill.avatar ? 8 * Y.u : 26 * Y.u; verticalCenter: parent.verticalCenter }
            spacing: 14 * Y.u
            RoundImage {
                visible: !!(shelf.row.pill && shelf.row.pill.avatar)
                width: 56 * Y.u; height: width
                anchors.verticalCenter: parent.verticalCenter
                source: shelf.row.pill ? shelf.row.pill.avatar || "" : ""
                fallback: shelf.row.pill ? shelf.row.pill.title : ""
            }
            Icon {
                visible: !!(shelf.row.pill && !shelf.row.pill.avatar)
                name: shelf.row.pill && shelf.row.pill.icon === "search" ? "search" : "history"
                size: 36 * Y.u
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: shelf.row.pill ? shelf.row.pill.title : ""
                color: Y.text
                font.family: Y.font; font.pixelSize: 28 * Y.u; font.weight: Font.Medium
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }

    // ------------------------------------------------------------------ cards
    ListView {
        id: list
        y: shelf.headH
        width: parent.width
        height: Math.round(shelf.cardW * 9 / 16) + (shelf.boxed ? 194 : 210) * Y.u
        orientation: ListView.Horizontal
        spacing: Y.gap
        clip: false
        focus: true
        model: shelf.row.items || []
        cacheBuffer: Math.round(Y.bigW * 3)
        // the focus stays at the left; the row moves under it
        highlightRangeMode: shelf.fixed ? ListView.NoHighlightRange : ListView.StrictlyEnforceRange
        leftMargin: shelf.fixed ? shelf.indent : 0
        preferredHighlightBegin: shelf.indent
        preferredHighlightEnd: shelf.indent + shelf.cardW
        highlightMoveDuration: 180
        highlightFollowsCurrentItem: true
        boundsBehavior: Flickable.StopAtBounds
        keyNavigationEnabled: true
        interactive: false
        Keys.onLeftPressed: e => { if (currentIndex === 0) Y.toGuide(); else decrementCurrentIndex(); }
        Keys.onRightPressed: incrementCurrentIndex()
        Keys.onReturnPressed: shelf.open(shelf.row.items[currentIndex])
        Keys.onEnterPressed: shelf.open(shelf.row.items[currentIndex])
        onCurrentIndexChanged: if (count && currentIndex >= count - 5) shelf.loadMore()
        delegate: VideoCard {
            required property var modelData
            required property int index
            item: modelData
            on: ListView.isCurrentItem && shelf.activeFocus
            w: shelf.cardW
            boxed: shelf.boxed
            behind: shelf.behind
        }
    }

    // more cards, from the shelf's continuation (kept where the focus is)
    property bool loading: false
    function loadMore() {
        if (loading || !row.more) return;
        loading = true;
        const token = row.more;
        Y.call("more", {token: token}, r => {
            loading = false;
            if (row.more !== token) return;
            const i = list.currentIndex;
            row = Object.assign({}, row, {items: (row.items || []).concat(r.items || []), more: r.more || ""});
            list.currentIndex = i;
            list.positionViewAtIndex(i, ListView.Beginning);
        }, () => loading = false);
    }
}
