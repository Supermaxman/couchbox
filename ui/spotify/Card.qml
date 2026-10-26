// A square card: cover art, a name and a second line (artist, year, owner). It works out its
// height from its width and the text, so nothing is cut off. Artists get round art.
import QtQuick

Item {
    id: card
    property var item: ({})
    property bool current: false
    readonly property real artH: width - 2 * pad
    readonly property real pad: 14 * S.u
    implicitHeight: pad + artH + 14 * S.u + title.implicitHeight + 4 * S.u + sub.implicitHeight + pad
    scale: current ? S.lift : 1
    z: current ? 2 : 1
    Behavior on scale { NumberAnimation { duration: 120 } }

    Rectangle {
        anchors.fill: parent
        radius: S.radius
        color: card.current ? S.panel2 : S.panel
        border.color: card.current ? S.focus : "transparent"
        border.width: S.ring
    }
    Art {
        id: art
        x: card.pad; y: card.pad
        width: card.artH; height: card.artH
        item: card.item
    }
    Rectangle {                                  // playing now
        visible: !!card.item && !!card.item.uri && (S.nowUri === card.item.uri || ((S.now.context || {}).uri === card.item.uri)) && S.playing
        anchors { right: art.right; bottom: art.bottom; margins: 10 * S.u }
        width: 54 * S.u; height: width; radius: width / 2; color: S.accent
        Image { anchors.centerIn: parent; width: 28 * S.u; height: width; sourceSize: Qt.size(width, height); source: S.icon("bars") }
    }
    Text {
        id: title
        anchors { left: parent.left; right: parent.right; top: art.bottom; topMargin: 14 * S.u; leftMargin: card.pad; rightMargin: card.pad }
        text: card.item ? card.item.name || "" : ""
        color: S.text; font.family: S.font; font.pixelSize: S.tBody; font.weight: Font.DemiBold
        elide: Text.ElideRight; maximumLineCount: 1
    }
    Text {
        id: sub
        anchors { left: title.left; right: title.right; top: title.bottom; topMargin: 4 * S.u }
        text: S.subtitle(card.item)
        color: S.dim; font.family: S.font; font.pixelSize: S.tMeta
        elide: Text.ElideRight; maximumLineCount: 1
    }
}
