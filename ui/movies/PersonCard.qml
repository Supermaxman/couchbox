// A person in a row: a round photo, the name, and their role (a character, a job, what they're
// known for).
import QtQuick

Item {
    id: card
    property var item: ({})
    property bool on: false
    width: M.personW
    height: photo.height + caption.implicitHeight + 18 * M.u
    scale: on ? M.lift : 1
    z: on ? 2 : 0
    Behavior on scale { NumberAnimation { duration: 120 } }
    RoundPhoto {
        id: photo
        anchors.horizontalCenter: parent.horizontalCenter
        width: parent.width - 20 * M.u; height: width
        source: card.item.image || ""
        name: card.item.name || card.item.title || ""
    }
    Rectangle {
        anchors { fill: photo; margins: -M.ring - 3 * M.u }
        radius: width / 2; color: "transparent"
        border.color: M.focus; border.width: M.ring
        visible: card.on
    }
    Column {
        id: caption
        anchors { left: parent.left; right: parent.right; top: photo.bottom; topMargin: 14 * M.u }
        spacing: 3 * M.u
        Text { width: parent.width; horizontalAlignment: Text.AlignHCenter; text: card.item.name || card.item.title || ""; color: card.on ? M.text : M.text2
               font.family: M.font; font.pixelSize: M.tMeta; font.weight: Font.DemiBold; elide: Text.ElideRight }
        Text { width: parent.width; horizontalAlignment: Text.AlignHCenter; text: card.item.role || card.item.sub || ""; color: M.dim
               font.family: M.font; font.pixelSize: M.tSmall; elide: Text.ElideRight; visible: !!text }
    }
}
