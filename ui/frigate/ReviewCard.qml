// A review item (an alert or a detection): its picture with the camera's name, icons for what
// was seen, what it was and when. The card works out its own height (implicitHeight) from
// its width and the text sizes, so nothing gets cut off.
import QtQuick

Item {
    id: card
    property var r: ({})
    property bool current: false
    property bool showCamera: true
    readonly property color sev: F.sevColor(r)
    readonly property real thumbH: Math.round(width * 9 / 16)
    readonly property real pad: 16 * F.u
    readonly property real badge: 44 * F.u
    readonly property var kinds: (r.kinds || []).slice(0, 3)
    implicitHeight: thumbH + pad + Math.max(badge, title.implicitHeight) + 6 * F.u + meta.implicitHeight + pad

    Rectangle {
        id: box
        anchors.fill: parent
        radius: F.radius
        color: card.current ? F.panel2 : F.panel
        clip: true
        Item {
            id: pic
            width: parent.width; height: card.thumbH
            Rectangle { anchors.fill: parent; color: "#111114" }
            Image {
                anchors.centerIn: parent
                visible: thumb.status !== Image.Ready
                width: 64 * F.u; height: width; sourceSize: Qt.size(width, height)
                source: F.icon(card.kinds.length ? card.kinds[0].kind : "motion")
                opacity: 0.18
            }
            Image {
                id: thumb
                anchors.fill: parent
                source: card.r.thumb || ""
                sourceSize.width: Math.round(card.width)
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
            }
            Rectangle {                          // the camera, top left
                visible: card.showCamera && !!card.r.cameraLabel
                x: 12 * F.u; y: 12 * F.u
                width: Math.min(camText.implicitWidth + 24 * F.u, pic.width - 24 * F.u - (live.visible ? live.width + 12 * F.u : 30 * F.u))
                height: camText.implicitHeight + 10 * F.u; radius: 8 * F.u
                color: "#b3000000"
                Text {
                    id: camText
                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 12 * F.u; rightMargin: 12 * F.u }
                    text: card.r.cameraLabel || ""; elide: Text.ElideRight
                    color: "white"; font.family: F.font; font.pixelSize: F.tSmall; font.weight: Font.DemiBold
                }
            }
            Rectangle {                          // happening now
                id: live
                visible: !!card.r.live
                anchors { right: parent.right; top: parent.top; margins: 12 * F.u }
                width: liveText.implicitWidth + 22 * F.u; height: liveText.implicitHeight + 10 * F.u; radius: 8 * F.u
                color: F.alert
                Text { id: liveText; anchors.centerIn: parent; text: "NOW"; color: "white"; font.family: F.font; font.pixelSize: F.tSmall - 2 * F.u; font.weight: Font.Bold }
            }
            Rectangle {                          // not looked at yet
                visible: !card.r.live && !card.r.reviewed
                anchors { right: parent.right; top: parent.top; margins: 16 * F.u }
                width: 16 * F.u; height: width; radius: width / 2
                color: card.sev
                border.color: "#80000000"; border.width: 2 * F.u
            }
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 5 * F.u; color: card.sev }   // alert red, detection amber
        }
        Row {                                    // icons for what was seen
            id: badges
            x: card.pad; y: card.thumbH + card.pad
            spacing: -8 * F.u
            Repeater {
                model: card.kinds
                delegate: KindBadge {
                    required property var modelData
                    kind: modelData.kind; size: card.badge
                    fill: F.panel2
                    border.color: box.color; border.width: 3 * F.u
                }
            }
        }
        Text {
            id: title
            anchors { left: badges.right; leftMargin: card.kinds.length ? 14 * F.u : 0; right: parent.right; rightMargin: card.pad }
            y: card.thumbH + card.pad + (Math.max(card.badge, implicitHeight) - implicitHeight) / 2
            text: F.seen(card.r)
            elide: Text.ElideRight; maximumLineCount: 1
            color: F.text; font.family: F.font; font.pixelSize: F.tBody - 2 * F.u; font.weight: Font.DemiBold
        }
        Text {
            id: meta
            x: card.pad; width: parent.width - 2 * card.pad
            y: card.thumbH + card.pad + Math.max(card.badge, title.implicitHeight) + 6 * F.u
            text: (card.r.start ? F.when(card.r.start) : "") + "  ·  " + F.length(card.r)
            elide: Text.ElideRight; maximumLineCount: 1
            color: F.dim; font.family: F.font; font.pixelSize: F.tMeta
        }
    }
    Rectangle {                                  // focus ring
        anchors.fill: parent; anchors.margins: -F.ring
        radius: F.radius + F.ring
        color: "transparent"
        border.color: F.focus; border.width: F.ring
        visible: card.current
    }
    scale: current ? F.lift : 1
    z: current ? 2 : 1
    Behavior on scale { NumberAnimation { duration: 120 } }
}
