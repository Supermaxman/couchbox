// An artist: their picture and name, Play and Shuffle, their popular songs, albums, singles
// and EPs, and what they appear on.
import QtQuick

Sections {
    id: page
    property var item: ({})
    property var d: ({})
    property bool loading: true
    signal leftEdge()
    headerTakesFocus: true
    onToRail: leftEdge()
    function load() {
        loading = true; d = ({}); cur = -1;
        S.call("detail", {item: item}, r => { page.d = r; page.loading = false; }, e => { page.loading = false; S.toast(e); });
    }
    onItemChanged: if (item && item.kind) Qt.callLater(load)
    header: Component {
        FocusScope {
            id: hdr
            signal downEdge()
            signal leftEdge()
            property int btn: 0
            height: 330 * S.u
            Keys.onLeftPressed: { if (btn > 0) btn--; else leftEdge(); }
            Keys.onRightPressed: btn = Math.min(1, btn + 1)
            Keys.onDownPressed: downEdge()
            Keys.onReturnPressed: S.play({context: page.d.uri || page.item.uri, shuffle: btn === 1})
            Keys.onEnterPressed: S.play({context: page.d.uri || page.item.uri, shuffle: btn === 1})
            Art { id: pic; width: 300 * S.u; height: width; item: page.d.kind ? page.d : page.item; round: true }
            Column {
                anchors { left: pic.right; leftMargin: 50 * S.u; right: parent.right; rightMargin: S.edge; verticalCenter: pic.verticalCenter }
                spacing: 14 * S.u
                Text { text: "ARTIST"; color: S.dim; font.family: S.font; font.pixelSize: S.tSmall; font.weight: Font.Bold; font.letterSpacing: 2 * S.u }
                Text { width: parent.width; text: page.d.name || page.item.name || ""; elide: Text.ElideRight
                       color: S.text; font.family: S.font; font.pixelSize: 76 * S.u; font.weight: Font.Black }
                Text { width: parent.width; visible: !!(page.d.genres || []).length; text: (page.d.genres || []).slice(0, 3).join(" · "); elide: Text.ElideRight
                       color: S.dim; font.family: S.font; font.pixelSize: S.tMeta }
                Row {
                    spacing: 22 * S.u
                    topPadding: 10 * S.u
                    SButton { anchors.verticalCenter: parent.verticalCenter; icon: "play-dark"; primary: true; current: hdr.activeFocus && hdr.btn === 0 }
                    SButton { anchors.verticalCenter: parent.verticalCenter; icon: "shuffle"; current: hdr.activeFocus && hdr.btn === 1 }
                }
            }
        }
    }
    sections: [
        {type: "tracks", title: "Popular", items: d.top || [], maxRows: 5},
        {type: "shelf", title: "Albums", items: d.albums || []},
        {type: "shelf", title: "Singles and EPs", items: d.singles || []},
        {type: "shelf", title: "Appears on", items: d.appears_on || []}
    ]
}
