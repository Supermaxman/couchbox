// Something is under way: an arc that turns. It turns on Qt's render thread (an Animator), so
// it keeps moving while the app waits on a slow disk or a busy daemon: the screen never looks
// frozen.
import QtQuick

Item {
    id: s
    property color color: T.accent
    property bool running: visible
    implicitWidth: 34 * T.u
    implicitHeight: implicitWidth
    Canvas {
        id: arc
        anchors.fill: parent
        onPaint: {
            const c = getContext("2d"), w = Math.max(2, width * 0.13), r = width / 2 - w;
            c.reset();
            c.lineWidth = w;
            c.lineCap = "round";
            c.strokeStyle = Qt.rgba(s.color.r, s.color.g, s.color.b, 0.22);
            c.beginPath(); c.arc(width / 2, height / 2, r, 0, 2 * Math.PI); c.stroke();
            c.strokeStyle = s.color;
            c.beginPath(); c.arc(width / 2, height / 2, r, -Math.PI / 2, Math.PI / 2 * 0.6); c.stroke();
        }
        onWidthChanged: requestPaint()
        RotationAnimator on rotation { from: 0; to: 360; duration: 900; loops: Animation.Infinite; running: s.running }
    }
}
