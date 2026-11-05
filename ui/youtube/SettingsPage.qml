// Settings, as YouTube's TV app lays it out: the guide stays open beside it (Settings marked), a
// list of categories under grey capital headers, a divider, and the chosen one's details on the
// right. About keeps what plays the videos (for checking the box's setup).
//   Up / Down: the categories; OK (or Right) on one with a button: the button; Left: the guide.
import QtQuick

FocusScope {
    id: page
    objectName: "settings"
    readonly property string label: "Settings"
    property var about: ({})
    property int cur: 0
    readonly property var groups: [
        {header: "Account", items: [{key: "accounts", label: "Accounts"}]},
        {header: "Playback", items: [{key: "video", label: "Video quality"}, {key: "ads", label: "Ads"}]},
        {header: "About", items: [{key: "about", label: "About"}]},
    ]
    readonly property var items: groups.reduce((a, g) => a.concat(g.items), [])
    readonly property var item: items[cur] || ({})
    function focusDetail() { return {item: item.key || ""}; }
    function load() {
        Y.call("about", {}, a => page.about = a, () => {});
    }
    // what each category says, and its button (if any)
    readonly property var detail: {
        const a = page.about;
        if (item.key === "accounts")
            return {title: "Accounts", facts: [["Watching as", Y.profile ? Y.profile.name : "a guest"]],
                    body: "Each person on this TV can sign in with their own account, or watch as a guest.",
                    button: "Who's watching"};
        if (item.key === "video")
            return {title: "Video quality", facts: [["Video", "H.264 up to 1080p60, AAC sound"], ["Choose", "In the player: settings, then Quality"]],
                    body: "The Pi decodes H.264 in hardware, so videos play as H.264 (VacuumTube's “h264ify”)."};
        if (item.key === "ads")
            return {title: "Ads", facts: [["Ads", "Never shown: none are asked for, and ad shelves are left out"]], body: ""};
        return {title: "About", body: "",
                facts: [["yt-dlp", a.ytdlp ? a.ytdlp + (a.ytdlpPath ? "  (" + a.ytdlpPath + ")" : "") : "missing: run  sudo couchbox-yt-dlp"],
                        ["JavaScript", a.js || "none: fewer formats (install nodejs)"], ["TV client", a.client || ""]]};
    }
    function press() { if (item.key === "accounts") Y.whoIsWatching(); }

    Keys.onUpPressed: cur = Math.max(0, cur - 1)
    Keys.onDownPressed: cur = Math.min(items.length - 1, cur + 1)
    Keys.onLeftPressed: Y.toGuide()
    Keys.onRightPressed: press()
    Keys.onReturnPressed: press()
    Keys.onEnterPressed: press()

    // the page sits right of the open guide (the pages move 378 right with it): the list from x 525
    readonly property real listX: 525 * Y.u - (Y.guideOpen - Y.left)
    Column {
        x: page.listX; y: 150 * Y.u
        width: 420 * Y.u
        Repeater {
            model: page.groups
            Column {
                id: grp
                required property var modelData
                required property int index
                width: parent.width
                Text {
                    width: parent.width
                    topPadding: (grp.index ? 30 : 0) * Y.u
                    bottomPadding: 12 * Y.u
                    leftPadding: 24 * Y.u
                    text: grp.modelData.header.toUpperCase()
                    color: Y.dim; font.family: Y.font; font.pixelSize: 22 * Y.u; font.weight: Font.Medium
                }
                Repeater {
                    model: grp.modelData.items
                    Rectangle {
                        required property var modelData
                        readonly property bool on: page.activeFocus && page.item.key === modelData.key
                        readonly property bool sel: page.item.key === modelData.key
                        width: grp.width; height: 72 * Y.u
                        radius: 14 * Y.u
                        color: on ? Y.text : sel ? Y.raised : "transparent"
                        Text {
                            x: 24 * Y.u; anchors.verticalCenter: parent.verticalCenter
                            text: parent.modelData.label
                            color: parent.on ? Y.ink : Y.text
                            font.family: Y.font; font.pixelSize: 30 * Y.u; font.weight: Font.Medium
                        }
                    }
                }
            }
        }
    }
    Rectangle {                               // the divider
        x: page.listX + 442 * Y.u; y: 150 * Y.u
        width: 2 * Y.u; height: parent.height - 250 * Y.u
        color: Y.raised2
    }
    Column {                                  // the details
        x: page.listX + 486 * Y.u; y: 150 * Y.u
        width: page.width - x - 96 * Y.u - (Y.guideOpen - Y.left)   // (the page is pushed right)
        spacing: 26 * Y.u
        Text { text: page.detail.title || ""; color: Y.text; font.family: Y.font; font.pixelSize: 40 * Y.u; font.weight: Font.Bold }
        Text {
            visible: !!page.detail.body
            width: parent.width
            text: page.detail.body || ""
            color: Y.dim; font.family: Y.font; font.pixelSize: 28 * Y.u
            wrapMode: Text.WordWrap
        }
        Repeater {
            model: page.detail.facts || []
            Row {
                required property var modelData
                spacing: 30 * Y.u
                Text { width: 220 * Y.u; text: parent.modelData[0]; color: Y.dim; font.family: Y.font; font.pixelSize: 26 * Y.u }
                Text { width: page.width - page.listX - 1100 * Y.u - (Y.guideOpen - Y.left); text: parent.modelData[1]; color: Y.text; font.family: Y.font; font.pixelSize: 26 * Y.u; wrapMode: Text.WordWrap }
            }
        }
        Rectangle {
            visible: !!page.detail.button
            width: bt.implicitWidth + 64 * Y.u; height: 64 * Y.u; radius: height / 2
            color: Y.glass
            Text { id: bt; anchors.centerIn: parent; text: page.detail.button || ""; color: Y.text; font.family: Y.font; font.pixelSize: 26 * Y.u; font.weight: Font.Medium }
        }
    }
}
