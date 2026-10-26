// Your Library: Liked Songs and your playlists, Spotify's playlists you saved, albums, artists.
import QtQuick

Sections {
    id: page
    property var info: ({})
    property bool loading: true
    function load() {
        loading = true;
        S.call("library", {}, r => { page.info = r; page.loading = false; }, e => { page.loading = false; S.toast(e); });
    }
    header: Component {
        Text { text: "Your Library"; color: S.text; font.family: S.font; font.pixelSize: S.tTitle; font.weight: Font.Bold }
    }
    readonly property var liked: ({kind: "liked", uri: "liked", id: "liked", name: "Liked Songs", total: info.liked_total || 0})
    sections: [
        {type: "shelf", title: "Playlists", items: info.playlists ? [liked].concat((info.playlists || []).filter(p => !p.spotify)) : []},
        {type: "shelf", title: "Made for you", items: (info.playlists || []).filter(p => p.spotify)},
        {type: "shelf", title: "Albums", items: info.albums || []},
        {type: "shelf", title: "Artists", items: info.artists || [], cardW: 230}
    ]
}
