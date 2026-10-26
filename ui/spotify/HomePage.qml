// Home: what you played lately, Spotify's playlists for you, your playlists, new releases
// from your artists, your top artists and songs.
import QtQuick

Sections {
    id: page
    property var info: ({})
    property bool loading: true
    function load() {
        loading = true;
        S.call("home", {}, r => { page.info = r; page.loading = false; }, e => { page.loading = false; S.toast(e); });
    }
    function greeting() {
        const h = new Date().getHours();
        return h < 5 ? "Good night" : h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
    }
    header: Component {
        Column {
            spacing: 8 * S.u
            Text { text: page.greeting(); color: S.text; font.family: S.font; font.pixelSize: S.tTitle; font.weight: Font.Bold }
            Text { text: page.loading ? "Loading your music…" : (S.status.user ? "Signed in as " + S.status.user : "");
                   color: S.dim; font.family: S.font; font.pixelSize: S.tMeta }
        }
    }
    sections: [
        {type: "shelf", title: "Recently played", items: info.recent || []},
        {type: "shelf", title: "Made for you", items: info.made_for_you || []},
        {type: "shelf", title: "Your playlists", items: info.playlists || []},
        {type: "shelf", title: "New from your artists", items: info.new || []},
        {type: "shelf", title: "Your top artists", items: info.top_artists || [], cardW: 230},
        {type: "shelf", title: "On repeat", items: info.top_tracks || []}
    ]
    Text {
        anchors.centerIn: parent
        visible: !page.loading && !page.live.length
        width: parent.width * 0.6; wrapMode: Text.WordWrap; horizontalAlignment: Text.AlignHCenter
        text: "Nothing here yet. Play something from Search, or from the Spotify app on your phone (pick this TV as the speaker)."
        color: S.dim; font.family: S.font; font.pixelSize: S.tBody
    }
}
