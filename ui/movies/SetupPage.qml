// Nothing to look things up with yet: set up Seerr, or add a TMDB API key.
import QtQuick

FocusScope {
    id: page
    property string problem: ""
    Rectangle { anchors.fill: parent; color: M.bg }
    Column {
        anchors.centerIn: parent
        width: 1100 * M.u
        spacing: 26 * M.u
        Row {
            spacing: 18 * M.u
            Rectangle { width: 64 * M.u; height: width; radius: 16 * M.u; color: M.accent
                Image { anchors.centerIn: parent; width: 40 * M.u; height: width; sourceSize: M.sz(width, height); source: "icons/mark.svg" } }
            Text { anchors.verticalCenter: parent.verticalCenter; text: "Movies & TV"; color: M.text; font.family: M.font; font.pixelSize: 48 * M.u; font.weight: Font.Bold }
        }
        Text {
            width: parent.width; wrapMode: Text.WordWrap
            text: "Movies & TV looks things up on TMDB. It needs one of these, in Settings → Apps:"
            color: M.text2; font.family: M.font; font.pixelSize: M.tBody
        }
        Text {
            width: parent.width; wrapMode: Text.WordWrap; lineHeight: 1.25
            text: "•  Seerr: its address and API key (Seerr → Settings → General). Then Movies & TV also knows what's in your Jellyfin.\n"
                  + "•  Or a free TMDB API key: sign up at themoviedb.org, then Settings → API → API Read Access Token, under Movies & TV."
            color: M.text2; font.family: M.font; font.pixelSize: M.tBody
        }
        Text { visible: !!page.problem; width: parent.width; wrapMode: Text.WordWrap; text: page.problem; color: M.faint; font.family: M.font; font.pixelSize: M.tMeta }
    }
}
