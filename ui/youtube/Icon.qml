// An icon in any colour: a small SVG (24x24, drawn here) handed to Image as a data: address, so
// one drawing serves the white, grey and dark (on a focused, white row) versions.
//   Icon { name: "search"; color: Y.text; size: 40 * Y.u }
// Two Images, one shown: a new drawing (another colour, the filled one) loads into the hidden one
// and is swapped in once it's ready, so the icon never blinks out while it loads (the guide's
// icons flickered as the focus moved: each change of colour loaded a new picture in its place).
import QtQuick
import "IconPaths.js" as Drawings

Item {
    id: icon
    property string name: ""
    property color color: Y.text
    property real size: 40 * Y.u
    property bool filled: false              // the current page's guide entry: its filled drawing
    property real weight: 1.8                // the stroke, in the drawing's 24ths (the player's buttons: heavier)
    width: size
    height: size
    readonly property string source: name ? svg(filled && Drawings.paths[name + "-filled"] ? name + "-filled" : name, color) : ""
    property int front: 0                    // which Image is shown
    property string srcA: ""
    property string srcB: ""
    onSourceChanged: show()
    Component.onCompleted: show()
    function show() {
        if ((front === 0 ? srcA : srcB) === source) {       // back to what's shown: drop what was loading
            if (front === 0) { srcB = ""; } else { srcA = ""; }
            return;
        }
        if (front === 0) srcB = source; else srcA = source;
        settle();
    }
    function settle() {                      // the hidden one is ready with the wanted drawing: show it
        const back = front === 0 ? imgB : imgA, bsrc = front === 0 ? srcB : srcA;
        if (bsrc === source && (back.status === Image.Ready || !source)) front = 1 - front;
    }
    Image {
        id: imgA
        anchors.fill: parent
        sourceSize: Y.sz(icon.size, icon.size)
        smooth: true
        source: icon.srcA
        visible: icon.front === 0
        onStatusChanged: icon.settle()
    }
    Image {
        id: imgB
        anchors.fill: parent
        sourceSize: Y.sz(icon.size, icon.size)
        smooth: true
        source: icon.srcB
        visible: icon.front === 1
        onStatusChanged: icon.settle()
    }
    function svg(name, c) {
        const p = Drawings.paths[name] || "";
        const col = String(c);
        let body;
        if (p === "m")                       // YouTube Music's mark, in the guide's outline style (YouTube's TV app)
            body = "<g fill='none' stroke='" + col + "' stroke-width='" + icon.weight + "'><circle cx='12' cy='12' r='9.3'/><circle cx='12' cy='12' r='5.3'/></g>"
                 + "<path d='M10.6 9.9v4.2l3.7-2.1z' fill='" + col + "'/>";
        else {
            const kind = p.slice(0, 1), parts = p.slice(2).split("|");
            const stroke = s => "<g fill='none' stroke='" + col + "' stroke-width='" + (kind === "t" ? Math.max(2.7, icon.weight + 0.9) : icon.weight) + "' stroke-linecap='round' stroke-linejoin='round'>" + s + "</g>";
            const fill = s => "<g fill='" + col + "' fill-rule='evenodd'>" + s + "</g>";
            body = (kind === "f" ? fill(parts[0]) : stroke(parts[0])) + (parts[1] ? fill(parts[1]) : "");
        }
        return "data:image/svg+xml;utf8," + encodeURIComponent("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>" + body + "</svg>");
    }
}
