// "Type on your phone": the QR code of the box's phone typing page (couchbox-phone), as the other
// apps' keyboard pop-up shows it. What's typed there arrives as key presses to the focused field.
import QtQuick

Rectangle {
    id: card
    property string phoneDir: "/run/couchbox/phone"
    property string phoneUrl: ""
    width: 541 * Y.u
    height: 209 * Y.u
    radius: 18 * Y.u
    color: Y.phone
    border.color: "#2a3554"
    border.width: 2 * Y.u
    function refresh() {
        if (demo) return;                     // screenshots: no phone page
        qr.source = "";
        qr.source = "file://" + phoneDir + "/phone.png";
        const x = new XMLHttpRequest();
        x.onreadystatechange = () => { if (x.readyState === XMLHttpRequest.DONE) card.phoneUrl = (x.responseText || "").trim(); };
        x.open("GET", "file://" + phoneDir + "/phone.url");
        x.send();
    }
    onVisibleChanged: if (visible) refresh()
    Component.onCompleted: refresh()
    Rectangle {
        id: box
        x: 19 * Y.u; y: 20 * Y.u
        width: 169 * Y.u; height: width
        radius: 10 * Y.u
        color: "white"
        Image {
            id: qr
            anchors { fill: parent; margins: 12 * Y.u }
            sourceSize: Y.sz(width, height)
            smooth: false
            cache: false
        }
        Icon { anchors.centerIn: parent; visible: qr.status !== Image.Ready; name: "mic"; size: 64 * Y.u; color: "#9aa3c0" }
    }
    Column {
        anchors { left: box.right; leftMargin: 24 * Y.u; right: parent.right; rightMargin: 18 * Y.u; verticalCenter: parent.verticalCenter }
        spacing: 10 * Y.u
        Text { text: "Type on your phone"; color: Y.text; font.family: Y.font; font.pixelSize: 30 * Y.u; font.weight: Font.Medium }
        Text {
            width: parent.width
            visible: !!card.phoneUrl
            text: card.phoneUrl.replace(/^https?:\/\//, "").replace(/:\d+$/, "").replace(/\/$/, "")
            color: "#9aa3c0"; font.family: Y.font; font.pixelSize: Y.tSmall; elide: Text.ElideRight
        }
        Text { text: "or press the mic button and say it"; color: "#c9cde0"; font.family: Y.font; font.pixelSize: Y.tSmall }
    }
}
