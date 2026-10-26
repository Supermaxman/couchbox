// A poster card: the poster (or a made-up one in the title's colours), then the title, the year
// and the score. `on` draws the focus ring; `rank` puts a number on it; `role` adds a line
// (a character, or a job) for filmographies and cast.
import QtQuick

Item {
    id: card
    property var item: ({})
    property bool on: false
    property int rank: 0
    property string role: ""
    property bool captioned: true
    width: M.posterW
    height: art.height + (captioned ? caption.implicitHeight + 16 * M.u : 0)
    scale: on ? M.lift : 1
    z: on ? 2 : 0
    Behavior on scale { NumberAnimation { duration: 120 } }

    Rectangle {
        id: art
        width: parent.width; height: Math.round(parent.width * 1.5)
        radius: M.radius; clip: true
        gradient: Gradient {
            GradientStop { position: 0; color: Qt.hsla(M.hue(card.item.title), 0.45, 0.30, 1) }
            GradientStop { position: 1; color: Qt.hsla((M.hue(card.item.title) + 0.12) % 1, 0.50, 0.14, 1) }
        }
        Text {                               // no poster: the title, large
            visible: img.status !== Image.Ready
            anchors { fill: parent; margins: 18 * M.u }
            text: card.item.title || ""
            color: "#f4f4f5"; opacity: 0.9
            font.family: M.font; font.pixelSize: 30 * M.u; font.weight: Font.Bold
            wrapMode: Text.WordWrap; verticalAlignment: Text.AlignBottom; maximumLineCount: 5; elide: Text.ElideRight
        }
        Image {
            id: img
            anchors.fill: parent
            source: card.item.poster || ""
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            sourceSize.width: Math.round(card.width)
        }
        Rectangle {                          // the score, top right
            visible: !!card.item.score
            anchors { right: parent.right; top: parent.top; margins: 10 * M.u }
            width: scoreRow.implicitWidth + 18 * M.u; height: 38 * M.u; radius: 8 * M.u
            color: "#d0000000"
            Row {
                id: scoreRow
                anchors.centerIn: parent
                spacing: 6 * M.u
                Text { text: "★"; color: M.accent; font.pixelSize: 21 * M.u; anchors.verticalCenter: parent.verticalCenter }
                Text { text: card.item.score ? Number(card.item.score).toFixed(1) : ""; color: "white"; font.family: M.font; font.pixelSize: 21 * M.u; font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter }
            }
        }
        Rectangle {                          // the rank, top left
            visible: card.rank > 0
            anchors { left: parent.left; top: parent.top; margins: 10 * M.u }
            width: Math.max(height, rankText.implicitWidth + 18 * M.u); height: 42 * M.u; radius: 8 * M.u
            color: M.accent
            Text { id: rankText; anchors.centerIn: parent; text: card.rank; color: M.accentDark; font.family: M.font; font.pixelSize: 24 * M.u; font.weight: Font.Bold }
        }
    }
    Rectangle {                              // focus ring
        anchors { fill: art; margins: -M.ring - 2 * M.u }
        radius: M.radius + M.ring
        color: "transparent"
        border.color: M.focus; border.width: M.ring
        visible: card.on
    }
    Column {
        id: caption
        visible: card.captioned
        anchors { left: parent.left; right: parent.right; top: art.bottom; topMargin: 12 * M.u }
        spacing: 3 * M.u
        Text { width: parent.width; text: card.item.title || ""; color: card.on ? M.text : M.text2; font.family: M.font; font.pixelSize: M.tMeta; font.weight: Font.DemiBold; elide: Text.ElideRight }
        Text {
            width: parent.width
            text: card.role || [card.item.year, card.item.type === "tv" ? "Series" : ""].filter(x => !!x).join(" · ")
            color: M.dim; font.family: M.font; font.pixelSize: M.tSmall; elide: Text.ElideRight
        }
    }
}
