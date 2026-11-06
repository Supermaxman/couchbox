// A round picture (a channel's), drawn on a Canvas clipped to a circle: for the few on a page
// (the cards use Corners instead), and it needs no shader effect. radius >= 0: a rounded
// rectangle instead (cards over the video, where no colour behind them can paint the corners).
import QtQuick

Item {
    id: round
    property string source: ""
    property string fallback: ""             // initials while there's no picture
    property bool ready: false
    property real radius: -1
    property bool cover: false                // fill it, cropping (a thumbnail), rather than stretch
    // the address to load ("//yt3..." without its scheme from some answers)
    readonly property string url: source.indexOf("//") === 0 ? "https:" + source : source
    Rectangle {
        anchors.fill: parent
        radius: round.radius < 0 ? width / 2 : round.radius
        color: Qt.hsla(Y.hue(round.fallback), 0.5, 0.4, 1)
        visible: !round.ready && round.radius < 0
        Text { anchors.centerIn: parent; text: round.fallback.slice(0, 2); color: "white"; font.family: Y.font; font.pixelSize: parent.height * 0.4 }
    }
    Canvas {
        id: canvas
        anchors.fill: parent
        visible: round.ready
        onImageLoaded: round.check()
        onAvailableChanged: round.check()
        onPaint: {
            const c = getContext("2d");
            c.reset();
            if (!round.url || !isImageLoaded(round.url)) return;
            c.beginPath();
            if (round.radius < 0) c.arc(width / 2, height / 2, Math.min(width, height) / 2, 0, 2 * Math.PI);
            else c.roundedRect(0, 0, width, height, round.radius, round.radius);
            c.closePath();
            c.clip();
            if (round.cover) {                 // the picture's middle, at the box's shape
                const im = c.createImageData(round.url);
                const iw = im.width || width, ih = im.height || height;
                const k = Math.max(width / iw, height / ih);
                c.drawImage(round.url, (width - iw * k) / 2, (height - ih * k) / 2, iw * k, ih * k);
            } else c.drawImage(round.url, 0, 0, width, height);
        }
    }
    // Loaded already (the same picture elsewhere: Who's watching, the controls) gives no
    // imageLoaded: so look, and look again shortly (the guide's picture stayed initials)
    function check() {
        if (!url) return;
        if (canvas.isImageLoaded(url)) { ready = true; canvas.requestPaint(); }
    }
    function begin() {
        ready = false;
        if (!url) return;
        if (canvas.isImageLoaded(url)) { check(); return; }
        canvas.loadImage(url);
        recheck.restart();
    }
    Timer { id: recheck; interval: 400; repeat: true; property int n: 0
            onTriggered: { round.check(); if (round.ready || ++n > 10) { stop(); n = 0; } } }
    onUrlChanged: begin()
    Component.onCompleted: begin()
}
