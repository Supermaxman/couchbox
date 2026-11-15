// "Use your phone as the remote": the phone page's QR code, on every setup step. Before the
// box is online, couchboxd opens a setup Wi-Fi: then one code joins it and a second opens
// the remote. Until it opens (the box first waits to see whether it gets online), the card
// holds the codes' places and says about when they come.
import QtQuick
import "../settings"

Item {
    id: card
    property var phone: ({mode: "none"})
    readonly property bool twoCodes: phone.mode === "hotspot" || phone.mode === "waiting"
    visible: phone.mode === "lan" || twoCodes
    height: visible ? col.height : 0

    // the codes, rebuilt only when they change: it asks every 5 s, and new images each time flash
    property var codes: []
    function refresh() {
        T.call("setup.phone", {}, r => {
            card.phone = r;
            const c = r.mode === "hotspot" || r.mode === "waiting"
                    ? [{qr: r.wifi || "", cap: "1. Join its Wi-Fi"}, {qr: r.url || "", cap: "2. Open the remote"}]
                    : r.mode === "lan" ? [{qr: r.url, cap: "Scan with the camera"}] : [];
            if (JSON.stringify(c) !== JSON.stringify(card.codes)) card.codes = c;
        }, () => {});
    }
    Component.onCompleted: refresh()
    Timer { interval: 5000; running: true; repeat: true; onTriggered: card.refresh() }
    Connections {
        target: T
        function onEvent(topic, d) { if (topic === "setup.hotspot" || topic === "network.changed") card.refresh(); }
    }
    function when(s) {
        if (s <= 10) return "in a few seconds";
        if (s < 50) return "in about " + Math.ceil(s / 10) * 10 + " seconds";
        if (s < 90) return "in about a minute";
        return "in about " + Math.round(s / 60) + " minutes";
    }

    Column {
        id: col
        width: parent.width
        spacing: 14 * T.u
        Text {
            width: parent.width
            text: card.twoCodes ? "No remote? Use your phone" : "Use your phone as the remote"
            color: T.text
            font.family: T.font; font.pixelSize: 25 * T.u; font.weight: Font.DemiBold
        }
        Row {
            spacing: 22 * T.u
            Repeater {
                model: card.codes
                Column {
                    required property var modelData
                    spacing: 8 * T.u
                    Rectangle {
                        width: 150 * T.u; height: width; radius: 10 * T.u
                        color: modelData.qr ? "white" : T.panel
                        border.color: modelData.qr ? "transparent" : T.line
                        border.width: 2 * T.u
                        Image { anchors.fill: parent; anchors.margins: 10 * T.u; smooth: false; source: modelData.qr ? backend.qr(modelData.qr) : "" }
                    }
                    Text { text: modelData.cap; color: T.dim; font.family: T.font; font.pixelSize: 20 * T.u }
                }
            }
        }
        Text {
            width: parent.width
            visible: card.twoCodes
            wrapMode: Text.WordWrap
            text: card.phone.mode === "waiting"
                  ? "The codes show " + card.when(card.phone.eta || 0) + ", once the box has checked for internet."
                  : "Wi-Fi " + (card.phone.ssid || "") + " · password " + (card.phone.password || "")
            color: T.dim
            font.family: T.font; font.pixelSize: 20 * T.u
        }
    }
}
