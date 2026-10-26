// A vertically scrolling page for the remote. Items marked "property bool stop: true" (rows,
// button bars, lists) are where Up/Down go, in screen order; inside them, their own lists
// handle the arrows. The page scrolls to keep what has focus in view. Up from the first
// stop and Left from a row's start reach Main (search bar, sidebar).
import QtQuick

FocusScope {
    id: page
    default property alias content: col.data
    property alias flick: flick
    property alias column: col
    property real bottomPad: 80 * S.u
    property bool clipContent: true          // false: backdrops may reach the sidebar

    Flickable {
        id: flick
        readonly property real pad: 20 * S.u        // room for a focused card at the left edge to grow
        anchors { fill: parent; leftMargin: -pad }
        contentHeight: col.height + page.bottomPad
        interactive: false
        clip: page.clipContent
        Behavior on contentY { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
        Item {
            id: col
            x: flick.pad
            width: flick.width - flick.pad
            height: childrenRect.height
        }
    }

    function stops() {
        const out = [];
        const walk = it => {
            for (const c of it.children) {
                if (!c.visible) continue;
                if (c.stop === true) out.push(c);
                else walk(c);
            }
        };
        walk(col);
        const y = it => it.mapToItem(col, 0, 0).y;
        const x = it => it.mapToItem(col, 0, 0).x;
        out.sort((a, b) => Math.abs(y(a) - y(b)) > 8 ? y(a) - y(b) : x(a) - x(b));
        return out;
    }

    function within(item, root) {
        for (let i = item; i; i = i.parent) if (i === root) return true;
        return false;
    }

    function currentStop(list) {
        const f = Window.activeFocusItem;
        return list.findIndex(s => f && within(f, s));
    }

    function focusFirst() {
        const st = stops();
        if (!st.length) return;
        st[0].forceActiveFocus();
        autoStop = st[0];
    }

    // Rows load at different times: until the remote is used, keep focus on the topmost one.
    property bool touched: false
    property var autoStop: null
    Timer {
        property int n: 0
        interval: 300
        repeat: true
        running: page.activeFocus && !page.touched
        onTriggered: {
            const f = page.Window.activeFocusItem;
            // the remote moved focus out of the row we put it in: leave it alone from now on
            if (++n > 30 || page.autoStop && !(f && page.within(f, page.autoStop))) { page.touched = true; return; }
            if (page.stops()[0] !== page.autoStop) page.focusFirst();
        }
    }

    function move(d) {
        const st = stops();
        const i = currentStop(st);
        const j = i + d;
        if (i < 0 || j < 0 || j >= st.length) return false;
        st[j].forceActiveFocus();
        return true;
    }

    // keep the focused thing (and, when it fits, its whole stop) in view
    function reveal(item) {
        const st = stops();
        const i = st.findIndex(s => within(item, s));
        const target = i >= 0 && st[i].height < flick.height * 0.8 ? st[i] : item;
        const top = target.mapToItem(col, 0, 0).y - (i === 0 ? 400 * S.u : 90 * S.u);
        const bottom = target.mapToItem(col, 0, target.height).y + 40 * S.u;
        let y = flick.contentY;
        if (bottom > y + flick.height) y = bottom - flick.height;
        if (top < y) y = top;
        flick.contentY = Math.max(0, Math.min(y, flick.contentHeight - flick.height));
    }

    Connections {
        target: page.Window.window
        function onActiveFocusItemChanged() {
            const f = page.Window.activeFocusItem;
            if (f && page.visible && within(f, col)) reveal(f);
        }
    }

    // focused from outside (a new page, back from the sidebar) with nothing inside focused yet
    onActiveFocusChanged: if (activeFocus && Window.activeFocusItem === page) Qt.callLater(focusFirst)

    Keys.onUpPressed: event => { event.accepted = move(-1); }
    Keys.onDownPressed: event => { event.accepted = move(1); }
}
