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
    function focusDetail() { return {key: key, loaded: loaded, rows: feed.count, row: feed.index, problem: problem, fromCopy: fromCopy, fresh: !!fresh}; }
    readonly property bool empty: loaded && feed.count === 0

    // Home: last time's at once (the app's copy), then YouTube's new one in its place, unless the
    // remote has moved on meanwhile: then the new one waits (fresh) until the copy is out of the
    // way, when Up reaches the search pill or Home is shown again from the guide
    property bool fromCopy: false
    property string asking: ""                 // the page asked for, while its answer is on the way
    property var copy: null                    // Home's copy handed over at the start (Main: the status answer)
    property var fresh: null                   // Home's new answer, kept while the copy is in use
    property int gen: 0                        // the latest ask (an older answer coming late is dropped)
    function showFresh() { if (fresh) { const r = fresh; fresh = null; feed.setPage(r); } }
    onVisibleChanged: if (visible && !activeFocus) showFresh()
    // Home's Refresh button (its last row; a tab's, if it has one): the page again from YouTube,
    // with new videos, from its first shelf once it comes
    function reload(token) {
        asking = ""; copy = null;
        load(token);
    }
    function load(token) {        // token: Home's Refresh button's
        const what = key + "|" + browseId;
        if (asking === what) return;           // already on its way (Home was asked for twice at start)
        asking = what;
        problem = "";
        fromCopy = false;
        fresh = null;
        const g = ++gen;
        const asked = Date.now();
        const show = r => { feed.setPage(r); if (page.activeFocus) page.focusFeed(); if (key === "home" && !Y.homeShown) { Y.homeShown = true; Y.call("mark", {step: "home-shown"}, () => {}, () => {}); } };
        const done = r => {
            if (!page || g !== gen) return;
            if (asking === what) asking = "";
            if (page.key + "|" + page.browseId !== what) return;     // (another tab since)
            if (fromCopy && Y.lastKey > asked) fresh = r;
            else show(r);
            loaded = true; fromCopy = false;
        };
        const fail = e => {
            if (!page || g !== gen) return;
            if (asking === what) asking = "";
            if (token && feed.count) Y.toast(e);          // (a refresh: the page as it was stays)
            else if (!fromCopy) { loaded = true; problem = e; }
        };
        if (key === "home") {
            if (copy && (copy.shelves || []).length) { fromCopy = true; show(copy); }
            else if (!token) Y.call("homeCached", {}, r => { if (page && g === gen && !loaded && r.page && (r.page.shelves || []).length) { fromCopy = true; show(r.page); } }, () => {});
            copy = null;
            Y.call("home", token ? {token: token} : {}, done, fail);
        } else if (token) Y.call("more", {token: token}, done, fail);
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
        y: 161 * Y.u
        width: parent.width
        height: parent.height - y
        grow: true
        onAtTop: { header.forceActiveFocus(); page.showFresh(); }
        onOpen: it => Y.open(it)
        onReload: token => page.reload(token)
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
