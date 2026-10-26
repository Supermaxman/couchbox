// The Frigate app's shared state: Frigate's dark look (its web UI's zinc palette), sizes for a
// TV across the room, the back end (frigate.py, on threads), the cameras and camera groups,
// and requests that Main.qml acts on (sign in, toast).
pragma Singleton
import QtQuick

QtObject {
    id: f

    property real u: 1                       // Main sets height / 1080

    // ------------------------------------------------------------------ Frigate's look
    readonly property color bg: "#09090b"            // zinc-950
    readonly property color side: "#0f0f12"
    readonly property color panel: "#18181b"         // zinc-900
    readonly property color panel2: "#27272a"        // zinc-800
    readonly property color line: "#27272a"
    readonly property color text: "#fafafa"
    readonly property color text2: "#d4d4d8"         // zinc-300
    readonly property color dim: "#a1a1aa"           // zinc-400
    readonly property color faint: "#71717a"         // zinc-500
    readonly property color alert: "#ef4444"         // review severity: alert
    readonly property color detection: "#f59e0b"     //                  detection
    readonly property color live: "#22c55e"
    readonly property color accent: "#3b82f6"        // selection
    readonly property color focus: "#60a5fa"         // focus ring
    readonly property string font: "Inter"

    readonly property real edge: 56 * u              // right margin, clear of TV overscan
    readonly property real railW: 330 * u
    readonly property real radius: 14 * u
    readonly property real gap: 26 * u
    readonly property real ring: 4 * u                // focus ring
    readonly property real lift: 1.05                // focused cards grow a little (as elsewhere on Couchbox)

    // type: sized for reading across the room
    readonly property real tTitle: 46 * u
    readonly property real tHead: 30 * u
    readonly property real tBody: 26 * u
    readonly property real tMeta: 22 * u
    readonly property real tSmall: 19 * u

    // what was seen -> its icon (icons/*.svg, white line drawings; frigate.py's kind())
    function icon(kind) { return Qt.resolvedUrl("icons/" + (kind || "object") + ".svg"); }
    // "Person, Dog" (and recognised names: "Person (Max)")
    function seen(r) {
        const k = (r.kinds || []).map(x => x.label);
        const n = (r.names || []).length ? " (" + r.names.join(", ") + ")" : "";
        return (k.join(", ") || "Motion") + n;
    }
    function sevColor(r) { return r.severity === "alert" ? alert : detection; }

    // ------------------------------------------------------------------ data
    property var cameras: []                 // [{name, label, stream, aspect}]
    property var groups: []                  // [{name, icon, cameras: [names]}]
    property var activeCams: []              // cameras with something going on now
    property var activeKinds: ({})           //   and what: {camera: [kind, ...]}
    property var status: ({})                // {configured, url, signedIn, user}

    function camera(name) {
        for (const c of cameras) if (c.name === name) return c;
        return {name: name, label: name, stream: name};
    }
    function groupCams(i) {
        const g = groups[i];
        return g ? g.cameras.map(n => camera(n)) : cameras;
    }
    function isActive(name) { return activeCams.indexOf(name) >= 0; }
    function clock(t) { return Qt.formatTime(new Date(t * 1000), "h:mm AP"); }

    // "3:42 PM", or "Yesterday, 9:10 PM", or "Mon 12 Oct, 9:10 PM"
    function when(t) {
        const d = new Date(t * 1000), now = new Date();
        const time = Qt.formatTime(d, "h:mm AP");
        if (d.toDateString() === now.toDateString()) return time;
        const y = new Date(now.getTime() - 86400000);
        if (d.toDateString() === y.toDateString()) return "Yesterday, " + time;
        return Qt.formatDate(d, "ddd d MMM") + ", " + time;
    }
    function ago(t) {
        const s = Math.max(0, Date.now() / 1000 - t);
        return s < 60 ? "just now" : s < 3600 ? Math.round(s / 60) + " min ago" : s < 86400 ? Math.round(s / 3600) + " h ago" : Math.round(s / 86400) + " d ago";
    }
    function length(r) {
        if (r.live) return "now";
        const s = Math.max(1, Math.round(r.end - r.start));
        return s < 60 ? s + " s" : Math.floor(s / 60) + " min " + (s % 60 ? s % 60 + " s" : "");
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
            const cb = f.waiting[id];
            delete f.waiting[id];
            if (!cb) return;
            let r = null;
            try { r = JSON.parse(json); } catch (e) { r = {error: "Frigate sent something unexpected."}; }
            try {
                if (r && r.error) {
                    if (r.signin) f.signInNeeded(r.error);
                    if (cb[1]) cb[1](r.error);
                } else if (cb[0]) cb[0](r);
            } catch (e) {}
        }
    }

    signal signInNeeded(string why)
    signal toast(string text)
}
