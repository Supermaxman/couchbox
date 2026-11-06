// YouTube's shared state: the look (YouTube's TV app: near-black, white focus, red progress,
// Roboto), the back end (couchbox.services.youtube / ytstream, on threads) and small helpers.
// Sizes are the TV app's at 1920x1080, times u (Main sets height / 1080).
pragma Singleton
import QtQuick

QtObject {
    id: y
    // Image sizes in real pixels: the TV may run scaled (QT_SCALE_FACTOR 1.5), and Qt decodes an
    // Image at its sourceSize as given, so logical sizes come out soft. sourceSize: Y.sz(width, height)
    readonly property real dpr: Qt.application.screens.length ? Qt.application.screens[0].devicePixelRatio : 1
    function px(n) { return Math.ceil(n * dpr); }
    function sz(w, h) { return Qt.size(px(w), px(h)); }

    property real u: 1
    property var video: null                  // the one MpvVideo (Main): it lives as long as the app
    property var profile: null                // who's watching: {id, account, name, handle, photo, premium}, null: a guest
    readonly property bool signedIn: !!profile
    property bool videoSide: false            // the player's side panel is open: the video sits to its left
    property rect videoRect: Qt.rect(0, 0, 0, 0)   // somewhere else entirely (Shorts: upright, mid-screen)
    property var queue: []                    // cards to play next (a card's menu: Play next, Add to queue)
    property bool queueAuto: false            // the queue is a playlist's rest (it ends with the player)
    // a video from a playlist: the playlist's next videos play after it, in order
    function playList(after, it) {
        queue = (after || []).filter(x => x.type === "video" || x.type === "live");
        queueAuto = true;
        open(it);
    }
    property bool shot: false                 // --shot: still (no blinking caret)
    // the TV's settings (ytextras.Settings: SponsorBlock, DeArrow, dislikes, Hide Shorts, H.264 only)
    property var settings: ({sponsorblock: true, skip: {sponsor: true}, dearrow: false, dislikes: false, hide_shorts: false, h264: true})
    function setting(key, value) { call("setting", {key: key, value: value}, s => y.settings = s); }
    // SponsorBlock's colours for its kinds of segment (its own defaults; Endcards lighter, to show on
    // the dark bar), for the progress bar
    readonly property var segmentColors: ({sponsor: "#00d400", selfpromo: "#ffff00", interaction: "#cc00ff", intro: "#00ffff",
                                           outro: "#4a5cff", preview: "#008fd6", hook: "#395699", filler: "#7300ff", music_offtopic: "#ff9900"})
    property bool dimmed: false               // the guide has the focus: the page behind it greys
    property real lastKey: Date.now()         // the last key pressed (couchbox-yt's key filter)
    property bool homeShown: false            // (the app's start: timing)
    // how far each video was watched in this run (the cards' red bars, up to date on the way back
    // from the player, before YouTube's pages say so): {id: fraction}
    property var seen: ({})
    function noteSeen(id, frac) { if (id && frac >= 0) { const m = Object.assign({}, seen); m[id] = Math.min(1, frac); seen = m; } }
    function progressOf(it) { return it ? (seen[it.id] !== undefined ? seen[it.id] : it.progress || 0) : 0; }
    // where a part-watched card starts: a few seconds before its red bar ends (0: from the start)
    function resumeAt(progress, duration) {
        const p = progress || 0, d = typeof duration === "string" ? String(duration).split(":").reduce((n, x) => n * 60 + (parseInt(x) || 0), 0) : duration || 0;
        return p > 0.02 && p < 0.95 && d > 0 ? Math.max(0, Math.floor(p * d - 3)) : 0;
    }
    property Connections keyWatch: Connections { target: typeof keyfilter !== "undefined" ? keyfilter : null; ignoreUnknownSignals: true
                                             function onPressed() { y.lastKey = Date.now(); } }
    property bool pushed: false               // the guide is open: the page is pushed right

    // ------------------------------------------------------------------ look
    readonly property color bg: "#0f0f0f"
    readonly property color raised: "#272727"         // the search pill, badges, buttons
    readonly property color raised2: "#3f3f3f"        // dividers, chip outlines
    readonly property color text: "#f1f1f1"           // white text; the focus ring and focused rows
    readonly property color dim: "#aaaaaa"            // grey text: channels, views, unfocused titles
    readonly property color faint: "#717171"
    readonly property color soft: "#cccccc"           // shelf subtitles, the seek strip's other chapters
    readonly property color glass: "#1affffff"        // pills on the page: white at 10%
    readonly property color ink: "#0f0f0f"            // text on a focused (white) row
    readonly property color red: "#ff0033"            // progress, the logo
    readonly property color magenta: "#ff2791"        // the progress's other end (red to magenta, as YouTube's)
    readonly property Gradient progress: Gradient {
        orientation: Gradient.Horizontal
        GradientStop { position: 0; color: y.red }
        GradientStop { position: 1; color: y.magenta }
    }
    readonly property color sponsor: "#00d400"
    readonly property color phone: "#121a2e"          // the "Type on your phone" card
    readonly property string font: "Roboto"
    // page titles (Subscriptions, Settings and its panes', a list's): YouTube's are YouTube Sans
    // (not ours to ship); Ubuntu's font is its closest (fonts-ubuntu), else Roboto
    readonly property string titleFont: Qt.fontFamilies().indexOf("Ubuntu") >= 0 ? "Ubuntu" : font
    readonly property real titleScale: titleFont === "Ubuntu" ? 1.04 : 1

    readonly property real left: 156 * u              // where pages start, right of the collapsed guide
    readonly property real guideOpen: 534 * u         // ... and with the guide open
    readonly property real ring: 8 * u                // focus ring around cards
    readonly property real radius: 16 * u             // cards' corners
    readonly property real gap: 36 * u                // between cards

    // Leanback's card sizes: a focused home shelf grows its cards; search, channel and the
    // player's related rows keep one size
    readonly property real bigW: 720 * u
    readonly property real cardW: 528 * u
    readonly property real tTitle: 34 * u           // a card's title: semibold, lines 48 apart
    readonly property real tTitleLine: 48 * u
    readonly property real tShelf: 30 * u
    readonly property real tMeta: 24 * u
    readonly property real tSmall: 22 * u

    // ------------------------------------------------------------------ formatting
    function clock(s) {                      // 3956 -> "1:05:56", 76 -> "1:16"
        s = Math.max(0, Math.floor(s || 0));
        const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), sec = s % 60;
        const two = n => (n < 10 ? "0" : "") + n;
        return h ? h + ":" + two(m) + ":" + two(sec) : m + ":" + two(sec);
    }
    function count(n) {                      // 2134567 -> "2.1M"
        if (!n) return "";
        if (n >= 1e9) return (n / 1e9).toFixed(n >= 1e10 ? 0 : 1).replace(/\.0$/, "") + "B";
        if (n >= 1e6) return (n / 1e6).toFixed(n >= 1e7 ? 0 : 1).replace(/\.0$/, "") + "M";
        if (n >= 1e3) return (n / 1e3).toFixed(n >= 1e4 ? 0 : 1).replace(/\.0$/, "") + "K";
        return String(n);
    }
    function html(t) { return String(t || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
    // a made-up thumbnail for cards without one (the demo): two colours from the title
    function hue(s) { let h = 0; for (let i = 0; i < (s || "").length; i++) h = (h * 31 + s.charCodeAt(i)) % 360; return h / 360; }
    // the chapter at a position (chapters: [{start, title}], in order)
    function chapterAt(chapters, pos) {
        let c = -1;
        for (let i = 0; i < (chapters || []).length; i++) if (chapters[i].start <= pos + 0.5) c = i;
        return c;
    }

    // ------------------------------------------------------------------ back end (threads)
    property int nextId: 1
    property var waiting: ({})
    function call(op, args, done, fail) {
        const id = nextId++;
        waiting[id] = [done, fail, op];
        backend.call(id, op, JSON.stringify(args || {}));
    }
    property Connections replies: Connections {
        target: backend
        function onReply(id, json) {
            const cb = y.waiting[id];
            delete y.waiting[id];
            if (!cb) return;
            let r = null;
            try { r = JSON.parse(json); } catch (e) { r = {error: "Something unexpected came back."}; }
            try {
                if (r && r.error) { if (cb[1]) cb[1](r.error); else y.toast(r.error); }
                else if (cb[0]) cb[0](r);
            } catch (e) {                     // which answer, and where (QV4's stack: function@file:line)
                console.log("youtube:", e, "| in the answer to", cb[2], "|", String(e.stack || "").split("\n").slice(0, 4).join(" < "));
            }
        }
    }

    // what the pages ask Main for
    signal open(var item)                     // a card: {type: video | short | live | channel | playlist | browse | search, id, ...}
    signal toast(string text)
    signal toGuide()                          // Left off a page's first column, Back from a page
    signal search(string query)               // the search pill, a chip, a cluster's search pill
    signal whoIsWatching()                    // the guide's picture: the profiles
    signal signIn()                           // Add account, a "Sign in" button
    signal openList(string title, string browseId)   // Library's tiles: History, Watch later, a playlist
    signal cardMenu(var item, var focusItem)  // OK held (or Menu) on a card: Play next, Add to queue...
}
