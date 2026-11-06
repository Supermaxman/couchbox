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
        height: logo.h * 0.9
        width: height * word.width / 20 * 1.15     // (a little wider than drawn: YouTube's mark is 208 x 43 with Premium)
        anchors.verticalCenter: parent.verticalCenter
        sourceSize: Y.sz(width, height)
        smooth: true
        source: "data:image/svg+xml;utf8," + encodeURIComponent(
            "<svg xmlns='http://www.w3.org/2000/svg' preserveAspectRatio='none' viewBox='0 0 " + word.width + " 20'>"
            + "<g fill='none' stroke='" + Y.text + "' stroke-width='2.6' stroke-linecap='butt' stroke-linejoin='round'>" + word.strokes + "</g>"
            + "<g fill='" + Y.text + "'>" + word.fills + "</g></svg>")
    }

    // the letters, cap height 20, x-height 12.6 (from y 7.4), strokes 2.6 wide: [advance, strokes,
    // fills]. Capitals are filled shapes (square ends), the rounds slightly squared like YouTube's.
    readonly property var letters: ({
        "Y": [9.4, "", "<path d='M0 0H2.9L4.7 6.2 6.5 0H9.4L6 11.3V20H3.4V11.3Z'/>"],
        "T": [9.0, "", "<path d='M0 0H9V2.6H5.8V20H3.2V2.6H0Z'/>"],
        "o": [8.0, "M4 8.7C1.9 8.7 1.3 9.7 1.3 11.8V15.6C1.3 17.7 1.9 18.7 4 18.7S6.7 17.7 6.7 15.6V11.8C6.7 9.7 6.1 8.7 4 8.7Z", ""],
        "u": [8.0, "M1.3 7.4V15.6C1.3 17.7 2 18.7 3.6 18.7 5.4 18.7 6.7 17.5 6.7 15.4M6.7 7.4V20", ""],
        "b": [8.0, "M1.3 11.8C1.3 9.8 2.6 8.7 4.4 8.7 6.1 8.7 6.7 9.7 6.7 11.8V15.6C6.7 17.7 6.1 18.7 4.4 18.7 2.6 18.7 1.3 17.6 1.3 15.6", "<path d='M0 0H2.6V20H0Z'/>"],
        "e": [8.0, "M1.3 13.3H6.7V11.8C6.7 9.7 6.1 8.7 4 8.7S1.3 9.7 1.3 11.8V15.6C1.3 17.7 1.9 18.7 4 18.7 5.7 18.7 6.5 17.9 6.7 16.3", ""],
        "P": [8.6, "M1.3 1.3H4.6C6.6 1.3 7.3 2.4 7.3 4.6V7.2C7.3 9.4 6.6 10.5 4.6 10.5H1.3", "<path d='M0 0H2.6V20H0Z'/>"],
        "r": [6.0, "M1.3 12.2C1.3 9.8 2.6 8.7 5.6 8.7", "<path d='M0 7.4H2.6V20H0Z'/>"],
        "m": [12.4, "M1.3 11.6C1.3 9.6 2.2 8.7 3.8 8.7S6.2 9.6 6.2 11.6V20M6.2 11.6C6.2 9.6 7.1 8.7 8.7 8.7S11.1 9.6 11.1 11.6V20", "<path d='M0 7.4H2.6V20H0Z'/>"],
        "i": [2.6, "", "<path d='M0 7.4H2.6V20H0Z'/><circle cx='1.3' cy='3.3' r='1.65'/>"]
    })
    function word(text) {
        let x = 0, strokes = "", fills = "";
        for (const ch of text) {
            const g = letters[ch];
            if (!g) continue;
            if (g[1]) strokes += "<g transform='translate(" + x + " 0)'><path d='" + g[1] + "'/></g>";
            if (g[2]) fills += "<g transform='translate(" + x + " 0)'>" + g[2] + "</g>";
            x += g[0] + 0.8;
        }
        return {width: Math.max(1, x - 0.8), strokes: strokes, fills: fills};
    }
}
