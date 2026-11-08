// Settings, as YouTube's TV app lays it out: the guide open beside it while it has the focus (it
// folds to its rail when the focus comes into the list, as on every page), a list of categories under grey capital headers, a divider, and the chosen one's details on the
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
        {header: "Account", items: [{key: "accounts", label: "Accounts"}, {key: "premium", label: "Your Premium benefits"}, {key: "purchases", label: "Purchases and memberships"}]},
        {header: "Family", items: [{key: "restricted", label: "Restricted mode"}, {key: "parent", label: "Parent code"}]},
        {header: "Playback", items: [{key: "video", label: "Video"}, {key: "player", label: "Player"}, {key: "captions", label: "Captions"}, {key: "ads", label: "Ads"}]},
        {header: "Appearance", items: [{key: "guide", label: "Guide tabs"}]},
        {header: "Link TV & phone", items: [{key: "wifi", label: "Link with Wi-Fi"}, {key: "tvcode", label: "Link with TV code"}]},
        {header: "Extras", items: [{key: "sponsorblock", label: "SponsorBlock"}, {key: "extras", label: "DeArrow and more"}]},
        {header: "About", items: [{key: "about", label: "About"}]},
    ]
    readonly property var items: groups.reduce((a, g) => a.concat(g.items), [])
    readonly property var item: items[cur] || ({})
    function focusDetail() { return {item: item.key || "", area: area, row: (rows[row] || {}).key || "", on: !!(rows[row] || {}).on, code: codeFor, locked: !!Y.settings.parent_lock}; }
    function load() {
        Y.call("about", {}, a => page.about = a, () => {});
        Y.call("settings", {}, st => Y.settings = st, () => {});
    }
    onCurChanged: { area = "list"; row = 0; if (item.key === "tvcode" && !tvCode) newCode(); }
    // "Link with TV code": 12 digits from couchbox-yt-cast for the phone app's Settings → Watch on TV
    property string tvCode: ""
    property string codeProblem: ""
    function newCode() {
        codeProblem = "";
        Y.call("castCode", {}, r => { page.tvCode = r.code || ""; }, e => { page.tvCode = ""; page.codeProblem = e; });
    }

    // the chosen category: a title, a line, facts, and rows (switches: key; a button: press)
    readonly property var detail: {
        const a = page.about, st = Y.settings, sk = st.skip || {};
        if (item.key === "accounts")
            return {title: "Accounts", body: "Each person on this TV can sign in with their own account, or watch as a guest.",
                    facts: [["Watching as", Y.profile ? Y.profile.name : "a guest"]], rows: [{key: "who", label: "Who's watching", button: true}]};
        if (item.key === "video")
            return {title: "Video", body: "Choose the quality while a video plays: the player's settings, then Quality.", facts: [],
                    rows: [{key: "h264", label: "H.264 only", on: !!st.h264, group: "Formats",
                            desc: "The kind of video this TV plays most smoothly, up to 1080p. Turn it off for other kinds, which may stutter."},
                           {key: "unlock_resolution", label: "Unlock resolution", on: !!st.unlock_resolution, group: "Quality",
                            desc: "Sharper than 1080p, up to 4K, when H.264 only is off"},
                           {key: "remove_superres", label: "Remove Super Resolution", on: !!st.remove_superres, group: "Quality",
                            desc: "Skip the versions YouTube sharpened with AI"},
                           {key: "match_rate", label: "Match the TV to the video's frame rate", group: "The TV", value: st.match_rate || "off",
                            choices: [["film", "Film only"], ["always", "Always"], ["off", "Off"]],
                            desc: "Film only: for 24 and 25 fps films over 5 minutes (smoother; the screen goes black a moment when it changes). Always: for every video."}]};
        if (item.key === "player")
            return {title: "Player", body: "Keys on a keyboard: P and D faster and slower, A normal speed, C captions, M sound.", facts: [], rows: [
                {key: "remaining_time", label: "Show remaining time", on: !!st.remaining_time, desc: "The time left in place of the video's length", group: "On screen"},
                {key: "autoplay", label: "Autoplay next video", on: st.autoplay !== false, desc: "When a video ends, the next one plays after a few seconds", group: "Playback"},
                {key: "previews", label: "Previews", on: false, off: true, desc: "Playing a card's video, muted, while it has the focus: not on this TV yet", group: "Playback"},
                {key: "pause_on_blur", label: "Pause on blur", on: !!st.pause_on_blur, desc: "Pause when another window comes in front", group: "Playback"},
                {key: "block_continue", label: "Block \"Continue watching?\"", on: !!st.block_continue, group: "Playback",
                 desc: "Autoplay doesn't stop to ask after 2 hours without a key"}]};
        if (item.key === "premium")
            return {title: "Your Premium benefits", body: "Premium's benefits and your membership are shown on a phone or computer.", rows: [],
                    facts: [["Watching as", Y.profile ? Y.profile.name + (Y.profile.premium ? " (YouTube Premium)" : "") : "a guest"],
                            ["Open", "youtube.com/premium"]]};
        if (item.key === "purchases")
            return {title: "Purchases and memberships", body: "Films and shows you bought or rented, and channel memberships, are listed on a phone or computer.", rows: [],
                    facts: [["Open", "youtube.com/paid_memberships"]]};
        if (item.key === "restricted")
            return {title: "Restricted mode", facts: [],
                    body: "Hides videos that may be mature, for every profile on this TV." + (st.parent_lock ? " The parent code turns it off." : " A parent code (Family) keeps it on."),
                    rows: [{key: "restricted", label: "Restricted mode", on: !!st.restricted, group: "This TV", locked: !!st.parent_lock,
                            desc: "YouTube leaves out what may be mature in search, Home and videos. Not every video is caught."}]};
        if (item.key === "parent")
            return {title: "Parent code", facts: [],
                    body: st.parent_lock ? "Restricted mode can be turned off, and this code changed, only with it." : "Four digits that keep Restricted mode as it is.",
                    rows: [{key: "parent_code", label: st.parent_lock ? "Remove the parent code" : "Set a parent code", button: true}]};
        if (item.key === "captions")
            return {title: "Captions", body: "CC on the player turns them on or off for the video playing.", facts: [], rows: [
                {key: "captions_always", label: "Always show captions", on: st.captions_always !== false, group: "Every video",
                 desc: "In English when there are any (the video's own, then automatic, then translated), else in the video's language. Turned off with CC, they stay off for that video."}]};
        if (item.key === "wifi")
            return {title: "Link with Wi-Fi", facts: [], rows: [{key: "cast", label: "Cast from phones", on: st.cast !== false,
                    desc: "Phones on this Wi-Fi see the TV in the YouTube app's cast list, as “Couchbox YouTube (beta)”"}],
                    body: "On a phone on the same Wi-Fi, open the YouTube app, tap the cast button and pick this TV. What it plays shows here."};
        if (item.key === "tvcode")
            return {title: "Link with TV code", code: page.tvCode, facts: [],
                    body: page.codeProblem || (page.tvCode ? "In the YouTube app on your phone: Settings, Watch on TV, Enter TV code." : "Getting a code…"),
                    rows: [{key: "newcode", label: "Get a new code", button: true}]};
        if (item.key === "guide") {
            const tabs = [["music", "Music"], ["gaming", "Gaming"], ["news", "News"], ["podcasts", "Podcasts"], ["movies", "Movies & TV"], ["live", "Live"], ["sports", "Sports"]];
            const gt = st.guide_tabs || {};
            return {title: "Guide tabs", body: "The tabs the guide lists (Search, Home, Shorts, Subscriptions and Library always are).", facts: [],
                    rows: tabs.map(t => ({key: "tab." + t[0], label: t[1], on: gt[t[0]] !== false}))};
        }
        if (item.key === "ads")
            return {title: "Ads", facts: [["Ads", "Never shown: none are asked for, and ad shelves are left out"]], body: "", rows: []};
        if (item.key === "sponsorblock") {
            const kinds = [["sponsor", "Sponsor", "Paid promotion and sponsor reads"], ["selfpromo", "Self-promotion", "Merch, the creator's own products and channels"],
                           ["interaction", "Interaction reminder", "Asking you to like, subscribe or follow"], ["intro", "Intro", "Intervals and opening animations"],
                           ["outro", "Endcards and credits", "The end, after the video's content"], ["preview", "Preview or recap", "What's coming, or what happened before"],
                           ["hook", "Hook", "A teaser at the start"], ["filler", "Filler", "Tangents and jokes not needed for the video"]];
            return {title: "SponsorBlock", body: "Skips sponsor reads and other parts of videos that viewers have marked. The progress bar shows them in colour.",
                    facts: [], rows: [{key: "sponsorblock", label: "Skip marked parts", on: !!st.sponsorblock, desc: "On for every video; choose which kinds below", group: "Every video"}]
                        .concat(kinds.map(k => ({key: "skip." + k[0], label: "Skip: " + k[1], on: !!sk[k[0]], desc: k[2], off: !st.sponsorblock, group: "Parts to skip"})))};
        }
        if (item.key === "extras")
            return {title: "DeArrow and more", body: "Extras from the community, and what the pages leave out.", facts: [], rows: [
                {key: "dearrow", label: "DeArrow", on: !!st.dearrow, desc: "Clearer titles and pictures, written by viewers, in place of clickbait", group: "From other viewers"},
                {key: "dislikes", label: "Return YouTube Dislike", on: !!st.dislikes, desc: "How many people disliked a video, shown in its Description", group: "From other viewers"},
                {key: "hide_shorts", label: "Hide Shorts", on: !!st.hide_shorts, desc: "Leave Shorts out of Home, the tabs, search and channels", group: "On the pages"}]};
        return {title: "About", body: "", rows: [],
                facts: [["yt-dlp", a.ytdlp ? a.ytdlp + (a.ytdlpPath ? "  (" + a.ytdlpPath + ")" : "") : "missing: run  sudo couchbox-yt-dlp"],
                        ["JavaScript", a.js || "none: fewer formats (install nodejs)"], ["TV client", a.client || ""]]};
    }
    readonly property var rows: detail.rows || []
    function press() {
        const r = rows[row];
        if (!r) return;
        if (r.key === "who") Y.whoIsWatching();
        else if (r.key === "parent_code") askCode(Y.settings.parent_lock ? "remove" : "set");
        else if (r.key === "restricted" && r.locked) askCode("restricted");
        else if (r.key === "newcode") newCode();
        else if (r.choices) {                 // a choice: OK steps to the next
            const keys = r.choices.map(c => c[0]), i = keys.indexOf(r.value);
            Y.setting(r.key, keys[(i + 1) % keys.length]);
        } else if (!r.off) Y.setting(r.key, !r.on);
    }
    // the parent code: four digits on the remote (Up / Down a digit, Left / Right, or the number keys)
    property string codeFor: ""               // "" | set | remove | restricted
    property var digits: [0, 0, 0, 0]
    property int digit: 0
    function askCode(what) { codeFor = what; digits = [0, 0, 0, 0]; digit = 0; pad.forceActiveFocus(); }
    function codeKey(k) {
        const d = digits.slice();
        if (k >= Qt.Key_0 && k <= Qt.Key_9) { d[digit] = k - Qt.Key_0; digits = d; if (digit < 3) digit++; else codeDone(); return true; }
        if (k === Qt.Key_Up) { d[digit] = (d[digit] + 1) % 10; digits = d; return true; }
        if (k === Qt.Key_Down) { d[digit] = (d[digit] + 9) % 10; digits = d; return true; }
        if (k === Qt.Key_Left) { digit = Math.max(0, digit - 1); return true; }
        if (k === Qt.Key_Right) { if (digit < 3) digit++; return true; }
        if (k === Qt.Key_Return || k === Qt.Key_Enter) { codeDone(); return true; }
        if (k === Qt.Key_Escape || k === Qt.Key_Back) { codeFor = ""; pad.focus = false; page.forceActiveFocus(); return true; }
        return true;
    }
    function codeDone() {
        const code = digits.join(""), what = codeFor;
        codeFor = "";
        pad.focus = false;
        page.forceActiveFocus();
        if (what === "set") Y.setting("parent_code", code, "", ok => { if (ok) Y.toast("Parent code set: " + code + ". Keep it somewhere safe."); });
        else if (what === "remove") Y.setting("parent_code", "", code, ok => { if (ok) Y.toast("Parent code removed"); });
        else if (what === "restricted") Y.setting("restricted", !Y.settings.restricted, code);
    }
    function enterRows() { if (rows.length) { area = "rows"; row = 0; } }

    Keys.onUpPressed: { if (area === "list") cur = Math.max(0, cur - 1); else row = Math.max(0, row - 1); }
    Keys.onDownPressed: { if (area === "list") cur = Math.min(items.length - 1, cur + 1); else row = Math.min(rows.length - 1, row + 1); }
    Keys.onLeftPressed: { if (area === "rows") area = "list"; else Y.toGuide(); }
    Keys.onRightPressed: if (area === "list") enterRows()
    Keys.onReturnPressed: { if (area === "list") enterRows(); else press(); }
    Keys.onEnterPressed: { if (area === "list") enterRows(); else press(); }
    Keys.onEscapePressed: e => { if (area === "rows") area = "list"; else e.accepted = false; }

    // laid out with the guide folded (the list's names at x 165); the open guide pushes it all 378
    // right, as on every page (the list's names at 543, the pane's title centred at 1638)
    readonly property real listX: 147 * Y.u
    Text {                                    // the page's name, as YouTube's
        x: 172 * Y.u; y: 80 * Y.u
        height: 48 * Y.u; verticalAlignment: Text.AlignVCenter
        text: "Settings"
        color: Y.text; font.family: Y.titleFont; font.pixelSize: 46 * Y.titleScale * Y.u; font.weight: Font.Bold
    }
    Flickable {                               // the categories, scrolled so the chosen one is always whole
        id: cats
        x: page.listX; y: 192 * Y.u
        width: 420 * Y.u
        height: page.height - y
        clip: true
        interactive: false
        contentHeight: catCol.height + 40 * Y.u
        property real selY: 0                 // the chosen row's place in the list
        onSelYChanged: follow()
        onHeightChanged: follow()
        function follow() {                   // its group's header in view above it, room below it,
            const top = catCol.y + selY - 46 * Y.u, bottom = catCol.y + selY + 78 * Y.u + 40 * Y.u;
            let want = Math.max(0, Math.min(contentHeight - height, Math.max(Math.min(contentY, top), bottom - height)));
            // ...and the list's top on a row's (or a header's) top: no row cut in half up there
            const tops = [0];
            for (const g of catCol.children)
                for (const it of g.children || []) if (it.height > 0 && it.visible) tops.push(catCol.y + it.mapToItem(catCol, 0, 0).y);
            const fit = tops.filter(t => t >= want - 0.5 && t <= top + 0.5).sort((a, b) => a - b);
            if (fit.length) want = fit[0];
            contentY = Math.max(0, Math.min(Math.max(0, contentHeight - height), want));
        }
        Behavior on contentY { NumberAnimation { duration: 140 } }
    Column {
        id: catCol
        y: 20 * Y.u
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
                    topPadding: (grp.index ? 22 : 0) * Y.u
                    bottomPadding: 8 * Y.u
                    leftPadding: 18 * Y.u
                    text: grp.modelData.header.toUpperCase()
                    color: Y.dim; font.family: Y.font; font.pixelSize: 22 * Y.u; font.weight: Font.Bold
                }
                Repeater {
                    model: grp.modelData.items
                    Rectangle {
                        required property var modelData
                        readonly property bool sel: page.item.key === modelData.key
                        readonly property bool on: page.activeFocus && sel && page.area === "list"
                        onSelChanged: if (sel) cats.selY = mapToItem(catCol, 0, 0).y
                        Component.onCompleted: if (sel) cats.selY = mapToItem(catCol, 0, 0).y
                        width: grp.width; height: 78 * Y.u
                        radius: 16 * Y.u
                        color: on ? Y.text : sel ? Y.raised : "transparent"
                        Text {
                            x: 18 * Y.u; anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - 36 * Y.u
                            elide: Text.ElideRight
                            text: parent.modelData.label
                            color: parent.on ? Y.ink : Y.text
                            font.family: Y.font; font.pixelSize: 30 * Y.u; font.weight: Font.Medium
                        }
                    }
                }
            }
        }
    }
    }
    Rectangle {                               // the divider
        x: page.listX + 442 * Y.u; y: 192 * Y.u
        width: 2 * Y.u; height: parent.height - y
        color: Y.raised2
    }
    FocusScope {                              // the parent code's four digits (they have the keys while up)
        id: pad
        visible: !!page.codeFor
        anchors.fill: parent
        z: 20
        Keys.onPressed: e => { if (!page.codeFor) { e.accepted = false; return; } page.codeKey(e.key); e.accepted = true; }
    Rectangle {
        visible: !!page.codeFor
        anchors.fill: parent
        color: Y.bg
        Column {
            anchors.centerIn: parent
            spacing: 30 * Y.u
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: page.codeFor === "set" ? "Choose a parent code" : "Enter the parent code"
                color: Y.text; font.family: Y.font; font.pixelSize: 44 * Y.u; font.weight: Font.Bold
            }
            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 24 * Y.u
                Repeater {
                    model: 4
                    Rectangle {
                        required property int index
                        width: 110 * Y.u; height: 140 * Y.u; radius: 18 * Y.u
                        color: page.digit === index ? Y.text : Y.raised
                        Text { anchors.centerIn: parent; text: page.digits[parent.index]; color: page.digit === parent.index ? Y.ink : Y.text
                               font.family: Y.font; font.pixelSize: 64 * Y.u; font.weight: Font.Bold }
                    }
                }
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Up and Down change a digit, Left and Right move (or the number keys). OK when done, Back to cancel."
                color: Y.dim; font.family: Y.font; font.pixelSize: 26 * Y.u
            }
        }
    }
    }
    // the details, centred: a large heading, the line under it, facts, a button, or the rows of
    // switches in VacuumTube's look (cards on a darker panel, a count of them, capital sub-headers)
    Flickable {
        id: pane
        x: page.listX + 470 * Y.u; y: 192 * Y.u
        width: page.width - x - 42 * Y.u
        height: page.height - y - 30 * Y.u
        clip: true
        interactive: false
        contentHeight: paneCol.height + 40 * Y.u
        contentY: {
            const it = rowsCol.children[page.row];
            if (page.area !== "rows" || !it || !page.detail.rows.length || page.detail.rows[0].button) return 0;
            const bottom = rowsBox.y + rowsHead.height + 4 * Y.u + rowsCol.y + it.y + it.height + 30 * Y.u;
            return Math.max(0, Math.min(contentHeight - height, bottom - height));
        }
        Behavior on contentY { NumberAnimation { duration: 140 } }
        Column {
            id: paneCol
            width: pane.width
            spacing: 22 * Y.u
            Item { width: 1; height: 4 * Y.u }
            Text {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                text: page.detail.title || ""
                color: Y.text; font.family: Y.titleFont; font.pixelSize: 56 * Y.titleScale * Y.u; font.weight: Font.Bold
            }
            Text {
                visible: !!page.detail.body
                anchors.horizontalCenter: parent.horizontalCenter
                width: Math.min(parent.width, 820 * Y.u)
                horizontalAlignment: Text.AlignHCenter
                text: page.detail.body || ""
                color: Y.dim; font.family: Y.font; font.pixelSize: 28 * Y.u
                wrapMode: Text.WordWrap
                lineHeightMode: Text.FixedHeight; lineHeight: 42 * Y.u
            }
            Text {                            // the TV code, large
                visible: !!page.detail.code
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                text: page.detail.code || ""
                color: Y.text; font.family: Y.font; font.pixelSize: 72 * Y.u; font.weight: Font.Bold
                font.letterSpacing: 4 * Y.u
            }
            Repeater {
                model: page.detail.facts || []
                Text {
                    required property var modelData
                    width: paneCol.width
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    textFormat: Text.StyledText
                    text: "<font color='#aaaaaa'>" + Y.html(modelData[0]) + "</font>&nbsp;&nbsp;&nbsp;" + Y.html(modelData[1])
                    color: Y.text; font.family: Y.font; font.pixelSize: 26 * Y.u
                }
            }
            Repeater {                        // a button (Who's watching): a pill, centred
                model: (page.detail.rows || []).filter(r => r.button)
                Rectangle {
                    required property var modelData
                    readonly property bool on: page.activeFocus && page.area === "rows"
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: bt.implicitWidth + 120 * Y.u; height: 96 * Y.u; radius: height / 2
                    color: on ? Y.text : Y.raised
                    Text { id: bt; anchors.centerIn: parent; text: parent.modelData.label; color: parent.on ? Y.ink : Y.text; font.family: Y.font; font.pixelSize: 30 * Y.u; font.weight: Font.Medium }
                }
            }
            Item {                            // the switches
                id: rowsBox
                visible: page.rows.length > 0 && !page.rows[0].button
                width: parent.width
                height: visible ? rowsHead.height + rowsCol.height + 36 * Y.u : 0
                Row {
                    id: rowsHead
                    width: parent.width
                    height: 40 * Y.u
                    Text {                    // (no second heading: the title above says it)
                        width: parent.width
                        horizontalAlignment: Text.AlignRight
                        text: page.rows.length + (page.rows.length === 1 ? " option" : " options")
                        color: Y.dim; font.family: Y.font; font.pixelSize: 22 * Y.u
                    }
                }
                Rectangle {
                    y: rowsHead.height + 4 * Y.u
                    width: parent.width
                    height: rowsCol.height + 24 * Y.u
                    radius: 18 * Y.u
                    color: "#212121"
                    Column {
                        id: rowsCol
                        x: 12 * Y.u; y: 12 * Y.u
                        width: parent.width - 24 * Y.u
                        spacing: 8 * Y.u
                        Repeater {
                            model: page.rows
                            Column {                   // a row, under its group's label when a group starts here
                                id: rw
                                required property var modelData
                                required property int index
                                width: rowsCol.width
                                readonly property bool heads: !!modelData.group && (index === 0 || (page.rows[index - 1] || {}).group !== modelData.group)
                                Text {
                                    visible: rw.heads
                                    leftPadding: 12 * Y.u
                                    topPadding: (rw.index ? 18 : 6) * Y.u
                                    bottomPadding: 10 * Y.u
                                    text: (rw.modelData.group || "").toUpperCase()
                                    color: Y.dim; font.family: Y.font; font.pixelSize: 20 * Y.u; font.weight: Font.Bold
                                    font.letterSpacing: 1.5 * Y.u
                                }
                            Rectangle {
                                id: r
                                readonly property var modelData: rw.modelData
                                readonly property int index: rw.index
                                readonly property bool focused: page.activeFocus && page.area === "rows" && page.row === index
                                width: rowsCol.width
                                height: Math.max(92 * Y.u, rcol.height + 36 * Y.u)
                                radius: 14 * Y.u
                                color: focused ? "#3a3a3a" : "#2b2b2b"
                                border.color: focused ? Y.text : "transparent"
                                border.width: 3 * Y.u
                                opacity: r.modelData.off ? 0.45 : 1
                                Column {
                                    id: rcol
                                    x: 24 * Y.u
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: parent.width - 190 * Y.u
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
                                Text {                // a choice: its value (OK: the next)
                                    visible: !!r.modelData.choices
                                    anchors { right: parent.right; rightMargin: 42 * Y.u; verticalCenter: parent.verticalCenter }
                                    text: r.modelData.choices ? ((r.modelData.choices.find(c => c[0] === r.modelData.value) || [0, ""])[1]) : ""
                                    color: Y.text; font.family: Y.font; font.pixelSize: 26 * Y.u; font.weight: Font.Medium
                                }
                                Rectangle {           // a switch: white, its knob right, when on
                                    visible: !r.modelData.choices
                                    anchors { right: parent.right; rightMargin: 42 * Y.u; verticalCenter: parent.verticalCenter }
                                    width: 76 * Y.u; height: 42 * Y.u; radius: height / 2
                                    color: r.modelData.on ? Y.text : "#5a5a5a"
                                    Rectangle {
                                        width: 32 * Y.u; height: width; radius: width / 2
                                        anchors.verticalCenter: parent.verticalCenter
                                        x: r.modelData.on ? parent.width - width - 5 * Y.u : 5 * Y.u
                                        color: r.modelData.on ? "#1f1f1f" : Y.text
                                    }
                                }
                            }
                            }
                        }
                    }
                }
            }
        }
    }
}
