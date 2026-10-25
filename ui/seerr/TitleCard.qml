// A poster card, as on the website: MOVIE/SERIES and status badges; when focused, the year,
// title and overview over the poster. Cards that only know (mediaType, tmdbId) fetch the
// rest. OK opens the details page.
import QtQuick

Item {
    id: card
    property string mediaType: "movie"
    property int tmdbId: 0
    property string title: ""
    property string year: ""
    property string poster: ""
    property string overview: ""
    property int status: 0
    property string caption: ""              // under the card ("as Chani")
    width: S.cardW
    height: S.cardH + (caption ? 42 * S.u : 0)

    Component.onCompleted: {
        if (!title && tmdbId)
            S.details(mediaType, tmdbId, r => {
                const c = S.card(r, mediaType);
                title = c.title; year = c.year; poster = c.poster; overview = c.overview; status = c.status;
            });
    }

    Keys.onReturnPressed: S.openMedia(mediaType, tmdbId)
    Keys.onEnterPressed: S.openMedia(mediaType, tmdbId)

    Rectangle {
        id: frame
        width: parent.width
        height: S.cardH
        radius: 12 * S.u
        color: S.panel
        border.color: S.line
        border.width: 1
        clip: true
        scale: card.activeFocus ? 1.06 : 1
        Behavior on scale { NumberAnimation { duration: 110 } }

        Image {
            anchors.fill: parent
            anchors.margins: 1
            source: S.img(card.poster, "w300_and_h450_face")
            sourceSize.width: 300
            asynchronous: true
            fillMode: Image.PreserveAspectCrop
        }
        Text {                                // no poster
            anchors.centerIn: parent
            width: parent.width - 24 * S.u
            visible: !card.poster && !!card.title
            text: card.title
            color: S.dim
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            font.family: S.font
            font.pixelSize: 22 * S.u
        }
        Rectangle {                           // focused: details over the poster, like hover
            anchors.fill: parent
            visible: card.activeFocus && !!card.title
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(0.07, 0.09, 0.15, 0.35) }
                GradientStop { position: 1.0; color: Qt.rgba(0.07, 0.09, 0.15, 0.97) }
            }
            Column {
                anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: 14 * S.u }
                spacing: 4 * S.u
                Text { text: card.year; color: S.text2; font.family: S.font; font.pixelSize: 17 * S.u }
                Text {
                    width: parent.width; text: card.title; color: S.text; wrapMode: Text.WordWrap
                    maximumLineCount: 3; elide: Text.ElideRight
                    font.family: S.font; font.pixelSize: 24 * S.u; font.weight: Font.Bold
                }
                Text {
                    width: parent.width; text: card.overview; color: S.text2; wrapMode: Text.WordWrap
                    maximumLineCount: 5; elide: Text.ElideRight; font.family: S.font; font.pixelSize: 16 * S.u
                    lineHeight: 1.1
                }
            }
        }
        TypePill { x: 10 * S.u; y: 10 * S.u; mediaType: card.mediaType }
        StatusIcon { anchors { right: parent.right; top: parent.top; margins: 10 * S.u } status: card.status }
        Ring { on: card.activeFocus; radiusOf: 12 }
    }
    Text {
        anchors { top: frame.bottom; topMargin: 10 * S.u; horizontalCenter: parent.horizontalCenter }
        width: parent.width
        visible: !!card.caption
        text: card.caption
        horizontalAlignment: Text.AlignHCenter
        elide: Text.ElideRight
        color: S.text2
        font.family: S.font
        font.pixelSize: 18 * S.u
    }
}
