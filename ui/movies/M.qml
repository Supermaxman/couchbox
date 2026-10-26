// Movies & TV's shared state: the look (dark, an amber accent; sized for a TV across the room),
// the back end (movies.py, on threads) and small formatting helpers.
pragma Singleton
import QtQuick

QtObject {
    id: m

    property real u: 1                       // Main sets height / 1080

    // ------------------------------------------------------------------ look
    readonly property color bg: "#0b0b0d"
    readonly property color side: "#101013"
    readonly property color panel: "#18181b"
    readonly property color panel2: "#27272a"
    readonly property color line: "#2a2a2e"
    readonly property color text: "#fafafa"
    readonly property color text2: "#d4d4d8"
    readonly property color dim: "#a1a1aa"
    readonly property color faint: "#71717a"
    readonly property color accent: "#f5b301"         // amber: the mark, selection, IMDb-style stars
    readonly property color accentDark: "#1a1400"      // text on the accent
    readonly property color focus: "#fcd34d"           // focus ring
    readonly property color good: "#22c55e"
    readonly property color rt: "#fa320a"              // Rotten Tomatoes red (fresh)
    readonly property string font: "Inter"

    readonly property real edge: 56 * u              // right margin, clear of TV overscan
    readonly property real railW: 330 * u
    readonly property real radius: 12 * u
    readonly property real gap: 24 * u
    readonly property real ring: 4 * u
    readonly property real lift: 1.06

    readonly property real tHero: 62 * u
    readonly property real tTitle: 46 * u
    readonly property real tHead: 30 * u
    readonly property real tBody: 26 * u
    readonly property real tMeta: 22 * u
    readonly property real tSmall: 19 * u

    readonly property real posterW: 214 * u          // a poster card (2:3) and its caption
    readonly property real posterH: posterW * 1.5
    readonly property real personW: 190 * u

    property var status: ({})                // {ok, source: seerr | tmdb | demo, seerr, credits: [...]}

    // ------------------------------------------------------------------ formatting
    function votes(n) {                      // 883621 -> "884K"
        if (!n) return "";
        return n >= 1e6 ? (n / 1e6).toFixed(n >= 1e7 ? 0 : 1) + "M" : n >= 1000 ? Math.round(n / 1000) + "K" : String(n);
    }
    function runtime(min) {
        if (!min) return "";
        return min >= 60 ? Math.floor(min / 60) + " h" + (min % 60 ? " " + min % 60 + " min" : "") : min + " min";
    }
    function date(d) {                       // "2016-11-10" -> "10 Nov 2016"
        if (!d) return "";
        const x = new Date(d + "T12:00:00");
        return isNaN(x) ? d : Qt.formatDate(x, "d MMM yyyy");
    }
    function age(born, died) {
        if (!born) return 0;
        const b = new Date(born + "T12:00:00"), e = died ? new Date(died + "T12:00:00") : new Date();
        let a = e.getFullYear() - b.getFullYear();
        if (e.getMonth() < b.getMonth() || (e.getMonth() === b.getMonth() && e.getDate() < b.getDate())) a--;
        return a;
    }
    function kindLabel(t) { return t === "tv" ? "TV series" : t === "movie" ? "Movie" : "Person"; }
    function deptLabel(d) {
        return ({Acting: "Acting", Directing: "Directing", Writing: "Writing", Production: "Producing", Creator: "Created",
                 Sound: "Music & sound", Camera: "Camera", Editing: "Editing", Crew: "Crew", Art: "Art"})[d] || d;
    }
    // a made-up poster for titles without one: two colours from the title
    function hue(s) { let h = 0; for (let i = 0; i < (s || "").length; i++) h = (h * 31 + s.charCodeAt(i)) % 360; return h / 360; }

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
            } catch (e) { console.log("movies:", e); }
        }
    }

    // open something: Main pushes the page (titles, people, seasons)
    signal open(var target)                   // {type: movie | tv | person | season, id, n?, dept?}
    signal toast(string text)
}
