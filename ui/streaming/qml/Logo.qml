// The site's logo: its image (2nd Try) or its wordmark in the accent colour (":DROPOUT").
import QtQuick

Item {
    property real size: 46                    // text size / about the image's height, at 1080p
    implicitWidth: img.visible ? img.width : txt.implicitWidth
    implicitHeight: img.visible ? img.height : txt.implicitHeight
    Image {
        id: img
        visible: !!D.site.logo && status === Image.Ready
        source: D.site.logo ? D.img(D.site.logo, 0, 0) + "&h=" + Math.round(parent.size * 2.4 * D.u) : ""
        height: parent.size * 1.3 * D.u
        width: implicitWidth * height / Math.max(1, implicitHeight)
        fillMode: Image.PreserveAspectFit
        asynchronous: true
    }
    Text {
        id: txt
        visible: !img.visible
        text: D.site.logo_text || D.name
        color: D.accent
        font.family: D.font
        font.pixelSize: parent.size * D.u
        font.weight: Font.Black
        font.letterSpacing: 1.5 * D.u
    }
}
