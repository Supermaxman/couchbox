// The Weather app's shared state: its look (the dark zinc of Couchbox's own apps, with a sky
// accent), sizes for a TV across the room, the back end (weather.py, on threads) and the
// forecast it last got.
pragma Singleton
import QtQuick

QtObject {
    id: w

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
    readonly property color accent: "#38bdf8"         // sky
    readonly property color focus: "#7dd3fc"
    readonly property color warm: "#fbbf24"           // highs, sun
    readonly property color cool: "#60a5fa"           // lows, rain
    readonly property color wind: "#a78bfa"
    readonly property string font: "Inter"

    readonly property real edge: 56 * u
    readonly property real railW: 330 * u
    readonly property real radius: 16 * u
    readonly property real gap: 24 * u
    readonly property real ring: 4 * u
    readonly property real lift: 1.05

    readonly property real tHero: 150 * u
    readonly property real tTitle: 46 * u
    readonly property real tHead: 30 * u
    readonly property real tBody: 26 * u
    readonly property real tMeta: 22 * u
    readonly property real tSmall: 19 * u

    function icon(name) { return Qt.resolvedUrl("icons/" + (name || "cloudy") + ".svg"); }
    function glyph(name) { return Qt.resolvedUrl("icons/g-" + name + ".svg"); }
    function deg(t) { return (t === null || t === undefined) ? "–" : t + "°"; }
    function unit(k) { return data && data.units ? data.units[k] : ""; }
    function amount(x) {
        if (!data) return "";
        if (data.units.system === "imperial") return (x < 1 ? x.toFixed(2).replace(/0+$/, "").replace(/\.$/, "") : x.toFixed(1)) + " in";
        return (x >= 1 ? Math.round(x) : x.toFixed(1)) + " mm";
    }
    // 0..1 -> a colour from cool to warm, for the week's temperature bars
    function tempColor(t) {
        const lo = data && data.units.system === "imperial" ? 20 : -6, hi = data && data.units.system === "imperial" ? 95 : 35;
        const k = Math.max(0, Math.min(1, (t - lo) / (hi - lo)));
        return Qt.hsla(0.62 - 0.55 * k, 0.85, 0.62, 1);
    }

    // ------------------------------------------------------------------ data
    property var data: null                  // weather.py's forecast (see parse())
    property string glance: ""               // the model's "today at a glance", if any

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
            const cb = w.waiting[id];
            delete w.waiting[id];
            if (!cb) return;
            let r = null;
            try { r = JSON.parse(json); } catch (e) { r = {error: "The forecast came back garbled."}; }
            try {
                if (r && r.error) { if (cb[1]) cb[1](r.error); }
                else if (cb[0]) cb[0](r);
            } catch (e) {}
        }
    }
}
