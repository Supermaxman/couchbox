// An image cropped to a circle (actor photos, avatars). Drawn on a Canvas (photo, then
// keep only a smooth circle of it), so it looks the same with or without the GPU.
import QtQuick

Item {
    id: root
    property url source
    property int sourceWidth: 185
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
            // cover: a square from the middle of the photo (upper part for portraits)
            const iw = photo.implicitWidth, ih = photo.implicitHeight, side = Math.min(iw, ih);
            const k = iw / photo.sourceSize.width || 1;
            ctx.save();
            ctx.beginPath();
            ctx.arc(width / 2, height / 2, Math.min(width, height) / 2, 0, 2 * Math.PI);
            ctx.closePath();
            ctx.clip();
            const scale = width / side;
            const dw = iw * scale, dh = ih * scale;
            ctx.drawImage(root.source, (width - dw) / 2, ih > iw ? -(dh - height) / 4 : (height - dh) / 2, dw, dh);
            ctx.restore();
        }
    }
}
