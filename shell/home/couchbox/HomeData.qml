// Couchbox: what the home screen shows, from /var/lib/couchbox/home/home.json (written by
// couchboxd from Settings: the app order, hidden apps, names, weather place, clock). Read
// again every 2 s, so changes in Settings show at once. home-data.js holds the same data
// from when the home screen was installed, for the first paint.
// Continue watching comes from the TV user's couchbox-ontv service, in the file home.json names
// (continueWatching.file; null while it's turned off in Settings), read on the same beat.
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
    property var continueItems: []
    property string last: ""
    property string lastContinue: ""

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
        if (!d.continueFile) {
            if (d.continueItems.length) d.continueItems = [];
            d.lastContinue = "";
            return;
        }
        read(d.continueFile, text => {
            if (!text || text === d.lastContinue) return;
            try { d.continueItems = JSON.parse(text).items || []; d.lastContinue = text; } catch (e) {}
        });
    }
    property Timer poll: Timer { interval: 2000; repeat: true; running: true; triggeredOnStart: true; onTriggered: d.reload() }

    // Changes to the row go through the couchbox command (the TV user may: couchbox group).
    signal run(string cmd)
}
