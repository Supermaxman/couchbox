// Search: the search box (keyboard pop-up, phone, or the mic) and the results as a grid.
import QtQuick

FocusScope {
    id: page
    property string query: ""
    function search(q) {
        query = q.trim();
        if (!query) return;
        results.op = "search";
        results.args = {q: query};
        results.reload();
        results.forceActiveFocus();
    }
    function ask() { D.askText("Search " + D.name, page.query, false, t => page.search(t)); }

    Rectangle {
        id: box
        x: D.edge
        y: 150 * D.u
        width: parent.width - 2 * D.edge
        height: 84 * D.u
        radius: 8 * D.u
        color: activeFocus ? D.panel2 : D.panel
        border.color: activeFocus ? D.accent : D.line
        border.width: activeFocus ? 4 * D.u : 1
        focus: true
        Text {
            anchors { left: parent.left; leftMargin: 30 * D.u; verticalCenter: parent.verticalCenter }
            text: "⌕   " + (page.query || "Search shows, episodes and people")
            color: page.query ? D.text : D.dim
            font.family: D.font
            font.pixelSize: 30 * D.u
        }
        Keys.onReturnPressed: page.ask()
        Keys.onEnterPressed: page.ask()
        Keys.onDownPressed: results.forceActiveFocus()
        Keys.onPressed: event => {                       // typing on the phone starts a search
            if (event.text.length === 1 && event.text > " " && !(event.modifiers & Qt.ControlModifier)) {
                D.askText("Search " + D.name, event.text, false, t => page.search(t));
                event.accepted = true;
            }
        }
    }
    GridPage {
        id: results
        anchors { left: parent.left; right: parent.right; top: box.bottom; bottom: parent.bottom }
        headTop: 20 * D.u
        op: ""
        shape: "wide"
        empty: page.query ? "Nothing found for “" + page.query + "”." : "Search for a show, episode or cast member."
        Keys.onUpPressed: box.forceActiveFocus()
    }
    Component.onCompleted: Qt.callLater(ask)
}
