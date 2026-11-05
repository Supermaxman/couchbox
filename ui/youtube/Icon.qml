// An icon in any colour: a small SVG (24x24, drawn here) handed to Image as a data: address, so
// one drawing serves the white, grey and dark (on a focused, white row) versions.
//   Icon { name: "search"; color: Y.text; size: 40 * Y.u }
import QtQuick

Image {
    id: icon
    property string name: ""
    property color color: Y.text
    property real size: 40 * Y.u
    property bool filled: false              // the selected guide entry: the filled drawing, if there is one
    width: size
    height: size
    sourceSize: Y.sz(size, size)
    smooth: true
    // stroked drawings ("s") and filled ones ("f"); a "|" joins a stroked part and a filled part
    readonly property var paths: ({
        search: "s:<circle cx='10.5' cy='10.5' r='6.5'/><path d='M15.3 15.3 20.5 20.5'/>",
        home: "s:<path d='M4 10.5 12 4l8 6.5V20h-5.5v-5.5h-5V20H4z'/>",
        "home-filled": "f:<path d='M3.5 10.5 12 3.5l8.5 7V20.5h-6v-6h-5v6h-6z'/>",
        shorts: "s:<path d='M14.6 3.6 7.4 7.5a3.5 3.5 0 0 0 .3 6.3l.9.4-1.3.7a3.5 3.5 0 0 0 3.3 6.2l7.2-3.9a3.5 3.5 0 0 0-.3-6.3l-.9-.4 1.3-.7a3.5 3.5 0 0 0-3.3-6.2z'/>|<path d='M10.4 9.6v4.8l4.1-2.4z'/>",
        subscriptions: "s:<rect x='3.5' y='7.5' width='17' height='12.5' rx='1.5'/><path d='M6.5 4.5h11'/><path d='M10.5 10.8v5.9l4.8-2.95z'/>",
        library: "s:<rect x='7.5' y='3.5' width='13' height='13' rx='1.5'/><path d='M4.5 7.5v12a1 1 0 0 0 1 1h12'/><path d='M12.2 7.4v5.7l4.5-2.85z'/>",
        gaming: "s:<path d='M7.6 6.5h8.8a4.6 4.6 0 0 1 4.5 5.5l-.9 4.4a2.6 2.6 0 0 1-4.4 1.3L13.9 16h-3.8l-1.7 1.7A2.6 2.6 0 0 1 4 16.4L3.1 12a4.6 4.6 0 0 1 4.5-5.5z'/><path d='M8 9.6v4M6 11.6h4'/>|<circle cx='15.5' cy='10.5' r='1'/><circle cx='17.3' cy='12.7' r='1'/>",
        news: "s:<rect x='3.5' y='5' width='17' height='14' rx='1.5'/><rect x='6.5' y='8.5' width='5' height='4'/><path d='M14 9h3.5M14 12h3.5M6.5 15.5h11'/>",
        podcasts: "s:<circle cx='12' cy='10.5' r='2.2'/><path d='M12 14v6.5'/><path d='M8.3 14.5a5.4 5.4 0 1 1 7.4 0'/><path d='M6 17.3a8.6 8.6 0 1 1 12 0'/>",
        movies: "s:<rect x='3.5' y='9' width='17' height='11' rx='1.5'/><rect x='3.5' y='4.5' width='17' height='4.5' rx='1'/><path d='M8.2 4.5 6.8 9M13.2 4.5 11.8 9M18.2 4.5 16.8 9'/>",
        live: "s:<circle cx='12' cy='12' r='2'/><path d='M8.6 8.6a4.8 4.8 0 0 0 0 6.8M15.4 8.6a4.8 4.8 0 0 1 0 6.8M5.8 5.8a8.8 8.8 0 0 0 0 12.4M18.2 5.8a8.8 8.8 0 0 1 0 12.4'/>",
        sports: "s:<path d='M7.5 4h9v5a4.5 4.5 0 0 1-9 0z'/><path d='M7.5 6H4.5v1.5a3 3 0 0 0 3 3M16.5 6h3v1.5a3 3 0 0 1-3 3'/><path d='M12 13.5V17M9.5 17h5v3h-5z'/>",
        settings: "s:<path d='M18.83 10.47 L21.12 10.81 L21.12 13.19 L18.83 13.53 L17.91 15.75 L19.29 17.61 L17.61 19.29 L15.75 17.91 L13.53 18.83 L13.19 21.12 L10.81 21.12 L10.47 18.83 L8.25 17.91 L6.39 19.29 L4.71 17.61 L6.09 15.75 L5.17 13.53 L2.88 13.19 L2.88 10.81 L5.17 10.47 L6.09 8.25 L4.71 6.39 L6.39 4.71 L8.25 6.09 L10.47 5.17 L10.81 2.88 L13.19 2.88 L13.53 5.17 L15.75 6.09 L17.61 4.71 L19.29 6.39 L17.91 8.25Z'/><circle cx='12' cy='12' r='3'/>",
        person: "s:<circle cx='12' cy='8.5' r='3.5'/><path d='M5 19.5a7 7 0 0 1 14 0'/>",
        history: "s:<path d='M4.6 12a7.4 7.4 0 1 0 2.2-5.3'/><path d='M4.4 4.2v3.7h3.7'/><path d='M12 8v4.5l3 1.8'/>",
        back: "s:<path d='M19 12H5.5M11 6l-6 6 6 6'/>",
        backspace: "s:<path d='M9 5h10.5a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H9l-6-7z'/><path d='M12 9.5l5 5M17 9.5l-5 5'/>",
        globe: "s:<circle cx='12' cy='12' r='8.5'/><path d='M3.5 12h17M12 3.5c2.4 2.5 3.4 5.4 3.4 8.5s-1 6-3.4 8.5c-2.4-2.5-3.4-5.4-3.4-8.5s1-6 3.4-8.5z'/>",
        bell: "s:<path d='M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 1.8h-15z'/><path d='M10 20.5a2 2 0 0 0 4 0'/>",
        prev: "f:<path d='M5.5 5h2.2v14H5.5z'/><path d='M19 5v14L9 12z'/>",
        next: "f:<path d='M16.3 5h2.2v14h-2.2z'/><path d='M5 5v14l10-7z'/>",
        play: "f:<path d='M7.5 4.5v15l12-7.5z'/>",
        pause: "f:<path d='M6.5 4.5h4v15h-4zM13.5 4.5h4v15h-4z'/>",
        like: "s:<path d='M7.5 10.5v9.5h-3v-9.5z'/><path d='M7.5 10.5l3.8-6.6a1.9 1.9 0 0 1 3.5 1.4L14 10h4.7a2 2 0 0 1 2 2.4l-1.3 6a2 2 0 0 1-2 1.6H7.5'/>",
        "like-filled": "f:<path d='M3.5 10h4v10.5h-4z'/><path d='M8.5 20.5V10l3.6-6.3a2 2 0 0 1 3.7 1.5L15 9.5h3.8a2.2 2.2 0 0 1 2.1 2.7l-1.4 6.5a2.3 2.3 0 0 1-2.2 1.8z'/>",
        dislike: "s:<g transform='rotate(180 12 12)'><path d='M7.5 10.5v9.5h-3v-9.5z'/><path d='M7.5 10.5l3.8-6.6a1.9 1.9 0 0 1 3.5 1.4L14 10h4.7a2 2 0 0 1 2 2.4l-1.3 6a2 2 0 0 1-2 1.6H7.5'/></g>",
        comments: "s:<path d='M4 4.5h16v11.5H8.5L4 20z'/><path d='M8 8.5h8M8 12h5'/>",
        sparkle: "f:<path d='M12 2.5c.7 4.6 2.9 6.8 9.5 9.5-6.6 2.7-8.8 4.9-9.5 9.5-.7-4.6-2.9-6.8-9.5-9.5 6.6-2.7 8.8-4.9 9.5-9.5z'/>",
        "ask": "s:<path d='M18.5 12.5a7 7 0 1 1-4-6.3'/><path d='M8.5 19l-3 2.5v-4'/>|<path d='M18.5 2.5c.3 1.9 1.2 2.8 4 4-2.8 1.2-3.7 2.1-4 4-.3-1.9-1.2-2.8-4-4 2.8-1.2 3.7-2.1 4-4z'/>",
        save: "s:<path d='M6.5 4h11v16.5L12 16.6l-5.5 3.9z'/>",
        thanks: "s:<path d='M12 20s-8-4.7-8-10.2A4.3 4.3 0 0 1 12 7.3a4.3 4.3 0 0 1 8 2.5C20 15.3 12 20 12 20z'/><path d='M13.8 10.4c-.3-.6-1-1-1.8-1-1 0-1.8.6-1.8 1.4 0 1.9 3.6 1 3.6 2.9 0 .8-.8 1.4-1.8 1.4-.8 0-1.5-.4-1.8-1M12 8.3v1.1M12 14.9v1.1'/>",
        cc: "s:<rect x='3' y='5.5' width='18' height='13' rx='2'/><path d='M10.4 10.3a2.1 2.1 0 1 0 0 3.4M16.4 10.3a2.1 2.1 0 1 0 0 3.4'/>",
        check: "s:<path d='M5 12.5l4.5 4.5L19 7.5'/>",
        mic: "s:<rect x='9' y='3.5' width='6' height='11' rx='3'/><path d='M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3'/>",
        list: "s:<path d='M9 6.5h11M9 12h11M9 17.5h11'/>|<circle cx='4.8' cy='6.5' r='1.3'/><circle cx='4.8' cy='12' r='1.3'/><circle cx='4.8' cy='17.5' r='1.3'/>",
        "bell-all": "s:<path d='M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 1.8h-15z'/><path d='M10 20.5a2 2 0 0 0 4 0'/><path d='M3.5 8.5a8 8 0 0 1 2.6-4.6M20.5 8.5a8 8 0 0 0-2.6-4.6'/>",
        "bell-filled": "f:<path d='M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 1.8h-15z'/><path d='M9.8 20.2h4.4a2.2 2.2 0 0 1-4.4 0z'/>",
        "bell-off": "s:<path d='M8.2 6.1A6 6 0 0 1 18 11v4.2M6 11v5.5l-1.5 1.8h12'/><path d='M10 20.5a2 2 0 0 0 4 0'/><path d='M3.5 3.5l17 17'/>",
        unsubscribe: "s:<circle cx='10' cy='8.5' r='3.5'/><path d='M3.5 19.5a6.5 6.5 0 0 1 10.5-5.1'/><path d='M16.5 15.5l4 4M20.5 15.5l-4 4'/>",
        "dislike-filled": "f:<g transform='rotate(180 12 12)'><path d='M3.5 10h4v10.5h-4z'/><path d='M8.5 20.5V10l3.6-6.3a2 2 0 0 1 3.7 1.5L15 9.5h3.8a2.2 2.2 0 0 1 2.1 2.7l-1.4 6.5a2.3 2.3 0 0 1-2.2 1.8z'/></g>",
        "save-filled": "f:<path d='M6.5 4h11v16.5L12 16.6l-5.5 3.9z'/>",
        plus: "s:<path d='M12 5v14M5 12h14'/>",
        lock: "s:<rect x='5.5' y='10.5' width='13' height='10' rx='1.5'/><path d='M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5'/>",
        chevron: "s:<path d='M9 5.5l6.5 6.5L9 18.5'/>",
        heart: "s:<path d='M12 20s-8-4.7-8-10.2A4.3 4.3 0 0 1 12 7.3a4.3 4.3 0 0 1 8 2.5C20 15.3 12 20 12 20z'/>",
        "heart-filled": "f:<path d='M12 20.5s-8.5-5-8.5-10.8a4.6 4.6 0 0 1 8.5-2.6 4.6 4.6 0 0 1 8.5 2.6c0 5.8-8.5 10.8-8.5 10.8z'/>",
        remix: "s:<path d='M5 12a7 7 0 0 1 12-4.9L19 9M19 12a7 7 0 0 1-12 4.9L5 15'/><path d='M19 4.5V9h-4.5M5 19.5V15h4.5M12 9v6M9 12h6'/>",
        more: "f:<circle cx='12' cy='5.5' r='1.8'/><circle cx='12' cy='12' r='1.8'/><circle cx='12' cy='18.5' r='1.8'/>",
        speed: "s:<path d='M4.6 17a8.5 8.5 0 1 1 14.8 0'/><path d='M12 13l4-5'/>|<circle cx='12' cy='13' r='1.6'/>",
        "cc-filled": "f:<path d='M5 5.5h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2zm5.4 4.3a2.6 2.6 0 0 0-3.9 2.2 2.6 2.6 0 0 0 3.9 2.2l-.8-1.2a1.2 1.2 0 0 1-1.7-1 1.2 1.2 0 0 1 1.7-1zm6 0a2.6 2.6 0 0 0-3.9 2.2 2.6 2.6 0 0 0 3.9 2.2l-.8-1.2a1.2 1.2 0 0 1-1.7-1 1.2 1.2 0 0 1 1.7-1z'/>",
        music: "m"
    })
    function svg(name, c) {
        const p = paths[name] || "";
        const col = String(c);
        let body;
        if (p === "m")                       // YouTube Music's mark keeps its own red
            body = "<circle cx='12' cy='12' r='9.5' fill='#ff0033'/><circle cx='12' cy='12' r='5.2' fill='none' stroke='#fff' stroke-width='1.3'/>"
                 + "<path d='M10.4 9.6v4.8l4.1-2.4z' fill='#fff'/>";
        else {
            const kind = p.slice(0, 1), parts = p.slice(2).split("|");
            const stroke = s => "<g fill='none' stroke='" + col + "' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'>" + s + "</g>";
            const fill = s => "<g fill='" + col + "'>" + s + "</g>";
            body = (kind === "f" ? fill(parts[0]) : stroke(parts[0])) + (parts[1] ? fill(parts[1]) : "");
        }
        return "data:image/svg+xml;utf8," + encodeURIComponent("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>" + body + "</svg>");
    }
    source: name ? svg(filled && paths[name + "-filled"] ? name + "-filled" : name, color) : ""
}
