// Shorts, as YouTube's TV app plays them: the vertical video in the middle (on its own colours),
// and on the right its title, the next Short, the channel, Subscribe, and like, comments, remix
// and more. Down plays the next Short, Up the one before; OK pauses; Right goes to the buttons;
// Back leaves. Each Short loops until Down.
import QtQuick

FocusScope {
    id: page
    objectName: "shorts"
    property string startId: ""                // opened from a card: that Short first
    property var items: []                     // [{id, thumb, color}]
    property string more: ""
    property int index: 0
    property string problem: ""                // nothing to play: why
    property int emptyTries: 0                 // batches in a row with no new Shorts
    property var info: ({})                    // the current Short's title, channel... (short)
    property var nextInfo: ({})
    property var s: null                       // its stream
    property string area: "video"              // video | side
    property int side: 0                       // 0 Subscribe, 1 like, 2 comments, 3 remix, 4 more
    readonly property var video: Y.video
    readonly property var cur: items[index] || ({})
    readonly property string label: info.title || "Shorts"
    readonly property bool watching: !!s && !video.paused
    readonly property rect place: Qt.rect(592 * Y.u, 8 * Y.u, 609 * Y.u, 1064 * Y.u)
    readonly property string videoId: cur.id || ""
    function focusDetail() { return {videoId: videoId, index: index, area: area}; }
    signal closed()

    Component.onCompleted: {
        Y.videoRect = place;
        if (startId) { items = [{type: "short", id: startId, thumb: "", color: ""}]; play(0); }
        loadMore();
    }
    Component.onDestruction: { Y.videoRect = Qt.rect(0, 0, 0, 0); video.stop(); }
    // A batch can come back empty with more to follow (signed in, the first one often does): ask
    // again a few times before saying there's nothing.
    function loadMore() {
        Y.call("shorts", {token: more}, r => {
            if (!page) return;
            const add = (r.items || []).filter(x => !items.some(y => y.id === x.id));
            items = items.concat(add);
            more = r.more || "";
            emptyTries = add.length ? 0 : emptyTries + 1;
            if (!s && items.length) play(0);
            else if (!items.length && more && emptyTries < 4) loadMore();
            else if (!items.length) problem = "No Shorts to show right now.";
            fetchNext();
        }, e => { if (page && !items.length) problem = e; });
    }
    function play(i) {
        if (i < 0 || i >= items.length) return;
        index = i;
        s = null;
        info = {};
        const id = items[i].id;
        Y.call("stream", {id: id}, r => { if (!page || page.videoId !== id) return; page.s = r; video.loadWith(r.url, 0, "loop-file=inf"); });
        Y.call("short", {id: id}, r => { if (page && page.videoId === id) page.info = r; }, () => {});
        fetchNext();
        if (items.length - i < 4 && more) loadMore();
    }
    function fetchNext() {
        const n = items[index + 1];
        nextInfo = {};
        if (n) Y.call("prefetch", {id: n.id}, () => {}, () => {});          // Down plays it: its stream now
        if (n) Y.call("short", {id: n.id}, r => { if (page && page.items[page.index + 1] && page.items[page.index + 1].id === n.id) page.nextInfo = r; }, () => {});
    }

    Keys.onPressed: e => {
        const k = e.key;
        if (k === Qt.Key_Escape || k === Qt.Key_Back) { if (area === "side") area = "video"; else closed(); }
        else if (k === Qt.Key_MediaTogglePlayPause || k === Qt.Key_MediaPlay || k === Qt.Key_MediaPause) video.togglePause();
        else if (area === "video") {
            if (k === Qt.Key_Down) play(index + 1);
            else if (k === Qt.Key_Up) play(index - 1);
            else if (k === Qt.Key_Right) { area = "side"; side = Y.signedIn && !info.subscribed ? 0 : 1; }
            else if (k === Qt.Key_Return || k === Qt.Key_Enter) video.togglePause();
            else return;
        } else {
            if (k === Qt.Key_Left) { if (side <= 1) area = "video"; else side--; }
            else if (k === Qt.Key_Right) side = Math.min(4, side + 1);
            else if (k === Qt.Key_Up) side = 0;
            else if (k === Qt.Key_Down) side = Math.max(1, side);
            else if (k === Qt.Key_Return || k === Qt.Key_Enter) act();
            else return;
        }
        e.accepted = true;
    }
    function act() {
        if (side === 0) {
            if (!Y.signedIn) return Y.toast("Sign in to subscribe: the guide's picture, then Add account.");
            const on = !info.subscribed;
            Y.call("subscribe", {id: info.channelId, on: on}, () => { if (page) page.info = Object.assign({}, page.info, {subscribed: on}); });
        } else if (side === 1) {
            if (!Y.signedIn) return Y.toast("Sign in to like Shorts.");
            const now = info.like === "like" ? "none" : "like";
            Y.call("like", {id: videoId, status: now}, () => { if (page) page.info = Object.assign({}, page.info, {like: now}); });
        } else if (side === 2) Y.toast("Comments on Shorts come in a later update.");
        else if (side === 3) Y.toast("Remixing isn't on TVs.");
        else Y.toast("More options come in a later update.");
    }

    // ------------------------------------------------------------------ the look
    // the Short's own colours around it (the video, under this page, shows through the middle)
    readonly property color tint: page.cur.color || "#3b2f29"
    Repeater {
        model: [Qt.rect(0, 0, page.place.x - 8 * Y.u, page.height),
                Qt.rect(page.place.x + page.place.width + 8 * Y.u, 0, page.width - page.place.x - page.place.width - 8 * Y.u, page.height),
                Qt.rect(page.place.x - 8 * Y.u, 0, page.place.width + 16 * Y.u, page.place.y - 8 * Y.u),
                Qt.rect(page.place.x - 8 * Y.u, page.place.y + page.place.height + 8 * Y.u, page.place.width + 16 * Y.u, page.height)]
        Rectangle {                            // its colour, strongest by the video, darker to the screen's sides
            required property rect modelData
            required property int index
            x: modelData.x; y: modelData.y; width: modelData.width; height: Math.max(0, modelData.height)
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: index === 1 ? Qt.lighter(page.tint, 1.07) : index === 0 ? Qt.darker(page.tint, 1.5) : Qt.lighter(page.tint, 1.07) }
                GradientStop { position: 1; color: index === 0 ? Qt.lighter(page.tint, 1.07) : index === 1 ? Qt.darker(page.tint, 1.5) : Qt.lighter(page.tint, 1.07) }
            }
        }
    }
    Corners {                                  // the ambient colour into the frame's rounded corners
        x: page.place.x - 8 * Y.u; y: page.place.y - 8 * Y.u
        width: page.place.width + 16 * Y.u; height: page.place.height + 16 * Y.u
        r: 36 * Y.u
        color: Qt.lighter(page.tint, 1.07)
    }
    Rectangle {                                // the frame (white with the focus)
        id: frame
        x: page.place.x - 8 * Y.u; y: page.place.y - 8 * Y.u
        width: page.place.width + 16 * Y.u; height: page.place.height + 16 * Y.u
        radius: 36 * Y.u
        color: "transparent"
        border.width: 8 * Y.u
        border.color: page.area === "video" && page.activeFocus ? Y.text : "#7a6f69"
    }
    Rectangle {                                // while it starts: its picture (or its colours, the demo)
        x: page.place.x; y: page.place.y; width: page.place.width; height: page.place.height
        visible: !page.s || !hasVideo
        gradient: Gradient {
            GradientStop { position: 0; color: Qt.hsla(Y.hue(page.info.title || page.cur.id), 0.4, 0.3, 1) }
            GradientStop { position: 1; color: Qt.hsla((Y.hue(page.info.title || page.cur.id) + 0.2) % 1, 0.5, 0.1, 1) }
        }
        Image {
            anchors.fill: parent
            source: page.cur.thumb || ""
            fillMode: Image.PreserveAspectCrop
            sourceSize: Y.sz(width, height)
            asynchronous: true
        }
        Text {
            anchors.centerIn: parent
            visible: !page.s && !page.cur.thumb
            text: page.problem || (page.items.length ? "Loading…" : "Finding Shorts…")
            color: Y.dim; font.family: Y.font; font.pixelSize: 30 * Y.u
        }
    }
    Corners {                                  // the video's rounded corners, in the frame's colour
        x: page.place.x; y: page.place.y; width: page.place.width; height: page.place.height
        r: 28 * Y.u
        color: frame.border.color
        z: 1
    }

    Column {                                   // the right: title, next, channel, Subscribe, buttons
        x: 1278 * Y.u
        width: 580 * Y.u
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 96 * Y.u
        spacing: 34 * Y.u
        Text {
            width: parent.width
            text: page.info.title || ""
            color: Y.text; font.family: Y.font; font.pixelSize: 32 * Y.u; font.weight: Font.Bold
            lineHeightMode: Text.FixedHeight; lineHeight: 48 * Y.u
            wrapMode: Text.WordWrap; maximumLineCount: 3; elide: Text.ElideRight
        }
        Row {
            visible: !!page.nextInfo.title
            x: 7 * Y.u                         // (YouTube's sits a little right of the title)
            spacing: 22 * Y.u
            Icon { name: "play"; size: 40 * Y.u; color: Y.text; anchors.verticalCenter: parent.verticalCenter }
            Text { width: 500 * Y.u; text: page.nextInfo.title || ""; color: Y.text; font.family: Y.font; font.pixelSize: 30 * Y.u; elide: Text.ElideRight; anchors.verticalCenter: parent.verticalCenter }
        }
        Row {
            spacing: 18 * Y.u
            RoundImage { width: 54 * Y.u; height: width; source: page.info.avatar || ""; fallback: page.info.handle ? page.info.handle.slice(1) : ""; anchors.verticalCenter: parent.verticalCenter }
            Text { text: page.info.handle || ""; color: Y.text; font.family: Y.font; font.pixelSize: 30 * Y.u; font.weight: Font.Medium; anchors.verticalCenter: parent.verticalCenter }
        }
        Rectangle {                            // Subscribe / Subscribed
            readonly property bool on: page.area === "side" && page.side === 0 && page.activeFocus
            width: subRow.implicitWidth + 44 * Y.u; height: 72 * Y.u; radius: height / 2
            x: -13 * Y.u
            color: on ? Y.text : "transparent"
            Row {
                id: subRow
                anchors.centerIn: parent
                spacing: 26 * Y.u
                Icon { name: page.info.subscribed ? "check" : "plus"; size: 38 * Y.u; color: parent.parent.on ? Y.ink : Y.text; anchors.verticalCenter: parent.verticalCenter }
                Text { text: page.info.subscribed ? "Subscribed" : "Subscribe"; color: parent.parent.on ? Y.ink : Y.text; font.family: Y.font; font.pixelSize: 30 * Y.u; font.weight: Font.Medium; anchors.verticalCenter: parent.verticalCenter }
            }
        }
        Row {
            x: -8 * Y.u
            spacing: 24 * Y.u
            Repeater {
                model: [page.info.like === "like" ? "heart-filled" : "heart", "comments-round", "remix", "more"]
                CtlButton {
                    required property string modelData
                    required property int index
                    icon: modelData
                    plain: true
                    weight: 1.9                // outlines, as YouTube's
                    on: page.area === "side" && page.side === index + 1 && page.activeFocus
                }
            }
        }
    }
}
