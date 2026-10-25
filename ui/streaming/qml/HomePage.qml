// Home: the featured banner, then the website's rows (Continue Watching, My List, New
// Releases, Trending, each show...). Rows load as they come near the screen.
import QtQuick

VPage {
    id: page
    property var rows: []

    function refresh() {
        D.call("browse", {}, r => page.rows = r.rows.filter(x => x.kind !== "featured"));
        D.call("featured", {}, r => hero.items = r.items);
    }
    Component.onCompleted: refresh()
    // back from the player: Continue Watching changed
    function returned() {
        for (const s of rowsCol.children)
            if (s.op === "watching" && s.loaded) s.reload();
    }

    // rows within about a screen and a half load
    function wake() {
        const limit = flick.contentY + flick.height * 1.6;
        for (const s of rowsCol.children)
            if (s.active !== undefined && !s.active && s.y + rowsCol.y < limit) s.active = true;
    }
    Connections { target: page.flick; function onContentYChanged() { page.wake(); } }
    Timer { interval: 300; running: true; repeat: true; triggeredOnStart: false; onTriggered: page.wake() }

    Hero { id: hero; y: 0 }

    Column {
        id: rowsCol
        y: hero.height - 70 * D.u
        width: page.width
        spacing: 26 * D.u
        Repeater {
            model: page.rows
            Shelf {
                required property var modelData
                title: modelData.title
                shape: modelData.kind === "watching" ? "wide" : modelData.shape
                op: modelData.kind === "watching" ? "watching" : "items"
                args: ({href: modelData.href})
                playDirect: modelData.kind === "watching"
            }
        }
    }
}
