// A page of posters (See All, a genre, studio or network, search results, Movies, Series),
// loading more as you scroll down.
import QtQuick

FocusScope {
    id: page
    property string title: ""
    property string path: ""
    property string mediaType: ""
    property bool lazy: path.indexOf("/watchlist") >= 0      // entries without posters: cards fetch details
    property int pageNo: 0
    property int pages: 1
    property bool loading: false
    property string empty: "No results."

    // Movies / Series: the website's sort and filters (Up from the grid's top row)
    property bool filters: false
    readonly property bool tv: mediaType === "tv"
    readonly property var sorts: tv
        ? [["popularity.desc", "Popularity"], ["first_air_date.desc", "Newest"], ["first_air_date.asc", "Oldest"],
           ["vote_average.desc", "Highest Rated"], ["name.asc", "Title A–Z"]]
        : [["popularity.desc", "Popularity"], ["primary_release_date.desc", "Newest"], ["primary_release_date.asc", "Oldest"],
           ["vote_average.desc", "Highest Rated"], ["revenue.desc", "Box Office"], ["original_title.asc", "Title A–Z"]]
    readonly property var decades: [["", "Any Year"], ["2020", "2020s"], ["2010", "2010s"], ["2000", "2000s"], ["1990", "1990s"],
                                    ["1980", "1980s"], ["1970", "1970s"], ["old", "Before 1970"]]
    readonly property var ratings: [[0, "Any Rating"], [5, "5+"], [6, "6+"], [7, "7+"], [8, "8+"]]
    property var genres: [[0, "All Genres"]]
    property var providers: [[0, "Any Service"]]
    property int sortAt: 0
    property int genreAt: 0
    property int decadeAt: 0
    property int ratingAt: 0
    property int providerAt: 0
    property string base: ""                 // the path without filters

    function filtered() {
        const q = ["sortBy=" + sorts[sortAt][0]];
        const today = new Date().toISOString().slice(0, 10);
        const from = tv ? "firstAirDateGte" : "primaryReleaseDateGte", to = tv ? "firstAirDateLte" : "primaryReleaseDateLte";
        if (genres[genreAt][0]) q.push("genre=" + genres[genreAt][0]);
        const dec = decades[decadeAt][0];
        if (dec === "old") q.push(to + "=1969-12-31");
        else if (dec) q.push(from + "=" + dec + "-01-01", to + "=" + (parseInt(dec) + 9) + "-12-31");
        else if (sorts[sortAt][0].indexOf("date.desc") >= 0) q.push(to + "=" + today);     // newest: released ones
        if (ratings[ratingAt][0]) q.push("voteAverageGte=" + ratings[ratingAt][0]);
        if (ratings[ratingAt][0] || sorts[sortAt][0] === "vote_average.desc") q.push("voteCountGte=200");
        if (providers[providerAt][0]) q.push("watchProviders=" + providers[providerAt][0], "watchRegion=US");
        return base + (base.indexOf("?") >= 0 ? "&" : "?") + q.join("&");
    }
    function refilter() {
        path = filtered();
        model.clear(); pageNo = 0; pages = 1; loading = false;
        load();
    }

    ListModel { id: model }

    function load() {
        if (loading || pageNo >= pages) return;
        loading = true;
        const p = pageNo + 1;
        S.get(path + (path.indexOf("?") >= 0 ? "&" : "?") + "page=" + p, r => {
            for (const it of r.results || []) {
                if (lazy) { model.append({k: "title", id: it.tmdbId, a: "", b: "", img: "", t: it.mediaType, n: 0, ov: ""}); continue; }
                const c = S.card(it, mediaType);
                model.append({k: c.kind, id: c.tmdbId, a: c.title, b: c.year, img: c.poster, t: c.mediaType, n: c.status, ov: c.overview});
            }
            pageNo = p;
            pages = r.totalPages || 1;
            loading = false;
        }, () => { loading = false; });
    }
    Component.onCompleted: {
        if (filters) {
            base = path;
            S.get("/genres/" + (tv ? "tv" : "movie"), r => genres = [[0, "All Genres"]].concat(r.map(g => [g.id, g.name])));
            S.get("/watchproviders/" + (tv ? "tv" : "movies") + "?watchRegion=US",
                  r => providers = [[0, "Any Service"]].concat(r.slice(0, 16).map(p => [p.id, p.name])));
            path = filtered();
        }
        load();
    }
    Keys.onUpPressed: event => {
        event.accepted = filters && !bar.activeFocus;
        if (event.accepted) bar.forceActiveFocus();
    }

    Text {
        id: heading
        x: 0
        y: 124 * S.u
        text: page.title
        color: S.heading
        font.family: S.font
        font.pixelSize: 46 * S.u
        font.weight: Font.Bold
    }

    FocusScope {
        id: bar
        visible: page.filters
        anchors { right: parent.right; rightMargin: S.edge; verticalCenter: heading.verticalCenter }
        width: barRow.width
        height: barRow.height
        Row {
            id: barRow
            spacing: 12 * S.u
            Repeater {
                model: [["⇅", "Sort", page.sorts, "sortAt"], ["", "Genre", page.genres, "genreAt"], ["", "Released", page.decades, "decadeAt"],
                        ["", "Rating", page.ratings, "ratingAt"], ["", "Streaming", page.providers, "providerAt"]]
                SButton {
                    required property var modelData
                    required property int index
                    focus: index === 0
                    icon: modelData[0]
                    text: modelData[2][page[modelData[3]]] ? modelData[2][page[modelData[3]]][1] : ""
                    kind: page[modelData[3]] > 0 && index > 0 ? "primary" : ""
                    onClicked: S.pick(modelData[1], modelData[2].map(o => o[1]), page[modelData[3]], i => { page[modelData[3]] = i; page.refilter(); })
                }
            }
        }
        Keys.onLeftPressed: event => {
            const kids = barRow.children.filter(c => c.clicked !== undefined);
            const i = kids.findIndex(c => c.activeFocus);
            event.accepted = i > 0;
            if (event.accepted) kids[i - 1].forceActiveFocus();
        }
        Keys.onRightPressed: event => {
            const kids = barRow.children.filter(c => c.clicked !== undefined);
            const i = kids.findIndex(c => c.activeFocus);
            event.accepted = i >= 0 && i < kids.length - 1;
            if (event.accepted) kids[i + 1].forceActiveFocus();
        }
        Keys.onDownPressed: grid.forceActiveFocus()
        Keys.onUpPressed: event => { event.accepted = false; }
    }

    GridView {
        id: grid
        anchors { left: parent.left; right: parent.right; top: heading.bottom; bottom: parent.bottom; topMargin: 24 * S.u }
        cellWidth: S.cardW + S.rowGap
        cellHeight: S.cardH + 36 * S.u
        focus: true
        clip: true
        model: model
        cacheBuffer: 1500
        highlightMoveDuration: 150
        highlightRangeMode: GridView.ApplyRange
        preferredHighlightBegin: 40 * S.u
        preferredHighlightEnd: height - S.cardH - 40 * S.u
        topMargin: 22 * S.u
        leftMargin: 18 * S.u
        onCurrentIndexChanged: if (currentIndex > count - 20) page.load()
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
            required property string ov
            focus: GridView.isCurrentItem
            sourceComponent: k === "person" ? personC : titleC
            Component { id: titleC; TitleCard { focus: true; mediaType: d.t || "movie"; tmdbId: d.id; title: d.a; year: d.b; poster: d.img; overview: d.ov; status: d.n } }
            Component { id: personC; PersonCard { focus: true; personId: d.id; name: d.a; photo: d.img } }
        }
    }

    Text {
        anchors.centerIn: parent
        visible: !page.loading && model.count === 0
        text: page.empty
        color: S.dim
        font.family: S.font
        font.pixelSize: 30 * S.u
    }
}
