// A photo cropped to a circle (people), drawn on a Canvas so it looks the same with or without
// the GPU (as the Seerr app does). No photo: the initials.
import QtQuick

Item {
    id: root
    property url source
    property string name: ""
    property int sourceWidth: 185
    Rectangle {
        anchors.fill: parent; radius: width / 2
        color: Qt.hsla(M.hue(root.name), 0.30, 0.24, 1)
        visible: photo.status !== Image.Ready
        Text {
            anchors.centerIn: parent
            text: root.name.split(" ").filter(x => !!x).slice(0, 2).map(x => x[0]).join("")
            color: M.text2; font.family: M.font; font.pixelSize: root.width * 0.32; font.weight: Font.DemiBold
        }
    }
    Image {                                   // only to learn the photo's size
        id: photo
        source: root.source
        sourceSize.width: root.sourceWidth
        asynchronous: true
        visible: false
        onStatusChanged: if (status === Image.Ready) canvas.loadImage(root.source)
    }
    Canvas {
        id: canvas
        anchors.fill: parent
        onImageLoaded: requestPaint()
        onWidthChanged: requestPaint()
        onPaint: {
            const ctx = getContext("2d");
            ctx.reset();
            if (!isImageLoaded(root.source) || !width || photo.status !== Image.Ready) return;
            const iw = photo.implicitWidth, ih = photo.implicitHeight, side = Math.min(iw, ih);
            ctx.save();
            ctx.beginPath();
            ctx.arc(width / 2, height / 2, Math.min(width, height) / 2, 0, 2 * Math.PI);
            ctx.closePath();
            ctx.clip();
            const scale = width / side;
            const dw = iw * scale, dh = ih * scale;
            ctx.drawImage(root.source, (width - dw) / 2, ih > iw ? -(dh - height) / 5 : (height - dh) / 2, dw, dh);
            ctx.restore();
        }
    }
}
