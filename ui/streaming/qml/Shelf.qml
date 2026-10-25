// A row of cards with a title, like the website's rows. Loads its items when it comes near
// the screen (active), more as you move right. Sources:
//   op "items" {href}  a browse row / collection;  op "watching";  items: [cards] given
import QtQuick

FocusScope {
    id: shelf
    property bool stop: model.count > 0
    property string title: ""
    property string shape: "wide"
    property string op: "items"
    property var args: ({})
    property var given: null                 // cards given directly
    property bool playDirect: false
    property bool active: false
    property int page: 0
    property bool more: true
    property bool loading: false
    property bool loaded: false
    readonly property real cardH: D.shapeH(shape) + (shape !== "poster" ? 96 * D.u : 0)
    width: parent ? parent.width : 0
    height: visible ? 64 * D.u + cardH + 40 * D.u : 0
    visible: model.count > 0 || !loaded

    ListModel { id: model }

    function load() {
        if (given) {
            model.clear();
            for (const c of given) model.append({j: JSON.stringify(c)});
            loaded = true; more = false;
            return;
        }
        if (loading || !more) return;
        loading = true;
        const p = page + 1;
        D.call(op, Object.assign({page: p}, args), r => {
            for (const c of r.items || []) model.append({j: JSON.stringify(c)});
            page = p; more = !!r.more; loading = false; loaded = true;
        }, () => { loading = false; loaded = true; more = false; });
    }
    function reload() { model.clear(); page = 0; more = true; loaded = false; loading = false; load(); }
    onActiveChanged: if (active && !loaded) load()
    onGivenChanged: if (given) load()
    Component.onCompleted: if (active || given) load()

    Text {
        id: heading
        x: D.edge
        text: shelf.title
        color: D.text
        font.family: D.font
        font.pixelSize: 31 * D.u
        font.weight: Font.Black
    }

    ListView {
        id: list
        anchors { left: parent.left; right: parent.right; top: heading.bottom; topMargin: 20 * D.u }
        height: shelf.cardH + 20 * D.u
        orientation: ListView.Horizontal
        spacing: D.gap
        leftMargin: D.edge
        rightMargin: D.edge
        focus: true
        clip: false
        model: model
        cacheBuffer: 1600
        highlightMoveDuration: 200
        highlightRangeMode: ListView.ApplyRange
        preferredHighlightBegin: D.edge
        preferredHighlightEnd: width - D.edge - D.shapeW(shelf.shape)
        boundsBehavior: Flickable.StopAtBounds
        onCurrentIndexChanged: if (currentIndex > count - 6) shelf.load()
        delegate: Card {
            required property string j
            y: 10 * D.u
            c: JSON.parse(j)
            shape: shelf.shape
            playDirect: shelf.playDirect
            focus: ListView.isCurrentItem
        }
    }

    Row {                                     // loading
        x: D.edge
        anchors.top: list.top
        anchors.topMargin: 10 * D.u
        spacing: D.gap
        visible: !shelf.loaded
        Repeater {
            model: 6
            Rectangle { width: D.shapeW(shelf.shape); height: D.shapeH(shelf.shape); radius: 6 * D.u; color: D.panel }
        }
    }
}
