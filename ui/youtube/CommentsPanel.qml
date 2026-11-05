// The comments beside the video: who, when, the text, its likes and replies; more load as the
// list nears its end. Up and Down move; Back closes.
import QtQuick

FocusScope {
    id: panel
    property string token: ""                 // the first page's continuation (the watch page's)
    property string count: ""
    property var items: []
    property string more: ""
    property bool loading: false
    property string problem: ""
    signal closed()
    x: 1254 * Y.u
    width: 612 * Y.u
    height: parent ? parent.height : 0
    function load() {
        items = []; more = ""; problem = "";
        if (!token) { problem = "Comments are turned off for this video."; return; }
        fetch(token);
    }
    function fetch(t) {
        loading = true;
        Y.call("comments", {token: t}, r => {
            loading = false;
            items = items.concat(r.items || []);
            more = r.more || "";
            if (!items.length) problem = "No comments yet.";
        }, e => { loading = false; problem = e; });
    }
    Keys.onUpPressed: list.decrementCurrentIndex()
    Keys.onDownPressed: { list.incrementCurrentIndex(); if (list.currentIndex >= items.length - 3 && more && !loading) fetch(more); }
    Keys.onEscapePressed: closed()
    Keys.onBackPressed: closed()
    Keys.onLeftPressed: {}
    Keys.onRightPressed: {}

    Row {
        y: 40 * Y.u
        spacing: 14 * Y.u
        Text { text: "Comments"; color: Y.text; font.family: Y.font; font.pixelSize: 36 * Y.u; font.weight: Font.Bold }
        Text { text: panel.count; color: Y.dim; font.family: Y.font; font.pixelSize: 32 * Y.u; anchors.baseline: parent.children[0].baseline }
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
            width: list.width
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
                    Text { visible: c.modelData.replies > 0; text: c.modelData.replies + (c.modelData.replies === 1 ? " reply" : " replies"); color: c.on ? Y.ink : Y.dim; font.family: Y.font; font.pixelSize: 22 * Y.u }
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
