// CouchKit TextEntry: the keyboard pop-up for every text field in our TV apps.
//
// An on-screen keyboard for the remote (arrows move, OK presses the key, Back closes) next
// to a QR code for the phone typing page (couchbox-phone). Text typed on the phone arrives as key
// presses: characters are typed, Backspace deletes, Ctrl+A then Backspace clears, and the
// phone's Enter (keypad Enter, unlike the remote's OK) is "done". While it's open, the voice
// button dictates: couchbox-voice types what was said here (and submits) instead of running the
// assistant (it's told through POST 127.0.0.1:8790/typing).
//
//   TextEntry { id: entry; anchors.fill: parent; title: "Search Seerr"; onAccepted: t => search(t) }
//   entry.open(currentText, itemToFocusAfter)
//
// The launcher must add /usr/share/couchbox/ui to the QML import path and set
// QML_XHR_ALLOW_FILE_READ=1 (the phone page's address is read from /run/couchbox/phone/phone.url).
import QtQuick

FocusScope {
    id: entry
    visible: false
    z: 100

    property string title: "Search"
    property string doneLabel: "Search"
    property string placeholder: "Use the keys below, type on your phone, or press the mic and say it"
    property string text: ""
    property bool password: false         // show dots instead of the text
    // colours: each app passes its own
    property color accent: "#8f7cf8"
    property color bg: "#0e1222"
    property color panel: "#171c38"
    property color keyColor: "#1d2346"
    property color line: "#2c3566"
    property color ink: "#eef0ff"
    property color dim: "#9aa3d0"
    property string phoneDir: "/run/couchbox/phone"

    signal accepted(string text)
    signal canceled()

    readonly property real u: height / 1080
    readonly property real unit: 84 * u    // one key's width and height
    readonly property real gap: 10 * u
    property var returnFocus: null
    property string phoneUrl: ""
    property int row: 0
    property int col: 0
    property bool caps: false
    property bool allSelected: false       // after Ctrl+A: the next Backspace clears

    readonly property var layout: {
        const ch = s => s.split("").map(k => ({k: k, label: k, w: 1}));
        return [ch("abcdefghijklm"), ch("nopqrstuvwxyz"), ch("1234567890@.-"),
                [{k: "shift", label: "⇧", w: 2}, {k: "space", label: "Space", w: 4}, {k: "del", label: "⌫", w: 2},
                 {k: "clear", label: "Clear", w: 2}, {k: "done", label: doneLabel, w: 3}]];
    }

    // tell couchbox-voice the pop-up is open (it expires after 2 minutes, so keep saying it)
    function voiceTyping(on) {
        const x = new XMLHttpRequest();
        x.open("POST", "http://127.0.0.1:8790/typing");
        x.setRequestHeader("Content-Type", "application/json");
        x.setRequestHeader("X-Couchbox", "1");
        x.send(JSON.stringify({on: on}));
    }
    onVisibleChanged: voiceTyping(visible)
    Timer { interval: 60000; repeat: true; running: entry.visible; onTriggered: entry.voiceTyping(true) }
    Component.onDestruction: if (visible) voiceTyping(false)

    function open(initial, focusAfter) {
        text = initial || "";
        returnFocus = focusAfter || null;
        row = 0; col = 0; caps = false; allSelected = false;
        qr.source = "";
        qr.source = "file://" + phoneDir + "/phone.png";
        const x = new XMLHttpRequest();
        x.onreadystatechange = () => {
            if (x.readyState === XMLHttpRequest.DONE)
                phoneUrl = (x.responseText || "").trim();
        };
        x.open("GET", "file://" + phoneDir + "/phone.url");
        x.send();
        visible = true;
        forceActiveFocus();
    }

    function close() {
        visible = false;
        if (returnFocus)
            returnFocus.forceActiveFocus();
    }

    function type(s) {
        if (allSelected) { text = ""; allSelected = false; }
        text += s;
    }

    function backspace() {
        text = allSelected ? "" : text.slice(0, -1);
        allSelected = false;
    }

    function done() {
        const t = text;
        close();
        accepted(t);
    }

    function press(k) {
        if (k === "shift") caps = !caps;
        else if (k === "space") type(" ");
        else if (k === "del") backspace();
        else if (k === "clear") { text = ""; allSelected = false; }
        else if (k === "done") done();
        else type(caps ? k.toUpperCase() : k);
    }

    // centre of a key, in key units, for moving up and down to the nearest key
    function centre(r, i) {
        let x = 0;
        for (let j = 0; j < i; j++) x += layout[r][j].w + gap / unit;
        return x + layout[r][i].w / 2;
    }

    function moveRow(d) {
        const r = Math.max(0, Math.min(layout.length - 1, row + d));
        if (r === row) return;
        const want = centre(row, col);
        let best = 0;
        for (let i = 1; i < layout[r].length; i++)
            if (Math.abs(centre(r, i) - want) < Math.abs(centre(r, best) - want)) best = i;
        row = r; col = best;
    }

    Keys.onPressed: event => {
        const k = event.key;
        if (k === Qt.Key_Left) col = Math.max(0, col - 1);
        else if (k === Qt.Key_Right) col = Math.min(layout[row].length - 1, col + 1);
        else if (k === Qt.Key_Up) moveRow(-1);
        else if (k === Qt.Key_Down) moveRow(1);
        else if (k === Qt.Key_Return) press(layout[row][col].k);
        else if (k === Qt.Key_Enter) done();                      // the phone's Enter
        else if (k === Qt.Key_Escape || k === Qt.Key_Back) { close(); canceled(); }
        else if (k === Qt.Key_Backspace) backspace();
        else if (k === Qt.Key_A && (event.modifiers & Qt.ControlModifier)) allSelected = true;
        else if (event.text.length === 1 && event.text >= " " && !(event.modifiers & Qt.ControlModifier)) type(event.text);
        else return;
        event.accepted = true;
    }

    // ------------------------------------------------------------------ looks
    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(0, 0, 0, 0.6)
    }

    Rectangle {
        id: box
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 56 * u
        width: content.width + 112 * u
        height: content.height + 96 * u
        radius: 28 * u
        color: entry.panel
        border.color: entry.line
        border.width: 1

        Row {
            id: content
            anchors.centerIn: parent
            spacing: 56 * u

            Column {
                spacing: 24 * u

                Text {
                    text: entry.title
                    color: entry.dim
                    font.pixelSize: 26 * u
                    font.weight: Font.DemiBold
                }

                Rectangle {
                    width: keys.width
                    height: 88 * u
                    radius: height / 2
                    color: entry.bg
                    border.width: 3 * u
                    border.color: entry.accent

                    Row {
                        anchors.verticalCenter: parent.verticalCenter
                        x: 32 * u
                        width: parent.width - 64 * u
                        clip: true
                        spacing: 2 * u
                        Text {
                            id: shown
                            text: entry.text ? (entry.password ? "•".repeat(entry.text.length) : entry.text) : ""
                            color: entry.allSelected ? entry.bg : entry.ink
                            font.pixelSize: 36 * u
                            Rectangle {        // Ctrl+A from the phone: show it as selected
                                anchors.fill: parent
                                z: -1
                                visible: entry.allSelected && !!entry.text
                                color: entry.accent
                            }
                        }
                        Rectangle {
                            width: 3 * u
                            height: 44 * u
                            anchors.verticalCenter: parent.verticalCenter
                            color: entry.accent
                            SequentialAnimation on opacity {
                                running: entry.visible
                                loops: Animation.Infinite
                                NumberAnimation { to: 0; duration: 500; easing.type: Easing.InOutQuad }
                                NumberAnimation { to: 1; duration: 500; easing.type: Easing.InOutQuad }
                            }
                        }
                        Text {
                            visible: !entry.text
                            text: entry.placeholder
                            color: entry.dim
                            font.pixelSize: 30 * u
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                }

                Column {
                    id: keys
                    spacing: entry.gap
                    Repeater {
                        model: entry.layout.length
                        Row {
                            id: keyRow
                            readonly property int r: index
                            spacing: entry.gap
                            Repeater {
                                model: entry.layout[keyRow.r]
                                Rectangle {
                                    readonly property bool current: entry.row === keyRow.r && entry.col === index
                                    readonly property bool on: modelData.k === "shift" && entry.caps
                                    width: modelData.w * entry.unit + (modelData.w - 1) * entry.gap
                                    height: entry.unit
                                    radius: 14 * entry.u
                                    color: current ? entry.accent : on ? entry.line : entry.keyColor
                                    scale: current ? 1.06 : 1
                                    Behavior on scale { NumberAnimation { duration: 90 } }
                                    Text {
                                        anchors.centerIn: parent
                                        text: modelData.label.length === 1 && entry.caps ? modelData.label.toUpperCase() : modelData.label
                                        color: parent.current ? entry.bg : entry.ink
                                        font.pixelSize: (modelData.w > 1 ? 28 : 34) * entry.u
                                        font.weight: parent.current ? Font.Bold : Font.Normal
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // the phone page, for typing more than a word or two
            Column {
                anchors.verticalCenter: parent.verticalCenter
                spacing: 18 * u
                width: 360 * u

                Text {
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    text: "Or type on your phone"
                    color: entry.ink
                    font.pixelSize: 28 * u
                    font.weight: Font.DemiBold
                }
                Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 300 * u
                    height: width
                    radius: 18 * u
                    color: "white"
                    Image {
                        id: qr
                        anchors.fill: parent
                        anchors.margins: 14 * u
                        smooth: false
                        cache: false
                        fillMode: Image.PreserveAspectFit
                    }
                    Text {
                        anchors.centerIn: parent
                        visible: qr.status !== Image.Ready
                        width: parent.width - 40 * u
                        wrapMode: Text.WordWrap
                        horizontalAlignment: Text.AlignHCenter
                        text: "Phone typing isn't running"
                        color: "#333"
                        font.pixelSize: 22 * u
                    }
                }
                Text {
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: "Scan with the camera" + (entry.phoneUrl ? "\n" + entry.phoneUrl.replace(/^https?:\/\//, "").replace(/:\d+$/, "") : "")
                    color: entry.dim
                    font.pixelSize: 22 * u
                    lineHeight: 1.2
                }
            }
        }
    }
}
