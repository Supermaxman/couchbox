// A map: tiles from maps.py's relay (Google's or OpenStreetMap's), routes drawn on top, pins for
// the start and the end. With focus the remote moves it: arrows pan; OK switches to zooming
// (Up in, Down out) and back; Back leaves the map.
import QtQuick

FocusScope {
    id: map
    property real lat: 37.78
    property real lon: -122.42
    property int zoom: 12
    property int minZoom: 3
    property int maxZoom: 19
    property var routes: []                  // [{points: [[lat, lon], ...], chosen: bool}]
    property var pins: []                    // [{lat, lon, kind: "start" | "end" | "place"}]
    property bool zooming: false
    readonly property real tile: 300 * M.u   // a tile on screen (256 px tiles drawn a bit larger: read from the couch)
    readonly property string base: M.status.tiles || ""
    signal leave()

    clip: true
    Rectangle { anchors.fill: parent; color: "#1f2430" }

    // ------------------------------------------------------------------ projection
    function worldX(lo, z) { return (lo + 180) / 360 * Math.pow(2, z) * tile; }
    function worldY(la, z) {
        const r = Math.max(-85.05, Math.min(85.05, la)) * Math.PI / 180;
        return (1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2 * Math.pow(2, z) * tile;
    }
    function lonOf(x, z) { return x / (Math.pow(2, z) * tile) * 360 - 180; }
    function latOf(y, z) {
        const n = Math.PI - 2 * Math.PI * y / (Math.pow(2, z) * tile);
        return 180 / Math.PI * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n)));
    }
    readonly property real cx: worldX(lon, zoom)
    readonly property real cy: worldY(lat, zoom)
    function screen(la, lo) { return Qt.point(worldX(lo, zoom) - cx + width / 2, worldY(la, zoom) - cy + height / 2); }

    // fit a box {south, west, north, east} with some room around it
    function fit(b, pad) {
        if (!b || width <= 0) return;
        pad = pad === undefined ? 90 * M.u : pad;
        let z = maxZoom;
        for (; z > minZoom; z--) {
            const w = worldX(b.east, z) - worldX(b.west, z), h = worldY(b.south, z) - worldY(b.north, z);
            if (w <= width - 2 * pad && h <= height - 2 * pad) break;
        }
        zoom = Math.min(z, 17);
        lat = latOf((worldY(b.north, zoom) + worldY(b.south, zoom)) / 2, zoom);
        lon = lonOf((worldX(b.west, zoom) + worldX(b.east, zoom)) / 2, zoom);
    }
    function show(la, lo, z) { lat = la; lon = lo; if (z) zoom = z; }
    function pan(dx, dy) {
        lon = lonOf(cx + dx * width / 3, zoom);
        lat = latOf(Math.max(0, Math.min(Math.pow(2, zoom) * tile, cy + dy * height / 3)), zoom);
    }
    function zoomBy(d) { zoom = Math.max(minZoom, Math.min(maxZoom, zoom + d)); }

    Keys.onLeftPressed: zooming ? undefined : pan(-1, 0)
    Keys.onRightPressed: zooming ? undefined : pan(1, 0)
    Keys.onUpPressed: zooming ? zoomBy(1) : pan(0, -1)
    Keys.onDownPressed: zooming ? zoomBy(-1) : pan(0, 1)
    Keys.onReturnPressed: zooming = !zooming
    Keys.onEnterPressed: zooming = !zooming
    Keys.onEscapePressed: { zooming = false; leave(); }
    Keys.onBackPressed: { zooming = false; leave(); }
    onActiveFocusChanged: if (!activeFocus) zooming = false

    // ------------------------------------------------------------------ tiles
    readonly property var tiles: {
        if (!base || width <= 0 || height <= 0) return [];
        const n = Math.pow(2, zoom), left = cx - width / 2, top = cy - height / 2;
        const out = [];
        for (let ty = Math.floor(top / tile); ty <= Math.floor((top + height) / tile); ty++) {
            if (ty < 0 || ty >= n) continue;
            for (let tx = Math.floor(left / tile); tx <= Math.floor((left + width) / tile); tx++)
                out.push({url: base + "/" + zoom + "/" + (((tx % n) + n) % n) + "/" + ty, x: tx * tile - left, y: ty * tile - top});
        }
        return out;
    }
    Repeater {
        model: map.tiles
        delegate: Image {
            required property var modelData
            x: Math.round(modelData.x); y: Math.round(modelData.y)
            width: Math.ceil(map.tile); height: width
            source: modelData.url
            asynchronous: true
            smooth: true
            sourceSize: Qt.size(512, 512)
            opacity: status === Image.Ready ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 150 } }
        }
    }
    Rectangle {                                  // OpenStreetMap's tiles are light: dim them for the TV at night
        anchors.fill: parent
        visible: !M.status.google
        color: "#000000"; opacity: 0.18
    }

    // ------------------------------------------------------------------ routes and pins
    Canvas {
        id: lines
        anchors.fill: parent
        renderStrategy: Canvas.Cooperative
        onPaint: {
            const g = getContext("2d");
            g.reset();
            g.lineJoin = "round"; g.lineCap = "round";
            const draw = (pts, w, c) => {
                g.beginPath();
                for (let i = 0; i < pts.length; i++) {
                    const p = map.screen(pts[i][0], pts[i][1]);
                    if (i) g.lineTo(p.x, p.y); else g.moveTo(p.x, p.y);
                }
                g.lineWidth = w; g.strokeStyle = c; g.stroke();
            };
            const rs = map.routes || [];
            for (const r of rs) if (!r.chosen) { draw(r.points, 14 * M.u, "#141821"); draw(r.points, 9 * M.u, M.routeAlt); }
            for (const r of rs) if (r.chosen) { draw(r.points, 17 * M.u, "#0b1d3d"); draw(r.points, 11 * M.u, M.route); }
        }
    }
    onCxChanged: lines.requestPaint()
    onCyChanged: lines.requestPaint()
    onRoutesChanged: lines.requestPaint()
    onWidthChanged: lines.requestPaint()
    onHeightChanged: lines.requestPaint()

    Repeater {
        model: map.pins
        delegate: Item {
            required property var modelData
            readonly property point p: map.screen(modelData.lat, modelData.lon)
            x: p.x - width / 2; y: p.y - height
            width: 54 * M.u; height: 70 * M.u
            visible: p.x > -width && p.x < map.width + width && p.y > 0 && p.y < map.height + height
            Rectangle {
                visible: parent.modelData.kind === "start"
                anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: -13 * M.u }
                width: 26 * M.u; height: width; radius: width / 2
                color: "white"; border.color: M.route; border.width: 7 * M.u
            }
            Image {
                visible: parent.modelData.kind !== "start"
                anchors.fill: parent
                source: M.icon(parent.modelData.kind === "end" ? "pin-end" : "pin-place")
                sourceSize: Qt.size(width, height)
            }
        }
    }

    // ------------------------------------------------------------------ what the remote does here, and credit
    Rectangle {
        visible: map.activeFocus
        anchors { left: parent.left; top: parent.top; margins: 22 * M.u }
        width: hintRow.implicitWidth + 36 * M.u; height: 58 * M.u; radius: 12 * M.u
        color: "#e618181b"; border.color: M.line
        Row {
            id: hintRow
            anchors.centerIn: parent
            spacing: 22 * M.u
            Text { text: map.zooming ? "▲ zoom in   ▼ zoom out" : "◀ ▲ ▼ ▶ move"; color: M.text; font.family: M.font; font.pixelSize: M.tMeta }
            Text { text: map.zooming ? "OK: move" : "OK: zoom"; color: M.dim; font.family: M.font; font.pixelSize: M.tMeta }
            Text { text: "Back: done"; color: M.dim; font.family: M.font; font.pixelSize: M.tMeta }
        }
    }
    Rectangle {
        anchors.fill: parent
        color: "transparent"
        border.color: map.activeFocus ? M.focus : "transparent"
        border.width: M.ring
        radius: 2 * M.u
    }
    Rectangle {
        anchors { right: parent.right; bottom: parent.bottom }
        width: credit.implicitWidth + 20 * M.u; height: credit.implicitHeight + 8 * M.u
        color: "#cc09090b"
        Text { id: credit; anchors.centerIn: parent; text: M.status.attribution || ""; color: M.dim; font.family: M.font; font.pixelSize: 15 * M.u }
    }
}
