// The sidebar: Home, Search, the top-rated movies and shows; where the data comes from at the
// bottom. Up/Down move, OK opens, Right goes to the page.
import QtQuick

FocusScope {
    id: rail
    property int section: 0                  // 0 home, 1 search, 2 top movies, 3 top shows
    readonly property var entries: [
        {label: "Home", icon: "home"}, {label: "Search", icon: "search"},
        {label: "Top movies", icon: "movie"}, {label: "Top shows", icon: "tv"}
    ]
    property int idx: 0
    signal chosen(int section)
    signal toPage()

    onActiveFocusChanged: if (activeFocus) idx = section
    Keys.onUpPressed: idx = Math.max(0, idx - 1)
    Keys.onDownPressed: idx = Math.min(entries.length - 1, idx + 1)
    Keys.onRightPressed: toPage()
    Keys.onReturnPressed: chosen(idx)
    Keys.onEnterPressed: chosen(idx)

    Rectangle { anchors.fill: parent; color: M.side }
    Rectangle { anchors { right: parent.right; top: parent.top; bottom: parent.bottom } width: 1; color: M.line }

    Row {                                        // the app's mark
        id: brand
        x: 40 * M.u; y: 48 * M.u
        spacing: 16 * M.u
        Rectangle {
            width: 54 * M.u; height: width; radius: 14 * M.u; color: M.accent
            Image { anchors.centerIn: parent; width: 34 * M.u; height: width; sourceSize: M.sz(width, height); source: "icons/mark.svg" }
        }
        Column {
            anchors.verticalCenter: parent.verticalCenter
            Text { text: "Movies & TV"; color: M.text; font.family: M.font; font.pixelSize: 34 * M.u; font.weight: Font.Bold }
        }
    }

    Column {
        anchors { left: parent.left; right: parent.right; top: brand.bottom; topMargin: 56 * M.u; leftMargin: 20 * M.u; rightMargin: 20 * M.u }
        spacing: 6 * M.u
        Repeater {
            model: rail.entries
            delegate: Rectangle {
                required property var modelData
                required property int index
                readonly property bool sel: rail.section === index
                readonly property bool cur: rail.activeFocus && rail.idx === index
                width: parent.width; height: 68 * M.u; radius: 12 * M.u
                color: cur ? M.panel2 : sel ? M.panel : "transparent"
                border.color: cur ? M.focus : "transparent"; border.width: 3 * M.u
                Rectangle { visible: parent.sel; anchors.verticalCenter: parent.verticalCenter; width: 5 * M.u; height: 34 * M.u; radius: 3 * M.u; color: M.accent }
                Image {
                    id: icon
                    x: 22 * M.u; anchors.verticalCenter: parent.verticalCenter
                    width: 30 * M.u; height: width; sourceSize: M.sz(width, height)
                    source: "icons/" + parent.modelData.icon + ".svg"
                    opacity: parent.sel || parent.cur ? 1 : 0.65
                }
                Text {
                    anchors { left: icon.right; leftMargin: 16 * M.u; right: parent.right; rightMargin: 12 * M.u; verticalCenter: parent.verticalCenter }
                    text: parent.modelData.label
                    color: parent.sel || parent.cur ? M.text : M.text2
                    font.family: M.font; font.pixelSize: 27 * M.u; font.weight: parent.sel ? Font.DemiBold : Font.Normal
                    elide: Text.ElideRight
                }
            }
        }
    }
    Column {                                     // where the data comes from (as TMDB's and IMDb's terms ask)
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom; leftMargin: 40 * M.u; rightMargin: 24 * M.u; bottomMargin: 34 * M.u }
        spacing: 8 * M.u
        Text {
            width: parent.width; wrapMode: Text.WordWrap
            text: M.status.source === "seerr" ? "From TMDB, through your Seerr" : M.status.source === "tmdb" ? "From TMDB" : M.status.source === "demo" ? "Demo titles" : ""
            color: M.dim; font.family: M.font; font.pixelSize: M.tSmall
        }
        Repeater {
            model: M.status.credits || []
            delegate: Text {
                required property string modelData
                width: parent.width; wrapMode: Text.WordWrap
                text: modelData; color: M.faint; font.family: M.font; font.pixelSize: 15 * M.u; lineHeight: 1.1
            }
        }
    }
}
