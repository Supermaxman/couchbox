// Search: type (the keyboard pop-up, a phone, or the mic) and see songs, artists, albums and
// playlists. The box at the top is selected first: OK types, Down goes to the results.
import QtQuick

Sections {
    id: page
    property string query: ""
    property var results: ({})
    property bool busy: false
    signal ask(string current)
    headerTakesFocus: true
    function search(q) {
        query = q;
        if (!q) { results = {}; return; }
        busy = true;
        S.call("search", {q: q}, r => { page.results = r; page.busy = false; page.cur = 0; page.focusCur(); },
               e => { page.busy = false; S.toast(e); });
    }
    header: Component {
        FocusScope {
            id: hdr
            signal downEdge()
            signal leftEdge()
            height: col.implicitHeight
            Keys.onReturnPressed: page.ask(page.query)
            Keys.onEnterPressed: page.ask(page.query)
            Keys.onDownPressed: downEdge()
            Keys.onLeftPressed: leftEdge()
            Column {
                id: col
                width: parent.width - S.edge
                spacing: 24 * S.u
                Text { text: "Search"; color: S.text; font.family: S.font; font.pixelSize: S.tTitle; font.weight: Font.Bold }
                Rectangle {
                    width: Math.min(parent.width, 1100 * S.u); height: 92 * S.u; radius: height / 2
                    color: hdr.activeFocus ? "#ffffff" : S.panel2
                    border.color: hdr.activeFocus ? S.accent : "transparent"; border.width: S.ring
                    Image { id: glass; x: 30 * S.u; anchors.verticalCenter: parent.verticalCenter; width: 38 * S.u; height: width
                            sourceSize: Qt.size(width, height); source: S.icon(hdr.activeFocus ? "search-dark" : "search") }
                    Text {
                        anchors { left: glass.right; leftMargin: 20 * S.u; right: parent.right; rightMargin: 30 * S.u; verticalCenter: parent.verticalCenter }
                        text: page.busy ? "Searching for “" + page.query + "”…" : page.query || "What do you want to listen to?"
                        color: hdr.activeFocus ? (page.query ? "#000000" : "#52525b") : (page.query ? S.text : S.dim)
                        font.family: S.font; font.pixelSize: S.tBody; elide: Text.ElideRight
                    }
                }
            }
        }
    }
    sections: [
        {type: "tracks", title: "Songs", items: results.tracks || [], maxRows: 5},
        {type: "shelf", title: "Artists", items: results.artists || [], cardW: 230},
        {type: "shelf", title: "Albums", items: results.albums || []},
        {type: "shelf", title: "Playlists", items: results.playlists || []}
    ]
}
