// "Use your phone as the remote": the phone page's QR code, on every setup step. Before the
// box is online, couchboxd opens a setup Wi-Fi: then one code joins it and a second opens
// the remote.
import QtQuick
import "../settings"

Item {
    id: card
    property var phone: ({mode: "none"})
    visible: phone.mode === "lan" || phone.mode === "hotspot"
    height: visible ? col.height : 0

    function refresh() { T.call("setup.phone", {}, r => card.phone = r, () => {}); }
    Component.onCompleted: refresh()
    Timer { interval: 5000; running: true; repeat: true; onTriggered: card.refresh() }
    Connections {
        target: T
        function onEvent(topic, d) { if (topic === "setup.hotspot" || topic === "network.changed") card.refresh(); }
    }

    Column {
        id: col
        width: parent.width
        spacing: 14 * T.u
        Text {
            width: parent.width
            text: card.phone.mode === "hotspot" ? "No remote? Use your phone" : "Use your phone as the remote"
            color: T.text
            font.family: T.font; font.pixelSize: 25 * T.u; font.weight: Font.DemiBold
        }
        Row {
            spacing: 22 * T.u
            Repeater {
                model: card.phone.mode === "hotspot"
                       ? [{qr: card.phone.wifi, cap: "1. Join its Wi-Fi"}, {qr: card.phone.url, cap: "2. Open the remote"}]
                       : card.phone.mode === "lan" ? [{qr: card.phone.url, cap: "Scan with the camera"}] : []
                Column {
                    required property var modelData
                    spacing: 8 * T.u
                    Rectangle {
                        width: 150 * T.u; height: width; radius: 10 * T.u; color: "white"
                        Image { anchors.fill: parent; anchors.margins: 10 * T.u; smooth: false; source: modelData.qr ? backend.qr(modelData.qr) : "" }
                    }
                    Text { text: modelData.cap; color: T.dim; font.family: T.font; font.pixelSize: 20 * T.u }
                }
            }
        }
        Text {
            width: parent.width
            visible: card.phone.mode === "hotspot"
            wrapMode: Text.WordWrap
            text: "Wi-Fi " + (card.phone.ssid || "") + " · password " + (card.phone.password || "")
            color: T.dim
            font.family: T.font; font.pixelSize: 20 * T.u
        }
    }
}
