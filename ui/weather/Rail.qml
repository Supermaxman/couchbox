// The sidebar: Today, the next two weeks, the alerts (when there are any); the place and when
// the forecast was made at the bottom. Up/Down move, OK opens, Right goes to the page.
import QtQuick

FocusScope {
    id: rail
    property int section: 0                  // 0 today, 1 week
    readonly property int alertCount: W.data ? W.data.alerts.length : 0
    readonly property var entries: {
        const e = [{kind: "today", label: "Today", icon: "today"}, {kind: "week", label: "Next 14 days", icon: "week"}];
        if (alertCount) e.push({kind: "alerts", label: alertCount > 1 ? alertCount + " alerts" : "Alert", icon: "alert"});
        return e;
    }
    property int idx: 0
    signal chosen(var entry)
    signal toPage()

    onActiveFocusChanged: if (activeFocus) idx = Math.min(section, entries.length - 1)
    Keys.onUpPressed: idx = Math.max(0, idx - 1)
    Keys.onDownPressed: idx = Math.min(entries.length - 1, idx + 1)
    Keys.onRightPressed: toPage()
    Keys.onReturnPressed: chosen(entries[idx])
    Keys.onEnterPressed: chosen(entries[idx])

    Rectangle { anchors.fill: parent; color: W.side }
    Rectangle { anchors { right: parent.right; top: parent.top; bottom: parent.bottom } width: 1; color: W.line }

    Row {
        id: brand
        x: 40 * W.u; y: 48 * W.u
        spacing: 16 * W.u
        Image { width: 58 * W.u; height: width; sourceSize: Qt.size(width, height); source: W.icon("partly-day"); anchors.verticalCenter: parent.verticalCenter }
        Text { anchors.verticalCenter: parent.verticalCenter; text: "Weather"; color: W.text; font.family: W.font; font.pixelSize: 38 * W.u; font.weight: Font.Bold }
    }

    Column {
        anchors { left: parent.left; right: parent.right; top: brand.bottom; topMargin: 56 * W.u; leftMargin: 20 * W.u; rightMargin: 20 * W.u }
        spacing: 6 * W.u
        Repeater {
            model: rail.entries
            delegate: Rectangle {
                id: entry
                required property var modelData
                required property int index
                readonly property bool sel: (modelData.kind === "today" && rail.section === 0) || (modelData.kind === "week" && rail.section === 1)
                readonly property bool cur: rail.activeFocus && rail.idx === index
                readonly property bool warn: modelData.kind === "alerts"
                width: parent.width; height: 68 * W.u; radius: 12 * W.u
                color: cur ? W.panel2 : sel ? W.panel : "transparent"
                border.color: cur ? W.focus : "transparent"; border.width: 3 * W.u
                Rectangle { visible: entry.sel; x: 0; anchors.verticalCenter: parent.verticalCenter; width: 5 * W.u; height: 34 * W.u; radius: 3 * W.u; color: W.accent }
                Image {
                    id: entryIcon
                    x: 22 * W.u; anchors.verticalCenter: parent.verticalCenter
                    width: 30 * W.u; height: width; sourceSize: Qt.size(width, height)
                    source: W.glyph(entry.modelData.icon)
                    opacity: entry.sel || entry.cur ? 1 : 0.7
                }
                Text {
                    anchors { left: entryIcon.right; leftMargin: 16 * W.u; right: parent.right; rightMargin: 14 * W.u; verticalCenter: parent.verticalCenter }
                    text: entry.modelData.label
                    color: entry.warn ? (W.data && W.data.alerts.length ? W.data.alerts[0].color : W.warm) : entry.sel || entry.cur ? W.text : W.text2
                    font.family: W.font; font.pixelSize: 27 * W.u; font.weight: entry.sel || entry.warn ? Font.DemiBold : Font.Normal
                    elide: Text.ElideRight
                }
            }
        }
    }

    Column {
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom; leftMargin: 42 * W.u; rightMargin: 24 * W.u; bottomMargin: 40 * W.u }
        spacing: 6 * W.u
        Text {
            width: parent.width
            text: W.data ? W.data.place.name : ""
            color: W.text2; font.family: W.font; font.pixelSize: 24 * W.u; font.weight: Font.DemiBold
            elide: Text.ElideRight
        }
        Text {
            width: parent.width
            text: W.data ? "Updated " + W.data.updatedText : ""
            color: W.faint; font.family: W.font; font.pixelSize: 20 * W.u; elide: Text.ElideRight
        }
        Text {
            width: parent.width
            text: "Forecast: Open-Meteo"
            color: W.faint; font.family: W.font; font.pixelSize: 18 * W.u; elide: Text.ElideRight
        }
    }
}
