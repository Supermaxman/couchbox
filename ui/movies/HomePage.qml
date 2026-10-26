// Home: the title in focus large at the top (its backdrop, score and story), then rows of
// what's trending, popular, top rated and coming soon. Up/Down change rows, Left at a row's
// start goes to the sidebar, OK opens the title.
import QtQuick

FocusScope {
    id: page
    property var rows: []
    property int row: 0
    property var current: null
    property bool loading: false
    property string problem: ""
    signal toRail()

    function load() {
        loading = true; problem = "";
        M.call("home", {}, r => { rows = r.rows; loading = false; row = 0; Qt.callLater(focusRow); },
               e => { loading = false; problem = e; });
    }
    function focusRow() {
        const s = rep.itemAt(row);
        if (!s) return;
        if (page.activeFocus) s.forceActiveFocus();
        current = rows[row].items[s.index] || null;
        flick.contentY = Math.max(0, s.y - 10 * M.u);
    }
    onActiveFocusChanged: if (activeFocus) focusRow()
    Keys.onUpPressed: if (row > 0) { row--; focusRow(); }
    Keys.onDownPressed: if (row < rows.length - 1) { row++; focusRow(); }

    // ------------------------------------------------------------------ the title in focus
    Item {
        id: hero
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: 470 * M.u
        clip: true
        Image {
            id: backdrop
            anchors { right: parent.right; top: parent.top; bottom: parent.bottom }
            width: height * 16 / 9
            source: page.current ? page.current.backdrop || "" : ""
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            sourceSize.width: 1280
            opacity: status === Image.Ready ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 250 } }
        }
        Rectangle {                              // fade the backdrop into the page, left and below
            anchors.fill: backdrop
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: M.bg }
                GradientStop { position: 0.45; color: "#cc0b0b0d" }
                GradientStop { position: 1; color: "#000b0b0d" }
            }
        }
        Rectangle {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            height: 160 * M.u
            gradient: Gradient { GradientStop { position: 0; color: "#000b0b0d" } GradientStop { position: 1; color: M.bg } }
        }
        Column {
            anchors { left: parent.left; leftMargin: 60 * M.u; top: parent.top; topMargin: 70 * M.u }
            width: Math.min(parent.width * 0.55, 900 * M.u)
            spacing: 16 * M.u
            visible: !!page.current
            Text {
                width: parent.width
                text: page.current ? page.current.title : ""
                color: M.text; font.family: M.font; font.pixelSize: M.tHero; font.weight: Font.Bold
                wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
            }
            Row {
                spacing: 18 * M.u
                Row {
                    visible: !!(page.current && page.current.score)
                    spacing: 8 * M.u
                    Text { text: "★"; color: M.accent; font.pixelSize: M.tBody; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: page.current && page.current.score ? Number(page.current.score).toFixed(1) : ""; color: M.text; font.family: M.font; font.pixelSize: M.tBody; font.weight: Font.DemiBold }
                    Text { text: page.current ? M.votes(page.current.votes) + " votes" : ""; color: M.dim; font.family: M.font; font.pixelSize: M.tMeta; anchors.verticalCenter: parent.verticalCenter }
                }
                Text {
                    text: page.current ? [page.current.year, M.kindLabel(page.current.type)].filter(x => !!x).join("  ·  ") : ""
                    color: M.text2; font.family: M.font; font.pixelSize: M.tBody
                }
            }
            Text {
                width: parent.width
                text: page.current ? page.current.overview : ""
                color: M.text2; font.family: M.font; font.pixelSize: M.tBody; lineHeight: 1.15
                wrapMode: Text.WordWrap; maximumLineCount: 4; elide: Text.ElideRight
            }
        }
    }

    // ------------------------------------------------------------------ rows
    Flickable {
        id: flick
        anchors { left: parent.left; right: parent.right; top: hero.bottom; bottom: parent.bottom }
        contentHeight: col.height + 400 * M.u
        interactive: false
        clip: true
        Behavior on contentY { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
        Column {
            id: col
            x: 60 * M.u
            width: flick.width - x
            topPadding: 14 * M.u
            spacing: 34 * M.u
            Repeater {
                id: rep
                model: page.rows
                delegate: Shelf {
                    required property var modelData
                    title: modelData.title
                    items: modelData.items
                    onIndexChanged: if (activeFocus) page.current = items[index] || null
                    onOpen: it => M.open(it)
                    onEdgeLeft: page.toRail()
                }
            }
        }
    }
    Text {
        anchors.centerIn: parent
        visible: page.loading || !!page.problem
        width: parent.width * 0.6; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
        text: page.problem || "Loading…"
        color: page.problem ? M.text2 : M.faint; font.family: M.font; font.pixelSize: M.tHead
    }
}
