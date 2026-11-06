// Subscriptions, as YouTube's TV app has it: the channels down the left (All first, then the most
// relevant, then A-Z; a blue dot for new videos) and, beside them, the feed of the one picked.
// Right goes into the feed; Left from its first card comes back to the channels.
import QtQuick

FocusScope {
    id: page
    property var channels: []
    property var allPage: null
    property int picked: 0
    property bool loaded: false
    property string problem: ""
    readonly property string label: "Subscriptions"
    readonly property real feedX: 621 * Y.u
    function focusDetail() { return {loaded: loaded, channels: channels.length, picked: picked, rows: feed.count, inFeed: feedFocused, problem: problem}; }

    function load() {
        problem = "";
        Y.call("subscriptions", {}, r => {
            loaded = true;
            channels = r.channels && r.channels.length ? r.channels : [{title: "All", id: "", thumb: "", section: "", new: false}];
            allPage = r.page;
            picked = 0;
            list.currentIndex = 0;
            feed.setPage(r.page);
            if (page.activeFocus && !feed.activeFocus) list.forceActiveFocus();
        }, e => { loaded = true; problem = e; });
    }
    onActiveFocusChanged: if (activeFocus && !list.activeFocus && !feed.activeFocus) list.forceActiveFocus()
    Timer {                                    // moving down the channels: show the one the focus rests on
        id: pick
        interval: 350
        onTriggered: page.show(list.currentIndex)
    }
    function show(i) {
        if (i === picked && feed.count) return;
        picked = i;
        const c = channels[i];
        if (!c) return;
        if (!c.id || c.all) { if (allPage) feed.setPage(allPage); return; }
        Y.call("channel", {id: c.id, params: c.params || ""}, r => { if (page.picked === i) feed.setPage(r); }, e => Y.toast(e));
    }
    // Left off the feed's first card comes back to the channels (Main asks: toGuide() is shared)
    readonly property bool feedFocused: feed.activeFocus
    function toChannels() { list.forceActiveFocus(); }

    Feed {
        id: feed
        dimIdle: true                          // its headers grey while the channels have the focus
        x: 0; y: 175 * Y.u
        width: parent.width
        height: parent.height - y
        indent: page.feedX
        perRow: 3
        gridScroll: true
        rowGap: 96 * Y.u                       // YouTube's grid here: rows 591 px apart
        onAtTop: {}
        onOpen: it => Y.open(it)
    }
    Rectangle {                                // the feed passes under the channels
        x: 0; y: 0; width: 600 * Y.u; height: parent.height
        color: Y.bg
    }
    Text {                                     // the page's name, level with the guide's picture
        x: 172 * Y.u; y: 68 * Y.u
        height: 72 * Y.u
        verticalAlignment: Text.AlignVCenter
        text: "Subscriptions"
        color: Y.text; font.family: Y.titleFont; font.pixelSize: 44 * Y.titleScale * Y.u; font.weight: Font.Bold
    }
    ListView {
        id: list
        x: 147 * Y.u; y: 192 * Y.u
        width: 420 * Y.u
        height: parent.height - y
        clip: true
        focus: true
        model: page.channels
        spacing: 0
        highlightRangeMode: ListView.ApplyRange
        preferredHighlightBegin: 0
        preferredHighlightEnd: height - 180 * Y.u
        highlightMoveDuration: 160
        interactive: false
        keyNavigationEnabled: true
        onCurrentIndexChanged: pick.restart()
        Keys.onLeftPressed: Y.toGuide()
        Keys.onRightPressed: if (feed.count) feed.forceActiveFocus()
        Keys.onReturnPressed: { pick.stop(); page.show(currentIndex); if (feed.count) feed.forceActiveFocus(); }
        Keys.onEnterPressed: { pick.stop(); page.show(currentIndex); if (feed.count) feed.forceActiveFocus(); }
        delegate: Item {
            id: row
            required property var modelData
            required property int index
            readonly property bool on: ListView.isCurrentItem && list.activeFocus
            readonly property bool sel: page.picked === index
            readonly property bool all: !!row.modelData.all || !row.modelData.id
            width: list.width
            height: (modelData.section ? 62 : 0) * Y.u + 78 * Y.u
            Text {                             // a heading ("A-Z"): small and grey, not a row
                visible: !!row.modelData.section
                x: 18 * Y.u; y: 18 * Y.u
                text: row.modelData.section || ""
                color: "#aaaaaa"; font.family: Y.font; font.pixelSize: 24 * Y.u; font.weight: Font.Medium
            }
            Rectangle {
                y: row.height - 78 * Y.u
                width: parent.width; height: 78 * Y.u
                radius: 16 * Y.u
                color: row.on ? Y.text : row.sel && !list.activeFocus ? Y.raised : "transparent"
                Item {
                    id: pic
                    x: 18 * Y.u
                    width: 54 * Y.u; height: width
                    anchors.verticalCenter: parent.verticalCenter
                    Icon { anchors.centerIn: parent; visible: row.all; name: "list"; size: 38 * Y.u; color: row.on ? Y.ink : Y.text }
                    RoundImage { anchors.fill: parent; visible: !row.all; source: row.modelData.thumb || ""; fallback: row.modelData.title || "" }
                    Rectangle {                // new videos
                        visible: !!row.modelData.new
                        anchors { right: parent.right; bottom: parent.bottom; margins: -2 * Y.u }
                        width: 16 * Y.u; height: width; radius: width / 2
                        color: "#3ea6ff"
                        border.color: row.on ? Y.text : Y.bg; border.width: 3 * Y.u
                    }
                }
                Text {
                    anchors { left: pic.right; leftMargin: 18 * Y.u; right: parent.right; rightMargin: 18 * Y.u; verticalCenter: parent.verticalCenter }
                    text: row.modelData.title || ""
                    color: row.on ? Y.ink : Y.text
                    font.family: Y.font; font.pixelSize: 31 * Y.u; font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
            }
        }
    }
    Rectangle { x: 590 * Y.u; y: 192 * Y.u; width: 3 * Y.u; height: parent.height - y; color: "#262626" }
    Text {
        visible: !page.loaded || !!page.problem
        x: page.feedX; y: 260 * Y.u
        width: parent.width - x - 108 * Y.u
        text: page.problem || ""
        color: Y.dim; font.family: Y.font; font.pixelSize: Y.tMeta
        wrapMode: Text.WordWrap
    }
}
