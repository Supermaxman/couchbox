// Settings, as YouTube's TV app lays it out: the guide stays open beside it (Settings marked), a
// list of categories under grey capital headers, a divider, and the chosen one's details on the
// right: VacuumTube's options as rows with a switch (SponsorBlock and its kinds of segment,
// DeArrow, Return YouTube Dislike, Hide Shorts, H.264 only), Who's watching, and About (what
// plays the videos, for checking the box's setup).
//   Up / Down: the categories; Right (or OK): into the rows; OK: flip a switch (or the button);
//   Left (or Back): back to the categories; Left again: the guide.
import QtQuick

FocusScope {
    id: page
    objectName: "settings"
    readonly property string label: "Settings"
    property var about: ({})
    property int cur: 0
    property string area: "list"              // list | rows
    property int row: 0
    readonly property var groups: [
        {header: "Account", items: [{key: "accounts", label: "Accounts"}]},
        {header: "Playback", items: [{key: "video", label: "Video"}, {key: "ads", label: "Ads"}]},
        {header: "Extras", items: [{key: "sponsorblock", label: "SponsorBlock"}, {key: "extras", label: "DeArrow and more"}]},
        {header: "About", items: [{key: "about", label: "About"}]},
    ]
    readonly property var items: groups.reduce((a, g) => a.concat(g.items), [])
    readonly property var item: items[cur] || ({})
    function focusDetail() { return {item: item.key || "", area: area, row: (rows[row] || {}).key || "", on: !!(rows[row] || {}).on}; }
    function load() {
        Y.call("about", {}, a => page.about = a, () => {});
        Y.call("settings", {}, st => Y.settings = st, () => {});
    }
    onCurChanged: { area = "list"; row = 0; }

    // the chosen category: a title, a line, facts, and rows (switches: key; a button: press)
    readonly property var detail: {
        const a = page.about, st = Y.settings, sk = st.skip || {};
        if (item.key === "accounts")
            return {title: "Accounts", body: "Each person on this TV can sign in with their own account, or watch as a guest.",
                    facts: [["Watching as", Y.profile ? Y.profile.name : "a guest"]], rows: [{key: "who", label: "Who's watching", button: true}]};
        if (item.key === "video")
            return {title: "Video", body: "Choose the quality while a video plays: the player's settings, then Quality.", facts: [],
                    rows: [{key: "h264", label: "H.264 only", on: !!st.h264,
                            desc: "The Pi decodes H.264 in hardware (up to 1080p60). Off: VP9 and AV1 too, decoded in software (they may stutter)."}]};
        if (item.key === "ads")
            return {title: "Ads", facts: [["Ads", "Never shown: none are asked for, and ad shelves are left out"]], body: "", rows: []};
        if (item.key === "sponsorblock") {
            const kinds = [["sponsor", "Sponsor", "Paid promotion and sponsor reads"], ["selfpromo", "Self-promotion", "Merch, the creator's own products and channels"],
                           ["interaction", "Interaction reminder", "Asking you to like, subscribe or follow"], ["intro", "Intro", "Intervals and opening animations"],
                           ["outro", "Endcards and credits", "The end, after the video's content"], ["preview", "Preview or recap", "What's coming, or what happened before"],
                           ["hook", "Hook", "A teaser at the start"], ["filler", "Filler", "Tangents and jokes not needed for the video"]];
            return {title: "SponsorBlock", body: "Skips the parts of a video its viewers marked (sponsor.ajay.app). The bar shows them in colour; OK undoes a skip.",
                    facts: [], rows: [{key: "sponsorblock", label: "SponsorBlock", on: !!st.sponsorblock, desc: "Look up each video's marked parts"}]
                        .concat(kinds.map(k => ({key: "skip." + k[0], label: "Skip: " + k[1], on: !!sk[k[0]], desc: k[2], off: !st.sponsorblock})))};
        }
        if (item.key === "extras")
            return {title: "DeArrow and more", body: "", facts: [], rows: [
                {key: "dearrow", label: "DeArrow", on: !!st.dearrow, desc: "Titles and pictures its viewers wrote in place of clickbait (dearrow.ajay.app)"},
                {key: "dislikes", label: "Return YouTube Dislike", on: !!st.dislikes, desc: "The dislike count, in a video's Description (returnyoutubedislike.com)"},
                {key: "hide_shorts", label: "Hide Shorts", on: !!st.hide_shorts, desc: "Leave Shorts out of Home, the tabs, search and channels"}]};
        return {title: "About", body: "", rows: [],
                facts: [["yt-dlp", a.ytdlp ? a.ytdlp + (a.ytdlpPath ? "  (" + a.ytdlpPath + ")" : "") : "missing: run  sudo couchbox-yt-dlp"],
                        ["JavaScript", a.js || "none: fewer formats (install nodejs)"], ["TV client", a.client || ""]]};
    }
    readonly property var rows: detail.rows || []
    function press() {
        const r = rows[row];
        if (!r) return;
        if (r.key === "who") Y.whoIsWatching();
        else if (!r.off) Y.setting(r.key, !r.on);
    }
    function enterRows() { if (rows.length) { area = "rows"; row = 0; } }

    Keys.onUpPressed: { if (area === "list") cur = Math.max(0, cur - 1); else row = Math.max(0, row - 1); }
    Keys.onDownPressed: { if (area === "list") cur = Math.min(items.length - 1, cur + 1); else row = Math.min(rows.length - 1, row + 1); }
    Keys.onLeftPressed: { if (area === "rows") area = "list"; else Y.toGuide(); }
    Keys.onRightPressed: if (area === "list") enterRows()
    Keys.onReturnPressed: { if (area === "list") enterRows(); else press(); }
    Keys.onEnterPressed: { if (area === "list") enterRows(); else press(); }
    Keys.onEscapePressed: e => { if (area === "rows") area = "list"; else e.accepted = false; }

    // the page sits right of the open guide (the pages move 378 right with it): the list from x 525
    readonly property real shift: Y.guideOpen - Y.left
    readonly property real listX: 525 * Y.u - shift
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
                        readonly property bool sel: page.item.key === modelData.key
                        readonly property bool on: page.activeFocus && sel && page.area === "list"
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
    Flickable {                               // the details (they scroll with the row in focus)
        id: pane
        x: page.listX + 486 * Y.u; y: 150 * Y.u
        width: page.width - x - 96 * Y.u - page.shift
        height: page.height - y - 60 * Y.u
        clip: true
        interactive: false
        contentHeight: paneCol.height
        contentY: {
            const it = rowsCol.children[page.row];
            if (page.area !== "rows" || !it) return 0;
            const bottom = rowsBox.y + it.y + it.height + 24 * Y.u;
            return Math.max(0, Math.min(contentHeight - height, bottom - height));
        }
        Behavior on contentY { NumberAnimation { duration: 140 } }
        Column {
            id: paneCol
            width: pane.width
            spacing: 26 * Y.u
            Text { text: page.detail.title || ""; color: Y.text; font.family: Y.font; font.pixelSize: 40 * Y.u; font.weight: Font.Bold }
            Text {
                visible: !!page.detail.body
                width: parent.width
                text: page.detail.body || ""
                color: Y.dim; font.family: Y.font; font.pixelSize: 26 * Y.u
                wrapMode: Text.WordWrap
            }
            Repeater {
                model: page.detail.facts || []
                Row {
                    required property var modelData
                    spacing: 30 * Y.u
                    Text { width: 220 * Y.u; text: parent.modelData[0]; color: Y.dim; font.family: Y.font; font.pixelSize: 26 * Y.u }
                    Text { width: paneCol.width - 250 * Y.u; text: parent.modelData[1]; color: Y.text; font.family: Y.font; font.pixelSize: 26 * Y.u; wrapMode: Text.WordWrap }
                }
            }
            Rectangle {                       // the rows, in one rounded group (VacuumTube's look)
                id: rowsBox
                visible: page.rows.length > 0
                width: parent.width
                height: rowsCol.height
                radius: 16 * Y.u
                color: "#212121"
                Column {
                    id: rowsCol
                    width: parent.width
                    Repeater {
                        model: page.rows
                        Rectangle {
                            id: r
                            required property var modelData
                            required property int index
                            readonly property bool focused: page.activeFocus && page.area === "rows" && page.row === index
                            width: rowsCol.width
                            height: Math.max(96 * Y.u, rcol.height + 40 * Y.u)
                            radius: 16 * Y.u
                            color: focused ? "#2e2e2e" : "transparent"
                            border.color: focused ? Y.text : "transparent"
                            border.width: 3 * Y.u
                            opacity: r.modelData.off ? 0.45 : 1
                            Rectangle {               // between rows
                                visible: r.index > 0 && !r.focused
                                width: parent.width; height: 2 * Y.u
                                color: "#2c2c2c"
                            }
                            Column {
                                id: rcol
                                x: 24 * Y.u
                                anchors.verticalCenter: parent.verticalCenter
                                width: parent.width - 170 * Y.u
                                spacing: 6 * Y.u
                                Text { text: r.modelData.label; color: Y.text; font.family: Y.font; font.pixelSize: 26 * Y.u; font.weight: Font.Medium }
                                Text {
                                    visible: !!r.modelData.desc
                                    width: parent.width
                                    text: r.modelData.desc || ""
                                    color: Y.dim; font.family: Y.font; font.pixelSize: 21 * Y.u
                                    wrapMode: Text.WordWrap
                                }
                            }
                            Rectangle {               // a switch: white and its knob right when on
                                visible: !r.modelData.button
                                anchors { right: parent.right; rightMargin: 24 * Y.u; verticalCenter: parent.verticalCenter }
                                width: 76 * Y.u; height: 42 * Y.u; radius: height / 2
                                color: r.modelData.on ? Y.text : "#5a5a5a"
                                Rectangle {
                                    width: 32 * Y.u; height: width; radius: width / 2
                                    anchors.verticalCenter: parent.verticalCenter
                                    x: r.modelData.on ? parent.width - width - 5 * Y.u : 5 * Y.u
                                    color: r.modelData.on ? "#1f1f1f" : Y.text
                                }
                            }
                            Icon {
                                visible: !!r.modelData.button
                                anchors { right: parent.right; rightMargin: 24 * Y.u; verticalCenter: parent.verticalCenter }
                                name: "chevron"; size: 34 * Y.u; color: Y.text
                            }
                        }
                    }
                }
            }
        }
    }
}
