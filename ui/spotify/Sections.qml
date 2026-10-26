// A page of sections stacked down the screen: rows of cards ("shelf") and song lists
// ("tracks"), below an optional header (any Item with a FocusScope, given as `header`).
// Up/Down move between sections, the page scrolls to keep the one in focus in view.
import QtQuick

FocusScope {
    id: page
    property var sections: []               // [{type: "shelf"|"tracks", title, items, context, maxRows}]
    property Component header: null
    property bool headerTakesFocus: false
    property int cur: headerTakesFocus ? -1 : 0
    property real topPad: 60 * S.u
    signal toRail()
    signal chosen(var item)

    readonly property var live: sections.filter(s => s.items && s.items.length)
    function focusCur() {
        if (cur < 0 && headerLoader.item) { headerLoader.item.forceActiveFocus(); scrollTo(0); return; }
        const it = rep.itemAt(cur);
        if (it && it.item) { it.item.forceActiveFocus(); scrollTo(it.y + col.y - 30 * S.u); }
    }
    // near the top: show the page from its top (its title and header stay in view)
    function scrollTo(y) { flick.contentY = y < flick.height * 0.45 ? 0 : Math.max(0, Math.min(y, flick.contentHeight - flick.height)); }
    function move(d) {
        const n = cur + d;
        if (n < (headerLoader.item && headerTakesFocus ? -1 : 0) || n >= live.length) return false;
        cur = n; focusCur(); return true;
    }
    onActiveFocusChanged: if (activeFocus) focusCur()
    onLiveChanged: { if (cur >= live.length) cur = Math.max(headerTakesFocus ? -1 : 0, live.length - 1); if (activeFocus) Qt.callLater(focusCur); }

    Flickable {
        id: flick
        readonly property real pad: 18 * S.u        // room for a focused card to grow at the left
        anchors { fill: parent; leftMargin: -pad }
        contentHeight: col.y + col.height + 160 * S.u
        interactive: false
        clip: true
        Behavior on contentY { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
        Loader {
            id: headerLoader
            x: flick.pad; y: page.topPad
            width: flick.width - flick.pad
            sourceComponent: page.header
        }
        Connections {
            target: headerLoader.item
            ignoreUnknownSignals: true
            function onDownEdge() { page.move(1); }
            function onLeftEdge() { page.toRail(); }
        }
        Column {
            id: col
            x: flick.pad
            y: (headerLoader.item ? headerLoader.y + headerLoader.height + 40 * S.u : page.topPad)
            width: flick.width - flick.pad - S.edge
            spacing: 44 * S.u
            Repeater {
                id: rep
                model: page.live
                delegate: Loader {
                    id: ld
                    required property var modelData
                    required property int index
                    width: col.width
                    sourceComponent: modelData.type === "tracks" ? tracksC : shelfC
                    Component {
                        id: shelfC
                        Shelf {
                            width: ld.width
                            title: ld.modelData.title || ""
                            items: ld.modelData.items
                            cardW: ld.modelData.cardW ? ld.modelData.cardW * S.u : 250 * S.u
                            Keys.onUpPressed: page.move(-1)
                            Keys.onDownPressed: page.move(1)
                            onLeftEdge: page.toRail()
                            onChosen: item => page.chosen(item)
                        }
                    }
                    Component {
                        id: tracksC
                        FocusScope {
                            width: ld.width
                            height: tcol.implicitHeight
                            Column {
                                id: tcol
                                width: parent.width
                                spacing: 14 * S.u
                                Text { visible: !!ld.modelData.title; text: ld.modelData.title || ""; color: S.text; font.family: S.font; font.pixelSize: S.tHead; font.weight: Font.Bold }
                                TrackList {
                                    width: parent.width
                                    focus: true
                                    items: ld.modelData.items
                                    contextUri: ld.modelData.context || ""
                                    maxRows: ld.modelData.maxRows || 0
                                    showAlbum: ld.modelData.showAlbum !== false
                                    onUpEdge: page.move(-1)
                                    onDownEdge: page.move(1)
                                    onLeftEdge: page.toRail()
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
