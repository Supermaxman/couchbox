// The YouTube mark at the top right of the pages, and on Who's watching: a red rounded play
// button and the name beside it, both drawn here as vectors (a look-alike: tall, narrow, heavy
// letters like YouTube's own; none of YouTube's files). "Premium" for a Premium member.
import QtQuick

Row {
    id: logo
    property real h: 44 * Y.u                 // the play button's height
    property bool premium: false              // a Premium member's: "Premium" beside the button
    spacing: h * 0.16
    Image {                                   // the button: a rounded, slightly cushioned rectangle and a white triangle
        width: logo.h * 1.42
        height: logo.h
        anchors.verticalCenter: parent.verticalCenter
        sourceSize: Y.sz(width, height)
        smooth: true
        source: "data:image/svg+xml;utf8," + encodeURIComponent(
            "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 142 100'>"
            + "<path fill='" + Y.red + "' d='M71 2C35 2 16 4 10 8 4 13 2 30 2 50s2 37 8 42c6 4 25 6 61 6s55-2 61-6c6-5 8-22 8-42s-2-37-8-42C126 4 107 2 71 2z'/>"
            + "<path fill='#fff' d='M57 29v42l36-21z'/></svg>")
    }
    Image {                                   // the name, as strokes (letters, below)
        readonly property var word: logo.word(logo.premium ? "Premium" : "YouTube")
        height: logo.h * 0.92
        width: height * word.width / 20
        anchors.verticalCenter: parent.verticalCenter
        sourceSize: Y.sz(width, height)
        smooth: true
        source: "data:image/svg+xml;utf8," + encodeURIComponent(
            "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 " + word.width + " 20'>"
            + "<g fill='none' stroke='" + Y.text + "' stroke-width='3.3' stroke-linecap='butt' stroke-linejoin='round'>" + word.strokes + "</g>"
            + "<g fill='" + Y.text + "'>" + word.fills + "</g></svg>")
    }

    // the letters, cap height 20, x-height 12.6 (from y 7.4): [advance, strokes, fills]
    readonly property var letters: ({
        "Y": [9.4, "M1.4 1 L4.7 10.4 L8 1 M4.7 10.4 V20", ""],
        "T": [9.2, "M0.2 2.6 H9 M4.6 2.6 V20", ""],
        "o": [8.2, "M4.1 9.05 C2.4 9.05 1.65 10.2 1.65 12.4 V15.6 C1.65 17.8 2.4 18.35 4.1 18.35 C5.8 18.35 6.55 17.8 6.55 15.6 V12.4 C6.55 10.2 5.8 9.05 4.1 9.05 Z", ""],
        "u": [8.2, "M1.65 7.4 V15.6 C1.65 17.6 2.4 18.35 3.9 18.35 C5.6 18.35 6.55 17.4 6.55 15.2 M6.55 7.4 V20", ""],
        "b": [8.4, "M1.65 0 V20 M1.65 12 C1.65 10 2.6 9.05 4.2 9.05 C5.9 9.05 6.75 10.2 6.75 12.4 V15.6 C6.75 17.8 5.9 18.35 4.2 18.35 C2.6 18.35 1.65 17.4 1.65 15.6", ""],
        "e": [8.2, "M1.65 13.4 H6.55 V12.4 C6.55 10.2 5.8 9.05 4.1 9.05 C2.4 9.05 1.65 10.2 1.65 12.4 V15.6 C1.65 17.8 2.4 18.35 4.1 18.35 C5.5 18.35 6.3 17.7 6.55 16.3", ""],
        "P": [8.8, "M1.65 20 V2.6 H4.8 C6.6 2.6 7.3 3.7 7.3 6 V7.4 C7.3 9.7 6.6 10.8 4.8 10.8 H1.65", ""],
        "r": [6.2, "M1.65 20 V7.4 M1.65 12 C1.65 9.9 2.8 9.05 5.4 9.05", ""],
        "m": [12.4, "M1.65 20 V7.4 M1.65 11.6 C1.65 9.8 2.5 9.05 3.9 9.05 C5.4 9.05 6.2 9.8 6.2 11.6 V20 M6.2 11.6 C6.2 9.8 7.1 9.05 8.5 9.05 C10 9.05 10.75 9.8 10.75 11.6 V20", ""],
        "i": [3.3, "M1.65 7.4 V20", "<circle cx='1.65' cy='3.2' r='1.85'/>"]
    })
    function word(text) {
        let x = 0, strokes = "", fills = "";
        for (const ch of text) {
            const g = letters[ch];
            if (!g) continue;
            strokes += "<g transform='translate(" + x + " 0)'><path d='" + g[1] + "'/></g>";
            if (g[2]) fills += "<g transform='translate(" + x + " 0)'>" + g[2] + "</g>";
            x += g[0] + 0.5;
        }
        return {width: Math.max(1, x - 0.5), strokes: strokes, fills: fills};
    }
}
