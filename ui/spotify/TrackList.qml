// A list of songs. Up/Down move (past the ends: upEdge/downEdge), OK plays from that song (in
// its album or playlist when there is one), Menu shows its actions, Left goes to leftEdge.
// maxRows > 0: shows that many rows at a time and scrolls within them.
import QtQuick

FocusScope {
    id: tl
    property var items: []
    property string contextUri: ""
    property int idx: 0
    property int maxRows: 0
    property bool showArt: true
    property bool showAlbum: true
    readonly property real rowH: 96 * S.u
    signal upEdge()
    signal downEdge()
    signal leftEdge()
    implicitHeight: list.height
    onItemsChanged: { idx = Math.min(idx, Math.max(0, items.length - 1)); S.check(items.map(t => t.uri)); }

    function playFrom(i) {
        const t = items[i];
        if (!t) return;
        if (contextUri) S.play({context: contextUri, offset: t.uri});
        else S.play({uris: items.slice(i, i + 100).map(x => x.uri)});
    }
    Keys.onUpPressed: { if (idx > 0) idx--; else upEdge(); }
    Keys.onDownPressed: { if (idx < items.length - 1) idx++; else downEdge(); }
    Keys.onLeftPressed: leftEdge()
    Keys.onReturnPressed: playFrom(idx)
    Keys.onEnterPressed: playFrom(idx)
    Keys.onMenuPressed: S.menu(items[idx], {context: contextUri})

    ListView {
        id: list
        width: parent.width
        height: (tl.maxRows > 0 ? Math.min(tl.items.length, tl.maxRows) : tl.items.length) * tl.rowH
        model: tl.items
        currentIndex: tl.idx
        clip: true
        interactive: false
        highlightMoveDuration: 140
        highlightRangeMode: ListView.ApplyRange
        preferredHighlightBegin: tl.rowH
        preferredHighlightEnd: height - 2 * tl.rowH
        delegate: TrackRow {
            required property var modelData
            required property int index
            width: list.width
            t: modelData
            num: index + 1
            showArt: tl.showArt
            showAlbum: tl.showAlbum
            current: tl.activeFocus && index === tl.idx
        }
    }
}
