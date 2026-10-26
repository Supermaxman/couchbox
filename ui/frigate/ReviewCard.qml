// A review item (an alert or a detection): its thumbnail, the camera, what was seen and when.
import QtQuick

Item {
    id: card
    property var r: ({})
    property bool current: false
    property bool showCamera: true
    readonly property color sev: r.severity === "alert" ? F.alert : F.detection

    Rectangle {
        id: box
        anchors.fill: parent
        radius: F.radius
        color: F.panel
        clip: true
        border.color: card.current ? F.focus : F.line
        border.width: (card.current ? 5 : 1) * F.u
        Item {
            id: pic
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: box.border.width }
            height: (parent.height - 2 * box.border.width) * 0.72
            clip: true
            Rectangle { anchors.fill: parent; color: "#111114" }
            Text { anchors.centerIn: parent; visible: thumb.status !== Image.Ready; text: "▣"; color: F.panel2; font.pixelSize: 64 * F.u }
            Image { id: thumb; anchors.fill: parent; source: card.r.thumb || ""; fillMode: Image.PreserveAspectCrop; asynchronous: true }
            Rectangle {                          // camera name, top left
                visible: card.showCamera
                anchors { left: parent.left; top: parent.top; margins: 12 * F.u }
                width: camText.implicitWidth + 24 * F.u; height: 38 * F.u; radius: 8 * F.u
                color: "#b3000000"
                Text { id: camText; anchors.centerIn: parent; text: card.r.cameraLabel || ""; color: "white"; font.family: F.font; font.pixelSize: 20 * F.u; font.weight: Font.DemiBold }
            }
            Rectangle {                          // happening now / not looked at yet
                anchors { right: parent.right; top: parent.top; margins: 14 * F.u }
                visible: card.r.live || !card.r.reviewed
                width: card.r.live ? liveText.implicitWidth + 24 * F.u : 16 * F.u
                height: card.r.live ? 34 * F.u : 16 * F.u
                radius: card.r.live ? 8 * F.u : 8 * F.u
                color: card.r.live ? F.alert : card.sev
                Text { id: liveText; visible: !!card.r.live; anchors.centerIn: parent; text: "NOW"; color: "white"; font.family: F.font; font.pixelSize: 18 * F.u; font.weight: Font.Bold }
            }
        }
        Rectangle { anchors { left: parent.left; top: pic.bottom; bottom: parent.bottom; margins: box.border.width } width: 6 * F.u; color: card.sev }
        Column {
            anchors { left: parent.left; right: parent.right; top: pic.bottom; bottom: parent.bottom; leftMargin: 24 * F.u; rightMargin: 16 * F.u }
            spacing: 2 * F.u
            topPadding: 10 * F.u
            Text { width: parent.width; text: (card.r.objects || []).join(", ") || "Motion"; color: F.text; font.family: F.font; font.pixelSize: 25 * F.u; font.weight: Font.DemiBold; elide: Text.ElideRight }
            Text { width: parent.width; text: (card.r.start ? F.when(card.r.start) : "") + "  ·  " + F.length(card.r); color: F.dim; font.family: F.font; font.pixelSize: 21 * F.u; elide: Text.ElideRight }
        }
    }
    scale: current ? 1.04 : 1
    z: current ? 2 : 1
    Behavior on scale { NumberAnimation { duration: 120 } }
}
