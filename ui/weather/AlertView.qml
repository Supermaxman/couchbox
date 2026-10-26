// The weather alerts in full (from the National Weather Service): Up/Down to scroll, Left/Right
// for the next alert, Back to close.
import QtQuick

FocusScope {
    id: view
    readonly property var alerts: W.data ? W.data.alerts : []
    property int index: 0
    readonly property var a: alerts[index] || null
    signal closed()

    onIndexChanged: flick.contentY = 0
    Keys.onUpPressed: flick.contentY = Math.max(0, flick.contentY - 160 * W.u)
    Keys.onDownPressed: flick.contentY = Math.max(0, Math.min(flick.contentHeight - flick.height, flick.contentY + 160 * W.u))
    Keys.onLeftPressed: index = Math.max(0, index - 1)
    Keys.onRightPressed: index = Math.min(alerts.length - 1, index + 1)
    Keys.onEscapePressed: closed()
    Keys.onBackPressed: closed()
    Keys.onReturnPressed: closed()

    Rectangle { anchors.fill: parent; color: W.bg }

    Flickable {
        id: flick
        anchors { fill: parent; leftMargin: 160 * W.u; rightMargin: 160 * W.u; topMargin: 70 * W.u; bottomMargin: 90 * W.u }
        contentHeight: col.height
        clip: true
        interactive: false
        Behavior on contentY { NumberAnimation { duration: 160 } }
        Column {
            id: col
            width: flick.width
            spacing: 22 * W.u
            Row {
                spacing: 18 * W.u
                Image { width: 54 * W.u; height: width; sourceSize: Qt.size(width, height); source: W.glyph("alert"); anchors.verticalCenter: parent.verticalCenter }
                Text {
                    text: view.a ? view.a.event : ""
                    color: view.a ? view.a.color : W.warm; font.family: W.font; font.pixelSize: W.tTitle; font.weight: Font.Bold
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
            Text {
                width: parent.width
                text: view.a ? [view.a.until ? "Until " + view.a.until : "", view.a.severity, view.a.sender].filter(x => x).join("  ·  ") : ""
                color: W.dim; font.family: W.font; font.pixelSize: W.tMeta
                wrapMode: Text.WordWrap
            }
            Text {
                width: parent.width
                text: view.a ? view.a.headline : ""
                visible: text !== ""
                color: W.text; font.family: W.font; font.pixelSize: W.tHead; font.weight: Font.DemiBold
                wrapMode: Text.WordWrap
            }
            Text {
                width: parent.width
                text: view.a ? view.a.description : ""
                color: W.text2; font.family: W.font; font.pixelSize: W.tBody; lineHeight: 1.25
                wrapMode: Text.WordWrap
            }
            Text {
                width: parent.width
                visible: text !== ""
                text: view.a ? view.a.instruction : ""
                color: W.text; font.family: W.font; font.pixelSize: W.tBody; lineHeight: 1.25; font.italic: true
                wrapMode: Text.WordWrap
            }
        }
    }
    Text {
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 30 * W.u }
        text: (view.alerts.length > 1 ? (view.index + 1) + " of " + view.alerts.length + "  ·  ◀ ▶ other alerts  ·  " : "") + "▲ ▼ scroll  ·  Back: close"
        color: W.faint; font.family: W.font; font.pixelSize: W.tMeta
    }
}
