// The YouTube mark at the top right of the pages: the red play button and the name.
import QtQuick

Row {
    property real h: 44 * Y.u                 // the play button's height
    spacing: h * 0.18
    Rectangle {
        width: parent.h * 1.42
        height: parent.h
        radius: parent.h * 0.28
        color: Y.red
        anchors.verticalCenter: parent.verticalCenter
        Canvas {
            anchors.centerIn: parent
            width: parent.height * 0.42
            height: parent.height * 0.46
            onPaint: {
                const c = getContext("2d");
                c.reset();
                c.fillStyle = "white";
                c.beginPath();
                c.moveTo(0, 0);
                c.lineTo(width, height / 2);
                c.lineTo(0, height);
                c.closePath();
                c.fill();
            }
        }
    }
    Text {
        text: "YouTube"
        color: Y.text
        font.family: Y.font
        font.pixelSize: parent.h * 1.0
        font.weight: Font.Bold
        font.letterSpacing: -parent.h * 0.04
        anchors.verticalCenter: parent.verticalCenter
    }
}
