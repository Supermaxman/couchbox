// Now Playing, full screen: the cover, the song and artists, progress, and the controls
// (shuffle, previous, play/pause, next, repeat, like, add to a playlist), with what's up next.
// Left/Right move between controls, OK presses, Up/Down go to the queue, Back closes.
import QtQuick

FocusScope {
    id: np
    signal closed()
    signal addToPlaylist(var track)
    property int btn: 2
    property bool inQueue: false
    property int qIdx: 0
    readonly property var item: S.now.item || null
    readonly property var info: S.nowInfo || ({})
    readonly property real dur: info.duration || ((((S.now.item || {}).decorations || {}).playback || {}).duration_ms || 0) / 1000
    property real pos: 0
    readonly property var controls: ["shuffle", "prev", "play", "next", "repeat", "like", "add"]
    readonly property bool liked: !!S.liked[S.nowUri]

    Timer { interval: 500; repeat: true; running: np.visible; triggeredOnStart: true; onTriggered: np.pos = np.position() }
    function position() {
        const n = S.now;
        if (!n.timestamp_ms) return (n.position_ms || 0) / 1000;
        return Math.min(np.dur || 1e9, (n.position_ms + Math.max(0, Date.now() - n.timestamp_ms) * (n.speed || 0)) / 1000);
    }
    function press(c) {
        if (c === "play") S.media("toggle");
        else if (c === "prev") S.media("previous");
        else if (c === "next") S.media("next");
        else if (c === "shuffle") S.media("shuffle", S.now.shuffle ? 0 : 1);
        else if (c === "repeat") S.media("repeat", S.now.repeat === "off" ? 1 : S.now.repeat === "context" ? 2 : 0);
        else if (c === "like" && S.nowUri) S.call("save", {uris: [S.nowUri], on: !liked}, () => { S.setLiked(S.nowUri, !liked); S.toast(liked ? "Added to Liked Songs." : "Removed from Liked Songs."); });
        else if (c === "add" && S.nowUri) np.addToPlaylist(Object.assign({uri: S.nowUri, kind: "track"}, np.info));
    }
    Keys.onLeftPressed: { if (inQueue) inQueue = false; else btn = Math.max(0, btn - 1); }
    Keys.onRightPressed: { if (!inQueue) { if (btn < controls.length - 1) btn++; else if ((S.now.queue || []).length) inQueue = true; } }
    Keys.onUpPressed: { if (inQueue) qIdx = Math.max(0, qIdx - 1); }
    Keys.onDownPressed: { if (inQueue) qIdx = Math.min((S.now.queue || []).length - 1, qIdx + 1); else if ((S.now.queue || []).length) inQueue = true; }
    Keys.onReturnPressed: inQueue ? S.play({uris: (S.now.queue || []).slice(qIdx).map(q => q.uri).filter(u => u.startsWith("spotify:track:"))}) : press(controls[btn])
    Keys.onEnterPressed: inQueue ? S.play({uris: (S.now.queue || []).slice(qIdx).map(q => q.uri).filter(u => u.startsWith("spotify:track:"))}) : press(controls[btn])
    Keys.onEscapePressed: closed()
    Keys.onBackPressed: closed()
    onVisibleChanged: if (visible) { btn = 2; inQueue = false; if (S.nowUri) S.check([S.nowUri]); }

    Rectangle { anchors.fill: parent; color: S.bg }
    Rectangle {                                  // the cover's colour washing down the screen
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0; color: Qt.darker(S.tint(np.info.album ? np.info.album.name : (np.info.name || "")), 1.4) }
            GradientStop { position: 0.75; color: S.bg }
        }
        opacity: 0.9
    }
    Art {
        id: cover
        x: 120 * S.u; anchors.verticalCenter: parent.verticalCenter; anchors.verticalCenterOffset: -40 * S.u
        width: 540 * S.u; height: width
        item: ({kind: "album", name: (np.info.album || {}).name || np.info.name || "", image: np.info.imageLarge || np.info.image || ""})
    }
    Column {
        id: infoCol
        anchors { left: cover.right; leftMargin: 70 * S.u; right: queueBox.left; rightMargin: 50 * S.u; top: cover.top; topMargin: 10 * S.u }
        spacing: 16 * S.u
        Text { text: S.now.context && S.now.context.decorations ? "PLAYING FROM " + ((S.now.context.decorations.identity || {}).name || "").toUpperCase() : (S.status.device ? "ON " + S.status.device.toUpperCase() : "")
               width: parent.width; elide: Text.ElideRight; color: S.dim; font.family: S.font; font.pixelSize: S.tSmall; font.weight: Font.Bold; font.letterSpacing: 2 * S.u }
        Text { width: parent.width; text: np.info.name || ((((np.item || {}).decorations || {}).identity || {}).name) || (S.now.logged_in ? "Nothing playing" : "Not connected")
               wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
               color: S.text; font.family: S.font; font.pixelSize: 64 * S.u; font.weight: Font.Bold }
        Text { width: parent.width; text: S.artists(np.info); elide: Text.ElideRight; color: S.text2; font.family: S.font; font.pixelSize: 34 * S.u }
        Text { width: parent.width; text: (np.info.album || {}).name || ""; elide: Text.ElideRight; color: S.dim; font.family: S.font; font.pixelSize: S.tBody }
    }
    Item {
        id: progress
        anchors { left: infoCol.left; right: infoCol.right; top: infoCol.bottom; topMargin: 50 * S.u }
        height: 60 * S.u
        Rectangle { id: track; width: parent.width; height: 8 * S.u; radius: 4 * S.u; color: "#40ffffff"
            Rectangle { width: np.dur > 0 ? parent.width * Math.min(1, np.pos / np.dur) : 0; height: parent.height; radius: 4 * S.u; color: S.text } }
        Text { anchors { left: parent.left; top: track.bottom; topMargin: 12 * S.u } text: S.mmss(np.pos); color: S.dim; font.family: S.font; font.pixelSize: S.tSmall }
        Text { anchors { right: parent.right; top: track.bottom; topMargin: 12 * S.u } text: S.mmss(np.dur); color: S.dim; font.family: S.font; font.pixelSize: S.tSmall }
    }
    Row {
        id: ctl
        anchors { left: infoCol.left; top: progress.bottom; topMargin: 30 * S.u }
        spacing: 16 * S.u
        Repeater {
            model: np.controls
            delegate: SButton {
                required property string modelData
                required property int index
                anchors.verticalCenter: parent.verticalCenter
                primary: modelData === "play"
                height: (primary ? 96 : 68) * S.u
                icon: modelData === "play" ? (S.playing ? "pause-dark" : "play-dark")
                      : modelData === "repeat" && S.now.repeat === "track" ? "repeat-one"
                      : modelData === "like" ? (np.liked ? "heart-filled" : "heart") : modelData
                on: (modelData === "shuffle" && !!S.now.shuffle) || (modelData === "repeat" && !!S.now.repeat && S.now.repeat !== "off")
                current: np.activeFocus && !np.inQueue && np.btn === index
            }
        }
    }
    Text {
        anchors { left: infoCol.left; top: ctl.bottom; topMargin: 26 * S.u }
        text: !np.inQueue ? ({shuffle: "Shuffle", prev: "Previous", play: S.playing ? "Pause" : "Play", next: "Next", repeat: "Repeat",
                              like: np.liked ? "Remove from Liked Songs" : "Add to Liked Songs", add: "Add to a playlist"})[np.controls[np.btn]] : ""
        color: S.dim; font.family: S.font; font.pixelSize: S.tMeta
    }
    Rectangle {
        id: queueBox
        anchors { right: parent.right; rightMargin: S.edge; top: parent.top; topMargin: 80 * S.u; bottom: parent.bottom; bottomMargin: 80 * S.u }
        width: 420 * S.u
        radius: S.radius
        color: "#99000000"
        visible: (S.now.queue || []).length > 0
        Text { id: qh; x: 30 * S.u; y: 26 * S.u; text: "Next up"; color: S.text; font.family: S.font; font.pixelSize: S.tHead; font.weight: Font.Bold }
        ListView {
            anchors { left: parent.left; right: parent.right; top: qh.bottom; topMargin: 16 * S.u; bottom: parent.bottom; margins: 16 * S.u }
            clip: true
            interactive: false
            model: S.now.queue || []
            currentIndex: np.qIdx
            highlightRangeMode: ListView.ApplyRange
            preferredHighlightBegin: 0; preferredHighlightEnd: height - 80 * S.u
            delegate: Rectangle {
                required property var modelData
                required property int index
                width: ListView.view.width; height: 72 * S.u; radius: 10 * S.u
                color: np.inQueue && np.qIdx === index ? S.panel2 : "transparent"
                border.color: np.inQueue && np.qIdx === index && np.activeFocus ? S.focus : "transparent"; border.width: 3 * S.u
                Text { anchors { left: parent.left; right: parent.right; leftMargin: 16 * S.u; rightMargin: 16 * S.u; verticalCenter: parent.verticalCenter }
                       text: modelData.name || modelData.uri; elide: Text.ElideRight
                       color: modelData.source === "queue" ? S.accent : S.text2; font.family: S.font; font.pixelSize: S.tMeta }
            }
        }
    }
}
