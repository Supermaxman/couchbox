// CouchKit PlayerIcon: the player controls' icons, drawn here (small 24x24 SVGs handed to Image
// as data: addresses), so they look the same in every app and in any colour, whatever fonts
// the box has (text glyphs and emoji came out differently per font).
//   PlayerIcon { name: "pause"; color: "white"; size: 40 * u }
// Two Images, one shown: a new drawing (another colour, play <-> pause) loads into the hidden
// one and is swapped in once it's ready, so the icon never blinks out while it changes.
import QtQuick
import QtQuick.Window

Item {
    id: icon
    property string name: ""
    property color color: "white"
    property real size: 40
    property real weight: 1.8                // the stroke, in the drawing's 24ths
    width: size
    height: size

    // "s:" stroked, "f:" filled (holes by even-odd); a "|" joins a stroked part and a filled part
    readonly property var paths: ({
        play: "f:<path d='M7.5 4.5v15l12-7.5z'/>",
        pause: "f:<path d='M6.5 4.5h4v15h-4zM13.5 4.5h4v15h-4z'/>",
        prev: "f:<path d='M5.5 5h2.2v14H5.5z'/><path d='M19 5v14L9 12z'/>",
        next: "f:<path d='M16.3 5h2.2v14h-2.2z'/><path d='M5 5v14l10-7z'/>",
        replay: "s:<path d='M4.6 12a7.4 7.4 0 1 0 2.2-5.3'/><path d='M4.4 4.2v3.7h3.7'/>",
        cc: "s:<rect x='3' y='5.5' width='18' height='13' rx='3'/><path d='M10.3 10.4a2 2 0 1 0 0 3.2M16.3 10.4a2 2 0 1 0 0 3.2'/>",
        chat: "s:<path d='M6 4.5h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H9.5L5 20.2V6.5a2 2 0 0 1 1-1.75'/><path d='M8.5 9h7M8.5 12.2h4.5'/>",
        write: "s:<path d='M4.5 19.5l.9-4.1L16 4.8a1.7 1.7 0 0 1 2.4 0l.8.8a1.7 1.7 0 0 1 0 2.4L8.6 18.6z'/><path d='M14.2 6.6l3.2 3.2'/>",
        heart: "s:<path d='M12 20s-8-4.7-8-10.2A4.3 4.3 0 0 1 12 7.3a4.3 4.3 0 0 1 8 2.5C20 15.3 12 20 12 20z'/>",
        "heart-filled": "f:<path d='M12 20.5s-8.5-5-8.5-10.8a4.6 4.6 0 0 1 8.5-2.6 4.6 4.6 0 0 1 8.5 2.6c0 5.8-8.5 10.8-8.5 10.8z'/>"
    })

    readonly property real dpr: Screen.devicePixelRatio || 1
    readonly property string source: name && paths[name] ? svg(paths[name], color) : ""
    property int front: 0                    // which Image is shown
    property string srcA: ""
    property string srcB: ""
    onSourceChanged: show()
    Component.onCompleted: show()
    function show() {
        if ((front === 0 ? srcA : srcB) === source) {       // back to what's shown: drop what was loading
            if (front === 0) srcB = ""; else srcA = "";
            return;
        }
        if (front === 0) srcB = source; else srcA = source;
        settle();
    }
    function settle() {                      // the hidden one is ready with the wanted drawing: show it
        const back = front === 0 ? imgB : imgA, bsrc = front === 0 ? srcB : srcA;
        if (bsrc === source && (back.status === Image.Ready || !source)) front = 1 - front;
    }
    function svg(p, c) {
        const col = String(c);
        const kind = p.slice(0, 1), parts = p.slice(2).split("|");
        const stroke = s => "<g fill='none' stroke='" + col + "' stroke-width='" + icon.weight + "' stroke-linecap='round' stroke-linejoin='round'>" + s + "</g>";
        const fill = s => "<g fill='" + col + "' fill-rule='evenodd'>" + s + "</g>";
        const body = (kind === "f" ? fill(parts[0]) : stroke(parts[0])) + (parts[1] ? fill(parts[1]) : "");
        return "data:image/svg+xml;utf8," + encodeURIComponent("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>" + body + "</svg>");
    }
    Image {
        id: imgA
        anchors.fill: parent
        sourceSize: Qt.size(Math.ceil(icon.size * icon.dpr), Math.ceil(icon.size * icon.dpr))
        smooth: true
        source: icon.srcA
        visible: icon.front === 0
        onStatusChanged: icon.settle()
    }
    Image {
        id: imgB
        anchors.fill: parent
        sourceSize: Qt.size(Math.ceil(icon.size * icon.dpr), Math.ceil(icon.size * icon.dpr))
        smooth: true
        source: icon.srcB
        visible: icon.front === 1
        onStatusChanged: icon.settle()
    }
}
