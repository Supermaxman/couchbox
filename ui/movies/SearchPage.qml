// Search movies, shows and people: OK on the box opens the keyboard pop-up (or type on a
// phone, or say it); results come in rows: people, movies, shows. Up from the first row goes
// back to the box.
import QtQuick

FocusScope {
    id: page
    property string query: ""
    property var res: null
    property bool loading: false
    property string problem: ""
    property int zone: 0                      // 0 the box, then the result rows
    signal toRail()
    signal ask(string current)

    readonly property var rows: !res ? [] : [
        {title: "People", kind: "person", items: res.people},
        {title: "Movies", kind: "poster", items: res.movies},
        {title: "Shows", kind: "poster", items: res.tv}
    ].filter(r => r.items.length)

    function search(q) {
        query = q.trim();
        if (!query) return;
        loading = true; problem = ""; res = null;
        M.call("search", {query: query}, r => { if (r.query !== page.query) return; res = r; loading = false; zone = rows.length ? 1 : 0; Qt.callLater(focusZone); },
               e => { loading = false; problem = e; });
    }
    function focusZone() {
        if (zone === 0) { box.forceActiveFocus(); flick.contentY = 0; return; }
        const s = rep.itemAt(zone - 1);
        if (s) { s.forceActiveFocus(); flick.contentY = Math.max(0, s.y - 10 * M.u); }
    }
    onActiveFocusChanged: if (activeFocus) focusZone()
    Keys.onUpPressed: if (zone > 0) { zone--; focusZone(); }
    Keys.onDownPressed: if (zone < rows.length) { zone++; focusZone(); }

    Text { id: heading; x: 60 * M.u; y: 56 * M.u; text: "Search"; color: M.text; font.family: M.font; font.pixelSize: M.tTitle; font.weight: Font.Bold }
    Rectangle {
        id: box
        anchors { left: parent.left; right: parent.right; top: heading.bottom; topMargin: 28 * M.u; leftMargin: 60 * M.u; rightMargin: M.edge + 40 * M.u }
        height: 88 * M.u; radius: 16 * M.u
        color: activeFocus ? M.panel2 : M.panel
        border.color: activeFocus ? M.focus : M.line; border.width: (activeFocus ? 3 : 1) * M.u
        Keys.onReturnPressed: page.ask(page.query)
        Keys.onEnterPressed: page.ask(page.query)
        Keys.onLeftPressed: page.toRail()
        Image { id: lens; x: 28 * M.u; anchors.verticalCenter: parent.verticalCenter; width: 36 * M.u; height: width; sourceSize: M.sz(width, height); source: "icons/search.svg"; opacity: 0.7 }
        Text {
            anchors { left: lens.right; leftMargin: 20 * M.u; right: parent.right; rightMargin: 28 * M.u; verticalCenter: parent.verticalCenter }
            text: page.query || "Movies, shows and people  (press OK to type, or use your phone)"
            color: page.query ? M.text : M.faint; font.family: M.font; font.pixelSize: page.query ? 32 * M.u : M.tBody; elide: Text.ElideRight
        }
    }
    Flickable {
        id: flick
        anchors { left: parent.left; right: parent.right; top: box.bottom; bottom: parent.bottom; topMargin: 40 * M.u }
        contentHeight: col.height + 300 * M.u
        interactive: false
        clip: true
        Behavior on contentY { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
        Column {
            id: col
            x: 60 * M.u
            width: flick.width - x
            topPadding: 10 * M.u
            spacing: 36 * M.u
            Repeater {
                id: rep
                model: page.rows
                delegate: Shelf {
                    required property var modelData
                    title: modelData.title
                    kind: modelData.kind
                    note: modelData.items.length + ""
                    items: modelData.items
                    onOpen: it => M.open(it)
                    onEdgeLeft: page.toRail()
                }
            }
        }
    }
    Text {
        anchors { horizontalCenter: flick.horizontalCenter; top: flick.top; topMargin: 120 * M.u }
        visible: page.loading || !!page.problem || (!!page.res && !page.rows.length) || !page.query
        width: parent.width * 0.7; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
        text: page.problem || (page.loading ? "Searching…" : !page.query ? "Try a title, like “Arrival”, or a person, like “Florence Pugh”."
                                                                             : "Nothing found for “" + page.query + "”.")
        color: page.problem ? M.text2 : M.faint; font.family: M.font; font.pixelSize: M.tHead
    }
}
