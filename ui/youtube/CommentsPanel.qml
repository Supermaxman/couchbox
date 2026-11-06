// The comments beside the video: who, when, the text, its likes and replies; more load as the
// list nears its end. Up and Down move; OK on a comment with replies opens them (the comment
// first, then its replies, more of them as the list nears its end); Back goes back to the
// comments on the same one, or closes.
import QtQuick

FocusScope {
    id: panel
    property string token: ""                 // the first page's continuation (the watch page's)
    property string count: ""
    property var items: []
    property string more: ""
    property bool loading: false
    property string problem: ""
    property var thread: null                 // a comment's replies open: {comment, items, more, index} (the comments, to go back to)
    function focusDetail() { return {comments: items.length, thread: !!thread, at: list.currentIndex, replies: thread ? items.length - 1 : 0,
                                     withReplies: items.findIndex(c => !!c.repliesToken)}; }
    signal closed()
    x: 1254 * Y.u
    width: 612 * Y.u
    height: parent ? parent.height : 0
    function load() {
        items = []; more = ""; problem = ""; thread = null;
        if (!token) { problem = "Comments are turned off for this video."; return; }
        fetch(token);
    }
    function fetch(t) {
        loading = true;
        const th = thread;                     // (replies that come after Back aren't the comments')
        Y.call("comments", {token: t}, r => {
            if (!panel || panel.thread !== th) return;   // (the player closed meanwhile, or Back)
            loading = false;
            items = items.concat(r.items || []);
            more = r.more || "";
            if (!items.length) problem = "No comments yet.";
            else if (thread && items.length === 1) problem = "No replies to show.";
        }, e => { if (panel) { panel.loading = false; panel.problem = e; } });
    }
    Keys.onUpPressed: list.decrementCurrentIndex()
    Keys.onDownPressed: { list.incrementCurrentIndex(); if (list.currentIndex >= items.length - 3 && more && !loading) fetch(more); }
    function openReplies() {
        const c = items[list.currentIndex];
        if (!c || !c.repliesToken || thread) return;
        thread = {comment: c, items: items, more: more, index: list.currentIndex};
        items = [Object.assign({}, c, {parent: true})]; more = ""; problem = "";
        list.currentIndex = 0;
        fetch(c.repliesToken);
    }
    function back() {
        if (!thread) { closed(); return; }
        const t = thread;
        thread = null; problem = ""; loading = false;
        items = t.items; more = t.more;
        list.currentIndex = t.index;
        list.positionViewAtIndex(t.index, ListView.Contain);
    }
    Keys.onReturnPressed: openReplies()
    Keys.onEnterPressed: openReplies()
    Keys.onEscapePressed: back()
    Keys.onBackPressed: back()
    Keys.onLeftPressed: {}
    Keys.onRightPressed: {}

    Row {
        y: 40 * Y.u
        spacing: 14 * Y.u
        Text { text: panel.thread ? "Replies" : "Comments"; color: Y.text; font.family: Y.font; font.pixelSize: 36 * Y.u; font.weight: Font.Bold }
        Text { text: panel.thread ? String(panel.thread.comment.replies || "") : panel.count; color: Y.dim; font.family: Y.font; font.pixelSize: 32 * Y.u; anchors.baseline: parent.children[0].baseline }
    }
    ListView {
        id: list
        y: 120 * Y.u
        width: parent.width
        height: parent.height - y - 30 * Y.u
        clip: true
        spacing: 12 * Y.u
        interactive: false
        model: panel.items
        highlightRangeMode: ListView.ApplyRange
        preferredHighlightBegin: 0
        preferredHighlightEnd: height * 0.7
        highlightMoveDuration: 160
        delegate: Rectangle {
            id: c
            required property var modelData
            required property int index
            readonly property bool on: ListView.isCurrentItem && panel.activeFocus
            readonly property bool reply: !!panel.thread && !c.modelData.parent
            x: reply ? 40 * Y.u : 0                // replies indented under their comment
            width: list.width - x
            height: body.height + 48 * Y.u
            radius: 16 * Y.u
            color: on ? Y.text : Y.raised
            RoundImage { x: 24 * Y.u; y: 24 * Y.u; width: 54 * Y.u; height: width; source: c.modelData.photo || ""; fallback: (c.modelData.author || "").replace("@", "") }
            Column {
                id: body
                x: 96 * Y.u; y: 24 * Y.u
                width: parent.width - 120 * Y.u
                spacing: 8 * Y.u
                Text {
                    width: parent.width
                    text: (c.modelData.pinned ? "Pinned  ·  " : "") + c.modelData.author + "  ·  " + c.modelData.time
                    color: c.on ? "#606060" : Y.dim; font.family: Y.font; font.pixelSize: 22 * Y.u; font.weight: Font.Medium
                    elide: Text.ElideRight
                }
                Text {
                    width: parent.width
                    text: c.modelData.text
                    color: c.on ? Y.ink : Y.text; font.family: Y.font; font.pixelSize: 25 * Y.u
                    wrapMode: Text.Wrap; maximumLineCount: c.on ? 12 : 4; elide: Text.ElideRight
                    lineHeight: 1.1
                }
                Row {
                    spacing: 20 * Y.u
                    visible: !!c.modelData.likes || c.modelData.replies > 0
                    Row {
                        spacing: 8 * Y.u
                        visible: !!c.modelData.likes
                        Icon { name: "like"; size: 26 * Y.u; color: c.on ? Y.ink : Y.dim }
                        Text { text: c.modelData.likes || ""; color: c.on ? Y.ink : Y.dim; font.family: Y.font; font.pixelSize: 22 * Y.u }
                    }
                    Text { visible: c.modelData.replies > 0; text: c.modelData.replies + (c.modelData.replies === 1 ? " reply" : " replies") + (c.on && c.modelData.repliesToken && !panel.thread ? "  ·  OK to read" : ""); color: c.on ? Y.ink : Y.dim; font.family: Y.font; font.pixelSize: 22 * Y.u }
                }
            }
        }
    }
    Text {
        visible: !!panel.problem || (panel.loading && !panel.items.length)
        y: 140 * Y.u
        width: parent.width
        text: panel.problem || "Loading comments…"
        color: Y.dim; font.family: Y.font; font.pixelSize: 26 * Y.u
        wrapMode: Text.WordWrap
    }
}
