// Stand-in for Qt WebEngine's web view when there's no web engine (off-screen screenshots,
// qmllint in CI): the same properties, signals and functions, and a drawing of a results
// page or an article, so the Search app's screens can be shown without the network.
import QtQuick

Rectangle {
    id: v
    color: backgroundColor
    property url url: ""
    property string title: ""
    property bool loading: false
    property int loadProgress: 100
    property bool canGoBack: false
    property bool canGoForward: false
    property real zoomFactor: 1
    property bool audioMuted: false
    property color backgroundColor: "white"
    property WebEngineSettings settings: WebEngineSettings {}
    property WebEngineProfile profile: WebEngineProfile {}
    signal newWindowRequested(var request)
    signal fullScreenRequested(var request)
    signal permissionRequested(var permission)
    signal javaScriptConsoleMessage(int level, string message, int lineNumber, string sourceID)

    readonly property bool results: url.toString().indexOf("/search?") >= 0
    onUrlChanged: { loading = true; title = results ? "Google Search" : "The Eiffel Tower: facts and figures"; done.restart(); }
    Timer { id: done; interval: 50; onTriggered: v.loading = false }
    function runJavaScript(script, callback) { if (callback) callback(script.indexOf("couchbox-search reader") >= 0 ? "{}" : "[]"); }
    function goBack() {}
    function goForward() {}
    function reload() {}
    function stop() {}

    readonly property real z1: zoomFactor * height / 1080
    Column {
        visible: v.results
        x: 180 * v.z1; y: 30 * v.z1
        spacing: 26 * v.z1
        Text { text: "About 1,230,000 results"; color: "#70757a"; font.pixelSize: 14 * v.z1 }
        Repeater {
            model: [["en.wikipedia.org", "Eiffel Tower - Wikipedia", "The tower is 330 metres (1,083 ft) tall, about the same height as an 81-storey building, and the tallest structure in Paris."],
                    ["example.org", "Eiffel Tower facts and figures", "At 330 m, it was the tallest man-made structure in the world until the Chrysler Building in New York City was finished in 1930."],
                    ["travel.example.com", "Visiting the Eiffel Tower: tickets and hours", "Lifts to the second floor and the summit, opening hours, and how to avoid the queues."]]
            Column {
                required property var modelData
                required property int index
                spacing: 4 * v.z1
                Text { text: modelData[0]; color: "#202124"; font.pixelSize: 14 * v.z1 }
                Rectangle {
                    width: t.implicitWidth + 8 * v.z1; height: t.implicitHeight + 4 * v.z1; color: "transparent"; radius: 6
                    border.color: index === 0 ? "#2dd4bf" : "transparent"; border.width: 4
                    Text { id: t; anchors.centerIn: parent; text: modelData[1]; color: "#1a0dab"; font.pixelSize: 20 * v.z1 }
                }
                Text { width: 600 * v.z1; text: modelData[2]; color: "#4d5156"; font.pixelSize: 14 * v.z1; wrapMode: Text.WordWrap }
            }
        }
    }
    Column {
        visible: !v.results && v.url.toString() !== ""
        x: 160 * v.z1; y: 40 * v.z1
        width: 700 * v.z1
        spacing: 14 * v.z1
        Text { text: "The Eiffel Tower: facts and figures"; color: "#111"; font.pixelSize: 32 * v.z1; font.bold: true; width: parent.width; wrapMode: Text.WordWrap }
        Repeater {
            model: 6
            Text { width: parent.width; color: "#333"; font.pixelSize: 15 * v.z1; wrapMode: Text.WordWrap
                   text: "The Eiffel Tower is a wrought-iron lattice tower on the Champ de Mars in Paris, France. It is named after the engineer Gustave Eiffel, whose company designed and built the tower from 1887 to 1889." }
        }
    }
}
