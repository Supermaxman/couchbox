// The Search app's shared state: its look (Couchbox's dark TV look, teal accent), sizes for a
// TV across the room, and the back end (search.py, on threads).
pragma Singleton
import QtQuick

QtObject {
    id: s

    property real u: 1                       // Main sets height / 1080

    readonly property color bg: "#0b0d10"
    readonly property color panel: "#15181d"
    readonly property color panel2: "#232830"
    readonly property color line: "#2a3038"
    readonly property color text: "#f5f7fa"
    readonly property color text2: "#d0d5dc"
    readonly property color dim: "#9aa3ad"
    readonly property color faint: "#6b7480"
    readonly property color accent: "#14b8a6"         // teal
    readonly property color focus: "#2dd4bf"          // focus ring
    readonly property color ai: "#a78bfa"             // anything the assistant wrote
    readonly property string font: "Inter"

    readonly property real edge: 56 * u
    readonly property real radius: 14 * u
    readonly property real ring: 4 * u
    readonly property real tTitle: 46 * u
    readonly property real tHead: 30 * u
    readonly property real tBody: 26 * u
    readonly property real tMeta: 22 * u

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
            try { r = JSON.parse(json); } catch (e) { r = {error: "Something unexpected came back."}; }
            try {
                if (r && r.error) { if (cb[1]) cb[1](r.error); }
                else if (cb[0]) cb[0](r);
            } catch (e) {}
        }
    }
}
