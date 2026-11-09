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
    property bool dim: false                  // the header grey (the guide open, the focus elsewhere)
    // a hero's row: small posters; Home's "Explore more topics": small topic cards, the current row's too
    readonly property real cardW: row.hero ? 288 * Y.u : row.topics ? 405 * Y.u : grow && current ? Y.bigW : baseW
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
        // its foot 74 above the row: a title without badges or a synopsis sits down by the row
        y: (shelf.hasHead ? 70 * Y.u : 0) + 468 * Y.u - 74 * Y.u - height
        width: shelf.width - shelf.indent - 280 * Y.u
        Text { text: shelf.focused.title || ""; color: Y.text; font.family: Y.font; font.pixelSize: 48 * Y.u; font.weight: Font.Bold; elide: Text.ElideRight; width: parent.width; height: 66 * Y.u; verticalAlignment: Text.AlignVCenter }
        readonly property bool hasLine: !!((shelf.focused.lines || [])[0] || (shelf.focused.badges || []).length)
        readonly property bool hasText: (shelf.focused.lines || []).length > 1
        Item { width: 1; height: 14 * Y.u; visible: parent.hasLine }
        Row {
            visible: parent.hasLine
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
        Item { width: 1; height: 20 * Y.u; visible: parent.hasText }
        Text {
            visible: parent.hasText
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
            // the current row's white; the others' (and all with the guide open) grey
            color: Y.dimmed || shelf.dim ? Y.dim : shelf.current ? Y.text : "#b7b7b7"
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
        height: shelf.row.topics ? Math.round(shelf.cardW * 8 / 15) + 9 * Y.u   // (nothing under a topic's picture)
                                 : Math.round(shelf.cardW * 9 / 16) + (shelf.boxed ? 194 : shelf.row.hero ? 12 : 198) * Y.u
        orientation: ListView.Horizontal
        spacing: Y.gap
        clip: false
        focus: true
        model: itemModel
        cacheBuffer: Math.round(Y.bigW * 3)
        // the focus stays at the left; the row moves under it. Topics: the focus moves to the
        // second card, then stays there (one topic always to its left), as YouTube's TV app has it
        readonly property bool walk: !!shelf.row.topics && !shelf.fixed
        highlightRangeMode: shelf.fixed ? ListView.NoHighlightRange : walk ? ListView.ApplyRange : ListView.StrictlyEnforceRange
        leftMargin: shelf.fixed || walk ? shelf.indent : 0
        preferredHighlightBegin: walk ? shelf.indent + shelf.cardW + Y.gap : shelf.indent
        preferredHighlightEnd: walk ? shelf.indent + 2 * shelf.cardW + Y.gap : shelf.indent + shelf.cardW
        highlightMoveDuration: 180
        highlightFollowsCurrentItem: true
        // where the row comes to rest for the current card: a card that will rest left of the
        // indent is a passed one from the moment the row starts to move
        readonly property real restX: !currentItem || shelf.fixed ? contentX
            : walk ? Math.max(-leftMargin, Math.min(currentItem.x - preferredHighlightBegin, contentWidth - width))
            : currentItem.x - preferredHighlightBegin
        boundsBehavior: Flickable.StopAtBounds
        keyNavigationEnabled: true
        interactive: false
        Keys.onLeftPressed: e => { if (currentIndex === 0) Y.toGuide(); else decrementCurrentIndex(); }
        Keys.onRightPressed: incrementCurrentIndex()
        // OK opens the card; held, or the Menu key, its menu (Play next, Add to queue...)
        Keys.onPressed: e => {
            if (e.key === Qt.Key_Menu) { Y.cardMenu(shelf.row.items[currentIndex], list); e.accepted = true; }
            else if (e.key === Qt.Key_Return || e.key === Qt.Key_Enter) {
                // held, the menu opens whole: what YouTube sends of it separately, asked for now
                if (!e.isAutoRepeat) { hold.restart(); Y.warmMenu(shelf.row.items[currentIndex]); }
                e.accepted = true;
            }
        }
        Keys.onReleased: e => {
            if ((e.key === Qt.Key_Return || e.key === Qt.Key_Enter) && !e.isAutoRepeat && hold.running) {
                hold.stop();
                Y.openedW = shelf.cardW;       // (the player's stand-in picture: this card's, as decoded)
                shelf.open(shelf.row.items[currentIndex]);
                e.accepted = true;
            }
        }
        Timer { id: hold; interval: 650; onTriggered: Y.cardMenu(shelf.row.items[list.currentIndex], list) }
        onCurrentIndexChanged: if (count && currentIndex >= count - 5) shelf.loadMore()
        delegate: VideoCard {
            required property int k
            required property int index
            item: (shelf.row.items || [])[k] || ({})
            on: ListView.isCurrentItem && shelf.activeFocus
            w: shelf.cardW
            boxed: shelf.boxed
            behind: shelf.behind
            captioned: !shelf.row.hero
            wide: !!shelf.row.hero
            metaSize: shelf.metaSize
            // a card scrolled past the row's start: at 10% on the current row, gone on the others,
            // switched at once (YouTube's TV app: .XVxlBe { opacity: 0.1 }, .tmaMPd { opacity: 0 })
            readonly property bool passed: !shelf.fixed && x - list.restX < shelf.indent - 1
            opacity: passed ? (shelf.current ? 0.1 : 0) : 1
        }
    }

    // the cards the row shows, by their place in row.items: more cards are added to it, never the
    // row made again (its pictures blinked and it slid back to the focus, as more came)
    ListModel { id: itemModel }
    function remodel() {
        itemModel.clear();
        const n = (row.items || []).length;
        if (n) itemModel.append(Array.from({length: n}, (_, k) => ({k: k})));
    }
    onRowChanged: remodel()
    Component.onCompleted: remodel()

    // more cards, from the shelf's continuation (kept where the focus is)
    property bool loading: false
    function loadMore() {
        if (loading || !row.more) return;
        loading = true;
        const token = row.more;
        Y.call("more", {token: token}, r => {
            if (!shelf) return;                // (gone meanwhile: its row was rebuilt or left)
            loading = false;
            if (row.more !== token) return;
            // added at the end, in place (the row object is the feed's too: a playlist's order sees them)
            if (!row.items) row.items = [];
            const base = row.items.length, add = r.items || [];
            for (const x of add) row.items.push(x);
            row.more = r.more || "";
            if (add.length) itemModel.append(add.map((_, j) => ({k: base + j})));
        }, () => { if (shelf) shelf.loading = false; });
    }
}
