// A cast member: round photo, name, character (website's cast slider and search results).
import QtQuick

Rectangle {
    id: card
    property int personId: 0
    property string name: ""
    property string photo: ""
    property string role: ""
    width: S.cardW
    height: S.cardH
    radius: 12 * S.u
    gradient: Gradient {
        GradientStop { position: 0.0; color: S.panel }
        GradientStop { position: 1.0; color: S.bg }
    }
    border.color: S.line
    border.width: 1
    scale: activeFocus ? 1.06 : 1
    Behavior on scale { NumberAnimation { duration: 110 } }
    Keys.onReturnPressed: S.openPerson(personId)
    Keys.onEnterPressed: S.openPerson(personId)

    Rectangle {
        id: face
        anchors.horizontalCenter: parent.horizontalCenter
        y: 22 * S.u
        width: 146 * S.u
        height: width
        radius: width / 2
        color: S.panel2
        RoundImage {
            anchors.fill: parent
            source: S.img(card.photo, "w185")
        }
        Text {
            anchors.centerIn: parent
            visible: !card.photo
            text: card.name ? card.name[0] : ""
            color: S.dim
            font.pixelSize: 56 * S.u
            font.weight: Font.Bold
        }
    }
    Text {
        id: nameText
        anchors { top: face.bottom; topMargin: 14 * S.u; horizontalCenter: parent.horizontalCenter }
        width: parent.width - 16 * S.u
        text: card.name
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        maximumLineCount: 2
        elide: Text.ElideRight
        color: S.text
        font.family: S.font
        font.pixelSize: 20 * S.u
        font.weight: Font.Bold
    }
    Text {
        anchors { top: nameText.bottom; topMargin: 4 * S.u; horizontalCenter: parent.horizontalCenter }
        width: parent.width - 16 * S.u
        text: card.role
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        maximumLineCount: 2
        elide: Text.ElideRight
        color: S.text2
        font.family: S.font
        font.pixelSize: 17 * S.u
    }
    Ring { on: card.activeFocus; radiusOf: 12 }
}
