// An album, a playlist or Liked Songs: the cover and buttons on the left (Play, Shuffle, Save,
// more), the songs on the right. Left/Right move between the buttons and the songs.
import QtQuick

FocusScope {
    id: page
    property var item: ({})                  // what was opened (a card): kind, id, uri, name...
    property var d: ({})                     // the full thing from the back end
    property bool loading: true
    property int zone: 0                     // 0 buttons, 1 songs
    property int btn: 0
    signal leftEdge()
    readonly property var tracks: d.tracks || []
    readonly property string ctx: d.context || d.uri || ""
    readonly property bool saved: !!S.liked[d.uri]
    readonly property string title: (d && d.name) || (item && item.name) || ""
    readonly property var buttons: {
        const b = [{id: "play", icon: "play-dark", primary: true}, {id: "shuffle", icon: "shuffle"}];
        if (d.kind === "album") b.push({id: "save", icon: saved ? "heart-filled" : "heart"});
        if (tracks.length) b.push({id: "more", icon: "more"});
        return b;
    }
    function load() {
        loading = true; d = ({}); zone = 0; btn = 0;
        S.call("detail", {item: item}, r => {
            page.d = r; page.loading = false;
            if (r.kind === "album") S.check([r.uri]);
        }, e => { page.loading = false; S.toast(e); });
    }
    onItemChanged: if (item && item.kind) Qt.callLater(load)
    function press(id) {
        if (id === "play") S.play({context: ctx});
        else if (id === "shuffle") S.play({context: ctx, shuffle: true});
        else if (id === "save") S.call("save", {uris: [d.uri], on: !saved}, () => { S.setLiked(d.uri, !saved); S.toast(saved ? "Saved to Your Library." : "Removed from Your Library."); });
        else if (id === "more") S.menu(Object.assign({}, d, {tracksUris: tracks.map(t => t.uri)}), {context: ctx});
    }
    Keys.onLeftPressed: { if (zone === 1) { zone = 0; } else if (btn > 0) btn--; else leftEdge(); }
    Keys.onRightPressed: { if (zone === 0) { if (btn < buttons.length - 1) btn++; else if (tracks.length) { zone = 1; songs.forceActiveFocus(); } } }
    Keys.onDownPressed: if (zone === 0 && tracks.length) { zone = 1; songs.forceActiveFocus(); }
    Keys.onReturnPressed: if (zone === 0) press(buttons[btn].id)
    Keys.onEnterPressed: if (zone === 0) press(buttons[btn].id)
    onZoneChanged: if (zone === 0) { songs.focus = false; page.forceActiveFocus(); }

    Item {
        id: left
        x: 0; y: 60 * S.u
        width: 560 * S.u; height: parent.height - y
        Art { id: cover; width: 480 * S.u; height: width; item: page.d.kind ? page.d : page.item }
        Text { id: kindText; anchors { top: cover.bottom; topMargin: 30 * S.u }
               text: S.kindLabel(page.d.kind ? page.d : page.item).toUpperCase(); color: S.dim; font.family: S.font; font.pixelSize: S.tSmall; font.weight: Font.Bold; font.letterSpacing: 2 * S.u }
        Text { id: titleText; anchors.top: kindText.bottom; anchors.topMargin: 8 * S.u; width: cover.width
               text: page.title; wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
               color: S.text; font.family: S.font; font.pixelSize: 44 * S.u; font.weight: Font.Bold }
        Text { id: metaText; anchors.top: titleText.bottom; anchors.topMargin: 10 * S.u; width: cover.width
               text: page.d.kind === "album" ? [S.artists(page.d), page.d.year, page.tracks.length + " songs"].filter(v => v).join(" · ")
                     : page.d.kind ? [page.d.owner ? "By " + page.d.owner : "", page.tracks.length ? page.tracks.length + " songs" : ""].filter(v => v).join(" · ") : ""
               wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
               color: S.dim; font.family: S.font; font.pixelSize: S.tMeta }
        Row {
            anchors { top: metaText.bottom; topMargin: 30 * S.u }
            spacing: 22 * S.u
            Repeater {
                model: page.buttons
                delegate: SButton {
                    required property var modelData
                    required property int index
                    anchors.verticalCenter: parent.verticalCenter
                    icon: modelData.icon
                    primary: !!modelData.primary
                    on: modelData.id === "save" && page.saved
                    current: page.activeFocus && page.zone === 0 && page.btn === index
                }
            }
        }
    }
    Item {
        anchors { left: left.right; leftMargin: 30 * S.u; right: parent.right; rightMargin: S.edge; top: parent.top; topMargin: 60 * S.u; bottom: parent.bottom }
        Text {
            visible: page.loading || (!page.tracks.length && !!page.d.kind)
            width: parent.width * 0.8; wrapMode: Text.WordWrap
            text: page.loading ? "Loading…" : page.d.note || "No songs here yet."
            color: S.dim; font.family: S.font; font.pixelSize: S.tBody
        }
        TrackList {
            id: songs
            anchors.fill: parent
            items: page.tracks
            contextUri: page.ctx
            showArt: page.d.kind !== "album"
            showAlbum: page.d.kind !== "album"
            maxRows: Math.max(1, Math.floor(height / rowH))
            onLeftEdge: page.zone = 0
            onUpEdge: page.zone = 0
        }
    }
}
