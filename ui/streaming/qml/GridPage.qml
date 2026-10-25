// A grid of cards: All Series, My List, search results. Loads more as you move down.
//   op/args: what to load ("items" {href}, "search" {q}, "collectionItems" {id})
import QtQuick

FocusScope {
    id: page
    property string title: ""
    property string op: "items"
    property var args: ({})
    property string shape: "wide"
    property string empty: "Nothing here yet."
    property int pageNo: 0
    property bool more: true
    property bool loading: false
    property bool loaded: false
    property real headTop: 150 * D.u
    ListModel { id: model }

    function reload() { model.clear(); pageNo = 0; more = true; loaded = false; load(); }
    function load() {
        if (loading || !more) return;
        loading = true;
        const p = pageNo + 1;
        D.call(op, Object.assign({page: p}, args), r => {
            for (const c of r.items || []) model.append({j: JSON.stringify(c)});
            pageNo = p; more = !!r.more; loading = false; loaded = true;
        }, err => { loading = false; loaded = true; more = false; D.toast(err); });
    }
    Component.onCompleted: if (op) load()

    Text {
        id: heading
        x: D.edge
        y: page.headTop
        text: page.title
        visible: !!text
        color: D.text
        font.family: D.font
        font.pixelSize: 48 * D.u
        font.weight: Font.Black
    }

    GridView {
        id: grid
        anchors { left: parent.left; right: parent.right; top: heading.bottom; bottom: parent.bottom; topMargin: 30 * D.u }
        leftMargin: D.edge - 10 * D.u
        rightMargin: D.edge
        topMargin: 14 * D.u
        cellWidth: D.shapeW(page.shape) + D.gap
        cellHeight: D.shapeH(page.shape) + (page.shape !== "poster" ? 110 : 40) * D.u
        focus: true
        clip: true
        model: model
        cacheBuffer: 2000
        highlightMoveDuration: 180
        highlightRangeMode: GridView.ApplyRange
        preferredHighlightBegin: 30 * D.u
        preferredHighlightEnd: height - cellHeight - 30 * D.u
        onCurrentIndexChanged: if (currentIndex > count - 12) page.load()
        delegate: Card {
            required property string j
            x: 10 * D.u
            c: JSON.parse(j)
            shape: page.shape
            focus: GridView.isCurrentItem
        }
    }
    Text {
        anchors.centerIn: parent
        visible: page.loaded && model.count === 0
        text: page.empty
        color: D.dim
        font.family: D.font
        font.pixelSize: 30 * D.u
    }
}
