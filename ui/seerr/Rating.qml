// One rating in the facts panel: Rotten Tomatoes critics (tomato / splat), audience
// (popcorn / spilled), IMDb, TMDB.
import QtQuick

Row {
    property string kind: "fresh"
    property string value: ""
    spacing: 8 * S.u
    Item {
        width: 28 * S.u
        height: 28 * S.u
        anchors.verticalCenter: parent.verticalCenter
        // tomato: red with a green top; splat: green
        Rectangle {
            visible: kind === "fresh" || kind === "rotten"
            anchors.centerIn: parent
            width: 20 * S.u; height: 18 * S.u; radius: width / 2
            color: kind === "fresh" ? "#fa320a" : "#0fc755"
            Rectangle { visible: kind === "fresh"; x: parent.width * 0.3; y: -3 * S.u; width: parent.width * 0.4; height: 6 * S.u; radius: 3 * S.u; color: "#00912d" }
        }
        // popcorn bucket: red and white; spilled: green
        Item {
            visible: kind === "popcorn" || kind === "spilled"
            anchors.fill: parent
            Rectangle { x: 4 * S.u; y: 1 * S.u; width: 16 * S.u; height: 9 * S.u; radius: 4 * S.u; color: kind === "popcorn" ? "#ffe0a3" : "#c6f0d2" }
            Rectangle {
                x: 5 * S.u; y: 8 * S.u; width: 14 * S.u; height: 15 * S.u; radius: 2 * S.u
                color: kind === "popcorn" ? "#fa320a" : "#0fc755"
                Row {
                    anchors.fill: parent
                    anchors.margins: 2 * S.u
                    spacing: 2 * S.u
                    Repeater { model: 3; Rectangle { width: 2 * S.u; height: parent.height; color: "white"; opacity: 0.9 } }
                }
            }
        }
        Rectangle {
            visible: kind === "imdb"
            anchors.centerIn: parent
            width: 34 * S.u; height: 17 * S.u; radius: 3 * S.u
            color: "#f5c518"
            Text { anchors.centerIn: parent; text: "IMDb"; color: "black"; font.family: S.font; font.pixelSize: 11 * S.u; font.weight: Font.Black }
        }
        Rectangle {
            visible: kind === "tmdb"
            anchors.centerIn: parent
            width: 34 * S.u; height: 17 * S.u; radius: 8 * S.u
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: "#90cea1" }
                GradientStop { position: 1; color: "#01b4e4" }
            }
            Text { anchors.centerIn: parent; text: "TMDB"; color: "#0d253f"; font.family: S.font; font.pixelSize: 10 * S.u; font.weight: Font.Black }
        }
    }
    Text {
        text: parent.value
        color: S.text2
        font.family: S.font
        font.pixelSize: 21 * S.u
        anchors.verticalCenter: parent.verticalCenter
        leftPadding: kind === "imdb" || kind === "tmdb" ? 6 * S.u : 0
    }
}
