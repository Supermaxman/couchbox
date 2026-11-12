// Couchbox: what the home screen shows, from /var/lib/couchbox/home/home.json (written by
// couchboxd from Settings: the app order, hidden apps, names, weather place, clock). Read
// again every 2 s, so changes in Settings show at once. home-data.js holds the same data
// from when the home screen was installed, for the first paint.
// Continue watching comes from the TV user's couchbox-ontv service, in the file home.json names
// (continueWatching.file; null while it's turned off in Settings), read on the same beat.
// While you were out (couchbox-away, the file in away.file) puts its card first in that row,
// until its reel has been watched to the end or is 12 hours old.
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
    property var watchingItems: []
    property var awayCard: null
    readonly property var continueItems: awayCard ? [awayCard].concat(watchingItems) : watchingItems
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
    property Timer poll: Timer { interval: 2000; repeat: true; running: true; triggeredOnStart: true; onTriggered: d.reload() }

    // Changes to the row go through the couchbox command (the TV user may: couchbox group).
    signal run(string cmd)
}
