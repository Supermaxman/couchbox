// Review: the group's alerts or detections, newest first, four across. Up reaches the tabs
// (Left/Right switch them), OK plays the recording, Left from the first column goes to the
// sidebar.
import QtQuick

FocusScope {
    id: page
    property int group: 0
    property int tab: 0                      // 0 alerts, 1 detections
    property var items: []
    property bool loading: true
    property string problem: ""
    readonly property int cols: 4
    property int zone: 1                     // 0 tabs, 1 cards
    property int ci: 0
    signal openReview(var r, var list)
    signal toRail()

    function load() {
        loading = true; problem = "";
        const g = F.groups[group];
        F.call("reviews", {severity: tab === 0 ? "alert" : "detection", cameras: group > 0 && g ? g.cameras : null, limit: 80},
               r => { items = r.items; loading = false; ci = Math.min(ci, Math.max(0, items.length - 1)); },
               e => { problem = e; loading = false; });
    }
    // only while it's showing (and so signed in): it isn't loaded behind the sign-in page
    onGroupChanged: { ci = 0; if (visible) load(); }
    onTabChanged: { ci = 0; if (visible) load(); }
    onVisibleChanged: if (visible) load()

    function ensureVisible() {
        const item = grid.children[ci];
        if (zone === 0 || !item) { flick.contentY = 0; return; }
        const top = item.y, bottom = item.y + item.height + 60 * F.u;
        if (top < flick.contentY) flick.contentY = Math.max(0, top);
        else if (bottom > flick.contentY + flick.height) flick.contentY = bottom - flick.height;
    }
    onCiChanged: ensureVisible()
    onZoneChanged: ensureVisible()

    Keys.onLeftPressed: {
        if (zone === 0) { if (tab > 0) tab--; else toRail(); }
        else if (ci % cols > 0) ci--; else toRail();
    }
    Keys.onRightPressed: {
        if (zone === 0) tab = Math.min(1, tab + 1);
        else if (ci % cols < cols - 1 && ci + 1 < items.length) ci++;
    }
    Keys.onUpPressed: { if (zone === 1 && ci >= cols) ci -= cols; else zone = 0; }
    Keys.onDownPressed: {
        if (zone === 0) { if (items.length) zone = 1; }
        else if (ci + cols < items.length) ci += cols;
        else if (Math.floor(ci / cols) < Math.floor((items.length - 1) / cols)) ci = items.length - 1;
    }
    Keys.onReturnPressed: if (zone === 1 && items.length) openReview(items[ci], items)
    Keys.onEnterPressed: if (zone === 1 && items.length) openReview(items[ci], items)

    Column {
        id: head
        x: 56 * F.u; y: 48 * F.u
        spacing: 26 * F.u
        Row {
            spacing: 20 * F.u
            Text { id: heading; text: "Review"; color: F.text; font.family: F.font; font.pixelSize: F.tTitle; font.weight: Font.Bold }
            Text { anchors.baseline: heading.baseline; text: (F.groups[page.group] || {name: ""}).name; color: F.dim; font.family: F.font; font.pixelSize: F.tMeta + 2 * F.u }
        }
        Row {
            spacing: 14 * F.u
            Repeater {
                model: [["Alerts", F.alert], ["Detections", F.detection]]
                delegate: Rectangle {
                    required property var modelData
                    required property int index
                    readonly property bool on: page.tab === index
                    readonly property bool cur: page.activeFocus && page.zone === 0 && page.tab === index
                    width: tabText.implicitWidth + 70 * F.u; height: tabText.implicitHeight + 28 * F.u; radius: height / 2
                    color: on ? F.panel2 : "transparent"
                    border.color: cur ? F.focus : on ? F.line : F.line; border.width: (cur ? 3 : 1) * F.u
                    Rectangle { x: 24 * F.u; anchors.verticalCenter: parent.verticalCenter; width: 12 * F.u; height: width; radius: width / 2; color: modelData[1] }
                    Text { id: tabText; x: 46 * F.u; anchors.verticalCenter: parent.verticalCenter; text: modelData[0]; color: parent.on ? F.text : F.dim; font.family: F.font; font.pixelSize: F.tBody; font.weight: Font.DemiBold }
                }
            }
        }
    }
    Flickable {
        id: flick
        anchors { left: parent.left; right: parent.right; top: head.bottom; bottom: parent.bottom; topMargin: 6 * F.u; leftMargin: 26 * F.u; rightMargin: F.edge - 30 * F.u }
        contentHeight: grid.height + 60 * F.u
        interactive: false
        clip: true
        Behavior on contentY { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
        Grid {
            id: grid
            y: 30 * F.u
            x: 30 * F.u
            columns: page.cols
            spacing: F.gap
            readonly property real tw: (flick.width - 60 * F.u - (page.cols - 1) * spacing) / page.cols
            Repeater {
                model: page.items
                delegate: ReviewCard {
                    required property var modelData
                    required property int index
                    width: grid.tw; height: implicitHeight
                    r: modelData
                    current: page.activeFocus && page.zone === 1 && page.ci === index
                }
            }
        }
    }
    Text {
        anchors.centerIn: flick
        visible: page.loading || page.problem || !page.items.length
        text: page.loading ? "Loading…" : page.problem ? page.problem : page.tab === 0 ? "No alerts." : "No detections."
        color: F.dim; font.family: F.font; font.pixelSize: 30 * F.u
    }
}
