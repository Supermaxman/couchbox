// Home and the guide's tabs (Music, Gaming, News, Podcasts, Movies & TV, Live, Sports): the search
// pill and the YouTube mark at the top, then the page's shelves, the current one with larger cards.
import QtQuick

FocusScope {
    id: page
    property string key: "home"
    property string browseId: "FEtopics"
    property string label: "Home"
    property bool loaded: false
    property string problem: ""
    readonly property bool empty: loaded && feed.count === 0

    function load() {
        problem = "";
        const done = r => { loaded = true; feed.setPage(r); if (page.activeFocus) page.focusFeed(); };
        const fail = e => { loaded = true; problem = e; };
        if (key === "home") Y.call("home", {}, done, fail);
        else Y.call("browse", {id: browseId}, done, fail);
    }
    function focusFeed() { if (feed.count) feed.forceActiveFocus(); else header.forceActiveFocus(); }
    onActiveFocusChanged: if (activeFocus && !header.activeFocus && !feed.activeFocus) focusFeed()

    Header {
        id: header
        x: Y.left
        width: parent.width - Y.left
        onSearchAsked: Y.search("")
        onDown: if (feed.count) feed.forceActiveFocus()
    }
    Feed {
        id: feed
        y: 162 * Y.u
        width: parent.width
        height: parent.height - y
        grow: true
        onAtTop: header.forceActiveFocus()
        onOpen: it => Y.open(it)
    }
    Text {
        visible: !page.loaded || !!page.problem || page.empty
        x: Y.left; y: 260 * Y.u
        width: parent.width - 2 * Y.left
        text: page.problem ? page.problem : page.loaded ? "Nothing here right now." : ""
        color: Y.dim
        font.family: Y.font; font.pixelSize: Y.tMeta
        wrapMode: Text.WordWrap
    }
}
