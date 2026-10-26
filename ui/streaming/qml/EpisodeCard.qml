// An episode on a show's page: a large 16:9 still with progress, the number and title, length,
// and the description under it. OK plays it (from where it was left).
import QtQuick

Item {
    id: card
    property var c: ({})
    width: D.epW
    height: D.epH + 170 * D.u
    Keys.onReturnPressed: D.play(c.id)
    Keys.onEnterPressed: D.play(c.id)

    Rectangle {
        id: frame
        width: D.epW
        height: D.epH
        radius: 6 * D.u
        color: D.panel
        clip: true
        scale: card.activeFocus ? 1.05 : 1
        Behavior on scale { NumberAnimation { duration: 110 } }
        Image {
            anchors.fill: parent
            source: D.img(card.c.landscape, D.epW * 1.2, D.epH * 1.2)
            sourceSize.width: D.px(D.epW)
            asynchronous: true
            fillMode: Image.PreserveAspectCrop
        }
        Rectangle {
            visible: card.activeFocus
            anchors.centerIn: parent
            width: 96 * D.u; height: width; radius: width / 2
            color: Qt.rgba(0, 0, 0, 0.55)
            border.color: D.accent; border.width: 3 * D.u
            Text { anchors.centerIn: parent; anchors.horizontalCenterOffset: 4 * D.u; text: "▶"; color: D.accent; font.pixelSize: 40 * D.u }
        }
        Rectangle {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            height: 8 * D.u
            color: Qt.rgba(0, 0, 0, 0.6)
            visible: (card.c.progress || 0) > 0
            Rectangle { width: parent.width * Math.min(1, card.c.progress || 0); height: parent.height; color: D.accent }
        }
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: "transparent"
            border.color: D.accent
            border.width: 5 * D.u
            visible: card.activeFocus
        }
    }
    Column {
        anchors { top: frame.bottom; topMargin: 16 * D.u; left: parent.left; right: parent.right }
        spacing: 8 * D.u
        Row {
            spacing: 12 * D.u
            width: parent.width
            Text {
                id: num
                visible: card.c.episode > 0
                text: card.c.episode + "."
                color: D.accent
                font.family: D.font
                font.pixelSize: 25 * D.u
                font.weight: Font.Black
            }
            Text {
                width: parent.width - (num.visible ? num.width + 12 * D.u : 0) - len.width - 12 * D.u
                text: card.c.title || ""
                elide: Text.ElideRight
                color: card.activeFocus ? D.accent : D.text
                font.family: D.font
                font.pixelSize: 25 * D.u
                font.weight: Font.Bold
            }
            Text {
                id: len
                text: card.c.live ? card.c.viewers : card.c.completed ? "Watched" : card.c.progress > 0 ? D.length(card.c.duration - card.c.timecode) + " left" : D.length(card.c.duration || 0)
                color: D.dim
                font.family: D.font
                font.pixelSize: 20 * D.u
                anchors.verticalCenter: parent.verticalCenter
            }
        }
        Text {
            width: parent.width
            text: card.c.description || ""
            wrapMode: Text.WordWrap
            maximumLineCount: 3
            elide: Text.ElideRight
            color: D.text2
            font.family: D.font
            font.pixelSize: 19 * D.u
            lineHeight: 1.15
        }
    }
}
