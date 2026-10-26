// A person: their photo, facts and biography, then tabs: Known for (their best-known titles)
// and their work by department (Acting, Directing, Writing, …) as a timeline, newest first,
// with the character or the job, and the whole biography. Up/Down move between the tabs and
// the work, Left/Right between tabs, OK opens a title, Back goes back.
import QtQuick

FocusScope {
    id: page
    property int pid: 0
    property string startDept: ""
    property var p: null
    property bool loading: true
    property string problem: ""
    property int zone: 0                      // 0 tabs, 1 the work
    property int tab: 0
    signal closed()

    readonly property string label: p ? p.name : ""
    readonly property var tabs: p ? [{dept: "", label: "Known for", count: 0}]
                                    .concat(p.tabs.map(x => ({dept: x.dept, label: M.deptLabel(x.dept), count: x.count})))
                                    .concat(p.bio ? [{dept: "bio", label: "Biography", count: 0}] : []) : []
    readonly property string dept: (tabs[tab] || {}).dept || ""
    readonly property bool bio: dept === "bio"
    readonly property var work: p && dept && !bio ? p.credits[dept] || [] : []

    function load() {
        loading = true; problem = "";
        M.call("person", {id: pid}, r => {
            p = r; loading = false; zone = 0;
            tab = 0;
            if (startDept) for (let i = 0; i < tabs.length; i++) if (tabs[i].dept.toLowerCase() === startDept.toLowerCase()) { tab = i; zone = 1; }
            Qt.callLater(focusZone);
        }, e => { loading = false; problem = e; });
    }
    Component.onCompleted: load()
    onActiveFocusChanged: if (activeFocus) focusZone()
    function focusZone() {
        if (zone === 0) tabRow.forceActiveFocus();
        else if (bio) bioFlick.forceActiveFocus();
        else if (dept) timeline.forceActiveFocus();
        else known.forceActiveFocus();
    }
    Keys.onUpPressed: if (zone > 0) { zone = 0; focusZone(); }
    Keys.onDownPressed: if (zone === 0) { zone = 1; focusZone(); }
    Keys.onEscapePressed: closed()
    Keys.onBackPressed: closed()

    Rectangle { anchors.fill: parent; color: M.bg }

    // ------------------------------------------------------------------ who they are
    RoundPhoto {
        id: photo
        x: 80 * M.u; y: 64 * M.u
        width: 250 * M.u; height: width
        source: page.p ? page.p.image : ""
        name: page.label
        sourceWidth: 500
    }
    Column {
        id: facts
        anchors { left: photo.right; leftMargin: 54 * M.u; right: parent.right; rightMargin: M.edge + 30 * M.u; top: photo.top; topMargin: 4 * M.u }
        spacing: 14 * M.u
        visible: !!page.p
        Text { width: parent.width; text: page.label; color: M.text; font.family: M.font; font.pixelSize: M.tHero; font.weight: Font.Bold; elide: Text.ElideRight }
        Text {
            width: parent.width
            text: !page.p ? "" : [
                {Acting: "Actor", Directing: "Director", Writing: "Writer", Production: "Producer", Sound: "Composer", Camera: "Cinematographer", Editing: "Editor"}[page.p.dept] || page.p.dept,
                page.p.born ? "Born " + M.date(page.p.born) + (page.p.died ? "" : " (age " + M.age(page.p.born) + ")") : "",
                page.p.died ? "Died " + M.date(page.p.died) + " (age " + M.age(page.p.born, page.p.died) + ")" : "",
                page.p.place
            ].filter(x => !!x).join("   ·   ")
            color: M.text2; font.family: M.font; font.pixelSize: M.tBody; elide: Text.ElideRight
        }
        Text {
            width: parent.width
            text: page.p ? (page.p.bio || "No biography yet.").replace(/\s*\n+\s*/g, " ") : ""
            color: M.dim; font.family: M.font; font.pixelSize: M.tMeta; lineHeight: 1.18
            wrapMode: Text.WordWrap; maximumLineCount: 3; elide: Text.ElideRight
        }
    }

    // ------------------------------------------------------------------ tabs
    FocusScope {
        id: tabRow
        anchors { left: parent.left; right: parent.right; top: photo.bottom; topMargin: 44 * M.u; leftMargin: 80 * M.u }
        height: 64 * M.u
        Keys.onLeftPressed: if (page.tab > 0) page.tab--
        Keys.onRightPressed: if (page.tab < page.tabs.length - 1) page.tab++
        Keys.onReturnPressed: { page.zone = 1; page.focusZone(); }
        Keys.onEnterPressed: { page.zone = 1; page.focusZone(); }
        ListView {                               // scrolls sideways when there are many
            id: tabList
            anchors.fill: parent
            anchors.rightMargin: M.edge
            orientation: ListView.Horizontal
            spacing: 14 * M.u
            clip: true
            interactive: false
            model: page.tabs
            currentIndex: page.tab
            highlightMoveDuration: 150
            preferredHighlightBegin: 0
            preferredHighlightEnd: width - 260 * M.u
            highlightRangeMode: ListView.ApplyRange
            delegate: Rectangle {
                required property var modelData
                required property int index
                readonly property bool sel: page.tab === index
                readonly property bool cur: sel && tabRow.activeFocus
                width: tabText.implicitWidth + 44 * M.u; height: 64 * M.u; radius: height / 2
                color: cur ? M.accent : sel ? M.panel2 : M.panel
                border.color: cur ? "white" : sel ? M.focus : M.line; border.width: (cur ? 3 : 1) * M.u
                Text {
                    id: tabText
                    anchors.centerIn: parent
                    text: parent.modelData.label + (parent.modelData.count ? "  " + parent.modelData.count : "")
                    color: parent.cur ? M.accentDark : parent.sel ? M.text : M.text2
                    font.family: M.font; font.pixelSize: 25 * M.u; font.weight: parent.sel ? Font.DemiBold : Font.Normal
                }
            }
        }
    }

    // ------------------------------------------------------------------ the work
    Shelf {
        id: known
        anchors { left: parent.left; right: parent.right; top: tabRow.bottom; topMargin: 40 * M.u; leftMargin: 80 * M.u }
        visible: !page.dept && items.length > 0
        title: ""
        items: page.p ? page.p.known_for : []
        onOpen: it => M.open(it)
    }
    ListView {
        id: timeline
        anchors { left: parent.left; right: parent.right; top: tabRow.bottom; bottom: parent.bottom; topMargin: 34 * M.u; leftMargin: 80 * M.u; rightMargin: M.edge }
        visible: !!page.dept
        clip: true
        model: page.work
        spacing: 10 * M.u
        cacheBuffer: 1200
        highlightMoveDuration: 140
        preferredHighlightBegin: 10 * M.u
        preferredHighlightEnd: height - 150 * M.u
        highlightRangeMode: ListView.ApplyRange
        keyNavigationEnabled: true
        onModelChanged: currentIndex = 0
        Keys.onUpPressed: e => { if (currentIndex === 0) { page.zone = 0; page.focusZone(); } else decrementCurrentIndex(); }
        Keys.onReturnPressed: M.open(page.work[currentIndex])
        Keys.onEnterPressed: M.open(page.work[currentIndex])
        delegate: Rectangle {
            id: rowItem
            required property var modelData
            required property int index
            readonly property bool cur: ListView.isCurrentItem && timeline.activeFocus
            readonly property string yr: modelData.year || ""
            readonly property bool newYear: index === 0 || (page.work[index - 1].year || "") !== yr
            width: timeline.width - 20 * M.u; height: 128 * M.u
            radius: M.radius
            color: cur ? M.panel2 : index % 2 ? "transparent" : "#0fffffff"
            border.color: cur ? M.focus : "transparent"; border.width: 3 * M.u
            Text {                                 // the year, once per year
                x: 24 * M.u; anchors.verticalCenter: parent.verticalCenter
                width: 110 * M.u
                text: rowItem.newYear ? (rowItem.yr || "Soon") : ""
                color: rowItem.yr ? M.accent : M.dim; font.family: M.font; font.pixelSize: 32 * M.u; font.weight: Font.Bold
            }
            Rectangle {
                id: thumb
                x: 150 * M.u; anchors.verticalCenter: parent.verticalCenter
                width: 72 * M.u; height: 108 * M.u; radius: 8 * M.u; clip: true
                color: Qt.hsla(M.hue(rowItem.modelData.title), 0.4, 0.22, 1)
                Image { anchors.fill: parent; source: rowItem.modelData.poster || ""; fillMode: Image.PreserveAspectCrop; asynchronous: true; sourceSize.width: M.px(width) }
            }
            Column {
                anchors { left: thumb.right; leftMargin: 26 * M.u; right: score.left; rightMargin: 20 * M.u; verticalCenter: parent.verticalCenter }
                spacing: 6 * M.u
                Text { width: parent.width; text: rowItem.modelData.title; color: M.text; font.family: M.font; font.pixelSize: M.tBody; font.weight: Font.DemiBold; elide: Text.ElideRight }
                Text {
                    width: parent.width
                    text: [rowItem.modelData.role ? (page.dept === "Acting" ? "as " : "") + rowItem.modelData.role : "",
                           rowItem.modelData.type === "tv" ? "TV series" + (rowItem.modelData.episodes ? " · " + rowItem.modelData.episodes + (rowItem.modelData.episodes > 1 ? " episodes" : " episode") : "") : ""
                          ].filter(x => !!x).join("   ·   ")
                    color: M.dim; font.family: M.font; font.pixelSize: M.tMeta; elide: Text.ElideRight
                }
            }
            Row {
                id: score
                anchors { right: parent.right; rightMargin: 28 * M.u; verticalCenter: parent.verticalCenter }
                spacing: 8 * M.u
                visible: !!rowItem.modelData.score
                Text { text: "★"; color: M.accent; font.pixelSize: M.tMeta; anchors.verticalCenter: parent.verticalCenter }
                Text { text: rowItem.modelData.score ? Number(rowItem.modelData.score).toFixed(1) : ""; color: M.text2; font.family: M.font; font.pixelSize: M.tMeta }
            }
        }
    }

    // ------------------------------------------------------------------ the whole biography
    Flickable {
        id: bioFlick
        anchors { left: parent.left; right: parent.right; top: tabRow.bottom; bottom: parent.bottom; topMargin: 40 * M.u; leftMargin: 80 * M.u; rightMargin: 300 * M.u; bottomMargin: 50 * M.u }
        visible: page.bio
        contentHeight: bioText.height
        clip: true
        interactive: false
        Behavior on contentY { NumberAnimation { duration: 160 } }
        Text {
            id: bioText
            width: bioFlick.width
            text: page.p ? page.p.bio : ""
            color: M.text2; font.family: M.font; font.pixelSize: M.tBody; lineHeight: 1.25; wrapMode: Text.WordWrap
        }
        Keys.onDownPressed: contentY = Math.min(Math.max(0, contentHeight - height), contentY + 180 * M.u)
        Keys.onUpPressed: e => { if (contentY <= 0) { page.zone = 0; page.focusZone(); } else contentY = Math.max(0, contentY - 180 * M.u); }
    }

    Text {
        anchors.centerIn: parent
        visible: page.loading || !!page.problem
        width: parent.width * 0.6; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
        text: page.problem || "Loading…"
        color: page.problem ? M.text2 : M.faint; font.family: M.font; font.pixelSize: M.tHead
    }
}
