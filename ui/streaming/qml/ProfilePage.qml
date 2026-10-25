// "Who's watching?" (accounts with more than one profile).
import QtQuick

FocusScope {
    id: page
    property var profiles: []
    signal done(var status)
    Rectangle { anchors.fill: parent; color: D.bg }
    Column {
        anchors.centerIn: parent
        spacing: 60 * D.u
        Text { anchors.horizontalCenter: parent.horizontalCenter; text: "Who's watching?"; color: D.text; font.family: D.font; font.pixelSize: 60 * D.u; font.weight: Font.Black }
        ListView {
            id: list
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.min(count, 5) * 280 * D.u
            height: 300 * D.u
            orientation: ListView.Horizontal
            interactive: false
            focus: true
            model: page.profiles
            delegate: Column {
                required property var modelData
                width: 280 * D.u
                spacing: 18 * D.u
                Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 200 * D.u; height: width; radius: 16 * D.u
                    color: D.panel
                    border.color: parent.ListView.isCurrentItem ? D.accent : "transparent"
                    border.width: 6 * D.u
                    Image { anchors.fill: parent; anchors.margins: 6 * D.u; source: modelData.image; fillMode: Image.PreserveAspectCrop; asynchronous: true }
                    Text { anchors.centerIn: parent; visible: !modelData.image; text: modelData.name[0] || "?"; color: D.text; font.pixelSize: 90 * D.u; font.weight: Font.Black }
                }
                Text { anchors.horizontalCenter: parent.horizontalCenter; text: modelData.name; color: D.text; font.family: D.font; font.pixelSize: 28 * D.u }
            }
            function pick() { D.call("profile", {index: page.profiles[currentIndex].index}, r => page.done(r), err => D.toast(err)); }
            Keys.onReturnPressed: pick()
            Keys.onEnterPressed: pick()
        }
    }
}
