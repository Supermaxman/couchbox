// The next two weeks, a day a row: the sky, the chance of rain, and the day's low to high on one
// scale for the fortnight (so warm and cold days stand out). Up/Down move, OK opens the day in
// detail, Left goes to the sidebar.
import QtQuick

FocusScope {
    id: page
    readonly property var days: W.data ? W.data.days : []
    readonly property real low: days.length ? Math.min(...days.map(x => x.lo)) : 0
    readonly property real high: days.length ? Math.max(...days.map(x => x.hi)) : 1
    property int di: 0
    signal openDay(string date)
    signal toRail()

    Keys.onUpPressed: di = Math.max(0, di - 1)
    Keys.onDownPressed: di = Math.min(days.length - 1, di + 1)
    Keys.onLeftPressed: toRail()
    Keys.onReturnPressed: if (days[di]) openDay(days[di].date)
    Keys.onEnterPressed: if (days[di]) openDay(days[di].date)

    Text {
        id: title
        x: 64 * W.u; y: 50 * W.u
        text: "Next 14 days"
        color: W.text; font.family: W.font; font.pixelSize: W.tTitle; font.weight: Font.Bold
    }
    Text {
        anchors { left: title.right; leftMargin: 22 * W.u; baseline: title.baseline }
        text: "OK for the hour by hour"
        color: W.dim; font.family: W.font; font.pixelSize: W.tMeta
    }

    ListView {
        id: list
        anchors { left: parent.left; right: parent.right; top: title.bottom; bottom: parent.bottom; leftMargin: 50 * W.u; rightMargin: W.edge - 14 * W.u; topMargin: 26 * W.u; bottomMargin: 30 * W.u }
        model: page.days
        currentIndex: page.di
        spacing: 8 * W.u
        clip: true
        interactive: false
        highlightMoveDuration: 160
        preferredHighlightBegin: 120 * W.u
        preferredHighlightEnd: height - 120 * W.u
        highlightRangeMode: ListView.ApplyRange
        delegate: Rectangle {
            id: row
            required property var modelData
            required property int index
            readonly property bool cur: page.activeFocus && page.di === index
            x: 14 * W.u
            width: list.width - 28 * W.u; height: 92 * W.u
            radius: W.radius
            color: cur ? W.panel2 : index % 2 ? "transparent" : Qt.rgba(1, 1, 1, 0.025)
            border.color: cur ? W.focus : "transparent"; border.width: W.ring
            scale: cur ? 1.01 : 1

            Column {
                id: dayCol
                x: 26 * W.u; anchors.verticalCenter: parent.verticalCenter
                width: 230 * W.u
                Text { width: parent.width; text: row.modelData.name; color: W.text; font.family: W.font; font.pixelSize: 29 * W.u; font.weight: Font.DemiBold; elide: Text.ElideRight }
                Text { width: parent.width; text: row.modelData.label; color: W.faint; font.family: W.font; font.pixelSize: W.tSmall; elide: Text.ElideRight }
            }
            Image {
                id: dayIcon
                anchors { left: dayCol.right; leftMargin: 10 * W.u; verticalCenter: parent.verticalCenter }
                width: 70 * W.u; height: width; sourceSize: W.sz(width, height)
                source: W.icon(row.modelData.icon)
            }
            Text {
                id: cond
                anchors { left: dayIcon.right; leftMargin: 20 * W.u; verticalCenter: parent.verticalCenter }
                width: 290 * W.u
                text: row.modelData.cond
                color: W.text2; font.family: W.font; font.pixelSize: W.tBody; elide: Text.ElideRight
            }
            Row {
                id: rainBox
                anchors { left: cond.right; leftMargin: 10 * W.u; verticalCenter: parent.verticalCenter }
                width: 210 * W.u
                spacing: 8 * W.u
                opacity: row.modelData.rain >= 10 || row.modelData.precip > 0 ? 1 : 0.35
                Image { anchors.verticalCenter: parent.verticalCenter; width: 24 * W.u; height: width; sourceSize: W.sz(width, height); source: W.glyph("rain") }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: row.modelData.rain + "%" + (row.modelData.precip > 0 ? "  " + W.amount(row.modelData.precip) : "")
                    color: W.cool; font.family: W.font; font.pixelSize: W.tMeta; font.weight: Font.DemiBold
                }
            }
            Text {
                id: loText
                anchors { left: rainBox.right; leftMargin: 10 * W.u; verticalCenter: parent.verticalCenter }
                width: 70 * W.u
                horizontalAlignment: Text.AlignRight
                text: W.deg(row.modelData.lo)
                color: W.dim; font.family: W.font; font.pixelSize: 28 * W.u
            }
            Item {                               // the fortnight's scale, the day's low to high on it
                id: bar
                anchors { left: loText.right; leftMargin: 18 * W.u; right: hiText.left; rightMargin: 18 * W.u; verticalCenter: parent.verticalCenter }
                height: 12 * W.u
                Rectangle { anchors.fill: parent; radius: height / 2; color: Qt.rgba(1, 1, 1, 0.09) }
                Rectangle {
                    readonly property real span: Math.max(1, page.high - page.low)
                    x: parent.width * (row.modelData.lo - page.low) / span
                    width: Math.max(height, parent.width * (row.modelData.hi - row.modelData.lo) / span)
                    height: parent.height; radius: height / 2
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0; color: W.tempColor(row.modelData.lo) }
                        GradientStop { position: 1; color: W.tempColor(row.modelData.hi) }
                    }
                }
            }
            Text {
                id: hiText
                anchors { right: windText.left; rightMargin: 16 * W.u; verticalCenter: parent.verticalCenter }
                width: 70 * W.u
                text: W.deg(row.modelData.hi)
                color: W.text; font.family: W.font; font.pixelSize: 28 * W.u; font.weight: Font.DemiBold
            }
            Text {
                id: windText
                anchors { right: parent.right; rightMargin: 26 * W.u; verticalCenter: parent.verticalCenter }
                width: 150 * W.u
                horizontalAlignment: Text.AlignRight
                text: row.modelData.windDir + " " + row.modelData.wind + " " + (W.data ? W.data.units.wind : "")
                color: row.modelData.gust >= (W.data ? W.data.units.windy : 99) ? W.wind : W.faint
                font.family: W.font; font.pixelSize: W.tMeta; elide: Text.ElideRight
            }
        }
    }
}
