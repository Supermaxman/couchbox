// A movie or a show: its backdrop and poster, the ratings (IMDb, Rotten Tomatoes, TMDB), the
// story, who made it, Play in Jellyfin / Request in Seerr / Trailer, then rows of the cast,
// the crew, the seasons, and more like it. Up/Down move between the buttons and the rows,
// Left/Right along them, OK opens, Back goes back.
import QtQuick

FocusScope {
    id: page
    property string kind: "movie"
    property int tid: 0
    property var t: null
    property bool loading: true
    property string problem: ""
    property int zone: 0
    property int btn: 0
    signal closed()

    readonly property string label: t ? t.title : ""
    readonly property var actions: {
        const a = [];
        if (!t) return a;
        if (t.jellyfin_id && (t.available === "available" || t.available === "partial"))
            a.push({label: t.available === "partial" ? "Play in Jellyfin (some)" : "Play in Jellyfin", icon: "play", act: "jellyfin"});
        if ((M.status.source === "seerr" || M.status.source === "demo") && t.available !== "available")
            a.push({label: t.available === "requested" ? "Requested · Seerr" : "Request in Seerr", icon: "plus", act: "seerr"});
        if (t.trailer) a.push({label: "Trailer", icon: "trailer", act: "trailer"});
        return a;
    }
    readonly property var zones: {
        const z = [];
        if (actions.length) z.push(buttons);
        for (const s of [cast, crew, seasons, recs, similar]) if (s.items.length) z.push(s);
        return z;
    }

    function load() {
        loading = true; problem = "";
        M.call("title", {kind: kind, id: tid}, r => { t = r; loading = false; zone = 0; btn = 0; Qt.callLater(focusZone); },
               e => { loading = false; problem = e; });
    }
    Component.onCompleted: load()
    onActiveFocusChanged: if (activeFocus) focusZone()
    function focusZone() {
        const z = zones[zone];
        if (!z) { page.forceActiveFocus(); return; }
        if (z === buttons) { const b = btnRep.itemAt(btn); if (b) b.forceActiveFocus(); flick.contentY = 0; }
        else { z.forceActiveFocus(); flick.contentY = Math.max(0, z.y + shelves.y - 300 * M.u); }
    }
    function run(a) {
        if (a.act === "jellyfin") { backend.post("/play/jellyfin", JSON.stringify({id: t.jellyfin_id})); M.toast("Opening in Jellyfin…"); }
        else if (a.act === "seerr") { backend.openSeerr(kind + ":" + tid); M.toast("Opening Seerr…"); }
        else if (a.act === "trailer") { backend.post("/play/youtube", JSON.stringify({id: t.trailer})); M.toast("Playing the trailer on YouTube…"); }
    }
    Keys.onUpPressed: if (zone > 0) { zone--; focusZone(); }
    Keys.onDownPressed: if (zone < zones.length - 1) { zone++; focusZone(); }
    Keys.onEscapePressed: closed()
    Keys.onBackPressed: closed()

    Rectangle { anchors.fill: parent; color: M.bg }
    Flickable {
        id: flick
        anchors.fill: parent
        contentHeight: content.height + 300 * M.u
        interactive: false
        Behavior on contentY { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
        Item {
            id: content
            width: flick.width
            height: shelves.y + shelves.height
            Image {
                id: backdrop
                anchors { left: parent.left; right: parent.right; top: parent.top }
                height: 760 * M.u
                source: page.t ? page.t.backdrop : ""
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                sourceSize.width: 1280
                opacity: status === Image.Ready ? 0.55 : 0
                Behavior on opacity { NumberAnimation { duration: 300 } }
            }
            Rectangle {
                anchors.fill: backdrop
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: M.bg }
                    GradientStop { position: 0.5; color: "#990b0b0d" }
                    GradientStop { position: 1; color: "#330b0b0d" }
                }
            }
            Rectangle {
                anchors { left: parent.left; right: parent.right; bottom: backdrop.bottom }
                height: 300 * M.u
                gradient: Gradient { GradientStop { position: 0; color: "#000b0b0d" } GradientStop { position: 1; color: M.bg } }
            }

            Poster {
                id: poster
                x: 80 * M.u; y: 90 * M.u
                width: 330 * M.u
                captioned: false
                visible: !!page.t
                item: page.t ? {title: page.t.title, poster: page.t.poster} : ({})
            }
            Column {
                id: info
                anchors { left: poster.right; leftMargin: 60 * M.u; right: parent.right; rightMargin: M.edge + 30 * M.u; top: poster.top }
                spacing: 20 * M.u
                visible: !!page.t
                Text {
                    width: parent.width
                    text: page.label
                    color: M.text; font.family: M.font; font.pixelSize: M.tHero; font.weight: Font.Bold
                    wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
                }
                Text {
                    width: parent.width
                    text: !page.t ? "" : [
                        page.t.year + (page.t.type === "tv" ? "–" + (page.t.end_year || "") : ""),
                        page.t.certification,
                        page.t.type === "tv" ? (page.t.seasons_count ? page.t.seasons_count + (page.t.seasons_count > 1 ? " seasons" : " season") : "") : M.runtime(page.t.runtime),
                        page.t.genres.slice(0, 3).join(", ")
                    ].filter(x => !!x).join("   ·   ")
                    color: M.text2; font.family: M.font; font.pixelSize: M.tBody; elide: Text.ElideRight
                }
                Scores { ratings: page.t ? page.t.ratings : ({}) }
                Text {
                    width: parent.width
                    visible: !!(page.t && page.t.tagline)
                    text: page.t ? page.t.tagline : ""
                    color: M.dim; font.family: M.font; font.pixelSize: M.tBody; font.italic: true; elide: Text.ElideRight
                }
                Text {
                    width: parent.width
                    text: page.t ? page.t.overview : ""
                    color: M.text2; font.family: M.font; font.pixelSize: M.tBody; lineHeight: 1.18
                    wrapMode: Text.WordWrap; maximumLineCount: 5; elide: Text.ElideRight
                }
                Grid {                               // who made it
                    columns: 2
                    columnSpacing: 24 * M.u; rowSpacing: 8 * M.u
                    Repeater {
                        model: !page.t ? [] : [
                            [page.t.directors.length > 1 ? "Directors" : "Director", page.t.directors.map(p => p.name).join(", ")],
                            ["Created by", page.t.creators.map(p => p.name).join(", ")],
                            [page.t.writers.length > 1 ? "Writers" : "Writer", page.t.writers.map(p => p.name).join(", ")],
                            ["On", page.t.networks.join(", ")],
                            ["Status", page.t.type === "tv" && page.t.status !== "Returning Series" ? page.t.status : ""]
                        ].filter(x => !!x[1]).reduce((a, x) => a.concat(x), [])
                        delegate: Text {
                            required property string modelData
                            required property int index
                            text: modelData
                            color: index % 2 ? M.text : M.faint
                            font.family: M.font; font.pixelSize: M.tMeta; font.weight: index % 2 ? Font.DemiBold : Font.Normal
                        }
                    }
                }
                FocusScope {
                    id: buttons
                    width: parent.width; height: page.actions.length ? 90 * M.u : 0
                    Row {
                        y: 12 * M.u
                        spacing: 20 * M.u
                        Repeater {
                            id: btnRep
                            model: page.actions
                            delegate: MButton {
                                required property var modelData
                                required property int index
                                text: modelData.label; icon: modelData.icon; primary: index === 0
                                onPressed: page.run(modelData)
                                Keys.onLeftPressed: if (index > 0) { page.btn = index - 1; btnRep.itemAt(page.btn).forceActiveFocus(); }
                                Keys.onRightPressed: if (index < page.actions.length - 1) { page.btn = index + 1; btnRep.itemAt(page.btn).forceActiveFocus(); }
                            }
                        }
                    }
                }
            }

            Column {
                id: shelves
                x: 80 * M.u
                y: Math.max(poster.y + poster.height, info.y + info.height) + 60 * M.u
                width: parent.width - x
                spacing: 40 * M.u
                Shelf { id: cast; title: page.kind === "tv" ? "Cast" : "Top cast"; kind: "person"
                        items: page.t ? page.t.cast.map(c => Object.assign({type: "person"}, c)) : []
                        onOpen: it => M.open(it) }
                Shelf { id: crew; title: "Crew"; kind: "person"
                        items: page.t ? page.t.crew.map(c => Object.assign({type: "person"}, c)) : []
                        onOpen: it => M.open(it) }
                Shelf { id: seasons; title: "Seasons"; note: page.t && page.t.episodes_count ? page.t.episodes_count + " episodes" : ""
                        items: page.t ? page.t.seasons.map(s => ({type: "season", id: page.t.id, n: s.n, show: page.t.title, title: s.name,
                                                                  poster: s.poster || page.t.poster, role: [s.year, s.episodes ? s.episodes + " episodes" : ""].filter(x => !!x).join(" · ")})) : []
                        onOpen: it => M.open(it) }
                Shelf { id: recs; title: "More like this"; items: page.t ? page.t.recommendations : []; onOpen: it => M.open(it) }
                Shelf { id: similar; title: "Similar"; items: page.t ? page.t.similar : []; onOpen: it => M.open(it) }
            }
        }
    }
    Text {
        anchors.centerIn: parent
        visible: page.loading || !!page.problem
        width: parent.width * 0.6; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
        text: page.problem || "Loading…"
        color: page.problem ? M.text2 : M.faint; font.family: M.font; font.pixelSize: M.tHead
    }
}
