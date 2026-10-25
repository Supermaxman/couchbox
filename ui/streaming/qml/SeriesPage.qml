// A show (or season, collection, movie), like the website's page for it: artwork, logo,
// seasons and description, Play / Continue, My List, Trailer; season tabs and the season's
// episodes. Collections show their videos; a season opens its show at that season.
import QtQuick

VPage {
    id: page
    property var cid: 0
    property var seasonId: 0                 // open at this season
    property var focusVideo: 0               // ... with this episode selected
    property bool autoplay: false            // "Watch Now" from the banner: start playing
    property var s: null                     // the series / collection card
    property int seasonAt: 0
    property bool onList: false
    property bool loadingEps: false
    ListModel { id: eps }

    function load(id) {
        D.call("collection", {id: id}, r => {
            if (r.kind === "season" && r.seriesId) {      // a season: show its series, at it
                seasonId = r.id;
                return load(r.seriesId);
            }
            s = r;
            D.call("onWatchlist", {id: r.id}, w => onList = w.on);
            if (r.kind === "series" && (r.seasonList || []).length) {
                const i = r.seasonList.findIndex(x => x.id === seasonId);
                pickSeason(i >= 0 ? i : 0);
            } else {
                loadEpisodes(r.id);
            }
        }, err => D.toast(err));
    }
    Component.onCompleted: load(cid)
    // back from the player: progress changed (keep the selected episode)
    function returned() {
        if (!s) return;
        focusVideo = epList.currentItem && epList.currentItem.c ? epList.currentItem.c.id : 0;
        loadEpisodes(s.kind === "series" && s.seasonList && s.seasonList.length ? s.seasonList[seasonAt].id : s.id);
    }

    function pickSeason(i) {
        seasonAt = i;
        loadEpisodes(s.seasonList[i].id);
    }
    function loadEpisodes(id) {
        eps.clear();
        loadingEps = true;
        D.call("collectionItems", {id: id}, r => {
            for (const c of r.items || []) eps.append({j: JSON.stringify(c)});
            loadingEps = false;
            const f = focusVideo ? r.items.findIndex(c => c.id === focusVideo) : -1;
            epList.currentIndex = f >= 0 ? f : 0;
            epList.positionViewAtIndex(epList.currentIndex, ListView.Beginning);
            if (f >= 0) Qt.callLater(() => epList.forceActiveFocus());
            if (autoplay) { autoplay = false; const t = target(); if (t) D.play(t.id); }
        }, () => loadingEps = false);
    }
    // what Play does: the episode in progress, else the first not watched, else the first
    function target() {
        const all = [];
        for (let i = 0; i < eps.count; i++) all.push(JSON.parse(eps.get(i).j));
        const vids = all.filter(c => c.kind === "video");
        return vids.find(c => c.progress > 0 && !c.completed) || vids.find(c => !c.completed) || vids[0] || null;
    }
    readonly property var next: eps.count >= 0 && !loadingEps ? target() : null
    // "S2 · E1" by the season tabs' numbering (what's on screen), not Dropout's franchise-wide one
    function playLabel() {
        if (!next || !next.episode) return "";
        const sl = s && s.seasonList ? s.seasonList : [];
        return sl.length > 1 ? "  S" + (sl[seasonAt].number || seasonAt + 1) + " · E" + next.episode : "  E" + next.episode;
    }

    // ------------------------------------------------------------------ artwork
    Item {
        id: art
        width: page.width
        height: 960 * D.u
        Image {
            anchors { right: parent.right; top: parent.top }
            width: parent.width * 0.78
            height: width * 9 / 16
            source: page.s ? D.img(page.s.background || page.s.landscape, 1600, 0) : ""
            sourceSize.width: 1600
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            opacity: status === Image.Ready ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 300 } }
            Rectangle {
                anchors.fill: parent
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: D.bg }
                    GradientStop { position: 0.35; color: Qt.rgba(0, 0, 0, 0.55) }
                    GradientStop { position: 1.0; color: Qt.rgba(0, 0, 0, 0.1) }
                }
            }
            Rectangle {
                anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                height: parent.height * 0.45
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 1.0; color: D.bg }
                }
            }
        }
    }

    // ------------------------------------------------------------------ header
    Column {
        id: header
        x: D.edge
        y: 150 * D.u
        width: page.width * 0.48
        spacing: 26 * D.u
        Image {
            id: logo
            visible: !!(page.s && page.s.logo) && status === Image.Ready
            source: page.s ? D.img(page.s.logo, 760, 0) : ""
            sourceSize.width: 760
            width: Math.min(640 * D.u, implicitWidth)
            height: Math.min(250 * D.u, width * implicitHeight / Math.max(1, implicitWidth))
            fillMode: Image.PreserveAspectFit
            horizontalAlignment: Image.AlignLeft
            asynchronous: true
        }
        Text {
            visible: !logo.visible
            width: parent.width
            text: page.s ? page.s.title : ""
            wrapMode: Text.WordWrap
            color: D.text
            font.family: D.font
            font.pixelSize: 60 * D.u
            font.weight: Font.Black
        }
        Text {
            text: page.s && page.s.meta ? page.s.meta : page.s ? [page.s.kind === "series" && page.s.seasons ? page.s.seasons + (page.s.seasons === 1 ? " Season" : " Seasons") : "",
                            page.s.items && page.s.kind !== "series" ? page.s.items + " Videos" : ""].filter(x => x).join("  ·  ") : ""
            visible: !!text
            color: D.accent
            font.family: D.font
            font.pixelSize: 24 * D.u
            font.weight: Font.Bold
            font.capitalization: Font.AllUppercase
            font.letterSpacing: 1.5 * D.u
        }
        Text {
            width: parent.width
            text: page.s ? page.s.longDescription : ""
            wrapMode: Text.WordWrap
            maximumLineCount: 5
            elide: Text.ElideRight
            color: D.text2
            font.family: D.font
            font.pixelSize: 24 * D.u
            lineHeight: 1.25
        }
        Item { width: 1; height: 6 * D.u }
        FocusScope {
            id: buttons
            property bool stop: !!page.s
            width: row.width
            height: row.height
            Row {
                id: row
                spacing: 18 * D.u
                DButton {
                    id: playBtn
                    focus: true
                    visible: !!page.next
                    icon: "▶"
                    text: page.next && page.next.live ? "Watch Live" : page.next ? (page.next.progress > 0 ? "Continue" : "Play") + page.playLabel() : "Play"
                    onClicked: D.play(page.next.id)
                    KeyNavigation.right: listBtn.visible ? listBtn : trailerBtn
                }
                DButton {
                    id: listBtn
                    visible: !D.site.no_list_button
                    icon: page.onList ? "✓" : "+"
                    // "My List", or the site's own words (Twitch: Follow / Following)
                    text: D.site.list_label ? D.site.list_label[page.onList ? 1 : 0] : "My List"
                    onClicked: {
                        const on = page.onList;
                        D.call("watchlist", {op: on ? "remove" : "add", kind: page.s.kind, id: page.s.id}, () => {
                            page.onList = !on;
                            D.toast(D.site.list_toast ? D.site.list_toast[on ? 1 : 0].replace("{}", page.s.title)
                                                      : on ? "Removed from My List." : "Added to My List.");
                        }, err => D.toast(err));
                    }
                    KeyNavigation.left: playBtn.visible ? playBtn : null
                    KeyNavigation.right: trailerBtn.visible ? trailerBtn : null
                }
                DButton {
                    id: trailerBtn
                    visible: !!(page.s && page.s.trailer)
                    text: "Trailer"
                    onClicked: D.play(parseInt(page.s.trailer))
                    KeyNavigation.left: listBtn.visible ? listBtn : playBtn
                }
            }
            onActiveFocusChanged: if (activeFocus && !playBtn.activeFocus && !listBtn.activeFocus && !trailerBtn.activeFocus) (playBtn.visible ? playBtn : listBtn.visible ? listBtn : trailerBtn).forceActiveFocus()
            // Play shows up once the episodes are in: move there if My List only had focus for lack of it
            Connections { target: page; function onNextChanged() { if (page.next && listBtn.activeFocus && !page.touched) playBtn.forceActiveFocus(); } }
        }
    }

    // ------------------------------------------------------------------ seasons + episodes
    Column {
        y: Math.max(header.y + header.height + 70 * D.u, 640 * D.u)
        width: page.width
        spacing: 30 * D.u

        FocusScope {                          // season tabs: Left/Right pick one
            id: tabs
            property bool stop: visible
            visible: !!(page.s && page.s.seasonList && page.s.seasonList.length > 1)
            width: page.width
            height: 60 * D.u
            ListView {
                id: tabRow
                anchors.fill: parent
                orientation: ListView.Horizontal
                interactive: false
                spacing: 14 * D.u
                leftMargin: D.edge
                rightMargin: D.edge
                currentIndex: page.seasonAt
                highlightMoveDuration: 200
                highlightRangeMode: ListView.ApplyRange
                preferredHighlightBegin: D.edge
                preferredHighlightEnd: width - D.edge - 300 * D.u
                model: page.s && page.s.seasonList ? page.s.seasonList : []
                delegate: Rectangle {
                        required property var modelData
                        required property int index
                        readonly property bool here: index === page.seasonAt
                        width: tabText.implicitWidth + 48 * D.u
                        height: 60 * D.u
                        radius: 30 * D.u
                        color: tabs.activeFocus && here ? D.accent : here ? Qt.rgba(1, 1, 1, 0.92) : Qt.rgba(1, 1, 1, 0.1)
                        Text {
                            id: tabText
                            anchors.centerIn: parent
                            text: modelData.name
                            color: parent.here ? (tabs.activeFocus ? D.accentInk : "#111111") : D.text
                            font.family: D.font
                            font.pixelSize: 23 * D.u
                            font.weight: Font.Bold
                        }
                    }
            }
            Keys.onLeftPressed: event => { event.accepted = page.seasonAt > 0; if (event.accepted) page.pickSeason(page.seasonAt - 1); }
            Keys.onRightPressed: event => { event.accepted = page.seasonAt < page.s.seasonList.length - 1; if (event.accepted) page.pickSeason(page.seasonAt + 1); }
            Keys.onReturnPressed: epList.forceActiveFocus()
        }

        Text {
            x: D.edge
            visible: !tabs.visible && eps.count > 0
            text: page.s && page.s.kind === "series" && page.s.seasonList && page.s.seasonList.length ? page.s.seasonList[0].name : "Videos"
            color: D.text
            font.family: D.font
            font.pixelSize: 31 * D.u
            font.weight: Font.Black
        }

        ListView {
            id: epList
            property bool stop: count > 0
            width: page.width
            height: D.epH + 190 * D.u
            orientation: ListView.Horizontal
            spacing: D.gap
            leftMargin: D.edge
            rightMargin: D.edge
            model: eps
            focus: true
            cacheBuffer: 2000
            highlightMoveDuration: 200
            highlightRangeMode: ListView.ApplyRange
            preferredHighlightBegin: D.edge
            preferredHighlightEnd: width - D.edge - D.epW
            boundsBehavior: Flickable.StopAtBounds
            delegate: Loader {
                required property string j
                readonly property var c: JSON.parse(j)
                y: 10 * D.u
                focus: ListView.isCurrentItem
                sourceComponent: c.kind === "video" ? epC : cardC
                Component { id: epC; EpisodeCard { focus: true; c: parent ? parent.c : ({}) } }
                Component { id: cardC; Card { focus: true; c: parent ? parent.c : ({}); shape: "wide" } }
            }
            Text {
                visible: page.loadingEps
                x: D.edge
                y: 80 * D.u
                text: "Loading episodes…"
                color: D.dim
                font.family: D.font
                font.pixelSize: 24 * D.u
            }
        }
    }
}
