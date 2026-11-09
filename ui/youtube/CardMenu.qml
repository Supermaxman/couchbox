// A card's menu (hold OK, or the Menu key, on a card), as YouTube's TV app has it: Play next, Add
// to queue, Save to Watch later, Save to playlist (the account's playlists, ticked where the
// video is), Remove from watch history (History's cards), Not interested, Don't
// recommend channel, Share (the link as a QR code) and Go to channel. Each says what it did in a
// notice. Up and Down move, OK picks, Back closes (or goes back to the menu).
// It opens whole: the options YouTube sends as a panel of their own (Not interested, Don't
// recommend channel) were asked for as OK went down (Y.warmMenu), and hold their places until they
// come; picked before that, they're sent once they do. It rises in, and fades out quicker.
import QtQuick

FocusScope {
    id: menu
    objectName: "cardmenu"
    property var item: null
    property int index: 0
    property var returnFocus: null
    property string mode: "main"              // main | playlists | share
    property var playlists: []                // Save to playlist's: [{id, title, saved}]
    property var shared: ({})                 // Share's: {url, qr}
    readonly property bool video: !!item && (item.type === "video" || item.type === "live" || item.type === "short")
    // the card's own feedback options, else the panel's (asked for on OK's press), else, while they
    // come, their places (a token-less option: sent once it comes)
    function fb(kind) {
        if (!item) return null;
        const have = item.feedback || Y.menuFeedback[item.id];
        if (have) return have.find(f => f.kind === kind) || null;
        return Y.menuFeedbackPending(item) && kind !== "remove_history" ? {kind: kind, token: ""} : null;
    }
    function focusDetail() { return {mode: mode, keys: options.map(o => o.key === "fb" ? o.fb.kind : o.key), at: (options[index] || {}).key || "",
                                     atId: ((options[index] || {}).pl || {}).id || ""}; }
    readonly property var options: {
        const o = [];
        if (!item) return o;
        if (mode === "playlists") {
            for (const p of playlists) o.push({key: "pl", label: p.title, icon: p.id === "WL" ? "history" : "list", checked: p.saved, pl: p});
            // (no New playlist: YouTube doesn't let the TV's sign-in make playlists)
            return o;
        }
        if (mode === "share") return o;
        if (video && item.type !== "short") {
            o.push({key: "next", label: "Play next", icon: "next"});
            o.push({key: "queue", label: "Add to queue", icon: "list"});
        }
        if (video) {
            o.push({key: "later", label: "Save to Watch later", icon: "history"});
            o.push({key: "playlist", label: "Save to playlist", icon: "playlist-add"});
        }
        const kinds = [["remove_history", "Remove from watch history"], ["not_interested", "Not interested"], ["no_channel", "Don't recommend channel"]];
        for (const k of kinds) {
            const f = fb(k[0]);
            if (f) o.push({key: "fb", label: k[1], icon: ({remove_history: "trash", not_interested: "not-interested", no_channel: "not-interested"})[k[0]], fb: f});
        }
        if (video) o.push({key: "share", label: "Share", icon: "share"});
        if (item.channelId || (video && item.type !== "live")) o.push({key: "channel", label: "Go to channel", icon: "person"});
        return o;
    }
    signal picked(string key, var item)       // what the app does: next, queue, channel
    function open(it, back) {
        if (!it) return;
        item = it; index = 0; returnFocus = back; mode = "main";
        if (!options.length) return;
        Y.warmMenu(it);                        // (asked for on OK's press already: here for the Menu key)
        shut.stop();
        if (!visible) { sheet.opacity = 0; scrim.opacity = 0; sheet.scale = 0.94; sheet.lift = 28 * Y.u; }
        visible = true;
        rise.restart();
        forceActiveFocus();
    }
    function close() {
        rise.stop();
        shut.restart();
        mode = "main";
        if (returnFocus) returnFocus.forceActiveFocus();
    }
    readonly property bool shown: visible && activeFocus
    ParallelAnimation {
        id: rise
        NumberAnimation { target: scrim; property: "opacity"; to: 1; duration: Y.tMenu; easing.type: Easing.OutCubic }
        NumberAnimation { target: sheet; property: "opacity"; to: 1; duration: Y.tMenu; easing.type: Easing.OutCubic }
        NumberAnimation { target: sheet; property: "scale"; to: 1; duration: Y.tMenu + 60; easing.type: Easing.OutCubic }
        NumberAnimation { target: sheet; property: "lift"; to: 0; duration: Y.tMenu + 60; easing.type: Easing.OutCubic }
    }
    SequentialAnimation {
        id: shut
        ParallelAnimation {
            NumberAnimation { target: scrim; property: "opacity"; to: 0; duration: Y.tOut; easing.type: Easing.InCubic }
            NumberAnimation { target: sheet; property: "opacity"; to: 0; duration: Y.tOut; easing.type: Easing.InCubic }
            NumberAnimation { target: sheet; property: "scale"; to: 0.97; duration: Y.tOut; easing.type: Easing.InCubic }
        }
        PropertyAction { target: menu; property: "visible"; value: false }
    }
    // a mode of its own (Save to…, Share): its rows slide in over the menu's
    onModeChanged: if (visible && !shut.running) swap.restart()
    ParallelAnimation {
        id: swap
        NumberAnimation { target: sheet; property: "opacity"; from: 0.2; to: 1; duration: Y.tMenu; easing.type: Easing.OutCubic }
        NumberAnimation { target: sheet; property: "shift"; from: 36 * Y.u; to: 0; duration: Y.tMenu; easing.type: Easing.OutCubic }
    }
    function needAccount(what) {
        if (Y.signedIn) return false;
        Y.toast("Sign in to " + what + ": the guide's picture, then Add account.");
        close();
        return true;
    }
    // Watch later: the card menu's own edit when the card has one (as the TV app sends it), else ours
    function saveTo(it, pid, add, done) {
        if (pid === "WL" && it.laterEdit) Y.call("editPlaylist", {edit: it.laterEdit, add: add}, done, e => Y.toast(e));
        else Y.call("save", {id: it.id, playlist: pid, add: add}, done, e => Y.toast(e));
    }
    function pick() {
        const o = options[index], it = item;
        if (!o) return;
        if (o.key === "channel" && !it.channelId) {   // (the card didn't say whose it is: its watch page does)
            close();
            Y.call("watch", {id: it.id}, r => { const c = ((r || {}).video || {}).channelId; if (c) picked("channel", Object.assign({}, it, {channelId: c})); else Y.toast("No channel for this video."); },
                   e => Y.toast(e));
            return;
        }
        if (o.key === "next" || o.key === "queue" || o.key === "channel") { close(); picked(o.key, it); return; }
        if (o.key === "later") {
            if (needAccount("save videos")) return;
            close();
            saveTo(it, "WL", true, () => Y.toast("Saved to Watch later"));
        } else if (o.key === "playlist") {
            if (needAccount("save videos")) return;
            Y.call("saveOptions", {id: it.id}, r => {
                if (menu.item !== it || !menu.visible) return;
                menu.playlists = r.playlists || []; menu.mode = "playlists"; menu.index = 0;
            }, e => { Y.toast(e); close(); });
        } else if (o.key === "pl") {
            const add = !o.pl.saved;
            saveTo(it, o.pl.id, add, () => {
                Y.toast((add ? "Saved to " : "Removed from ") + o.pl.title);
                menu.playlists = menu.playlists.map(p => p.id === o.pl.id ? Object.assign({}, p, {saved: add}) : p);
            });
        } else if (o.key === "fb") {
            if (needAccount("tell YouTube what you'd rather not see")) return;
            close();
            const kind = o.fb.kind;
            const said = ({remove_history: "Removed from watch history", not_interested: "Got it: fewer videos like this",
                           no_channel: "Got it: no more from this channel"})[kind];
            const send = f => Y.call("feedback", {token: f.token}, r => Y.toast(r && r.ok === false ? "YouTube didn't take it: try again later" : said), e => Y.toast(e));
            if (o.fb.token) send(o.fb);
            else Y.warmMenu(it, list => {      // (picked before YouTube's panel came: sent once it does)
                const f = (list || []).find(x => x.kind === kind);
                if (f) send(f); else Y.toast("YouTube didn't offer that for this video.");
            });
        } else if (o.key === "share") {
            Y.call("share", {id: it.id}, r => {
                if (menu.item !== it || !menu.visible) return;
                menu.shared = r || {}; menu.mode = "share";
                qr.source = ""; if (r.qr) qr.source = "file://" + r.qr;
            }, e => Y.toast(e));
        }
    }
    visible: false
    z: 150
    Keys.onUpPressed: index = Math.max(0, index - 1)
    Keys.onDownPressed: index = Math.min(options.length - 1, index + 1)
    // (OK held to open the menu repeats: those presses aren't a pick)
    Keys.onReturnPressed: e => { if (e.isAutoRepeat) return; if (mode === "share") close(); else pick(); }
    Keys.onEnterPressed: e => { if (e.isAutoRepeat) return; if (mode === "share") close(); else pick(); }
    Keys.onEscapePressed: { if (mode === "main") close(); else { mode = "main"; index = 0; } }
    Keys.onBackPressed: { if (mode === "main") close(); else { mode = "main"; index = 0; } }
    Keys.onLeftPressed: {}
    Keys.onRightPressed: {}
    Rectangle { id: scrim; anchors.fill: parent; color: "#cc000000" }
    Column {
        id: sheet
        property real lift: 0                  // rising in
        property real shift: 0                 // a mode sliding in
        x: (parent.width - width) / 2 + shift
        y: (parent.height - height) / 2 + lift
        // a list that changes its length while open (YouTube's options not coming) settles there
        Behavior on y { enabled: menu.visible && !rise.running; NumberAnimation { duration: Y.tFocus; easing.type: Easing.OutCubic } }
        width: 700 * Y.u
        spacing: 14 * Y.u
        transformOrigin: Item.Center
        Text {
            width: parent.width
            text: menu.mode === "playlists" ? "Save to…" : menu.mode === "share" ? "Share" : menu.item ? menu.item.title : ""
            horizontalAlignment: menu.mode === "share" ? Text.AlignHCenter : Text.AlignLeft
            color: Y.text; font.family: Y.font; font.pixelSize: 34 * Y.u; font.weight: Font.Bold
            wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
            bottomPadding: 18 * Y.u
        }
        MenuRows {
            width: parent.width
            options: menu.options
            index: menu.index
            focused: menu.activeFocus || shut.running   // (kept while it fades out)
            visible: menu.mode !== "share"
        }
        Column {                              // Share: the QR code and the link
            visible: menu.mode === "share"
            width: parent.width
            spacing: 18 * Y.u
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                width: 320 * Y.u; height: width; radius: 16 * Y.u
                color: "white"
                visible: qr.status === Image.Ready
                Image { id: qr; anchors { fill: parent; margins: 12 * Y.u } cache: false; smooth: false; fillMode: Image.PreserveAspectFit }
            }
            Text {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                text: (menu.shared.url || "").replace("https://", "")
                color: Y.text; font.family: Y.font; font.pixelSize: 34 * Y.u; font.weight: Font.Medium
            }
            Text {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                text: qr.status === Image.Ready ? "Point a phone's camera at the code to open the video." : "Type the link on a phone or computer."
                color: Y.dim; font.family: Y.font; font.pixelSize: 26 * Y.u
            }
        }
    }
}
