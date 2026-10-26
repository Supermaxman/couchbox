// The Spotify app's shared state: a dark look in the spirit of Spotify's (its own app, not a
// copy), sizes for a TV across the room, the back end (couchbox-spotify, on threads), what's
// playing on this TV, and requests Main.qml acts on (sign-in needed, toast, open something).
pragma Singleton
import QtQuick

QtObject {
    id: s

    property real u: 1                       // Main sets height / 1080

    // ------------------------------------------------------------------ look
    readonly property color bg: "#0b0b0d"
    readonly property color side: "#000000"
    readonly property color panel: "#18181b"
    readonly property color panel2: "#26262b"
    readonly property color line: "#2a2a30"
    readonly property color text: "#fafafa"
    readonly property color text2: "#d4d4d8"
    readonly property color dim: "#a7a7ad"
    readonly property color faint: "#73737a"
    readonly property color accent: "#1fd760"        // play, liked, selection
    readonly property color accentDark: "#169c46"
    readonly property color focus: "#ffffff"         // focus ring
    readonly property color danger: "#f87171"
    readonly property string font: "Inter"

    readonly property real edge: 56 * u
    readonly property real railW: 300 * u
    readonly property real radius: 12 * u
    readonly property real gap: 28 * u
    readonly property real ring: 4 * u
    readonly property real lift: 1.05
    readonly property real barH: 112 * u             // the mini player

    readonly property real tTitle: 52 * u
    readonly property real tHead: 32 * u
    readonly property real tBody: 26 * u
    readonly property real tMeta: 22 * u
    readonly property real tSmall: 19 * u

    function icon(name) { return Qt.resolvedUrl("icons/" + name + ".svg"); }
    function artists(x) { return ((x && x.artists) || []).map(a => a.name).join(", "); }
    function mmss(sec) {
        sec = Math.max(0, Math.round(sec || 0));
        const m = Math.floor(sec / 60), r = sec % 60;
        return m + ":" + (r < 10 ? "0" : "") + r;
    }
    function kindLabel(x) {
        if (!x) return "";
        if (x.kind === "album") return x.type === "single" ? "Single" : x.type === "compilation" ? "Compilation" : "Album";
        return {track: "Song", artist: "Artist", playlist: "Playlist", liked: "Playlist"}[x.kind] || "";
    }
    // a card's second line
    function subtitle(x) {
        if (!x) return "";
        if (x.kind === "track") return artists(x);
        if (x.kind === "album") return [x.year, artists(x)].filter(v => v).join(" · ");
        if (x.kind === "playlist") return x.description && x.spotify ? x.description : x.owner ? "By " + x.owner : "Playlist";
        if (x.kind === "artist") return "Artist";
        if (x.kind === "liked") return x.total + " songs";
        return "";
    }
    // placeholder art: a colour from the name
    function tint(name) {
        const c = ["#4c1d95", "#9a3412", "#065f46", "#1e3a8a", "#831843", "#3f6212", "#713f12", "#164e63"];
        let h = 0;
        for (let i = 0; i < (name || "").length; i++) h = (h * 31 + name.charCodeAt(i)) % 9973;
        return c[h % c.length];
    }

    // ------------------------------------------------------------------ data
    property var status: ({})                // {configured, signedIn, user, player: {...}, device}
    property var now: ({})                   // the player: {connected, logged_in, status, item, context, ...}
    property var nowInfo: ({})               // the playing song from the Web API (artists, album, art)
    property var liked: ({})                 // uri -> true, for hearts
    readonly property bool playing: now.status === "playing" || now.status === "buffering"
    readonly property string nowUri: (now.item && now.item.uri) || ""

    function setLiked(uri, on) { const l = Object.assign({}, liked); if (on) l[uri] = true; else delete l[uri]; liked = l; }
    function check(uris) {                   // fill in hearts for these songs
        const want = (uris || []).filter(u => u && u.startsWith("spotify:track:")).slice(0, 40);
        if (!want.length || demo) return;
        call("is_saved", {uris: want}, r => { const l = Object.assign({}, liked); want.forEach((u, i) => { if (r[i]) l[u] = true; else delete l[u]; }); liked = l; });
    }

    // ------------------------------------------------------------------ back end (threads)
    property int nextId: 1
    property var waiting: ({})
    function call(op, args, done, fail) {
        const id = nextId++;
        waiting[id] = [done, fail];
        backend.call(id, op, JSON.stringify(args || {}));
    }
    property Connections replies: Connections {
        target: backend
        function onReply(id, json) {
            const cb = s.waiting[id];
            delete s.waiting[id];
            if (!cb) return;
            let r = null;
            try { r = JSON.parse(json); } catch (e) { r = {error: "Spotify sent something unexpected."}; }
            try {
                if (r && r.error) {
                    if (r.signin) s.signInNeeded(r.error);
                    if (cb[1]) cb[1](r.error); else s.toast(r.error);
                } else if (cb[0]) cb[0](r);
            } catch (e) { console.log("spotify: " + e); }
        }
        function onPlayer(json) { try { s.now = JSON.parse(json); } catch (e) {} }
        function onNowInfo(json) { try { s.nowInfo = JSON.parse(json); } catch (e) {} }
    }

    // play something on this TV: a context (album, playlist, artist) from a song, or songs
    function play(args, done) {
        call("play", args, r => { if (done) done(r); }, e => s.toast(e));
    }
    function media(action, value) { call("media", {action: action, value: value || 0}, () => {}, e => s.toast(e)); }

    signal signInNeeded(string why)
    signal toast(string text)
    signal open(var item)                    // a card or a row chose something to show
    signal menu(var item, var context)       // the actions for a song or a card
}
