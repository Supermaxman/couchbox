// The morning show's shared look (the reel's: black, white words over shades) and its back end
// (bin/couchbox-show, on threads: call(op, args, done, failed)).
pragma Singleton
import QtQuick

QtObject {
    id: s
    readonly property real dpr: Qt.application.screens.length ? Qt.application.screens[0].devicePixelRatio : 1
    function sz(w, h) { return Qt.size(Math.ceil(w * dpr), Math.ceil(h * dpr)); }
    property real u: 1                       // Main sets height / 1080

    readonly property string font: "Inter"
    readonly property color text: "#fafafa"
    readonly property color text2: "#d4d4d8"
    readonly property color dim: "#a1a1aa"
    readonly property color morning: "#ffd89a"        // the show's own colour (its tile's subtitle)
    readonly property color panel: "#18181b"
    readonly property real side: 96 * u                // left and right margins, clear of overscan

    property int next: 1
    property var waiting: ({})
    function call(op, args, done, failed) {
        const id = next++;
        waiting[id] = {done: done, failed: failed};
        backend.call(id, op, JSON.stringify(args || {}));
    }
    property Connections conn: Connections {
        target: backend
        function onReply(id, js) {
            const w = s.waiting[id];
            delete s.waiting[id];
            if (!w) return;
            const r = JSON.parse(js);
            if (r && r.error) { if (w.failed) w.failed(r.error); }
            else if (w.done) w.done(r);
        }
    }
}
