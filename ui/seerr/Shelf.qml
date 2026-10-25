// A row of cards with a title, like the website's sliders. Kinds:
//   titles     a discover/search path, paged (results become poster cards)
//   media      the same path, but results are media entries (recently added): cards fetch details
//   watchlist  the same, watchlist entries
//   requests   /request results: request cards
//   genres / companies / people / list   cards from `items`
// `more` adds a "See All" card at the end (a path for the grid page, or "requests").
import QtQuick

FocusScope {
    id: shelf
    property bool stop: count > 0
    property string title: ""
    property string kind: "titles"
    property string path: ""
    property string mediaType: ""
    property var items: []
    property string more: ""
    property int maxPages: 5
    readonly property alias count: model.count
    property int page: 0
    property int pages: 1
    property bool loading: false
    property bool loaded: false
    readonly property real cardH: kind === "requests" ? 240 * S.u : kind === "genres" || kind === "companies" ? S.tileH : S.cardH
    width: parent ? parent.width : 0
    height: visible ? 70 * S.u + cardH + 30 * S.u : 0
    visible: count > 0 || !loaded

    ListModel { id: model }

    function add(it) {
        if (kind === "titles" || kind === "list") {
            const c = S.card(it, mediaType);
            if (c.kind === "person")
                model.append({k: "person", id: c.tmdbId, a: c.title, b: "", img: c.poster, t: "", n: 0, json: ""});
            else
                model.append({k: "title", id: c.tmdbId, a: c.title, b: c.year, img: c.poster, t: c.mediaType, n: c.status, json: c.overview});
        } else if (kind === "media" || kind === "watchlist") {
            model.append({k: "title", id: it.tmdbId, a: "", b: "", img: "", t: it.mediaType, n: it.status || 0, json: ""});
        } else if (kind === "requests") {
            model.append({k: "request", id: it.id, a: "", b: "", img: "", t: it.type, n: 0, json: JSON.stringify(it)});
        } else if (kind === "genres") {
            model.append({k: "genre", id: it.id, a: it.name, b: "", img: (it.backdrops || [""])[0], t: mediaType, n: 0, json: ""});
        } else if (kind === "companies") {
            model.append({k: "company", id: it.id, a: it.name, b: "", img: it.logo || "", t: mediaType, n: 0, json: ""});
        } else if (kind === "people") {
            model.append({k: "person", id: it.id, a: it.name, b: it.character || it.job || "", img: it.profilePath || "", t: "", n: 0, json: ""});
        }
    }

    function load() {
        if (loading || page >= Math.min(pages, maxPages)) return;
        if (!path) {
            for (const it of items) add(it);
            loaded = true; finish();
            return;
        }
        loading = true;
        const p = page + 1;
        const sep = path.indexOf("?") >= 0 ? "&" : "?";
        const q = kind === "media" ? sep + "take=20&skip=" + (p - 1) * 20
                : kind === "requests" ? sep + "take=10&skip=" + (p - 1) * 10 : sep + "page=" + p;
        S.get(path + q, r => {
            for (const it of r.results || []) add(it);
            page = p;
            pages = r.totalPages || (r.pageInfo ? r.pageInfo.pages : 1);
            if (kind === "requests" || kind === "media") pages = Math.min(pages, 1);
            loading = false; loaded = true;
            finish();
        }, () => { loading = false; loaded = true; });
    }

    function finish() {
        if (more && model.count && (model.count === 0 || model.get(model.count - 1).k !== "more") && page >= Math.min(pages, maxPages))
            model.append({k: "more", id: 0, a: title, b: more, img: "", t: mediaType, n: 0, json: ""});
    }

    function reload() { model.clear(); page = 0; pages = 1; loaded = false; load(); }
    Component.onCompleted: load()
    onItemsChanged: if (!path && loaded) reload()
    onPathChanged: if (loaded) reload()

    Text {
        id: heading
        x: 0
        y: 8 * S.u
        text: shelf.title + (shelf.more ? "  ›" : "")
        color: S.text2
        font.family: S.font
        font.pixelSize: 32 * S.u
        font.weight: Font.Bold
    }

    ListView {
        id: list
        anchors { left: parent.left; right: parent.right; top: heading.bottom; topMargin: 16 * S.u }
        height: shelf.cardH + 26 * S.u
        orientation: ListView.Horizontal
        spacing: S.rowGap
        focus: true
        model: model
        cacheBuffer: 1200
        highlightMoveDuration: 180
        highlightRangeMode: ListView.ApplyRange
        preferredHighlightBegin: 0
        preferredHighlightEnd: width - 520 * S.u
        boundsBehavior: Flickable.StopAtBounds
        onCurrentIndexChanged: if (currentIndex > count - 8) shelf.load()

        delegate: Loader {
            id: d
            required property int index
            required property string k
            required property int id
            required property string a
            required property string b
            required property string img
            required property string t
            required property int n
            required property string json
            focus: ListView.isCurrentItem
            y: 10 * S.u
            sourceComponent: k === "title" ? titleC : k === "person" ? personC : k === "request" ? requestC
                           : k === "genre" ? genreC : k === "company" ? companyC : moreC
            Component { id: titleC; TitleCard { focus: true; mediaType: d.t || "movie"; tmdbId: d.id; title: d.a; year: d.b; poster: d.img; overview: d.json; status: d.n } }
            Component { id: personC; PersonCard { focus: true; personId: d.id; name: d.a; role: d.b; photo: d.img } }
            Component { id: requestC; RequestCard { focus: true; request: JSON.parse(d.json) } }
            Component { id: genreC; GenreCard { focus: true; genreId: d.id; name: d.a; backdrop: d.img; mediaType: d.t } }
            Component { id: companyC; CompanyCard { focus: true; companyId: d.id; name: d.a; logo: d.img; mediaType: d.t } }
            Component { id: moreC; MoreCard { focus: true; title: d.a; path: d.b; mediaType: d.t; cardHeight: shelf.cardH } }
        }
    }

    Row {                                       // loading: gray placeholders
        anchors.fill: list
        spacing: S.rowGap
        visible: !shelf.loaded
        Repeater {
            model: 9
            Rectangle { y: 10 * S.u; width: shelf.cardH === S.cardH ? S.cardW : S.tileW; height: shelf.cardH; radius: 12 * S.u; color: S.panel }
        }
    }
}
