// Today: now (big), the day's numbers, the model's "at a glance" line (when the assistant is set
// up), any alert, and the next 48 hours. Left/Right move along the hours, OK opens that day in
// detail; Up reaches the alert (OK reads it); Left from the first hour goes to the sidebar.
import QtQuick

FocusScope {
    id: page
    readonly property var d: W.data
    readonly property var today: d ? d.days[0] : null
    readonly property var hours: d ? d.hours : []
    readonly property bool hasAlert: !!d && d.alerts.length > 0
    property int zone: 1                     // 0 the alert, 1 the hours
    property int hi: 0
    signal openDay(string date, int hour)
    signal openAlerts()
    signal toRail()

    onHasAlertChanged: if (!hasAlert) zone = 1
    Keys.onLeftPressed: { if (zone === 1 && hi > 0) hi--; else toRail(); }
    Keys.onRightPressed: { if (zone === 1) hi = Math.min(hours.length - 1, hi + 1); }
    Keys.onUpPressed: if (hasAlert) zone = 0
    Keys.onDownPressed: zone = 1
    Keys.onReturnPressed: activate()
    Keys.onEnterPressed: activate()
    function activate() {
        if (zone === 0) openAlerts();
        else if (hours[hi]) openDay(hours[hi].date, hours[hi].h);
    }

    Column {
        id: content
        anchors { left: parent.left; right: parent.right; top: parent.top; leftMargin: 64 * W.u; rightMargin: W.edge; topMargin: 50 * W.u }
        spacing: 26 * W.u

        Row {
            spacing: 22 * W.u
            Text { id: title; text: "Today"; color: W.text; font.family: W.font; font.pixelSize: W.tTitle; font.weight: Font.Bold }
            Text {
                anchors.baseline: title.baseline
                text: page.today ? page.today.long.split(", ").slice(1).join(", ") : ""
                color: W.dim; font.family: W.font; font.pixelSize: W.tHead
            }
        }

        Rectangle {                              // the alert (the worst one; the sidebar lists them all)
            visible: page.hasAlert
            width: parent.width; height: 84 * W.u; radius: W.radius
            readonly property var a: page.hasAlert ? page.d.alerts[0] : null
            readonly property bool cur: page.activeFocus && page.zone === 0
            color: Qt.rgba(0.96, 0.62, 0.04, 0.12)
            border.color: cur ? W.focus : (a ? a.color : W.warm); border.width: cur ? W.ring : 2 * W.u
            Image { id: alertIcon; x: 26 * W.u; anchors.verticalCenter: parent.verticalCenter; width: 38 * W.u; height: width; sourceSize: Qt.size(width, height); source: W.glyph("alert") }
            Text {
                anchors { left: alertIcon.right; leftMargin: 18 * W.u; right: alertMore.left; rightMargin: 18 * W.u; verticalCenter: parent.verticalCenter }
                text: parent.a ? parent.a.event + (parent.a.until ? "  ·  until " + parent.a.until : "") : ""
                color: W.text; font.family: W.font; font.pixelSize: W.tBody; font.weight: Font.DemiBold; elide: Text.ElideRight
            }
            Text {
                id: alertMore
                anchors { right: parent.right; rightMargin: 26 * W.u; verticalCenter: parent.verticalCenter }
                text: page.d && page.d.alerts.length > 1 ? "+" + (page.d.alerts.length - 1) + " more  ·  OK to read" : "OK to read"
                color: W.dim; font.family: W.font; font.pixelSize: W.tMeta
            }
        }

        Item {                                   // now, and the day's numbers beside it
            width: parent.width
            height: Math.max(hero.height, stats.height)
            Column {
                id: hero
                width: parent.width * 0.44
                spacing: 6 * W.u
                Row {
                    spacing: 18 * W.u
                    Image {
                        width: 190 * W.u; height: width; sourceSize: Qt.size(width, height)
                        source: page.d ? W.icon(page.d.now.icon) : ""
                    }
                    Column {
                        anchors.verticalCenter: parent.verticalCenter
                        Text {
                            text: page.d ? W.deg(page.d.now.temp) : ""
                            color: W.text; font.family: W.font; font.pixelSize: W.tHero; font.weight: Font.Light
                        }
                    }
                }
                Text {
                    width: parent.width
                    text: page.d ? page.d.now.cond : ""
                    color: W.text; font.family: W.font; font.pixelSize: 40 * W.u; font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
                Text {
                    width: parent.width
                    text: page.d && page.today ? "Feels like " + W.deg(page.d.now.feels) + "   ·   H " + W.deg(page.today.hi) + "   L " + W.deg(page.today.lo) : ""
                    color: W.text2; font.family: W.font; font.pixelSize: W.tBody
                    elide: Text.ElideRight
                }
            }
            Grid {
                id: stats
                anchors.right: parent.right
                width: parent.width * 0.54
                columns: 3
                spacing: 16 * W.u
                readonly property real cw: (width - 2 * spacing) / 3
                Stat {
                    width: stats.cw
                    glyph: "rain"; label: "Rain"
                    value: page.today ? page.today.rain + "%" : ""
                    note: page.today ? (page.today.precip > 0 ? W.amount(page.today.snow > 0 ? page.today.snow : page.today.precip) + (page.today.snow > 0 ? " snow" : "") + " today" : "None expected") : ""
                    tint: W.cool
                }
                Stat {
                    width: stats.cw
                    glyph: "wind"; label: "Wind"
                    value: page.d ? page.d.now.wind + " " + page.d.units.wind : ""
                    note: page.d ? page.d.now.windDir + ", gusts " + page.d.now.gust : ""
                }
                Stat {
                    width: stats.cw
                    glyph: "uv"; label: "UV index"
                    value: page.today ? Math.round(page.today.uv) + "" : ""
                    note: page.today ? (page.today.uv < 3 ? "Low today" : page.today.uv < 6 ? "Moderate at midday" : "High at midday") : ""
                    tint: page.today && page.today.uv >= 6 ? W.warm : W.text
                }
                Stat {
                    width: stats.cw
                    glyph: "humidity"; label: "Humidity"
                    value: page.d && page.d.now.humidity !== null ? page.d.now.humidity + "%" : "–"
                    note: page.d && page.d.now.visibility !== null ? "Visibility " + page.d.now.visibility + " " + page.d.now.visUnit : ""
                }
                Stat {
                    width: stats.cw
                    glyph: "sunrise"; label: "Sun"
                    value: page.today ? page.today.sunrise : ""
                    note: page.today ? "Sets " + page.today.sunset : ""
                }
                Stat {
                    width: stats.cw
                    glyph: "air"; label: page.d && page.d.aqi ? page.d.aqi.scale : "Air quality"
                    value: page.d && page.d.aqi ? page.d.aqi.value + "" : "–"
                    note: page.d && page.d.aqi ? page.d.aqi.label : "Not available here"
                    tint: page.d && page.d.aqi ? page.d.aqi.color : W.text
                }
            }
        }

        Text {                                   // the model's line (with the voice assistant set up)
            width: parent.width
            visible: W.glance !== ""
            text: W.glance
            color: W.text2; font.family: W.font; font.pixelSize: W.tBody; font.italic: true
            wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
        }

        Text { text: "Next 48 hours"; color: W.text; font.family: W.font; font.pixelSize: W.tHead; font.weight: Font.DemiBold }
    }

    ListView {
        id: strip
        anchors { left: content.left; right: parent.right; top: content.bottom; topMargin: 16 * W.u }
        height: 236 * W.u
        orientation: ListView.Horizontal
        spacing: 14 * W.u
        clip: false
        interactive: false
        model: page.hours
        currentIndex: page.hi
        highlightMoveDuration: 160
        preferredHighlightBegin: 0
        preferredHighlightEnd: width - W.edge - 150 * W.u
        highlightRangeMode: ListView.ApplyRange
        delegate: Rectangle {
            id: card
            required property var modelData
            required property int index
            readonly property bool cur: page.activeFocus && page.zone === 1 && page.hi === index
            readonly property bool midnight: modelData.h === 0 && index > 0
            width: 132 * W.u; height: strip.height - 16 * W.u
            y: 8 * W.u
            radius: W.radius
            color: cur ? W.panel2 : W.panel
            border.color: cur ? W.focus : midnight ? W.line : "transparent"; border.width: cur ? W.ring : 2 * W.u
            scale: cur ? W.lift : 1
            Behavior on scale { NumberAnimation { duration: 120 } }
            Column {
                anchors.centerIn: parent
                spacing: 8 * W.u
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: card.midnight ? Qt.formatDate(new Date(card.modelData.date + "T12:00:00"), "ddd") : card.modelData.hour
                    color: card.midnight ? W.accent : W.dim; font.family: W.font; font.pixelSize: W.tMeta; font.weight: card.midnight ? Font.Bold : Font.Medium
                }
                Image { anchors.horizontalCenter: parent.horizontalCenter; width: 64 * W.u; height: width; sourceSize: Qt.size(width, height); source: W.icon(card.modelData.icon) }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: W.deg(card.modelData.temp)
                    color: W.text; font.family: W.font; font.pixelSize: 32 * W.u; font.weight: Font.DemiBold
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: card.modelData.rain >= 10 ? card.modelData.rain + "%" : " "
                    color: W.cool; font.family: W.font; font.pixelSize: W.tSmall; font.weight: Font.DemiBold
                }
            }
        }
    }
}
