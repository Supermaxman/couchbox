// One Settings page: a title and a list of rows (see T.row). Up/Down move, OK acts,
// Left (or Back) goes back to the sections. Rows are plain objects:
//   {kind: toggle | choice | text | action | info | section | qr | app, label, value, help, on, act}
import QtQuick

FocusScope {
    id: page
    property string title: ""
    property string subtitle: ""
    property var rows: []
    property bool moving: false            // the home page's reorder mode
    property bool showHeading: true
    signal back()
    readonly property alias list: list
    function move(d) { return false; }

    Text {
        id: heading
        x: T.edge; y: 56 * T.u
        visible: page.showHeading
        height: visible ? implicitHeight : 0
        text: page.title
        color: T.text
        font.family: T.font; font.pixelSize: 46 * T.u; font.weight: Font.Bold
    }
    Text {
        id: sub
        anchors { left: heading.left; top: heading.bottom; topMargin: 8 * T.u; right: parent.right; rightMargin: T.edge }
        text: page.subtitle
        visible: text !== ""
        color: T.dim
        wrapMode: Text.WordWrap
        font.family: T.font; font.pixelSize: 22 * T.u
    }

    ListView {
        id: list
        anchors { left: parent.left; right: parent.right; top: sub.visible ? sub.bottom : heading.bottom; bottom: parent.bottom
                  topMargin: 28 * T.u; leftMargin: T.edge - 16 * T.u; rightMargin: T.edge - 16 * T.u }
        clip: true
        focus: true
        spacing: 6 * T.u
        model: page.rows
        highlightMoveDuration: 120
        preferredHighlightBegin: height * 0.3
        preferredHighlightEnd: height * 0.7
        highlightRangeMode: ListView.ApplyRange
        keyNavigationEnabled: false
        bottomMargin: 80 * T.u

        function step(d) {
            let i = currentIndex + d;
            while (i >= 0 && i < count && ["section", "info", "qr"].indexOf(page.rows[i].kind) >= 0 && !page.rows[i].act)
                i += d;
            if (i >= 0 && i < count) currentIndex = i;
            else if (d < 0) positionViewAtBeginning();
        }
        // The rows are rebuilt on every change: keep the cursor where it was.
        property int keep: -1
        onCurrentIndexChanged: if (currentIndex >= 0) keep = currentIndex
        onModelChanged: Qt.callLater(restore)
        Component.onCompleted: restore()
        function restore() {
            if (count === 0) return;
            const k = keep;
            currentIndex = -1;
            if (k >= 0 && k < count && ["section", "info", "qr"].indexOf(page.rows[k].kind) < 0) currentIndex = k;
            else { currentIndex = Math.min(Math.max(k, 0), count - 1) - 1; step(1); }
        }
        Keys.onUpPressed: if (!page.moving || !page.move(-1)) step(-1)
        Keys.onDownPressed: if (!page.moving || !page.move(1)) step(1)
        Keys.onLeftPressed: page.back()
        Keys.onReturnPressed: activate()
        Keys.onEnterPressed: activate()
        Keys.onEscapePressed: page.moving ? page.move(0) : page.back()
        function activate() {
            const r = page.rows[currentIndex];
            if (r && r.act) r.act();
        }

        delegate: Item {
            id: d
            required property var modelData
            required property int index
            readonly property var r: modelData
            readonly property bool cur: ListView.isCurrentItem && list.activeFocus
            width: list.width
            height: r.kind === "section" ? 74 * T.u : r.kind === "qr" ? qr.height + 40 * T.u
                  : Math.max(84 * T.u, col.implicitHeight + 34 * T.u)

            Text {
                visible: d.r.kind === "section"
                anchors { left: parent.left; leftMargin: 16 * T.u; bottom: parent.bottom; bottomMargin: 12 * T.u }
                text: d.r.label || ""
                color: T.accent
                font.family: T.font; font.pixelSize: 20 * T.u; font.weight: Font.Bold
                font.capitalization: Font.AllUppercase; font.letterSpacing: 2 * T.u
            }

            Rectangle {
                visible: d.r.kind !== "section"
                anchors.fill: parent
                radius: 14 * T.u
                color: d.cur ? (page.moving && d.r.kind === "app" ? T.accent : T.panel2) : d.r.kind === "info" || d.r.kind === "qr" ? "transparent" : T.panel
                border.color: d.cur ? T.accent : "transparent"
                border.width: 3 * T.u

                Column {
                    id: col
                    anchors { left: parent.left; leftMargin: 28 * T.u; right: side.left; rightMargin: 24 * T.u; verticalCenter: parent.verticalCenter }
                    spacing: 4 * T.u
                    Text {
                        width: parent.width
                        text: d.r.label || ""
                        color: page.moving && d.cur && d.r.kind === "app" ? T.accentInk : d.r.danger ? T.bad : T.text
                        elide: Text.ElideRight
                        font.family: T.font; font.pixelSize: 27 * T.u; font.weight: Font.DemiBold
                    }
                    Text {
                        width: parent.width
                        visible: !!d.r.help && (d.cur || d.r.kind === "info" || !!d.r.alwaysHelp)
                        text: d.r.help || ""
                        color: T.dim
                        wrapMode: Text.WordWrap
                        font.family: T.font; font.pixelSize: 20 * T.u
                    }
                }
                Row {
                    id: side
                    anchors { right: parent.right; rightMargin: 28 * T.u; verticalCenter: parent.verticalCenter }
                    spacing: 16 * T.u
                    Text {
                        visible: d.r.kind !== "toggle" && !!d.r.value
                        anchors.verticalCenter: parent.verticalCenter
                        text: d.r.value || ""
                        color: d.r.tone === "good" ? T.good : d.r.tone === "warn" ? T.warn : d.r.tone === "bad" ? T.bad
                             : page.moving && d.cur && d.r.kind === "app" ? T.accentInk : T.dim
                        font.family: T.font; font.pixelSize: 23 * T.u
                        elide: Text.ElideLeft
                        width: Math.min(implicitWidth, 560 * T.u)
                        horizontalAlignment: Text.AlignRight
                    }
                    Rectangle {                            // switch
                        visible: d.r.kind === "toggle"
                        anchors.verticalCenter: parent.verticalCenter
                        width: 64 * T.u; height: 36 * T.u; radius: height / 2
                        color: d.r.on ? T.accent : T.line
                        Rectangle {
                            x: d.r.on ? parent.width - width - 4 * T.u : 4 * T.u
                            anchors.verticalCenter: parent.verticalCenter
                            width: 28 * T.u; height: width; radius: width / 2
                            color: "white"
                            Behavior on x { NumberAnimation { duration: 120 } }
                        }
                    }
                    Text {
                        visible: d.r.kind === "choice" || d.r.kind === "text" || d.r.kind === "app"
                        anchors.verticalCenter: parent.verticalCenter
                        text: page.moving && d.cur && d.r.kind === "app" ? "⇅" : "›"
                        color: page.moving && d.cur ? T.accentInk : T.dim
                        font.family: T.font; font.pixelSize: 34 * T.u
                    }
                }
                Rectangle {
                    id: qr
                    visible: d.r.kind === "qr"
                    x: 28 * T.u
                    anchors.verticalCenter: parent.verticalCenter
                    width: d.r.kind === "qr" ? 280 * T.u : 0; height: width
                    radius: 14 * T.u
                    color: "white"
                    Image {
                        anchors.fill: parent; anchors.margins: 12 * T.u
                        source: d.r.kind === "qr" ? (d.r.qr || "") : ""
                        smooth: false
                        fillMode: Image.PreserveAspectFit
                    }
                }
            }
        }
    }
}
