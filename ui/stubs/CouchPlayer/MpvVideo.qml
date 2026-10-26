// Stand-in for the libmpv video item when there's no GPU (off-screen screenshots): a gray
// frame whose position advances, with the same properties and functions.
import QtQuick

Rectangle {
    color: "#2a2a2a"
    property real position: 0
    property real duration: 0
    property bool paused: false
    property bool buffering: false
    property bool ended: false
    property var subtitles: [{id: 1, title: "English", lang: "en"}]
    property int subtitle: 0
    property string error: ""
    function load(url, start) { position = start; duration = 3600; paused = false; }
    function loadLive(url) { position = 0; duration = 86400; paused = false; }
    function addSubtitle(url) {}
    function togglePause() { paused = !paused; }
    function setPaused(p) { paused = p; }
    function seek(d) { position = Math.max(0, Math.min(duration, position + d)); }
    function seekTo(p) { position = p; }
    function setSubtitle(s) { subtitle = s; }
    function stop() {}
    function setSubtitlePosition(p) {}
    function shutdown() {}
    Timer { interval: 1000; repeat: true; running: !parent.paused && parent.duration > 0; onTriggered: parent.position += 1 }
    Text { anchors.centerIn: parent; text: "video"; color: "#555"; font.pixelSize: 60 }
}
