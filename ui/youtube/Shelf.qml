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
    property real metaSize: Y.tMeta
    readonly property real cardW: row.hero ? 288 * Y.u : grow && current ? Y.bigW : baseW
    readonly property bool hasHead: !row.hero && !!(row.title || row.pill)    // a hero's title is the focused card's
    readonly property real headH: (row.pill ? 96 * Y.u : hasHead ? (row.subtitle ? 106 : 70) * Y.u : 0) + (row.hero ? 468 * Y.u : 0)
    readonly property var focused: (row.items || [])[list.currentIndex] || ({})
    signal open(var item)
    signal search(string query)
    onActiveFocusChanged: if (activeFocus && !list.activeFocus) list.forceActiveFocus()
    width: parent ? parent.width : 0
    height: headH + list.height
    Behavior on height { enabled: shelf.grow; NumberAnimation { duration: 160 } }

    // ------------------------------------------------------------------ a hero: the focused title, large
    // (Movies & TV): its name, a line of what it is with badges (green: pay to watch), two lines
    // of its description, then a row of small wide posters
    Column {
        visible: !!shelf.row.hero
        x: shelf.indent
        y: (shelf.hasHead ? 70 * Y.u : 0) + 180 * Y.u
        width: shelf.width - shelf.indent - 280 * Y.u
        Text { text: shelf.focused.title || ""; color: Y.text; font.family: Y.font; font.pixelSize: 56 * Y.u; font.weight: Font.Bold; elide: Text.ElideRight; width: parent.width; height: 66 * Y.u; verticalAlignment: Text.AlignVCenter }
        Item { width: 1; height: 14 * Y.u }
        Row {
            height: 34 * Y.u
            spacing: 8 * Y.u
            Text { text: (shelf.focused.lines || [])[0] || ""; color: Y.dim; font.family: Y.font; font.pixelSize: 24 * Y.u; height: parent.height; verticalAlignment: Text.AlignVCenter }
            Repeater {
                model: shelf.focused.badges || []
                Rectangle {
                    required property string modelData
                    readonly property bool pay: (shelf.focused.pay || []).indexOf(modelData) >= 0 || /buy|rent|pay to|try now|\$/i.test(modelData)
                    width: hb.implicitWidth + 12 * Y.u; height: 34 * Y.u; radius: 4 * Y.u
                    color: pay ? "#1d3a22" : Y.raised
                    Text { id: hb; anchors.centerIn: parent; text: parent.modelData; color: parent.pay ? "#3ea84f" : Y.soft; font.family: Y.font; font.pixelSize: 24 * Y.u; font.weight: Font.Medium }
                }
            }
        }
        Item { width: 1; height: 20 * Y.u }
        Text {
            width: Math.min(parent.width, 830 * Y.u)
            text: (shelf.focused.lines || []).slice(1).join(" • ")
            color: Y.text; font.family: Y.font; font.pixelSize: 28 * Y.u
            lineHeightMode: Text.FixedHeight; lineHeight: 40 * Y.u
            wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
        }
    }

    // ------------------------------------------------------------------ header
    Column {
        x: shelf.indent
        visible: !shelf.row.pill && shelf.hasHead
        Text {
            text: shelf.row.title || ""
            color: Y.dimmed ? Y.dim : Y.text
            font.family: Y.font; font.pixelSize: Y.tShelf; font.weight: Font.Medium
            height: 36 * Y.u
        }
        Text {                                 // a second line, 36 under the title's middle
            visible: !!shelf.row.subtitle
            text: shelf.row.subtitle || ""
            color: Y.dimmed ? Y.dim : Y.soft
            font.family: Y.font; font.pixelSize: Y.tSmall
            topPadding: 5 * Y.u
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
        height: Math.round(shelf.cardW * 9 / 16) + (shelf.boxed ? 194 : shelf.row.hero ? 12 : 201) * Y.u
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
        // OK opens the card; held, or the Menu key, its menu (Play next, Add to queue...)
        Keys.onPressed: e => {
            if (e.key === Qt.Key_Menu) { Y.cardMenu(shelf.row.items[currentIndex], list); e.accepted = true; }
            else if (e.key === Qt.Key_Return || e.key === Qt.Key_Enter) { if (!e.isAutoRepeat) hold.restart(); e.accepted = true; }
        }
        Keys.onReleased: e => {
            if ((e.key === Qt.Key_Return || e.key === Qt.Key_Enter) && !e.isAutoRepeat && hold.running) {
                hold.stop();
                shelf.open(shelf.row.items[currentIndex]);
                e.accepted = true;
            }
        }
        Timer { id: hold; interval: 650; onTriggered: Y.cardMenu(shelf.row.items[list.currentIndex], list) }
        onCurrentIndexChanged: if (count && currentIndex >= count - 5) shelf.loadMore()
        delegate: VideoCard {
            required property var modelData
            required property int index
            item: modelData
            on: ListView.isCurrentItem && shelf.activeFocus
            w: shelf.cardW
            boxed: shelf.boxed
            behind: shelf.behind
            captioned: !shelf.row.hero
            wide: !!shelf.row.hero
            metaSize: shelf.metaSize
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
