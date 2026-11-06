// One list in rows of three: History, Watch later, a playlist, or Library's other tiles. Back
// goes back.
import QtQuick

FocusScope {
    id: page
    objectName: "list"
    property string title: ""
    property string browseId: ""
    property string problem: ""
    property bool loaded: false
    readonly property string label: title
    function focusDetail() { return {browseId: browseId, loaded: loaded, rows: feed.count, problem: problem}; }
    signal closed()
    Component.onCompleted: Y.call("browse", {id: browseId}, r => {
        loaded = true;
        for (const s of r.shelves || []) if (s.title === page.title) s.title = "";     // said once, above
        feed.setPage(r);
        if (!feed.count) problem = "Nothing here yet.";
        feed.forceActiveFocus();
    }, e => { loaded = true; problem = e; })
    Keys.onEscapePressed: closed()
    Keys.onBackPressed: closed()
    Text {                                     // the page's name, level with the guide's picture
        x: 172 * Y.u; y: 68 * Y.u
        height: 72 * Y.u
        verticalAlignment: Text.AlignVCenter
        text: page.title
        color: Y.text; font.family: Y.font; font.pixelSize: 44 * Y.u; font.weight: Font.Bold
    }
    Feed {
        id: feed
        y: 150 * Y.u
        width: parent.width
        height: parent.height - y
        perRow: 3
        focus: true
        onOpen: it => Y.playList(feed.itemsAfter(it), it)      // the list's next videos after it
    }
    Text {
        visible: !!page.problem
        x: Y.left; y: 220 * Y.u
        text: page.problem
        color: Y.dim; font.family: Y.font; font.pixelSize: Y.tMeta
    }
}
