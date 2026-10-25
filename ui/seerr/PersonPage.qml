// A person, like the website: photo, name, birth, also known as, biography (OK shows all),
// then Appearances ("as Chani") and Crew.
import QtQuick

VPage {
    id: page
    clipContent: false
    property int personId: 0
    property var p: null
    property var cast: []
    property var crew: []
    property bool fullBio: false

    function dedupe(list) {
        const seen = {}, out = [];
        for (const c of list.slice().sort((a, b) => (b.popularity || 0) - (a.popularity || 0))) {
            const key = c.mediaType + c.id;
            if (seen[key]) { seen[key].caption += ", " + (c.character || c.job || ""); continue; }
            const it = {mediaType: c.mediaType, id: c.id, title: c.title || c.name || "", year: (c.releaseDate || c.firstAirDate || "").slice(0, 4),
                        poster: c.posterPath || "", overview: c.overview || "", status: c.mediaInfo ? c.mediaInfo.status : 0,
                        caption: c.character ? "as " + c.character : c.job || ""};
            seen[key] = it;
            out.push(it);
        }
        return out;
    }
    Component.onCompleted: {
        S.get("/person/" + personId, r => p = r, err => S.toast(err));
        S.get("/person/" + personId + "/combined_credits", r => { cast = dedupe(r.cast || []); crew = dedupe(r.crew || []); });
    }
    onPChanged: if (activeFocus) Qt.callLater(focusFirst)

    Image {
        x: -S.gutter
        width: page.width + S.gutter
        height: 520 * S.u
        source: page.cast.length ? S.img((page.cast.find(c => c.poster) || {}).poster, "w780") : ""
        sourceSize.width: 600
        fillMode: Image.PreserveAspectCrop
        opacity: 0.18
        asynchronous: true
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0.4; color: "transparent" }
                GradientStop { position: 1.0; color: S.bg }
            }
        }
    }

    Item {
        id: header
        y: 124 * S.u
        width: page.width - S.edge
        height: Math.max(photo.height, info.height)
        Rectangle {
            id: photo
            width: 220 * S.u; height: width; radius: width / 2; color: S.panel
            RoundImage { anchors.fill: parent; source: page.p ? S.img(page.p.profilePath, "w300") : ""; sourceWidth: 300 }
        }
        Column {
            id: info
            anchors { left: photo.right; leftMargin: 40 * S.u; right: parent.right }
            spacing: 8 * S.u
            Text { text: page.p ? page.p.name : ""; color: S.text; font.family: S.font; font.pixelSize: 50 * S.u; font.weight: Font.Bold }
            Text {
                visible: !!text
                text: page.p ? [page.p.birthday ? "Born " + S.date(page.p.birthday) : "", page.p.deathday ? "Died " + S.date(page.p.deathday) : "", page.p.placeOfBirth || ""].filter(x => x).join("  |  ") : ""
                color: S.text2; font.family: S.font; font.pixelSize: 22 * S.u
            }
            Text {
                width: parent.width
                visible: !!(page.p && page.p.alsoKnownAs && page.p.alsoKnownAs.length)
                text: page.p && page.p.alsoKnownAs ? "Also Known As: " + page.p.alsoKnownAs.slice(0, 4).join(", ") : ""
                elide: Text.ElideRight
                color: S.text2; font.family: S.font; font.pixelSize: 22 * S.u
            }
            Rectangle {                          // the biography: OK shows all of it
                id: bio
                property bool stop: bioText.truncated || page.fullBio
                width: parent.width
                height: bioText.height + 16 * S.u
                color: "transparent"
                radius: 8 * S.u
                border.color: activeFocus ? S.focus : "transparent"
                border.width: 3 * S.u
                Text {
                    id: bioText
                    x: 8 * S.u; y: 8 * S.u
                    width: parent.width - 16 * S.u
                    text: page.p ? page.p.biography || "" : ""
                    wrapMode: Text.WordWrap
                    maximumLineCount: page.fullBio ? 40 : 5
                    elide: Text.ElideRight
                    color: S.text2; font.family: S.font; font.pixelSize: 21 * S.u; lineHeight: 1.25
                }
                Keys.onReturnPressed: page.fullBio = !page.fullBio
                Keys.onEnterPressed: page.fullBio = !page.fullBio
            }
        }
    }

    Column {
        y: header.y + header.height + 52 * S.u
        width: page.width - S.edge
        spacing: 40 * S.u
        Repeater {
            model: [{title: "Appearances", list: page.cast}, {title: "Crew", list: page.crew}]
            Column {
                width: parent.width
                spacing: 18 * S.u
                visible: modelData.list.length > 0
                Text { text: modelData.title; color: S.text; font.family: S.font; font.pixelSize: 34 * S.u; font.weight: Font.Bold }
                GridView {
                    property bool stop: count > 0
                    width: parent.width
                    height: contentHeight
                    interactive: false
                    focus: true
                    cellWidth: S.cardW + S.rowGap
                    cellHeight: S.cardH + 84 * S.u
                    model: modelData.list
                    delegate: Item {
                        required property var modelData
                        required property int index
                        width: S.cardW + S.rowGap; height: S.cardH + 84 * S.u
                        focus: GridView.isCurrentItem
                        TitleCard {
                            x: 8 * S.u; y: 8 * S.u
                            focus: true
                            mediaType: modelData.mediaType; tmdbId: modelData.id; title: modelData.title; year: modelData.year
                            poster: modelData.poster; overview: modelData.overview; status: modelData.status; caption: modelData.caption
                        }
                    }
                }
            }
        }
    }
}
