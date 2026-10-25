// A movie or show, laid out like the website: backdrop header with poster, status, title,
// certification / runtime / genres and the buttons (Play on Jellyfin, Watch Trailer,
// Request); tagline, overview, crew and keywords beside the facts panel (ratings, release
// dates, money, language, country, studio or network, where it's streaming); seasons with
// episodes for shows; then Cast, Recommendations and Similar rows.
import QtQuick

VPage {
    id: page
    clipContent: false
    property string mediaType: "movie"
    property int tmdbId: 0
    property var d: null                     // /movie or /tv details
    property var ratings: null
    readonly property bool tv: mediaType === "tv"
    readonly property var info: d && d.mediaInfo ? d.mediaInfo : null
    readonly property int status: info ? info.status : 0
    readonly property real side: 440 * S.u        // the facts column
    readonly property real gap: 48 * S.u

    function load() {
        S.get("/" + mediaType + "/" + tmdbId, r => {
            S.cache[mediaType + "/" + tmdbId] = r;
            d = r;
            buildSeasons();
        }, err => S.toast(err));
        S.get(tv ? "/tv/" + tmdbId + "/ratings" : "/movie/" + tmdbId + "/ratingscombined",
              r => ratings = tv ? {rt: r} : r, () => ratings = {});
    }
    Component.onCompleted: load()
    Connections {
        target: S
        function onRequested(type, id) { if (type === page.mediaType && id === page.tmdbId) page.load(); }
    }
    onDChanged: if (activeFocus) Qt.callLater(focusFirst)

    // ------------------------------------------------------------------ helpers
    function year() { return d ? (d.releaseDate || d.firstAirDate || "").slice(0, 4) : ""; }
    function certification() {
        if (!d) return "";
        if (tv) {
            const us = ((d.contentRatings || {}).results || []).find(r => r.iso_3166_1 === "US");
            return us ? us.rating : "";
        }
        const us = ((d.releases || {}).results || []).find(r => r.iso_3166_1 === "US");
        const c = us ? us.release_dates.find(x => x.certification) : null;
        return c ? c.certification : "";
    }
    function metaLine() {
        if (!d) return "";
        const bits = [];
        if (tv) bits.push(d.numberOfSeasons + (d.numberOfSeasons === 1 ? " Season" : " Seasons"));
        else if (d.runtime) bits.push(d.runtime + " minutes");
        if (d.genres && d.genres.length) bits.push(d.genres.map(g => g.name).join(", "));
        return bits.join("  |  ");
    }
    function crew() {
        if (!d) return [];
        const out = [];
        if (tv) for (const c of d.createdBy || []) out.push({job: "Creator", name: c.name, id: c.id});
        const jobs = tv ? ["Producer", "Co-Producer", "Executive Producer", "Director", "Writer"]
                        : ["Director", "Screenplay", "Writer", "Novel", "Story", "Editor", "Producer", "Original Music Composer", "Director of Photography"];
        const crew = ((d.credits || {}).crew || []);
        for (const j of jobs)
            for (const c of crew.filter(c => c.job === j))
                if (out.length < 6 && !out.some(o => o.id === c.id && o.job === c.job)) out.push({job: c.job, name: c.name, id: c.id});
        return out.slice(0, 6);
    }
    function releaseDates() {
        if (!d || tv) return [];
        const us = ((d.releases || {}).results || []).find(r => r.iso_3166_1 === "US");
        const names = {1: "Premiere", 2: "Limited", 3: "Theatrical", 4: "Digital", 5: "Physical", 6: "TV"};
        if (!us) return [];
        const first = {};                         // the first theatrical, digital, physical... date
        for (const x of us.release_dates.slice().sort((a, b) => a.release_date < b.release_date ? -1 : 1))
            if (x.type >= 3 && !first[x.type]) first[x.type] = x.release_date;
        return Object.keys(first).sort().map(t => names[t] + ": " + S.date(first[t]));
    }
    function providers() {
        if (!d) return [];
        const us = (d.watchProviders || []).find(w => w.iso_3166_1 === "US");
        return us ? (us.flatrate || []) : [];
    }
    function facts() {
        if (!d) return [];
        const f = [];
        f.push(["Status", d.status || ""]);
        if (tv) {
            f.push(["First Air Date", S.date(d.firstAirDate)]);
            if (d.nextEpisodeToAir) f.push(["Next Air Date", S.date(d.nextEpisodeToAir.airDate)]);
        } else {
            const r = releaseDates();
            if (r.length) f.push(["Release Dates", r.join("\n")]);
            if (d.revenue) f.push(["Revenue", S.money(d.revenue)]);
            if (d.budget) f.push(["Budget", S.money(d.budget)]);
        }
        f.push(["Original Language", S.language(d.originalLanguage)]);
        const pc = (d.productionCountries || []).map(c => c.name);
        if (pc.length) f.push([pc.length > 1 ? "Production Countries" : "Production Country", pc.join("\n")]);
        if (tv) {
            if ((d.networks || []).length) f.push(["Network", d.networks.map(n => n.name).join(", ")]);
        } else if ((d.productionCompanies || []).length) {
            f.push([d.productionCompanies.length > 1 ? "Studios" : "Studio", d.productionCompanies.slice(0, 3).map(c => c.name).join("\n")]);
        }
        return f;
    }
    function trailer() {
        if (!d) return null;
        const v = (d.relatedVideos || []).filter(v => v.site === "YouTube");
        return v.find(v => v.type === "Trailer") || v.find(v => v.type === "Teaser") || null;
    }
    // seasons (not specials) that can still be requested
    function seasonStatus(n) {
        if (!info) return 0;
        const s = (info.seasons || []).find(s => s.seasonNumber === n);
        let st = s ? s.status : 0;
        for (const r of info.requests || [])
            if (r.status !== 3 && (r.seasons || []).some(x => x.seasonNumber === n)) st = Math.max(st, 2);
        return st;
    }
    function pending() { return info ? (info.requests || []).filter(r => r.status === 1) : []; }
    function decide(what) {
        const list = pending();
        let left = list.length;
        for (const r of list)
            S.call("POST", "/request/" + r.id + "/" + what, null, () => {
                if (--left === 0) { S.toast(what === "approve" ? "Approved." : "Declined."); load(); }
            }, err => S.toast(err));
    }
    function toggleWatchlist() {
        const on = d.onUserWatchlist;
        const done = () => {
            const copy = Object.assign({}, d);
            copy.onUserWatchlist = !on;
            d = copy;
            S.toast(on ? "Removed from your watchlist." : "Added to your watchlist.");
        };
        if (on) S.call("DELETE", "/watchlist/" + tmdbId, null, done, err => S.toast(err));
        else S.call("POST", "/watchlist", {tmdbId: tmdbId, mediaType: mediaType, title: d.title || d.name}, done, err => S.toast(err));
    }
    // focus lands on the most useful button: Play, else Request, else the first
    function firstButton() {
        const b = buttons.shown();
        const i = b.findIndex(x => x === playBtn);
        const j = b.findIndex(x => x === requestBtn);
        return i >= 0 ? i : j >= 0 ? j : 0;
    }
    function canRequest() {
        if (!d) return false;
        if (!tv) return status < 2 || status >= 7;
        return (d.seasons || []).some(s => s.seasonNumber > 0 && seasonStatus(s.seasonNumber) < 2);
    }

    // ------------------------------------------------------------------ seasons list model
    ListModel { id: seasonModel }
    function buildSeasons() {
        seasonModel.clear();
        if (!tv || !d) return;
        const ss = (d.seasons || []).filter(s => s.seasonNumber > 0).sort((a, b) => b.seasonNumber - a.seasonNumber);
        for (const s of ss)
            seasonModel.append({k: "season", n: s.seasonNumber, name: s.name || "Season " + s.seasonNumber, count: s.episodeCount || 0,
                                st: seasonStatus(s.seasonNumber), open: false, date: "", text: "", still: ""});
    }
    function toggleSeason(i) {
        const row = seasonModel.get(i);
        if (row.open) {
            let j = i + 1;
            while (j < seasonModel.count && seasonModel.get(j).k === "ep") seasonModel.remove(j);
            seasonModel.setProperty(i, "open", false);
            return;
        }
        seasonModel.setProperty(i, "open", true);
        S.get("/tv/" + tmdbId + "/season/" + row.n, r => {
            let j = i + 1;
            for (const e of (r.episodes || []).slice().sort((a, b) => b.episodeNumber - a.episodeNumber))
                seasonModel.insert(j++, {k: "ep", n: e.episodeNumber, name: e.name || "", count: 0, st: 0, open: false,
                                         date: e.airDate ? S.date(e.airDate) : "", text: e.overview || "", still: e.stillPath || ""});
        });
    }

    // ------------------------------------------------------------------ backdrop
    Item {
        id: backdrop
        x: -S.gutter                          // from the sidebar's edge
        width: page.width + S.gutter
        height: 720 * S.u
        Image {
            anchors.fill: parent
            source: page.d ? S.img(page.d.backdropPath, "w1920_and_h800_multi_faces") : ""
            sourceSize.width: 1280
            asynchronous: true
            fillMode: Image.PreserveAspectCrop
            opacity: 0.45
        }
        Rectangle {                           // fade into the page (opaque at the bottom)
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(0.07, 0.09, 0.15, 0.2) }
                GradientStop { position: 0.6; color: Qt.rgba(0.07, 0.09, 0.15, 0.55) }
                GradientStop { position: 1.0; color: S.bg }
            }
        }
    }

    // ------------------------------------------------------------------ header
    Item {
        id: header
        y: 120 * S.u
        width: page.width - S.edge
        height: 390 * S.u

        Rectangle {
            id: poster
            width: 260 * S.u
            height: 390 * S.u
            radius: 12 * S.u
            color: S.panel
            clip: true
            Image {
                anchors.fill: parent
                source: page.d ? S.img(page.d.posterPath, "w600_and_h900_bestv2") : ""
                sourceSize.width: 400
                asynchronous: true
                fillMode: Image.PreserveAspectCrop
            }
        }
        Column {
            anchors { left: poster.right; leftMargin: 36 * S.u; bottom: parent.bottom; bottomMargin: 8 * S.u; right: parent.right }
            spacing: 8 * S.u
            Pill {
                visible: page.status >= 2
                text: S.statusName(page.status)
                color: S.statusColor(page.status)
                size: 16
            }
            Flow {
                width: parent.width
                spacing: 12 * S.u
                Text {
                    width: Math.min(implicitWidth, parent.width)
                    wrapMode: Text.WordWrap
                    text: page.d ? page.d.title || page.d.name : ""
                    color: S.text
                    font.family: S.font
                    font.pixelSize: 50 * S.u
                    font.weight: Font.Bold
                }
                Text {
                    text: page.year() ? "(" + page.year() + ")" : ""
                    color: S.text2
                    font.family: S.font
                    font.pixelSize: 38 * S.u
                    font.weight: Font.DemiBold
                    topPadding: 8 * S.u
                }
            }
            Row {
                spacing: 8 * S.u
                Rectangle {
                    visible: !!page.certification()
                    width: cert.implicitWidth + 10 * S.u
                    height: cert.implicitHeight + 2 * S.u
                    radius: 4 * S.u
                    color: "transparent"
                    border.color: S.text2
                    border.width: 1
                    anchors.verticalCenter: parent.verticalCenter
                    Text { id: cert; anchors.centerIn: parent; text: page.certification(); color: S.text2; font.family: S.font; font.pixelSize: 21 * S.u }
                }
                Text {
                    text: (page.certification() ? "|  " : "") + page.metaLine()
                    color: S.text2
                    font.family: S.font
                    font.pixelSize: 22 * S.u
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            // the buttons, as on the website: watchlist star, Play on Jellyfin, Watch Trailer,
            // Request, Approve / Decline (a pending request), Report an Issue
            Item { width: 1; height: 14 * S.u }
            FocusScope {
                id: buttons
                property bool stop: btnRow.visibleChildren.length > 0
                width: btnRow.width
                height: btnRow.height
                function shown() { return btnRow.children.filter(b => b.visible && b.clicked !== undefined); }
                function step(d) {
                    const b = shown(), i = b.findIndex(x => x.activeFocus);
                    if (i + d < 0 || i + d >= b.length) return false;
                    b[i + d].forceActiveFocus();
                    return true;
                }
                onActiveFocusChanged: if (activeFocus && !shown().some(b => b.activeFocus) && shown().length) shown()[page.firstButton()].forceActiveFocus()
                Keys.onLeftPressed: event => { event.accepted = step(-1); }
                Keys.onRightPressed: event => { event.accepted = step(1); }
                Row {
                    id: btnRow
                    spacing: 14 * S.u
                    SButton {
                        id: starBtn
                        visible: !!page.d
                        icon: page.d && page.d.onUserWatchlist ? "★" : "☆"
                        text: page.d && page.d.onUserWatchlist ? "On Watchlist" : "Watchlist"
                        onClicked: page.toggleWatchlist()
                    }
                    SButton {
                        id: playBtn
                        visible: page.status >= 4 && page.status <= 5 && !!page.info && !!page.info.jellyfinMediaId
                        icon: "▶"
                        text: "Play on Jellyfin"
                        onClicked: { S.call("POST", "/play/jellyfin", {id: page.info.jellyfinMediaId}, () => {}); S.toast("Opening in Jellyfin…"); }
                    }
                    SButton {
                        id: trailerBtn
                        visible: !!page.trailer()
                        icon: "▷"
                        text: "Watch Trailer"
                        onClicked: { S.call("POST", "/play/youtube", {id: page.trailer().key}, () => {}); S.toast("Opening the trailer in YouTube…"); }
                    }
                    SButton {
                        id: requestBtn
                        visible: page.canRequest()
                        kind: "primary"
                        icon: "⤓"
                        text: page.tv && page.status >= 2 ? "Request More" : "Request"
                        onClicked: S.openRequest(page.d)
                    }
                    SButton {
                        visible: page.pending().length > 0
                        kind: "success"
                        icon: "✓"
                        text: "Approve"
                        onClicked: page.decide("approve")
                    }
                    SButton {
                        visible: page.pending().length > 0
                        kind: "danger"
                        icon: "✕"
                        text: "Decline"
                        onClicked: page.decide("decline")
                    }
                    SButton {
                        visible: !!page.info && page.status >= 4 && page.status <= 5
                        kind: "warning"
                        icon: "⚠"
                        text: "Report an Issue"
                        onClicked: S.openIssue(page.d)
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------------ body: left column + facts
    Column {
        id: body
        y: header.y + header.height + 48 * S.u
        x: 0
        width: page.width - page.side - page.gap - S.edge
        spacing: 30 * S.u

        Text {
            width: parent.width
            visible: !!(page.d && page.d.tagline)
            text: page.d ? page.d.tagline || "" : ""
            wrapMode: Text.WordWrap
            color: S.text2
            font.family: S.font
            font.pixelSize: 32 * S.u
            font.italic: true
        }
        Column {
            width: parent.width
            spacing: 10 * S.u
            Text { text: "Overview"; color: S.text; font.family: S.font; font.pixelSize: 32 * S.u; font.weight: Font.Bold }
            Text {
                width: parent.width
                text: page.d ? page.d.overview || "No overview." : ""
                wrapMode: Text.WordWrap
                color: S.text2
                font.family: S.font
                font.pixelSize: 22 * S.u
                lineHeight: 1.25
            }
        }
        Grid {
            width: parent.width
            columns: 3
            rowSpacing: 28 * S.u
            columnSpacing: 0
            Repeater {
                model: page.d ? page.crew() : []
                Column {
                    width: body.width / 3
                    spacing: 4 * S.u
                    Text { text: modelData.job; color: S.text; font.family: S.font; font.pixelSize: 22 * S.u; font.weight: Font.DemiBold }
                    Text { text: modelData.name; color: S.text2; font.family: S.font; font.pixelSize: 22 * S.u }
                }
            }
        }
        Item {
            width: parent.width
            height: crewLink.height
            visible: !!(page.d && page.d.credits && page.d.credits.crew && page.d.credits.crew.length)
            Rectangle {
                id: crewLink
                property bool stop: parent.visible
                anchors.right: parent.right
                width: crewText.implicitWidth + 36 * S.u
                height: 50 * S.u
                radius: 10 * S.u
                color: activeFocus ? S.panel2 : "transparent"
                border.color: activeFocus ? S.focus : "transparent"
                border.width: 3 * S.u
                Text {
                    id: crewText
                    anchors.centerIn: parent
                    text: "View Full Crew  →"
                    color: S.text2
                    font.family: S.font
                    font.pixelSize: 22 * S.u
                }
                Keys.onReturnPressed: S.openPeople("Full Crew", "people/" + page.mediaType + "/" + page.tmdbId + "/crew")
                Keys.onEnterPressed: S.openPeople("Full Crew", "people/" + page.mediaType + "/" + page.tmdbId + "/crew")
            }
        }
        Flow {
            width: parent.width
            spacing: 10 * S.u
            Repeater {
                model: page.d && page.d.keywords ? page.d.keywords.slice(0, 24) : []
                Rectangle {
                    width: kw.implicitWidth + 28 * S.u
                    height: kw.implicitHeight + 12 * S.u
                    radius: height / 2
                    color: Qt.rgba(0.12, 0.16, 0.22, 0.8)
                    border.color: S.line
                    border.width: 1
                    Text { id: kw; anchors.centerIn: parent; text: "⌁ " + modelData.name; color: S.text2; font.family: S.font; font.pixelSize: 18 * S.u }
                }
            }
        }

        // seasons (shows): OK opens a season's episodes
        Column {
            width: parent.width
            spacing: 14 * S.u
            visible: page.tv && seasonModel.count > 0
            Text { text: "Seasons"; color: S.text; font.family: S.font; font.pixelSize: 32 * S.u; font.weight: Font.Bold }
            ListView {
                id: seasons
                property bool stop: true
                width: parent.width
                height: contentHeight
                interactive: false
                focus: true
                model: seasonModel
                spacing: 0
                keyNavigationEnabled: true
                delegate: Item {
                    id: row
                    required property int index
                    required property string k
                    required property int n
                    required property string name
                    required property int count
                    required property int st
                    required property bool open
                    required property string date
                    required property string text
                    required property string still
                    width: seasons.width
                    height: k === "season" ? 76 * S.u : 220 * S.u
                    Keys.onReturnPressed: if (k === "season") page.toggleSeason(index)
                    Keys.onEnterPressed: if (k === "season") page.toggleSeason(index)

                    Rectangle {                    // a season bar
                        visible: row.k === "season"
                        anchors { fill: parent; topMargin: 4 * S.u; bottomMargin: 4 * S.u }
                        radius: 8 * S.u
                        color: row.ListView.isCurrentItem && seasons.activeFocus ? S.panel2 : S.panel
                        border.color: row.ListView.isCurrentItem && seasons.activeFocus ? S.focus : S.line
                        border.width: row.ListView.isCurrentItem && seasons.activeFocus ? 3 * S.u : 1
                        Row {
                            anchors { left: parent.left; leftMargin: 18 * S.u; verticalCenter: parent.verticalCenter }
                            spacing: 12 * S.u
                            Text { text: row.name; color: S.text; font.family: S.font; font.pixelSize: 24 * S.u; anchors.verticalCenter: parent.verticalCenter }
                            Pill { text: row.count + " Episodes"; color: S.line; size: 15; anchors.verticalCenter: parent.verticalCenter }
                        }
                        Row {
                            anchors { right: parent.right; rightMargin: 18 * S.u; verticalCenter: parent.verticalCenter }
                            spacing: 16 * S.u
                            Pill { visible: row.st >= 2; text: S.statusName(row.st); color: S.statusColor(row.st); size: 16; anchors.verticalCenter: parent.verticalCenter }
                            Text { text: row.open ? "⌃" : "⌄"; color: S.dim; font.pixelSize: 32 * S.u; anchors.verticalCenter: parent.verticalCenter }
                        }
                    }
                    Item {                         // an episode
                        visible: row.k === "ep"
                        anchors { fill: parent; leftMargin: 18 * S.u; rightMargin: 18 * S.u }
                        Rectangle {
                            anchors { fill: parent; margins: -6 * S.u }
                            radius: 8 * S.u
                            color: "transparent"
                            border.color: S.focus
                            border.width: 3 * S.u
                            visible: row.ListView.isCurrentItem && seasons.activeFocus
                        }
                        Column {
                            anchors { left: parent.left; right: still.left; rightMargin: 24 * S.u; top: parent.top; topMargin: 14 * S.u }
                            spacing: 10 * S.u
                            Row {
                                spacing: 10 * S.u
                                Text { text: row.n + " - " + row.name; color: S.text; font.family: S.font; font.pixelSize: 23 * S.u }
                                Pill { visible: !!row.date; text: row.date; color: S.line; size: 15; anchors.verticalCenter: parent.verticalCenter }
                            }
                            Text {
                                width: parent.width
                                text: row.text
                                wrapMode: Text.WordWrap
                                maximumLineCount: 4
                                elide: Text.ElideRight
                                color: S.text2
                                font.family: S.font
                                font.pixelSize: 20 * S.u
                            }
                        }
                        Rectangle {
                            id: still
                            anchors { right: parent.right; top: parent.top; topMargin: 12 * S.u }
                            width: 300 * S.u
                            height: 169 * S.u
                            radius: 8 * S.u
                            color: S.panel
                            clip: true
                            visible: !!row.still
                            Image {
                                anchors.fill: parent
                                source: row.still ? S.img("/" + row.still.split("/").pop(), "w300") : ""
                                sourceSize.width: 300
                                asynchronous: true
                                fillMode: Image.PreserveAspectCrop
                            }
                        }
                        Rectangle { anchors { left: parent.left; right: parent.right; bottom: parent.bottom } height: 1; color: S.line }
                    }
                }
            }
        }
    }

    // the facts panel (and the collection, for movies)
    Column {
        id: factsCol
        x: page.width - page.side - S.edge
        y: body.y
        width: page.side
        spacing: 18 * S.u

        Rectangle {
            id: collection
            property bool stop: visible
            visible: !!(page.d && page.d.collection)
            width: parent.width
            height: 78 * S.u
            radius: 10 * S.u
            color: S.panel
            clip: true
            border.color: activeFocus ? S.focus : S.line
            border.width: activeFocus ? 3 * S.u : 1
            Image {
                anchors.fill: parent
                source: page.d && page.d.collection ? S.img(page.d.collection.backdropPath, "w780") : ""
                sourceSize.width: 500
                asynchronous: true
                fillMode: Image.PreserveAspectCrop
                opacity: 0.35
            }
            Text {
                anchors { left: parent.left; leftMargin: 16 * S.u; verticalCenter: parent.verticalCenter }
                text: page.d && page.d.collection ? page.d.collection.name : ""
                color: S.text
                font.family: S.font
                font.pixelSize: 22 * S.u
            }
            Rectangle {
                anchors { right: parent.right; rightMargin: 12 * S.u; verticalCenter: parent.verticalCenter }
                width: 66 * S.u; height: 38 * S.u; radius: 8 * S.u
                color: Qt.rgba(0.12, 0.16, 0.22, 0.9); border.color: S.line; border.width: 1
                Text { anchors.centerIn: parent; text: "View"; color: S.text; font.family: S.font; font.pixelSize: 18 * S.u }
            }
            Keys.onReturnPressed: S.openGrid(page.d.collection.name, "/collection/" + page.d.collection.id, "movie")
            Keys.onEnterPressed: S.openGrid(page.d.collection.name, "/collection/" + page.d.collection.id, "movie")
        }

        Rectangle {
            width: parent.width
            height: facts.height
            radius: 8 * S.u
            color: Qt.rgba(0.07, 0.09, 0.15, 0.6)
            border.color: S.line
            border.width: 1
            visible: !!page.d
            Column {
                id: facts
                width: parent.width
                Item {                              // ratings
                    width: parent.width
                    height: 68 * S.u
                    visible: !!page.ratings && (!!page.ratings.rt || !!page.ratings.imdb) || !!(page.d && page.d.voteAverage)
                    Row {
                        anchors.centerIn: parent
                        spacing: 22 * S.u
                        Rating {
                            visible: !!(page.ratings && page.ratings.rt && page.ratings.rt.criticsScore)
                            kind: page.ratings && page.ratings.rt && page.ratings.rt.criticsScore >= 60 ? "fresh" : "rotten"
                            value: page.ratings && page.ratings.rt ? page.ratings.rt.criticsScore + "%" : ""
                        }
                        Rating {
                            visible: !!(page.ratings && page.ratings.rt && page.ratings.rt.audienceScore)
                            kind: page.ratings && page.ratings.rt && page.ratings.rt.audienceScore >= 60 ? "popcorn" : "spilled"
                            value: page.ratings && page.ratings.rt ? page.ratings.rt.audienceScore + "%" : ""
                        }
                        Rating {
                            visible: !!(page.ratings && page.ratings.imdb && page.ratings.imdb.criticsScore)
                            kind: "imdb"
                            value: page.ratings && page.ratings.imdb ? String(page.ratings.imdb.criticsScore) : ""
                        }
                        Rating {
                            visible: !!(page.d && page.d.voteAverage)
                            kind: "tmdb"
                            value: page.d ? Math.round(page.d.voteAverage * 10) + "%" : ""
                        }
                    }
                }
                Repeater {
                    model: page.d ? page.facts() : []
                    Item {
                        width: facts.width
                        height: Math.max(60 * S.u, value.implicitHeight + 32 * S.u)
                        Rectangle { width: parent.width; height: 1; color: S.line }
                        Text {
                            id: label
                            anchors { left: parent.left; leftMargin: 20 * S.u; top: parent.top; topMargin: 17 * S.u }
                            text: modelData[0]; color: S.text; font.family: S.font; font.pixelSize: 20 * S.u; font.weight: Font.DemiBold
                        }
                        Text {
                            id: value
                            anchors { right: parent.right; rightMargin: 20 * S.u; top: parent.top; topMargin: 17 * S.u }
                            width: parent.width - label.implicitWidth - 48 * S.u
                            horizontalAlignment: Text.AlignRight
                            wrapMode: Text.WordWrap
                            text: modelData[1]; color: S.dim; font.family: S.font; font.pixelSize: 20 * S.u
                            lineHeight: 1.15
                        }
                    }
                }
                Item {                              // where it's streaming (US)
                    width: facts.width
                    height: visible ? provTitle.height + provFlow.height + 34 * S.u : 0
                    visible: page.providers().length > 0
                    Rectangle { width: parent.width; height: 1; color: S.line }
                    Text {
                        id: provTitle
                        x: 16 * S.u; y: 13 * S.u
                        text: "Currently Streaming On"; color: S.text; font.family: S.font; font.pixelSize: 20 * S.u; font.weight: Font.DemiBold
                    }
                    Flow {
                        id: provFlow
                        x: 16 * S.u
                        anchors.top: provTitle.bottom
                        anchors.topMargin: 10 * S.u
                        width: parent.width - 32 * S.u
                        spacing: 12 * S.u
                        Repeater {
                            model: page.providers()
                            Rectangle {
                                width: 52 * S.u; height: 52 * S.u; radius: 10 * S.u; color: S.panel; clip: true
                                Image { anchors.fill: parent; source: S.img(modelData.logoPath, "w92"); sourceSize.width: 92; asynchronous: true }
                            }
                        }
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------------ rows
    Column {
        y: Math.max(body.y + body.height, factsCol.y + factsCol.height) + 60 * S.u
        width: page.width
        spacing: 34 * S.u
        Shelf {
            title: "Cast"
            kind: "people"
            items: page.d && page.d.credits ? page.d.credits.cast.slice(0, 20) : []
            more: page.d && page.d.credits && page.d.credits.cast.length > 20 ? "people/" + page.mediaType + "/" + page.tmdbId + "/cast" : ""
            visible: count > 0
        }
        Shelf {
            id: recs
            title: "Recommendations"
            path: page.d ? "/" + page.mediaType + "/" + page.tmdbId + "/recommendations" : ""
            mediaType: page.mediaType
            maxPages: 1
        }
        Shelf {
            title: page.tv ? "Similar Series" : "Similar Titles"
            path: page.d ? "/" + page.mediaType + "/" + page.tmdbId + "/similar" : ""
            mediaType: page.mediaType
            maxPages: 1
        }
    }
}
