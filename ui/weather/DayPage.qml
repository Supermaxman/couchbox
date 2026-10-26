// One day in detail: the sky, a few plain sentences about it, its numbers, and hour by hour
// temperature (and feels like), the chance of rain, and wind (and gusts). Left/Right go to the
// day before / after; Back returns.
import QtQuick

FocusScope {
    id: page
    property int index: 0
    property int hour: -1                    // the hour picked on Today (marked on the charts)
    readonly property var days: W.data ? W.data.days : []
    readonly property var day: days[index] || null
    readonly property var hours: day ? day.hours : []
    signal closed()

    function show(date, h) {
        for (let i = 0; i < days.length; i++) if (days[i].date === date) { index = i; break; }
        hour = h === undefined ? -1 : h;
    }
    Keys.onLeftPressed: if (index > 0) { index--; hour = -1; }
    Keys.onRightPressed: if (index < days.length - 1) { index++; hour = -1; }
    Keys.onEscapePressed: closed()
    Keys.onBackPressed: closed()

    Rectangle { anchors.fill: parent; color: W.bg }

    Item {
        id: head
        anchors { left: parent.left; right: parent.right; top: parent.top; leftMargin: 70 * W.u; rightMargin: W.edge; topMargin: 44 * W.u }
        height: 250 * W.u
        Image {
            id: bigIcon
            width: 170 * W.u; height: width; sourceSize: Qt.size(width, height)
            source: page.day ? W.icon(page.day.icon) : ""
        }
        Column {
            anchors { left: bigIcon.right; leftMargin: 30 * W.u; right: nums.left; rightMargin: 40 * W.u; top: parent.top; topMargin: 4 * W.u }
            spacing: 10 * W.u
            Row {
                spacing: 20 * W.u
                Text { id: dayTitle; text: page.day ? page.day.name : ""; color: W.text; font.family: W.font; font.pixelSize: W.tTitle; font.weight: Font.Bold }
                Text { anchors.baseline: dayTitle.baseline; text: page.day ? page.day.long.split(", ").slice(1).join(", ") : ""; color: W.dim; font.family: W.font; font.pixelSize: W.tHead }
            }
            Text {
                width: parent.width
                text: page.day ? page.day.summary : ""
                color: W.text2; font.family: W.font; font.pixelSize: W.tBody; lineHeight: 1.15
                wrapMode: Text.WordWrap; maximumLineCount: 4; elide: Text.ElideRight
            }
        }
        Grid {
            id: nums
            anchors { right: parent.right; top: parent.top; topMargin: 8 * W.u }
            columns: 2
            columnSpacing: 34 * W.u
            rowSpacing: 14 * W.u
            readonly property var cells: page.day ? [
                ["High / low", W.deg(page.day.hi) + " / " + W.deg(page.day.lo)],
                ["Feels like", W.deg(page.day.feelsHi) + " / " + W.deg(page.day.feelsLo)],
                ["Rain", page.day.rain + "%" + (page.day.precip > 0 ? ", " + W.amount(page.day.precip) : "")],
                ["Wind", page.day.windDir + " " + page.day.wind + ", gusts " + page.day.gust],
                ["Sunrise", page.day.sunrise],
                ["Sunset", page.day.sunset],
                ["UV max", Math.round(page.day.uv) + ""],
                ["Daylight", page.day.daylight + " h"]] : []
            Repeater {
                model: nums.cells
                delegate: Column {
                    required property var modelData
                    width: 230 * W.u
                    Text { text: modelData[0].toUpperCase(); color: W.faint; font.family: W.font; font.pixelSize: 16 * W.u; font.weight: Font.Bold; font.letterSpacing: 1.2 * W.u }
                    Text { width: parent.width; text: modelData[1]; color: W.text; font.family: W.font; font.pixelSize: 25 * W.u; font.weight: Font.DemiBold; elide: Text.ElideRight }
                }
            }
        }
    }

    Column {
        anchors { left: parent.left; right: parent.right; top: head.bottom; bottom: hints.top; leftMargin: 60 * W.u; rightMargin: W.edge; topMargin: 14 * W.u; bottomMargin: 10 * W.u }
        spacing: 8 * W.u
        readonly property real ch: (height - 3 * 40 * W.u - 5 * spacing) / 3
        readonly property int mark: page.hours.findIndex(x => x.h === page.hour)
        readonly property var labels: page.hours.map(x => x.hour)

        Text { x: 10 * W.u; height: 40 * W.u; verticalAlignment: Text.AlignBottom; text: "Temperature  ·  dashed: feels like"; color: W.text2; font.family: W.font; font.pixelSize: W.tMeta; font.weight: Font.DemiBold }
        Chart {
            width: parent.width; height: parent.ch
            values: page.hours.map(x => x.temp)
            values2: page.hours.map(x => x.feels)
            labels: parent.labels
            color: W.warm
            suffix: "°"
            mark: parent.mark
        }
        Text { x: 10 * W.u; height: 40 * W.u; verticalAlignment: Text.AlignBottom; text: "Chance of rain" + (page.day && page.day.precip > 0 ? "  ·  about " + W.amount(page.day.precip) + " in all" : ""); color: W.text2; font.family: W.font; font.pixelSize: W.tMeta; font.weight: Font.DemiBold }
        Chart {
            width: parent.width; height: parent.ch
            kind: "bars"
            values: page.hours.map(x => x.rain)
            labels: parent.labels
            color: W.cool
            minValue: 0; maxValue: 100
            suffix: "%"
            emptyText: "No rain expected"
            mark: parent.mark
        }
        Text { x: 10 * W.u; height: 40 * W.u; verticalAlignment: Text.AlignBottom; text: "Wind (" + W.unit("wind") + ")  ·  dashed: gusts"; color: W.text2; font.family: W.font; font.pixelSize: W.tMeta; font.weight: Font.DemiBold }
        Chart {
            width: parent.width; height: parent.ch
            values: page.hours.map(x => x.wind)
            values2: page.hours.map(x => x.gust)
            labels: parent.labels
            color: W.wind
            minValue: 0
            mark: parent.mark
        }
    }

    Row {
        id: hints
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 26 * W.u }
        spacing: 40 * W.u
        Text { text: page.index > 0 ? "◀  " + page.days[page.index - 1].name : ""; color: W.dim; font.family: W.font; font.pixelSize: W.tMeta }
        Text { text: "Back: close"; color: W.faint; font.family: W.font; font.pixelSize: W.tMeta }
        Text { text: page.index < page.days.length - 1 ? page.days[page.index + 1].name + "  ▶" : ""; color: W.dim; font.family: W.font; font.pixelSize: W.tMeta }
    }
}
