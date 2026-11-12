// Couchbox: what the home screen shows, from /var/lib/couchbox/home/home.json (written by
// couchboxd from Settings: the app order, hidden apps, names, weather place, clock). Read
// again every 2 s, so changes in Settings show at once. home-data.js holds the same data
// from when the home screen was installed, for the first paint.
// Continue watching comes from the TV user's couchbox-ontv service, in the file home.json names
// (continueWatching.file; null while it's turned off in Settings), read on the same beat.
// While you were out (couchbox-away, the file in away.file) puts its card first in that row,
// until its reel has been watched to the end or is 12 hours old. Today at home (couchbox-morning,
// the file in day.file) puts its card next, until it's been watched or the next morning.
// The morning show (couchbox-morning, the file in morning.file) puts its tile first on the app
// row (rowApps), from when it's made until noon or until it's been watched to the end.
pragma Singleton
import QtQuick

import "home-data.js" as Initial

QtObject {
    id: d
    property var data: Initial.data
    readonly property var apps: data && data.apps ? data.apps : []
    readonly property var weather: data ? data.weather : null
    readonly property bool clock24: !!(data && data.clock24)
    readonly property string continueFile: data && data.continueWatching ? data.continueWatching.file || "" : ""
    readonly property string awayFile: data && data.away ? data.away.file || "" : ""
    readonly property string dayFile: data && data.day ? data.day.file || "" : ""
    readonly property string morningFile: data && data.morning ? data.morning.file || "" : ""
    property var morningShow: null
    property var showTile: null
    property string lastMorning: ""
    readonly property var rowApps: showTile ? [showTile].concat(apps) : apps   // the row: the show's tile first
    property var watchingItems: []
    property var awayCard: null
    property var dayCard: null
    property var dayInfo: null
    property string lastDay: ""
    readonly property var continueItems: [awayCard, dayCard].filter(x => !!x).concat(watchingItems)
    property string activeMoment: ""        // the Moment playing (couchbox.moments' state, by the voice service)
    property string last: ""
    property string lastContinue: ""
    property string lastAway: ""
    property var awayReel: null
    readonly property int awayHold: 12 * 3600

    function read(path, done) {
        const x = new XMLHttpRequest();
        x.onreadystatechange = () => { if (x.readyState === XMLHttpRequest.DONE) done(x.responseText || ""); };
        x.open("GET", "file://" + path);
        x.send();
    }
    function reload() {
        read("/var/lib/couchbox/home/home.json", text => {
            if (!text || text === d.last) return;
            try { d.data = JSON.parse(text); d.last = text; } catch (e) {}
        });
        read("/var/lib/couchbox/moments.json", text => {
            let id = "";
            try { const a = JSON.parse(text).active; id = a ? a.id : ""; } catch (e) {}
            if (id !== d.activeMoment) d.activeMoment = id;
        });
        readAway();
        readDay();
        readMorning();
        if (!d.continueFile) {
            if (d.watchingItems.length) d.watchingItems = [];
            d.lastContinue = "";
            return;
        }
        read(d.continueFile, text => {
            if (!text || text === d.lastContinue) return;
            try { d.watchingItems = JSON.parse(text).items || []; d.lastContinue = text; } catch (e) {}
        });
    }
    function readAway() {
        if (!d.awayFile) { d.awayReel = null; d.lastAway = ""; showAway(); return; }
        read(d.awayFile, text => {
            if (text !== d.lastAway) {
                d.lastAway = text;
                try { d.awayReel = text ? JSON.parse(text) : null; } catch (e) { d.awayReel = null; }
            }
            showAway();
        });
    }
    function showAway() {                         // (also the 12 hours running out)
        const r = d.awayReel;
        const fresh = !!(r && r.card && !r.seen && r.clips && r.clips.length && Date.now() / 1000 - (r.until || 0) < d.awayHold);
        const card = fresh ? r.card : null;
        if (JSON.stringify(card) !== JSON.stringify(d.awayCard)) d.awayCard = card;
    }
    function readDay() {
        if (!d.dayFile) { d.dayInfo = null; d.lastDay = ""; showDay(); return; }
        read(d.dayFile, text => {
            if (text !== d.lastDay) {
                d.lastDay = text;
                try { d.dayInfo = text ? JSON.parse(text) : null; } catch (e) { d.dayInfo = null; }
            }
            showDay();
        });
    }
    function showDay() {                          // (also the next morning coming)
        const c = d.dayInfo;
        const card = c && c.card && !c.seen && Date.now() / 1000 < (c.until || 0) ? c.card : null;
        if (JSON.stringify(card) !== JSON.stringify(d.dayCard)) d.dayCard = card;
    }
    function readMorning() {
        if (!d.morningFile) { d.morningShow = null; d.lastMorning = ""; showMorning(); return; }
        read(d.morningFile, text => {
            if (text !== d.lastMorning) {
                d.lastMorning = text;
                try { d.morningShow = text ? JSON.parse(text) : null; } catch (e) { d.morningShow = null; }
            }
            showMorning();
        });
    }
    function showMorning() {                      // (also noon coming)
        const s = d.morningShow;
        const now = new Date();
        const today = now.getFullYear() + "-" + String(now.getMonth() + 1).padStart(2, "0") + "-" + String(now.getDate()).padStart(2, "0");
        const fresh = !!(s && s.tile && !s.seen && s.parts && s.parts.length && s.date === today && now.getTime() / 1000 < (s.until || 0));
        const tile = fresh ? s.tile : null;
        if (JSON.stringify(tile) !== JSON.stringify(d.showTile)) d.showTile = tile;
    }
    property Timer poll: Timer { interval: 2000; repeat: true; running: true; triggeredOnStart: true; onTriggered: d.reload() }

    // Changes to the row go through the couchbox command (the TV user may: couchbox group).
    signal run(string cmd)
}
