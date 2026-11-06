// Library: the coloured tiles (History, Watch later, Playlists, Music, Movies & TV, Podcasts), then
// YouTube's shelves of them (History, Watch later, playlists, liked videos).
import QtQuick

FocusScope {
    id: page
    property bool loaded: false
    property string problem: ""
    readonly property string label: "Library"
    function focusDetail() { return {loaded: loaded, rows: feed.count, row: feed.index, problem: problem}; }
    function load() {
        problem = "";
        Y.call("library", {}, r => {
            loaded = true;
            feed.setPage(r, [{at: 0, row: {kind: "tiles", tiles: r.tiles || []}}]);
            if (page.activeFocus) feed.forceActiveFocus();
        }, e => { loaded = true; problem = e; });
    }
    onActiveFocusChanged: if (activeFocus && !feed.activeFocus) feed.forceActiveFocus()
    Feed {
        id: feed
        y: 78 * Y.u                            // the tiles' tops at 90, as YouTube's
        width: parent.width
        height: parent.height - y
        onOpen: it => Y.open(it)
    }
    Text {
        visible: !!page.problem
        x: Y.left; y: 260 * Y.u
        width: parent.width - 2 * Y.left
        text: page.problem
        color: Y.dim; font.family: Y.font; font.pixelSize: Y.tMeta
        wrapMode: Text.WordWrap
    }
}
