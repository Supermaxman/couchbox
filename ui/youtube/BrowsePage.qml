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
    function focusDetail() { return {key: key, loaded: loaded, rows: feed.count, row: feed.index, problem: problem, fromCopy: fromCopy}; }
    readonly property bool empty: loaded && feed.count === 0

    // Home: last time's at once (the app's copy), then YouTube's new one in its place, unless the
    // remote has moved on meanwhile (then the copy stays until Home loads again)
    property bool fromCopy: false
    property string asking: ""                 // the page asked for, while its answer is on the way
    function load() {
        const what = key + "|" + browseId;
        if (asking === what) return;           // already on its way (Home was asked for twice at start)
        asking = what;
        problem = "";
        fromCopy = false;
        const asked = Date.now();
        const show = r => { feed.setPage(r); if (page.activeFocus) page.focusFeed(); };
        const done = r => {
            if (!page) return;
            if (asking === what) asking = "";
            if (page.key + "|" + page.browseId !== what) return;     // (another tab since)
            if (!(fromCopy && Y.lastKey > asked)) show(r);
            loaded = true; fromCopy = false;
        };
        const fail = e => { if (!page) return; if (asking === what) asking = ""; if (!fromCopy) { loaded = true; problem = e; } };
        if (key === "home") {
            Y.call("homeCached", {}, r => { if (page && !loaded && r.page && (r.page.shelves || []).length) { fromCopy = true; show(r.page); } }, () => {});
            Y.call("home", {}, done, fail);
        } else Y.call("browse", {id: browseId}, done, fail);
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
        y: 161 * Y.u
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
