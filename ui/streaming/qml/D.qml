// The Dropout app's shared state: Dropout's look (black, its yellow), sizes for a TV across
// the room, the bridge to the Python back end (vhx.py), and navigation requests (Main.qml
// opens the pages).
pragma Singleton
import QtQuick

QtObject {
    id: d

    property real u: 1                         // Main sets height / 1080
    property var site: ({})                    // Main sets it: name, accent, logo (vhx.SITES)
    property var video: null                   // the one video player (Main.qml)
    property bool subtitles: true              // CC on (saved by Main)
    property string chatMode: "overlay"        // Twitch chat: overlay, side, off (saved by Main)
    property real videoInset: 0                // the player page's side chat takes this from the video
    readonly property string name: site.name || "Dropout"

    // ------------------------------------------------------------------ Dropout's look
    readonly property color bg: site.bg || "#000000"
    readonly property color bg2: "#0d0d0d"
    readonly property color panel: "#1a1a1a"
    readonly property color panel2: "#262626"
    readonly property color line: "#333333"
    readonly property color text: "#ffffff"
    readonly property color text2: "#d4d4d4"
    readonly property color dim: "#9a9a9a"
    readonly property color accent: site.accent || "#feea3b"     // Dropout yellow, 2nd Try teal
    readonly property color accentInk: site.accent_ink || "#000000"
    readonly property string font: "Inter"

    // sizes (at 1080p)
    readonly property real edge: 96 * u               // left/right margin, clear of overscan
    readonly property real gap: 28 * u
    readonly property real posterW: 230 * u
    readonly property real posterH: 345 * u
    readonly property real squareW: 280 * u
    readonly property real wideW: 420 * u              // 16:9 thumbnails
    readonly property real wideH: 236 * u
    readonly property real epW: 500 * u                // episodes on a show's page
    readonly property real epH: 281 * u

    function shapeW(shape) { return shape === "poster" ? posterW : shape === "square" ? squareW : wideW; }
    function shapeH(shape) { return shape === "poster" ? posterH : shape === "square" ? squareW : wideH; }

    // ------------------------------------------------------------------ back end (vhx.py, threads)
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
            const cb = d.waiting[id];
            delete d.waiting[id];
            if (!cb) return;
            let r = null;
            try { r = JSON.parse(json); } catch (e) { r = {error: d.name + " sent something unexpected."}; }
            // a page that went away (destroyed) before the answer came can't take it
            try {
                if (r && r.error) {
                    if (r.signin) d.signInNeeded();
                    if (cb[1]) cb[1](r.error);
                } else if (cb[0]) cb[0](r);
            } catch (e) {}
        }
    }

    function img(src, w, h) {
        if (!src) return "";
        if (src.indexOf("imgix.net") < 0) return src;     // Nebula: sized by the back end
        const base = src.split("?")[0];
        return base + "?auto=format%2Ccompress&q=80" + (w ? "&w=" + Math.round(w) : "") + (h ? "&h=" + Math.round(h) + "&fit=crop" : "");
    }
    function clock(s) {
        s = Math.max(0, Math.floor(s));
        const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), ss = s % 60;
        return (h ? h + ":" + String(m).padStart(2, "0") : m) + ":" + String(ss).padStart(2, "0");
    }
    // a live stream's uptime from its start (ISO time): 5:28:17
    function uptime(iso) {
        if (!iso) return "";
        return clock((Date.now() - new Date(iso).getTime()) / 1000);
    }
    function length(s) {
        const h = Math.floor(s / 3600), m = Math.round(s % 3600 / 60);
        return h ? h + "h " + m + "m" : m + "m";
    }
    // Dropout numbers seasons across a franchise (Fantasy High's second is Dimension 20's
    // season 4), so a season's own name wins: "Fantasy High · E1", else "S5 · E2"
    function epLabel(c) {
        if (!c.episode) return "";
        if (c.seasonName && !/^season\s*\d+$/i.test(c.seasonName)) return c.seasonName + " · E" + c.episode;
        return c.seasonNumber ? "S" + c.seasonNumber + " · E" + c.episode : "Episode " + c.episode;
    }

    // ------------------------------------------------------------------ navigation (Main.qml)
    signal open(var item)                     // a card: series/collection page, category, or play a video
    signal play(var videoId)                  // a number (VHX) or a string id (Nebula)
    signal openGrid(string title, string op, var args)
    signal toNav()
    signal toast(string text)
    signal signInNeeded()
    signal askText(string title, string text, bool password, var done)
}
