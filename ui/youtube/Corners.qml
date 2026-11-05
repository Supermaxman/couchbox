// Rounded corners for a picture without a layer per card (too much for the Pi with a page of
// thumbnails): the four corners outside the rounding, painted in the colour behind the card.
import QtQuick
import QtQuick.Shapes

Shape {
    id: c
    property real r: Y.radius
    property color color: Y.bg
    property bool lower: true                 // the boxed cards' pictures only round their top
    preferredRendererType: Shape.CurveRenderer
    ShapePath {
        fillColor: c.color
        strokeColor: "transparent"
        strokeWidth: 0
        PathSvg {
            readonly property real w: c.width
            readonly property real h: c.height
            readonly property real r: c.r
            path: "M0 0H" + r + "A" + r + " " + r + " 0 0 0 0 " + r + "Z"
                + "M" + w + " 0V" + r + "A" + r + " " + r + " 0 0 0 " + (w - r) + " 0Z"
                + (c.lower ? "M0 " + h + "V" + (h - r) + "A" + r + " " + r + " 0 0 0 " + r + " " + h + "Z"
                            + "M" + w + " " + h + "H" + (w - r) + "A" + r + " " + r + " 0 0 0 " + w + " " + (h - r) + "Z" : "")
        }
    }
}
