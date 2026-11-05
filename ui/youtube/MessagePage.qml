// A page with something to say rather than videos: Subscriptions and Library before signing in,
// Shorts, and Settings (for now: what plays the videos, for checking the box's setup).
import QtQuick

FocusScope {
    id: page
    property string key: ""
    property string title: ""
    property string body: ""
    property string action: ""                // a button under the text (OK: a toast for now)
    property var facts: []                    // [[label, value]] (Settings)
    readonly property string label: title

    function load() {
        if (key !== "settings") return;
        Y.call("about", {}, a => {
            page.facts = [
                ["Video", "H.264 up to 1080p60, AAC sound (VacuumTube's “h264ify”)"],
                ["Ads", "Never shown: none are asked for, and ad shelves are left out"],
                ["yt-dlp", a.ytdlp ? a.ytdlp + (a.ytdlpPath ? "  (" + a.ytdlpPath + ")" : "") : "missing: run  sudo couchbox-yt-dlp"],
                ["JavaScript", a.js || "none: fewer formats (install nodejs)"],
                ["TV client", a.client || ""],
            ];
        }, () => {});
    }
    Keys.onLeftPressed: Y.toGuide()
    Keys.onReturnPressed: if (action) { if (key === "shorts") Y.open({type: "shorts", id: "-"}); else Y.signIn(); }
    Keys.onEnterPressed: if (action) { if (key === "shorts") Y.open({type: "shorts", id: "-"}); else Y.signIn(); }

    Text {                                     // the page's name, level with the guide's picture
        x: 172 * Y.u; y: 68 * Y.u
        height: 72 * Y.u
        verticalAlignment: Text.AlignVCenter
        text: page.title
        color: Y.text; font.family: Y.font; font.pixelSize: 44 * Y.u; font.weight: Font.Bold
    }
    Column {
        x: 172 * Y.u; y: 190 * Y.u
        width: Math.min(parent.width - 2 * Y.left, 1200 * Y.u)
        spacing: 28 * Y.u
        Text {
            visible: !!page.body
            width: parent.width
            text: page.body
            color: Y.dim
            font.family: Y.font; font.pixelSize: 30 * Y.u
            wrapMode: Text.WordWrap
            lineHeight: 1.2
        }
        Rectangle {
            visible: !!page.action
            width: actionT.implicitWidth + 72 * Y.u; height: 72 * Y.u; radius: height / 2
            color: page.activeFocus ? Y.text : Y.glass
            Text { id: actionT; anchors.centerIn: parent; text: page.action; color: page.activeFocus ? Y.ink : Y.text; font.family: Y.font; font.pixelSize: 26 * Y.u; font.weight: Font.Medium }
        }
        Column {
            visible: page.facts.length > 0
            spacing: 22 * Y.u
            Repeater {
                model: page.facts
                Row {
                    required property var modelData
                    spacing: 30 * Y.u
                    Text { width: 260 * Y.u; text: parent.modelData[0]; color: Y.dim; font.family: Y.font; font.pixelSize: 28 * Y.u }
                    Text { text: parent.modelData[1]; color: Y.text; font.family: Y.font; font.pixelSize: 28 * Y.u }
                }
            }
        }
    }
}
