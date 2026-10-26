// The sidebar: Places, Search, Directions (the trip that's open), Leave by, and which maps
// are in use. Up/Down move, OK opens, Right goes to the page.
import QtQuick

FocusScope {
    id: rail
    property int section: 0                  // 0 places, 1 search, 2 directions, 3 leave by
    property bool hasTrip: false
    readonly property var entries: [
        {section: 0, label: "Places", icon: "places"},
        {section: 1, label: "Search", icon: "search"},
        {section: 2, label: "Directions", icon: "route", off: !hasTrip},
        {section: 3, label: "Leave by", icon: "clock"},
    ]
    property int idx: 0
    signal chosen(int section)
    signal toPage()

    onActiveFocusChanged: if (activeFocus) idx = section
    Keys.onUpPressed: { let i = idx - 1; while (i >= 0 && entries[i].off) i--; if (i >= 0) idx = i; }
    Keys.onDownPressed: { let i = idx + 1; while (i < entries.length && entries[i].off) i++; if (i < entries.length) idx = i; }
    Keys.onRightPressed: toPage()
    Keys.onReturnPressed: chosen(entries[idx].section)
    Keys.onEnterPressed: chosen(entries[idx].section)

    Rectangle { anchors.fill: parent; color: M.side }
    Rectangle { anchors { right: parent.right; top: parent.top; bottom: parent.bottom } width: 1; color: M.line }

    Row {                                        // the app's mark: a folded map with a pin
        id: brand
        x: 40 * M.u; y: 48 * M.u
        spacing: 16 * M.u
        Rectangle {
            width: 54 * M.u; height: width; radius: 14 * M.u; color: M.accent
            Image { anchors.centerIn: parent; width: 34 * M.u; height: width; sourceSize: Qt.size(width, height); source: M.icon("mark") }
        }
        Text { anchors.verticalCenter: parent.verticalCenter; text: "Maps"; color: M.text; font.family: M.font; font.pixelSize: 38 * M.u; font.weight: Font.Bold }
    }

    Column {
        anchors { left: parent.left; right: parent.right; top: brand.bottom; topMargin: 56 * M.u; leftMargin: 20 * M.u; rightMargin: 20 * M.u }
        spacing: 6 * M.u
        Repeater {
            model: rail.entries
            delegate: Rectangle {
                required property var modelData
                required property int index
                readonly property bool sel: rail.section === modelData.section
                readonly property bool cur: rail.activeFocus && rail.idx === index
                width: parent.width; height: 68 * M.u; radius: 12 * M.u
                color: cur ? M.panel2 : sel ? M.panel : "transparent"
                border.color: cur ? M.focus : "transparent"; border.width: 3 * M.u
                opacity: modelData.off ? 0.35 : 1
                Rectangle { visible: parent.sel; x: 0; anchors.verticalCenter: parent.verticalCenter; width: 5 * M.u; height: 34 * M.u; radius: 3 * M.u; color: M.accent }
                Image {
                    id: ric
                    x: 22 * M.u; anchors.verticalCenter: parent.verticalCenter
                    width: 30 * M.u; height: width; sourceSize: Qt.size(width, height)
                    source: M.icon(parent.modelData.icon)
                    opacity: parent.sel || parent.cur ? 1 : 0.7
                }
                Text {
                    anchors { left: ric.right; leftMargin: 16 * M.u; right: parent.right; rightMargin: 14 * M.u; verticalCenter: parent.verticalCenter }
                    text: parent.modelData.label
                    color: parent.sel || parent.cur ? M.text : M.text2
                    font.family: M.font; font.pixelSize: 27 * M.u; font.weight: parent.sel ? Font.DemiBold : Font.Normal
                    elide: Text.ElideRight
                }
            }
        }
    }
    Column {                                     // which maps: Google (traffic) or OpenStreetMap
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom; leftMargin: 42 * M.u; rightMargin: 24 * M.u; bottomMargin: 40 * M.u }
        spacing: 6 * M.u
        Row {
            spacing: 10 * M.u
            Rectangle { anchors.verticalCenter: parent.verticalCenter; width: 12 * M.u; height: width; radius: width / 2; color: M.status.traffic ? M.light : M.faint }
            Text { text: M.status.provider || ""; color: M.text2; font.family: M.font; font.pixelSize: 21 * M.u; font.weight: Font.DemiBold }
        }
        Text {
            width: parent.width; wrapMode: Text.WordWrap
            text: M.status.provider ? (M.status.traffic ? "Live traffic" : "No traffic or transit. Add a Google Maps key in Settings → Apps → Maps for both.") : ""
            color: M.faint; font.family: M.font; font.pixelSize: 18 * M.u
        }
    }
}
