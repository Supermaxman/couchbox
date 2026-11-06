// A card's menu (hold OK, or the Menu key, on a card), as YouTube's TV app has it: Play next, Add
// to queue, Save to Watch later, Save to playlist (the account's playlists, ticked where the
// video is, and a new one), Remove from watch history (History's cards), Not interested, Don't
// recommend channel, Share (the link as a QR code) and Go to channel. Each says what it did in a
// notice. Up and Down move, OK picks, Back closes (or goes back to the menu).
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
    function fb(kind) { return ((item && item.feedback) || []).find(f => f.kind === kind) || null; }
    function focusDetail() { return {mode: mode, keys: options.map(o => o.key === "fb" ? o.fb.kind : o.key), at: (options[index] || {}).key || ""}; }
    readonly property var options: {
        const o = [];
        if (!item) return o;
        if (mode === "playlists") {
            for (const p of playlists) o.push({key: "pl", label: p.title, icon: p.id === "WL" ? "history" : "list", checked: p.saved, pl: p});
            o.push({key: "newpl", label: "New playlist", icon: "plus"});   // (named "New playlist": the remote has no keyboard)
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
        if (item.channelId) o.push({key: "channel", label: "Go to channel", icon: "person"});
        return o;
    }
    signal picked(string key, var item)       // what the app does: next, queue, channel
    function open(it, back) {
        item = it; index = 0; returnFocus = back; mode = "main";
        if (!options.length) return;
        visible = true;
        forceActiveFocus();
    }
    function close() { visible = false; mode = "main"; if (returnFocus) returnFocus.forceActiveFocus(); }
    function needAccount(what) {
        if (Y.signedIn) return false;
        Y.toast("Sign in to " + what + ": the guide's picture, then Add account.");
        close();
        return true;
    }
    function pick() {
        const o = options[index], it = item;
        if (!o) return;
        if (o.key === "next" || o.key === "queue" || o.key === "channel") { close(); picked(o.key, it); return; }
        if (o.key === "later") {
            if (needAccount("save videos")) return;
            close();
            Y.call("save", {id: it.id, playlist: "WL", add: true}, () => Y.toast("Saved to Watch later"), e => Y.toast(e));
        } else if (o.key === "playlist") {
            if (needAccount("save videos")) return;
            Y.call("saveOptions", {id: it.id}, r => {
                if (menu.item !== it || !menu.visible) return;
                menu.playlists = r.playlists || []; menu.mode = "playlists"; menu.index = 0;
            }, e => { Y.toast(e); close(); });
        } else if (o.key === "pl") {
            const add = !o.pl.saved;
            Y.call("save", {id: it.id, playlist: o.pl.id, add: add}, () => {
                Y.toast((add ? "Saved to " : "Removed from ") + o.pl.title);
                menu.playlists = menu.playlists.map(p => p.id === o.pl.id ? Object.assign({}, p, {saved: add}) : p);
            }, e => Y.toast(e));
        } else if (o.key === "newpl") {
            const title = "New playlist";
            close();
            Y.call("createPlaylist", {id: it.id, title: title},
                   () => Y.toast("Saved to a new playlist, “" + title + "” (rename it in the YouTube app)"), e => Y.toast(e));
        } else if (o.key === "fb") {
            if (needAccount("tell YouTube what you'd rather not see")) return;
            close();
            const said = ({remove_history: "Removed from watch history", not_interested: "Got it: fewer videos like this",
                           no_channel: "Got it: no more from this channel"})[o.fb.kind];
            Y.call("feedback", {token: o.fb.token}, r => Y.toast(r && r.ok === false ? "YouTube didn't take it: try again later" : said), e => Y.toast(e));
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
    Rectangle { anchors.fill: parent; color: "#cc000000" }
    Column {
        anchors.centerIn: parent
        width: 700 * Y.u
        spacing: 14 * Y.u
        Text {
            width: parent.width
            text: menu.mode === "playlists" ? "Save to…" : menu.mode === "share" ? "Share" : menu.item ? menu.item.title : ""
            horizontalAlignment: menu.mode === "share" ? Text.AlignHCenter : Text.AlignLeft
            color: Y.text; font.family: Y.font; font.pixelSize: 34 * Y.u; font.weight: Font.Bold
            wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
            bottomPadding: 18 * Y.u
        }
        Repeater {
            model: menu.options
            Rectangle {
                required property var modelData
                required property int index
                readonly property bool on: menu.index === index
                width: parent.width; height: 84 * Y.u; radius: 16 * Y.u
                color: on ? Y.text : Y.raised
                Icon { x: 28 * Y.u; anchors.verticalCenter: parent.verticalCenter; name: parent.modelData.icon; size: 36 * Y.u; color: parent.on ? Y.ink : Y.text }
                Text {
                    x: 90 * Y.u; width: parent.width - 170 * Y.u; anchors.verticalCenter: parent.verticalCenter
                    text: parent.modelData.label; elide: Text.ElideRight
                    color: parent.on ? Y.ink : Y.text; font.family: Y.font; font.pixelSize: 30 * Y.u; font.weight: Font.Medium
                }
                Icon {
                    visible: !!parent.modelData.checked
                    anchors { right: parent.right; rightMargin: 28 * Y.u; verticalCenter: parent.verticalCenter }
                    name: "check"; size: 36 * Y.u; color: parent.on ? Y.ink : Y.text
                }
            }
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
