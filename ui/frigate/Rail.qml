// The sidebar, like Frigate's: Live with the camera groups, Review, and the account.
// Up/Down move, OK opens, Right goes to the page.
import QtQuick

FocusScope {
    id: rail
    property int section: 0                  // 0 live, 1 review
    property int group: 0
    property int unreviewed: 0               // alerts not looked at yet (the Review badge)
    readonly property var entries: {
        const e = F.groups.map((g, i) => ({kind: "group", index: i, label: g.name, count: g.cameras.length}));
        e.push({kind: "review", label: "Review", count: 0});
        e.push({kind: "signout", label: "Sign out", count: 0});
        return e;
    }
    property int idx: 0
    signal chosen(var entry)
    signal toPage()

    function sync() { idx = section === 1 ? entries.length - 2 : Math.min(group, entries.length - 1); }
    onActiveFocusChanged: if (activeFocus) sync()
    Keys.onUpPressed: idx = Math.max(0, idx - 1)
    Keys.onDownPressed: idx = Math.min(entries.length - 1, idx + 1)
    Keys.onRightPressed: toPage()
    Keys.onReturnPressed: chosen(entries[idx])
    Keys.onEnterPressed: chosen(entries[idx])

    Rectangle { anchors.fill: parent; color: F.side }
    Rectangle { anchors { right: parent.right; top: parent.top; bottom: parent.bottom } width: 1; color: F.line }

    Row {                                        // the app's mark
        id: brand
        x: 40 * F.u; y: 48 * F.u
        spacing: 16 * F.u
        Rectangle {
            width: 54 * F.u; height: width; radius: 14 * F.u; color: F.accent
            Rectangle { anchors.centerIn: parent; width: 30 * F.u; height: 22 * F.u; radius: 5 * F.u; color: "white"
                Rectangle { anchors.centerIn: parent; width: 11 * F.u; height: width; radius: width / 2; color: F.accent } }
        }
        Text { anchors.verticalCenter: parent.verticalCenter; text: "Frigate"; color: F.text; font.family: F.font; font.pixelSize: 38 * F.u; font.weight: Font.Bold }
    }

    Column {
        anchors { left: parent.left; right: parent.right; top: brand.bottom; topMargin: 48 * F.u; leftMargin: 20 * F.u; rightMargin: 20 * F.u }
        spacing: 6 * F.u
        Text { leftPadding: 22 * F.u; bottomPadding: 6 * F.u; text: "LIVE"; color: F.faint; font.family: F.font; font.pixelSize: 20 * F.u; font.weight: Font.Bold; font.letterSpacing: 2 * F.u }
        Repeater {
            model: rail.entries
            delegate: Column {
                id: entryCol
                required property var modelData
                required property int index
                width: parent.width
                spacing: 6 * F.u
                Item {                           // a gap before Review and Sign out
                    width: 1; height: entryCol.modelData.kind === "review" ? 30 * F.u : entryCol.modelData.kind === "signout" ? 60 * F.u : 0
                }
                Rectangle {
                    readonly property bool sel: (entryCol.modelData.kind === "group" && rail.section === 0 && rail.group === entryCol.modelData.index)
                                                || (entryCol.modelData.kind === "review" && rail.section === 1)
                    readonly property bool cur: rail.activeFocus && rail.idx === entryCol.index
                    width: parent.width; height: 68 * F.u; radius: 12 * F.u
                    color: cur ? F.panel2 : sel ? F.panel : "transparent"
                    border.color: cur ? F.focus : "transparent"; border.width: 3 * F.u
                    Rectangle { visible: parent.sel; x: 0; anchors.verticalCenter: parent.verticalCenter; width: 5 * F.u; height: 34 * F.u; radius: 3 * F.u; color: F.accent }
                    Text {
                        anchors { left: parent.left; leftMargin: 22 * F.u; right: badge.left; rightMargin: 10 * F.u; verticalCenter: parent.verticalCenter }
                        text: entryCol.modelData.label
                        color: parent.sel || parent.cur ? F.text : entryCol.modelData.kind === "signout" ? F.faint : F.text2
                        font.family: F.font; font.pixelSize: 27 * F.u; font.weight: parent.sel ? Font.DemiBold : Font.Normal
                        elide: Text.ElideRight
                    }
                    Rectangle {
                        id: badge
                        readonly property int n: entryCol.modelData.kind === "review" ? rail.unreviewed : entryCol.modelData.count
                        visible: n > 0
                        anchors { right: parent.right; rightMargin: 18 * F.u; verticalCenter: parent.verticalCenter }
                        width: Math.max(height, badgeText.implicitWidth + 18 * F.u); height: 36 * F.u; radius: height / 2
                        color: entryCol.modelData.kind === "review" ? F.alert : F.panel2
                        Text { id: badgeText; anchors.centerIn: parent; text: badge.n; color: entryCol.modelData.kind === "review" ? "white" : F.dim; font.family: F.font; font.pixelSize: 20 * F.u; font.weight: Font.DemiBold }
                    }
                }
            }
        }
    }
    Text {
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom; leftMargin: 42 * F.u; rightMargin: 20 * F.u; bottomMargin: 40 * F.u }
        text: F.status.user ? "Signed in as " + F.status.user : ""
        color: F.faint; font.family: F.font; font.pixelSize: 21 * F.u; elide: Text.ElideRight
    }
}
