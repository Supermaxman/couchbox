// The Seerr app's shared state: the website's colours and sizes, the API (through
// couchbox-voice's proxy), a details cache, status names, and navigation requests (Main.qml
// connects to the signals and opens the pages).
pragma Singleton
import QtQuick

QtObject {
    id: s

    property real u: 1                       // Main sets height / 1080

    // ------------------------------------------------------------------ the website's look
    readonly property color bg: "#111827"            // gray-900
    readonly property color side: "#1a2131"
    readonly property color panel: "#1f2937"         // gray-800
    readonly property color panel2: "#273244"
    readonly property color line: "#374151"          // gray-700
    readonly property color text: "#ffffff"
    readonly property color text2: "#d1d5db"         // gray-300
    readonly property color dim: "#9ca3af"           // gray-400
    readonly property color indigo: "#6366f1"
    readonly property color indigoDark: "#4f46e5"
    readonly property color purple: "#9333ea"
    readonly property color heading: "#a78bfa"       // the purple page titles
    readonly property color green: "#22c55e"
    readonly property color yellow: "#eab308"
    readonly property color red: "#dc2626"
    readonly property color movieBlue: "#2563eb"
    readonly property color seriesPurple: "#7c3aed"
    readonly property color focus: "#818cf8"         // focus ring
    readonly property string font: "Inter"

    // sizes for a TV across the room (the website's, about a fifth bigger)
    readonly property real cardW: 210 * u            // posters 2:3
    readonly property real cardH: 315 * u
    readonly property real tileW: 340 * u            // genre, studio, network tiles
    readonly property real tileH: 170 * u
    readonly property real rowGap: 24 * u            // between cards in a row
    readonly property real edge: 56 * u              // right margin, clear of TV overscan
    readonly property real gutter: 48 * u            // between the sidebar and the pages

    // ------------------------------------------------------------------ API
    readonly property string api: "http://127.0.0.1:8790/seerr"
    readonly property string voice: "http://127.0.0.1:8790"
    readonly property string tmdb: "https://image.tmdb.org/t/p/"

    function call(method, path, body, done, fail) {
        const x = new XMLHttpRequest();
        x.onreadystatechange = () => {
            if (x.readyState !== XMLHttpRequest.DONE)
                return;
            let r = null;
            try { r = JSON.parse(x.responseText); } catch (e) {}
            // A card that scrolled away (and was destroyed) before the answer came can't take it.
            try {
                if (x.status === 200 && r && !r.error)
                    done(r);
                else if (fail)
                    fail(r && r.error ? r.error : "Seerr isn't answering.");
            } catch (e) {}
        };
        x.open(method, (path.startsWith("/play/") ? voice : api) + path);
        x.setRequestHeader("X-Couchbox", "1");
        if (body)
            x.setRequestHeader("Content-Type", "application/json");
        x.send(body ? JSON.stringify(body) : null);
    }

    function get(path, done, fail) { call("GET", path, null, done, fail); }

    // Details of a movie or show, cached: cards that only know (type, id) (recently added,
    // requests, watchlist) fetch them, as the website does.
    property var cache: ({})
    property var waiting: ({})
    function details(type, id, done) {
        const key = type + "/" + id;
        if (cache[key]) return done(cache[key]);
        if (waiting[key]) return waiting[key].push(done);
        waiting[key] = [done];
        get("/" + key, r => {
            cache[key] = r;
            const w = waiting[key]; delete waiting[key];
            for (const f of w) f(r);
        }, () => { delete waiting[key]; });
    }

    function img(path, size) {
        if (!path) return "";
        return path.startsWith("http") ? path : tmdb + (size || "w300_and_h450_face") + path;
    }

    // A search/discover result (or details) as a card's fields.
    function card(i, typeHint) {
        const type = i.mediaType || typeHint || (i.title !== undefined ? "movie" : "tv");
        return {kind: type === "person" ? "person" : "title", mediaType: type, tmdbId: i.tmdbId || i.id,
                title: i.title || i.name || "", year: (i.releaseDate || i.firstAirDate || "").slice(0, 4),
                poster: i.posterPath || i.profilePath || "", backdrop: i.backdropPath || "",
                overview: i.overview || "", status: i.mediaInfo ? i.mediaInfo.status : 0, caption: ""};
    }

    // ------------------------------------------------------------------ statuses
    // media: 1 unknown, 2 pending, 3 processing, 4 partly available, 5 available, 6 blocklisted, 7 deleted
    function statusName(st) {
        return ({2: "Pending", 3: "Requested", 4: "Partially Available", 5: "Available", 6: "Blocklisted", 7: "Deleted"})[st] || "";
    }
    function statusColor(st) {
        return st === 4 || st === 5 ? green : st === 2 ? yellow : st === 3 ? indigo : st >= 6 ? red : line;
    }
    // requests: 1 pending approval, 2 approved, 3 declined, 4 failed, 5 completed
    function requestName(r) {
        const m = r.media || {};
        if (r.status === 3) return "Declined";
        if (r.status === 4) return "Failed";
        if (r.status === 1) return "Pending Approval";
        if (m.status === 5) return "Available";
        if (m.status === 4) return "Partially Available";
        return "Requested";
    }
    function requestColor(r) {
        const n = requestName(r);
        return n === "Available" || n === "Partially Available" ? green : n === "Pending Approval" ? yellow
             : n === "Declined" || n === "Failed" ? red : indigo;
    }

    function money(n) { return n ? "$" + Number(n).toLocaleString(Qt.locale("en_US"), "f", 2) : ""; }
    // dates as TMDB gives them ("2024-03-01", or midnight UTC): the calendar day, not shifted
    // into this time zone (which would make it the day before)
    function date(d) {
        const m = (d || "").match(/^(\d{4})-(\d{2})-(\d{2})/);
        return m ? new Date(+m[1], +m[2] - 1, +m[3]).toLocaleDateString(Qt.locale("en_US"), "MMMM d, yyyy") : "";
    }
    function language(code) {
        const names = {en: "English", ja: "Japanese", ko: "Korean", fr: "French", es: "Spanish", de: "German",
                       it: "Italian", zh: "Mandarin", cn: "Cantonese", hi: "Hindi", pt: "Portuguese", ru: "Russian",
                       sv: "Swedish", da: "Danish", no: "Norwegian", nl: "Dutch", pl: "Polish", tr: "Turkish",
                       th: "Thai", ta: "Tamil", te: "Telugu", ar: "Arabic", he: "Hebrew", fi: "Finnish", cs: "Czech",
                       id: "Indonesian", tl: "Tagalog", uk: "Ukrainian", fa: "Persian", ml: "Malayalam"};
        return names[code] || (code || "").toUpperCase();
    }
    function capital(t) { return t ? t[0].toUpperCase() + t.slice(1) : t; }

    // ------------------------------------------------------------------ navigation (Main.qml)
    signal openMedia(string mediaType, int tmdbId)
    signal openPerson(int personId)
    signal openGrid(string title, string path, string mediaType)
    signal openRequests()
    signal openRequest(var media)                // the request dialog: a /movie or /tv result
    signal closedDialog()
    signal openIssue(var media)                  // the Report an Issue dialog
    signal openPeople(string title, string path) // full cast / crew: "people/<movie|tv>/<id>/<cast|crew>"
    signal askText(string title, string text, var done)   // the keyboard pop-up; done(text)
    signal pick(string title, var options, int current, var done)  // a list to choose from; done(index)
    signal requested(string mediaType, int tmdbId) // a request went through: pages refresh
    signal toSidebar()
    signal toSearch()
    signal toast(string text)
}
