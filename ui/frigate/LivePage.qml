// The live dashboard: recent alerts across the top (the last day's, not looked at yet), then
// the group's cameras, three across. Arrows move, OK opens (a camera full screen, an alert's
// recording), Left from the first column goes to the sidebar.
import QtQuick

FocusScope {
    id: page
    property int group: 0
    property var alerts: []
    readonly property var cams: F.groupCams(group)
    readonly property int cols: 3
    property int zone: alerts.length ? 0 : 1    // 0 alerts strip, 1 cameras
    property int ai: 0
    property int ci: 0
    signal openCamera(int index)
    signal openReview(var r)
    signal toRail()

    onAlertsChanged: { if (!alerts.length && zone === 0) zone = 1; ai = Math.min(ai, Math.max(0, alerts.length - 1)); }
    onGroupChanged: { ci = 0; ai = 0; zone = alerts.length ? 0 : 1; flick.contentY = 0; }

    function ensureVisible() {
        if (zone === 0) { flick.contentY = 0; return; }
        const item = grid.children[ci];
        if (!item) return;
        const top = gridWrap.y + item.y - 30 * F.u, bottom = gridWrap.y + item.y + item.height + 40 * F.u;
        if (top < flick.contentY) flick.contentY = Math.max(0, top - (ci < cols && alerts.length ? stripWrap.height : 0));
        else if (bottom > flick.contentY + flick.height) flick.contentY = bottom - flick.height;
    }
    onZoneChanged: ensureVisible()
    onCiChanged: ensureVisible()

    Keys.onLeftPressed: {
        if (zone === 0) { if (ai > 0) ai--; else toRail(); }
        else if (ci % cols > 0) ci--; else toRail();
    }
    Keys.onRightPressed: {
        if (zone === 0) ai = Math.min(alerts.length - 1, ai + 1);
        else if (ci % cols < cols - 1 && ci + 1 < cams.length) ci++;
    }
    Keys.onUpPressed: {
        if (zone === 1 && ci >= cols) ci -= cols;
        else if (zone === 1 && alerts.length) zone = 0;
    }
    Keys.onDownPressed: {
        if (zone === 0) zone = 1;
        else if (ci + cols < cams.length) ci += cols;
        else if (Math.floor(ci / cols) < Math.floor((cams.length - 1) / cols)) ci = cams.length - 1;
    }
    Keys.onReturnPressed: zone === 0 ? openReview(alerts[ai]) : openCamera(ci)
    Keys.onEnterPressed: zone === 0 ? openReview(alerts[ai]) : openCamera(ci)

    Flickable {
        id: flick
        anchors.fill: parent
        contentHeight: content.height + 80 * F.u
        interactive: false
        clip: true
        Behavior on contentY { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
        Column {
            id: content
            x: 56 * F.u
            width: page.width - 56 * F.u - F.edge
            spacing: 34 * F.u
            topPadding: 48 * F.u
            Row {
                spacing: 20 * F.u
                Text { text: (F.groups[page.group] || {name: "Cameras"}).name; color: F.text; font.family: F.font; font.pixelSize: 46 * F.u; font.weight: Font.Bold }
                Text { anchors.baseline: parent.children[0].baseline; text: page.cams.length + (page.cams.length === 1 ? " camera" : " cameras"); color: F.dim; font.family: F.font; font.pixelSize: 26 * F.u }
            }
            Column {
                id: stripWrap
                visible: page.alerts.length > 0
                width: parent.width
                spacing: 16 * F.u
                Text { text: "Recent alerts"; color: F.text2; font.family: F.font; font.pixelSize: 28 * F.u; font.weight: Font.DemiBold }
                ListView {
                    id: strip
                    width: parent.width
                    height: 250 * F.u
                    orientation: ListView.Horizontal
                    spacing: 22 * F.u
                    clip: false
                    interactive: false
                    model: page.alerts
                    currentIndex: page.ai
                    highlightRangeMode: ListView.ApplyRange
                    preferredHighlightBegin: 0
                    preferredHighlightEnd: width - 340 * F.u
                    highlightMoveDuration: 180
                    delegate: ReviewCard {
                        required property var modelData
                        required property int index
                        width: 340 * F.u; height: 250 * F.u
                        r: modelData
                        current: page.activeFocus && page.zone === 0 && page.ai === index
                    }
                }
            }
            Item {
                id: gridWrap
                width: parent.width
                height: grid.height
                Grid {
                    id: grid
                    columns: page.cols
                    spacing: 26 * F.u
                    readonly property real tw: (gridWrap.width - (page.cols - 1) * spacing) / page.cols
                    Repeater {
                        model: page.cams
                        delegate: CameraTile {
                            required property var modelData
                            required property int index
                            width: grid.tw; height: grid.tw * 9 / 16
                            cam: modelData
                            current: page.activeFocus && page.zone === 1 && page.ci === index
                            refreshing: page.visible
                        }
                    }
                }
            }
        }
    }
    Text {
        anchors.centerIn: parent
        visible: F.cameras.length === 0
        text: "Loading cameras…"
        color: F.dim; font.family: F.font; font.pixelSize: 30 * F.u
    }
}
