// The last card in a row: "See all" (the website's arrow next to a row's title).
import QtQuick

Rectangle {
    id: card
    property string title: ""
    property string path: ""
    property string mediaType: ""
    property real cardHeight: S.cardH
    width: S.cardW
    height: cardHeight
    radius: 12 * S.u
    color: activeFocus ? S.panel2 : S.panel
    border.color: S.line
    border.width: 1
    scale: activeFocus ? 1.06 : 1
    Behavior on scale { NumberAnimation { duration: 110 } }
    function activate() {
        if (path === "requests") S.openRequests();
        else if (path.startsWith("people/")) S.openPeople(title, path);
        else S.openGrid(title, path, mediaType);
    }
    Keys.onReturnPressed: activate()
    Keys.onEnterPressed: activate()
    Column {
        anchors.centerIn: parent
        spacing: 12 * S.u
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            width: 68 * S.u; height: width; radius: width / 2
            color: "transparent"; border.color: S.text2; border.width: 2 * S.u
            Text { anchors.centerIn: parent; text: "→"; color: S.text2; font.pixelSize: 34 * S.u }
        }
        Text { text: "See All"; color: S.text2; font.family: S.font; font.pixelSize: 22 * S.u; font.weight: Font.DemiBold }
    }
    Ring { on: card.activeFocus; radiusOf: 12 }
}
