// The sidebar: Home, Search, Your Library, Now Playing, and Setup. Up/Down move, OK opens,
// Right goes to the page.
import QtQuick

FocusScope {
    id: rail
    property int section: 0                  // 0 home, 1 search, 2 library
    readonly property var entries: [
        {id: "home", label: "Home", icon: "home"},
        {id: "search", label: "Search", icon: "search"},
        {id: "library", label: "Your Library", icon: "library"},
        {id: "now", label: "Now Playing", icon: "bars"},
        {id: "setup", label: "Setup", icon: "gear"}
    ]
    property int idx: 0
    signal chosen(string id)
    signal toPage()
    onActiveFocusChanged: if (activeFocus) idx = Math.min(section, 2)
    Keys.onUpPressed: idx = Math.max(0, idx - 1)
    Keys.onDownPressed: idx = Math.min(entries.length - 1, idx + 1)
    Keys.onRightPressed: toPage()
    Keys.onReturnPressed: chosen(entries[idx].id)
    Keys.onEnterPressed: chosen(entries[idx].id)

    Rectangle { anchors.fill: parent; color: S.side }
    Row {
        id: brand
        x: 40 * S.u; y: 48 * S.u
        spacing: 16 * S.u
        Rectangle {
            width: 56 * S.u; height: width; radius: width / 2; color: S.accent
            Image { anchors.centerIn: parent; width: 32 * S.u; height: width; sourceSize: Qt.size(width, height); source: S.icon("note-dark") }
        }
        Text { anchors.verticalCenter: parent.verticalCenter; text: "Spotify"; color: S.text; font.family: S.font; font.pixelSize: 38 * S.u; font.weight: Font.Bold }
    }
    Column {
        anchors { left: parent.left; right: parent.right; top: brand.bottom; topMargin: 56 * S.u; leftMargin: 20 * S.u; rightMargin: 20 * S.u }
        spacing: 8 * S.u
        Repeater {
            model: rail.entries
            delegate: Column {
                id: ec
                required property var modelData
                required property int index
                width: parent.width
                Item { width: 1; height: ec.modelData.id === "now" ? 30 * S.u : ec.modelData.id === "setup" ? 60 * S.u : 0 }
                Rectangle {
                    readonly property bool sel: rail.section === ec.index
                    readonly property bool cur: rail.activeFocus && rail.idx === ec.index
                    width: parent.width; height: 70 * S.u; radius: 12 * S.u
                    color: cur ? S.panel2 : sel ? S.panel : "transparent"
                    border.color: cur ? S.focus : "transparent"; border.width: 3 * S.u
                    Image { id: ic; x: 22 * S.u; anchors.verticalCenter: parent.verticalCenter; width: 32 * S.u; height: width
                            sourceSize: Qt.size(width, height); source: S.icon(ec.modelData.icon); opacity: parent.sel || parent.cur ? 1 : 0.65 }
                    Text {
                        anchors { left: ic.right; leftMargin: 20 * S.u; right: parent.right; rightMargin: 14 * S.u; verticalCenter: parent.verticalCenter }
                        text: ec.modelData.label; elide: Text.ElideRight
                        color: parent.sel || parent.cur ? S.text : S.dim
                        font.family: S.font; font.pixelSize: 27 * S.u; font.weight: parent.sel ? Font.Bold : Font.Normal
                    }
                }
            }
        }
    }
    Text {
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom; leftMargin: 42 * S.u; rightMargin: 20 * S.u; bottomMargin: S.nowUri ? S.barH + 30 * S.u : 40 * S.u }
        text: S.status.user ? "Signed in as " + S.status.user : ""
        color: S.faint; font.family: S.font; font.pixelSize: 21 * S.u; elide: Text.ElideRight
    }
}
