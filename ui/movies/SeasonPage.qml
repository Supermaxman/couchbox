// A season of a show: its episodes with their air dates, length, score and story. Up/Down
// move, Back goes back.
import QtQuick

FocusScope {
    id: page
    property int tid: 0
    property int n: 1
    property string show: ""
    property var s: null
    property bool loading: true
    property string problem: ""
    signal closed()
    readonly property string label: show + (s ? ": " + s.name : "")

    Component.onCompleted: M.call("season", {id: tid, n: n}, r => { s = r; loading = false; list.forceActiveFocus(); },
                                  e => { loading = false; problem = e; })
    onActiveFocusChanged: if (activeFocus) list.forceActiveFocus()
    Keys.onEscapePressed: closed()
    Keys.onBackPressed: closed()

    Rectangle { anchors.fill: parent; color: M.bg }
    Column {
        id: head
        x: 80 * M.u; y: 60 * M.u
        width: parent.width - x - M.edge
        spacing: 10 * M.u
        Text { text: page.show; color: M.dim; font.family: M.font; font.pixelSize: M.tHead }
        Text { text: page.s ? page.s.name : ""; color: M.text; font.family: M.font; font.pixelSize: M.tTitle; font.weight: Font.Bold }
        Text {
            width: parent.width
            text: page.s ? [page.s.year, page.s.episodes.length + " episodes"].filter(x => !!x).join("   ·   ") : ""
            color: M.text2; font.family: M.font; font.pixelSize: M.tBody
        }
    }
    ListView {
        id: list
        anchors { left: parent.left; right: parent.right; top: head.bottom; bottom: parent.bottom; topMargin: 34 * M.u; leftMargin: 80 * M.u; rightMargin: M.edge }
        clip: true
        model: page.s ? page.s.episodes : []
        spacing: 14 * M.u
        cacheBuffer: 1200
        highlightMoveDuration: 140
        preferredHighlightBegin: 10 * M.u
        preferredHighlightEnd: height - 200 * M.u
        highlightRangeMode: ListView.ApplyRange
        keyNavigationEnabled: true
        delegate: Rectangle {
            id: ep
            required property var modelData
            required property int index
            readonly property bool cur: ListView.isCurrentItem && list.activeFocus
            width: list.width - 20 * M.u; height: 180 * M.u
            radius: M.radius
            color: cur ? M.panel2 : M.panel
            border.color: cur ? M.focus : M.line; border.width: (cur ? 3 : 1) * M.u
            Rectangle {
                id: still
                x: 18 * M.u; anchors.verticalCenter: parent.verticalCenter
                width: 256 * M.u; height: 144 * M.u; radius: 8 * M.u; clip: true
                color: Qt.hsla(M.hue(page.show + ep.index), 0.35, 0.2, 1)
                Image { anchors.fill: parent; source: ep.modelData.still || ""; fillMode: Image.PreserveAspectCrop; asynchronous: true; sourceSize.width: M.px(width) }
                Text { visible: !ep.modelData.still; anchors.centerIn: parent; text: ep.modelData.n; color: M.text2; font.family: M.font; font.pixelSize: 48 * M.u; font.weight: Font.Bold }
            }
            Column {
                anchors { left: still.right; leftMargin: 28 * M.u; right: parent.right; rightMargin: 28 * M.u; verticalCenter: parent.verticalCenter }
                spacing: 8 * M.u
                Text { width: parent.width; text: ep.modelData.n + ".  " + ep.modelData.name; color: M.text; font.family: M.font; font.pixelSize: M.tBody; font.weight: Font.DemiBold; elide: Text.ElideRight }
                Text {
                    width: parent.width
                    text: [M.date(ep.modelData.date), M.runtime(ep.modelData.runtime), ep.modelData.score ? "★ " + Number(ep.modelData.score).toFixed(1) : ""].filter(x => !!x).join("   ·   ")
                    color: M.dim; font.family: M.font; font.pixelSize: M.tMeta
                }
                Text { width: parent.width; text: ep.modelData.overview; color: M.text2; font.family: M.font; font.pixelSize: M.tMeta; wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight }
            }
        }
    }
    Text {
        anchors.centerIn: parent
        visible: page.loading || !!page.problem
        text: page.problem || "Loading…"
        color: page.problem ? M.text2 : M.faint; font.family: M.font; font.pixelSize: M.tHead
    }
}
