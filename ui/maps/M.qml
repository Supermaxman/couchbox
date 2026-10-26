// The Maps app's shared state: the dark TV look (the same palette as Couchbox's other apps),
// sizes for reading across the room, formatters, and the back end (maps.py, on threads).
pragma Singleton
import QtQuick

QtObject {
    id: m
    // Image sizes in real pixels: the TV may run scaled (QT_SCALE_FACTOR 1.5), and Qt decodes an
    // Image at its sourceSize as given, so logical sizes come out soft. sourceSize: M.sz(width, height)
    readonly property real dpr: Qt.application.screens.length ? Qt.application.screens[0].devicePixelRatio : 1
    function px(n) { return Math.ceil(n * dpr); }
    function sz(w, h) { return Qt.size(px(w), px(h)); }

    property real u: 1                       // Main sets height / 1080

    // ------------------------------------------------------------------ look
    readonly property color bg: "#09090b"
    readonly property color side: "#0f0f12"
    readonly property color panel: "#18181b"
    readonly property color panel2: "#27272a"
    readonly property color line: "#27272a"
    readonly property color text: "#fafafa"
    readonly property color text2: "#d4d4d8"
    readonly property color dim: "#a1a1aa"
    readonly property color faint: "#71717a"
    readonly property color accent: "#10b981"         // the app's mark, what's selected
    readonly property color focus: "#60a5fa"          // focus ring (as in the other apps)
    readonly property color route: "#3b82f6"          // the chosen route on the map
    readonly property color routeAlt: "#71717a"
    readonly property color light: "#22c55e"          // traffic: light, moderate, heavy
    readonly property color moderate: "#f59e0b"
    readonly property color heavy: "#ef4444"
    readonly property string font: "Inter"

    readonly property real edge: 56 * u
    readonly property real railW: 330 * u
    readonly property real radius: 14 * u
    readonly property real gap: 26 * u
    readonly property real ring: 4 * u
    readonly property real lift: 1.04

    readonly property real tTitle: 46 * u
    readonly property real tHead: 30 * u
    readonly property real tBody: 26 * u
    readonly property real tMeta: 22 * u
    readonly property real tSmall: 19 * u

    function icon(name) { return Qt.resolvedUrl("icons/" + (name || "pin") + ".svg"); }
    function placeIcon(p) { return p && p.kind === "home" ? "home" : p && p.kind === "work" ? "work" : p && p.saved === undefined && p.kind === undefined ? "pin" : "star"; }
    function trafficColor(t) { return t === "heavy" ? heavy : t === "moderate" ? moderate : t === "light" ? light : text; }
    function modeIcon(mode) { return {drive: "car", transit: "transit", walk: "walk", bike: "bike"}[mode] || "car"; }
    function modeName(mode) { return {drive: "Drive", transit: "Transit", walk: "Walk", bike: "Bike"}[mode] || mode; }

    // ------------------------------------------------------------------ the status and places
    property var status: ({})                // {provider, google, traffic, modes, attribution, units, tiles, tile_px, home}
    property var places: []
    property var recent: []
    function setPlaces(r) { places = r.places || []; recent = r.recent || []; }

    // time: 12/24 h like the home screen (units: metric -> 24 h)
    readonly property bool h24: status.units === "metric"
    function clock(t) { return Qt.formatTime(new Date(t * 1000), h24 ? "HH:mm" : "h:mm AP"); }
    function day(t) {
        const d = new Date(t * 1000), now = new Date();
        if (d.toDateString() === now.toDateString()) return "Today";
        const tm = new Date(now.getTime() + 86400000);
        if (d.toDateString() === tm.toDateString()) return "Tomorrow";
        return Qt.formatDate(d, "ddd d MMM");
    }
    function mins(s) {
        const m = Math.max(1, Math.round(s / 60));
        return m < 60 ? m + " min" : Math.floor(m / 60) + " h" + (m % 60 ? " " + (m % 60) + " min" : "");
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
            const cb = m.waiting[id];
            delete m.waiting[id];
            if (!cb) return;
            let r = null;
            try { r = JSON.parse(json); } catch (e) { r = {error: "Something unexpected came back."}; }
            try {
                if (r && r.error) { if (cb[1]) cb[1](r.error); else m.toast(r.error); }
                else if (cb[0]) cb[0](r);
            } catch (e) { console.log("maps: " + e); }
        }
    }

    signal toast(string text)
}
