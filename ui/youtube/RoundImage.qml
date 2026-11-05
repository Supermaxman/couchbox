// A round picture (a channel's), drawn on a Canvas clipped to a circle: for the few on a page
// (the cards use Corners instead), and it needs no shader effect.
import QtQuick

Item {
    id: round
    property string source: ""
    property string fallback: ""             // initials while there's no picture
    property bool ready: false
    Rectangle {
        anchors.fill: parent
        radius: width / 2
        color: Qt.hsla(Y.hue(round.fallback), 0.5, 0.4, 1)
        visible: !round.ready
        Text { anchors.centerIn: parent; text: round.fallback.slice(0, 2); color: "white"; font.family: Y.font; font.pixelSize: parent.height * 0.4 }
    }
    Canvas {
        id: canvas
        anchors.fill: parent
        visible: round.ready
        onImageLoaded: { round.ready = isImageLoaded(round.source); requestPaint(); }
        onPaint: {
            const c = getContext("2d");
            c.reset();
            if (!round.source || !isImageLoaded(round.source)) return;
            c.beginPath();
            c.arc(width / 2, height / 2, Math.min(width, height) / 2, 0, 2 * Math.PI);
            c.closePath();
            c.clip();
            c.drawImage(round.source, 0, 0, width, height);
        }
    }
    onSourceChanged: {
        ready = false;
        if (!source) return;
        if (canvas.isImageLoaded(source)) { ready = true; canvas.requestPaint(); }
        else canvas.loadImage(source);
    }
    Component.onCompleted: if (source) canvas.loadImage(source)
}
