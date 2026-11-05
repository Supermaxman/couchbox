// Search, as YouTube's TV app has it: the pill with what's typed, YouTube's suggestions (or your
// recent searches) on the left, the letter keys in the middle, and "Type on your phone" at the top
// right. Text from the phone and from the mic (couchbox-voice) arrives as key presses. Then the
// results: the results shelf, chips of related searches, and the channel's and other shelves.
//   Back: from the results to the keys; from the keys out of Search (Main).
import QtQuick

FocusScope {
    id: page
    property string query: ""
    property bool results: false              // the results are showing (else the keys)
    property string searched: ""
    property var suggestions: []
    property bool recent: true                // the suggestions are recent searches
    property string problem: ""
    property bool loading: false

    // ------------------------------------------------------------------ keys
    property bool symbols: false
    readonly property var letters: symbols
        ? [["1", "2", "3", "4", "5", "6", "7", "del"], ["8", "9", "0", ".", ",", "?", "!", "sym"], ["@", "#", "&", "(", ")", ":", "/", "globe"], ["+", "=", "_", "\"", "$", "%", "*"]]
        : [["A", "B", "C", "D", "E", "F", "G", "del"], ["H", "I", "J", "K", "L", "M", "N", "sym"], ["O", "P", "Q", "R", "S", "T", "U", "globe"], ["V", "W", "X", "Y", "Z", "-", "'"]]
    readonly property var buttons: ["SPACE", "CLEAR", "SEARCH"]
    property string area: "keys"              // keys | list
    property int r: 0
    property int c: 0
    property int li: 0
    property bool allSelected: false          // Ctrl+A from the phone: the next Backspace clears

    function begin(q) {                       // the keys, with this text
        results = false;
        query = q || "";
        area = "keys"; r = 0; c = 0; li = 0;
        problem = "";
        refreshSuggestions();
        keys.forceActiveFocus();
    }
    function search(q) {
        q = (q || "").trim();
        if (!q) return;
        query = q; searched = q; results = true; loading = true; problem = "";
        feed.rows = [];
        Y.call("search", {q: q}, r => {
            loading = false;
            if (searched !== q) return;
            const extra = [];
            Y.call("suggest", {q: q}, s => {
                const chips = (s.items || []).filter(x => x.toLowerCase() !== q.toLowerCase()).slice(0, 8);
                if (chips.length && searched === q && feed.rows.length)
                    feed.rows = feed.rows.slice(0, 1).concat([{kind: "chips", chips: chips}], feed.rows.slice(1));
            }, () => {});
            feed.setPage(r, extra);
            if (!feed.count) problem = "No results for “" + q + "”.";
            if (page.activeFocus || page.results) feed.forceActiveFocus();
        }, e => { loading = false; problem = e; });
        feed.forceActiveFocus();
    }
    function press(k) {
        if (k === "del") backspace();
        else if (k === "sym") symbols = !symbols;
        else if (k === "globe") Y.toast("English keys only for now: type on your phone for other languages.");
        else if (k === "SPACE") type(" ");
        else if (k === "CLEAR") { query = ""; allSelected = false; }
        else if (k === "SEARCH") search(query);
        else type(k.toLowerCase());
    }
    function type(s) { if (allSelected) { query = ""; allSelected = false; } query += s; }
    function backspace() { query = allSelected ? "" : query.slice(0, -1); allSelected = false; }
    onQueryChanged: if (!results) suggestTimer.restart()
    Timer { id: suggestTimer; interval: 180; onTriggered: page.refreshSuggestions() }
    function refreshSuggestions() {
        const q = query;
        if (!q.trim()) {
            Y.call("searches", {}, s => { if (!page.query.trim()) { page.recent = true; page.suggestions = (s.items || []).slice(0, 5); } }, () => {});
            return;
        }
        Y.call("suggest", {q: q}, s => { if (s.q === page.query) { page.recent = false; page.suggestions = (s.items || []).slice(0, 9); } }, () => {});
    }

    // the voice button types here while the keys are up (couchbox-voice: POST /typing)
    function voiceTyping(on) {
        if (demo) return;
        const x = new XMLHttpRequest();
        x.open("POST", "http://127.0.0.1:8790/typing");
        x.setRequestHeader("Content-Type", "application/json");
        x.setRequestHeader("X-Couchbox", "1");
        x.send(JSON.stringify({on: on}));
    }
    readonly property bool typing: visible && !results
    onTypingChanged: voiceTyping(typing)
    Timer { interval: 60000; repeat: true; running: page.typing; onTriggered: page.voiceTyping(true) }
    Component.onDestruction: if (typing) voiceTyping(false)

    // ------------------------------------------------------------------ the pill
    Rectangle {
        id: pill
        x: Y.left; y: 66 * Y.u
        width: page.results ? 630 * Y.u : 1122 * Y.u
        height: 72 * Y.u
        radius: height / 2
        color: pillFocus.activeFocus ? Y.text : Y.raised
        Behavior on width { NumberAnimation { duration: 160 } }
        Text {
            anchors { left: parent.left; leftMargin: 34 * Y.u; right: parent.right; rightMargin: 34 * Y.u; verticalCenter: parent.verticalCenter }
            text: page.query || "Search"
            color: pillFocus.activeFocus ? Y.ink : page.query ? Y.text : "#bfbfbf"
            font.family: Y.font; font.pixelSize: 34 * Y.u; font.weight: Font.Medium
            elide: Text.ElideLeft
        }
        Rectangle {                            // the caret, while typing
            visible: !page.results
            x: Math.min(parent.width - 30 * Y.u, 34 * Y.u + caretMetrics.advanceWidth + 3 * Y.u)
            anchors.verticalCenter: parent.verticalCenter
            width: 3 * Y.u; height: 40 * Y.u
            color: Y.text
            opacity: page.query ? 1 : 0
            SequentialAnimation on opacity {
                running: !page.results && keys.activeFocus && !Y.shot
                loops: Animation.Infinite
                NumberAnimation { to: 0; duration: 500 }
                NumberAnimation { to: 1; duration: 500 }
            }
        }
        TextMetrics { id: caretMetrics; font.family: Y.font; font.pixelSize: 34 * Y.u; font.weight: Font.Medium; text: page.query }
    }
    FocusScope {
        id: pillFocus
        Keys.onReturnPressed: page.begin(page.query)
        Keys.onEnterPressed: page.begin(page.query)
        Keys.onDownPressed: feed.forceActiveFocus()
        Keys.onLeftPressed: Y.toGuide()
    }
    PhoneCard {
        anchors { right: parent.right; rightMargin: 39 * Y.u }
        y: 38 * Y.u
        visible: true
        z: 5
    }

    // ------------------------------------------------------------------ suggestions and keys
    FocusScope {
        id: keys
        visible: !page.results
        anchors.fill: parent
        focus: true
        Keys.onPressed: e => {
            const k = e.key;
            if (k === Qt.Key_Left) {
                if (page.area === "list") Y.toGuide();
                else if (page.c > 0 && page.r < 4) page.c--;
                else if (page.r === 4 && page.c > 0) page.c--;
                else if (page.suggestions.length) { page.area = "list"; page.li = Math.min(page.r, page.suggestions.length - 1); }
                else Y.toGuide();
            } else if (k === Qt.Key_Right) {
                if (page.area === "list") { page.area = "keys"; page.r = Math.min(page.li, 4); page.c = 0; }
                else if (page.r === 4) page.c = Math.min(2, page.c + 1);
                else page.c = Math.min(page.letters[page.r].length - 1, page.c + 1);
            } else if (k === Qt.Key_Up) {
                if (page.area === "list") { if (page.li > 0) page.li--; }
                else if (page.r === 4) { page.r = 3; page.c = page.c * 2 + 1; }
                else if (page.r > 0) page.r--;
            } else if (k === Qt.Key_Down) {
                if (page.area === "list") { if (page.li < page.suggestions.length - 1) page.li++; }
                else if (page.r === 3) { page.r = 4; page.c = page.c <= 1 ? 0 : page.c <= 3 ? 1 : 2; }
                else if (page.r < 3) { page.r++; page.c = Math.min(page.c, page.letters[page.r].length - 1); }
            } else if (k === Qt.Key_Return) {
                if (page.area === "list") page.search(page.suggestions[page.li]);
                else page.press(page.r === 4 ? page.buttons[page.c] : page.letters[page.r][page.c]);
            } else if (k === Qt.Key_Enter) {
                page.search(page.query);                          // the phone's Enter
            } else if (k === Qt.Key_Backspace) {
                page.backspace();
            } else if (k === Qt.Key_A && (e.modifiers & Qt.ControlModifier)) {
                page.allSelected = true;
            } else if (e.text && e.text.length === 1 && e.text >= " " && !(e.modifiers & Qt.ControlModifier)) {
                page.type(e.text);
            } else {
                return;
            }
            e.accepted = true;
        }

        Column {                               // suggestions / recent searches
            x: 165 * Y.u; y: 174 * Y.u
            width: 528 * Y.u
            spacing: 12 * Y.u
            Repeater {
                model: page.suggestions
                Rectangle {
                    id: sug
                    required property string modelData
                    required property int index
                    readonly property bool on: page.area === "list" && page.li === index && keys.activeFocus
                    width: parent.width; height: 54 * Y.u
                    radius: 12 * Y.u
                    color: on ? Y.text : "transparent"
                    Icon { x: 12 * Y.u; anchors.verticalCenter: parent.verticalCenter; name: page.recent ? "history" : "search"; size: 36 * Y.u; color: sug.on ? Y.ink : Y.text }
                    Text {
                        x: 66 * Y.u
                        width: parent.width - x - 12 * Y.u
                        anchors.verticalCenter: parent.verticalCenter
                        textFormat: Text.StyledText
                        // what's typed in regular type, the rest of the suggestion bold
                        text: {
                            const s = sug.modelData, q = page.query.toLowerCase();
                            const esc = t => t.replace(/&/g, "&amp;").replace(/</g, "&lt;");
                            if (page.recent || !q || s.toLowerCase().indexOf(q) !== 0) return "<b>" + esc(s) + "</b>";
                            return esc(s.slice(0, q.length)) + "<b>" + esc(s.slice(q.length)) + "</b>";
                        }
                        color: sug.on ? Y.ink : Y.text
                        font.family: Y.font; font.pixelSize: 30 * Y.u
                        elide: Text.ElideRight
                    }
                }
            }
        }

        Item {                                 // the letter keys
            x: 714 * Y.u; y: 168 * Y.u
            Repeater {
                model: 4
                Repeater {
                    id: keyRow
                    required property int index
                    readonly property int row: index
                    model: page.letters[row]
                    Rectangle {
                        id: key
                        required property string modelData
                        required property int index
                        readonly property bool on: page.area === "keys" && page.r === keyRow.row && page.c === index && keys.activeFocus
                        readonly property bool side: index === 7
                        x: side ? 483 * Y.u : index * 66 * Y.u
                        y: keyRow.row * 66 * Y.u
                        width: side ? 66 * Y.u : 66 * Y.u
                        height: 66 * Y.u
                        radius: width / 2
                        color: on ? Y.text : "transparent"
                        Text {
                            visible: key.modelData.length <= 1
                            anchors.centerIn: parent
                            text: key.modelData
                            color: key.on ? Y.ink : "#cccccc"
                            font.family: Y.font; font.pixelSize: 36 * Y.u
                        }
                        Icon {
                            visible: key.modelData === "del" || key.modelData === "globe"
                            anchors.centerIn: parent
                            name: key.modelData === "del" ? "backspace" : "globe"
                            size: 36 * Y.u
                            color: key.on ? Y.ink : "#cccccc"
                        }
                        Text {
                            visible: key.modelData === "sym"
                            anchors.centerIn: parent
                            text: page.symbols ? "ABC" : "&123"
                            color: key.on ? Y.ink : "#cccccc"
                            font.family: Y.font; font.pixelSize: 28 * Y.u; font.weight: Font.Medium
                        }
                    }
                }
            }
            Row {
                x: 21 * Y.u; y: 270 * Y.u
                spacing: 13 * Y.u
                Repeater {
                    model: page.buttons
                    Rectangle {
                        required property string modelData
                        required property int index
                        readonly property bool on: page.area === "keys" && page.r === 4 && page.c === index && keys.activeFocus
                        width: 131 * Y.u; height: 54 * Y.u
                        radius: 8 * Y.u
                        color: on ? Y.text : Y.raised
                        Text { anchors.centerIn: parent; text: parent.modelData; color: parent.on ? Y.ink : "#bbbbbb"; font.family: Y.font; font.pixelSize: 26 * Y.u; font.weight: Font.Bold }
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------------ results
    Feed {
        id: feed
        visible: page.results
        y: 186 * Y.u
        width: parent.width
        height: parent.height - y
        onAtTop: pillFocus.forceActiveFocus()
        onOpen: it => Y.open(it)
    }
    Text {
        visible: page.results && (page.loading || !!page.problem)
        x: Y.left; y: 230 * Y.u
        text: page.problem || "Searching…"
        color: Y.dim
        font.family: Y.font; font.pixelSize: Y.tMeta
    }

    // Back: the results go back to the keys (Main leaves Search from the keys)
    function back() {
        if (results) { begin(query); return true; }
        return false;
    }
}
