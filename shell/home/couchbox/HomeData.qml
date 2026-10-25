// Couchbox: what the home screen shows, from /var/lib/couchbox/home/home.json (written by
// couchboxd from Settings: the app order, hidden apps, names, weather place, clock). Read
// again every 2 s, so changes in Settings show at once. home-data.js holds the same data
// from when the home screen was installed, for the first paint.
pragma Singleton
import QtQuick

import "home-data.js" as Initial

QtObject {
    id: d
    property var data: Initial.data
    readonly property var apps: data && data.apps ? data.apps : []
    readonly property var weather: data ? data.weather : null
    readonly property bool clock24: !!(data && data.clock24)
    property string last: ""

    function reload() {
        const x = new XMLHttpRequest();
        x.onreadystatechange = () => {
            if (x.readyState !== XMLHttpRequest.DONE || !x.responseText || x.responseText === d.last) return;
            try { d.data = JSON.parse(x.responseText); d.last = x.responseText; } catch (e) {}
        };
        x.open("GET", "file:///var/lib/couchbox/home/home.json");
        x.send();
    }
    property Timer poll: Timer { interval: 2000; repeat: true; running: true; triggeredOnStart: true; onTriggered: d.reload() }

    // Changes to the row go through the couchbox command (the TV user may: couchbox group).
    signal run(string cmd)
}
