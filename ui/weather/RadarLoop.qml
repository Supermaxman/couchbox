// The weather pop-up's radar (couchbox-frigate-popup's Popup.qml): the frames radar.py's
// frames() gives (the last hour, and any forecast after it) as a loop over the dimmed map,
// centred on the town, as on the Radar page. A frame every half second, a pause on the newest;
// a frame whose tiles haven't all come in yet is skipped.
import QtQuick

Item {
    id: loop
    property var info: null                  // radar.py's frames(): source, frames, tiles, lat, lon
    property real u: 1
    property int zoom: 8
    property bool running: true
    property real textSize: 19 * u
    property bool showTime: true             // the frame's time, bottom left
    readonly property var frames: info ? info.frames : []
    readonly property var src: info ? info.source : null
    readonly property real tile: 256 * u     // a map tile on screen
    property int fi: 0
    property int hold: 0

    clip: true
    onInfoChanged: { fi = latest(); hold = 0; Qt.callLater(regrid); }
    onWidthChanged: Qt.callLater(regrid)
    onHeightChanged: Qt.callLater(regrid)

    function latest() {                      // the newest frame that isn't a forecast
        for (let i = frames.length - 1; i >= 0; i--) if (!frames[i].nowcast) return i;
        return Math.max(0, frames.length - 1);
    }
    function worldX(lo, z) { return (lo + 180) / 360 * Math.pow(2, z) * tile; }
    function worldY(la, z) {
        const r = Math.max(-85.05, Math.min(85.05, la)) * Math.PI / 180;
        return (1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2 * Math.pow(2, z) * tile;
    }
    function grid(z, size) {                 // tiles of `size` at zoom z covering the view: [{path, px, py}]
        if (!info || width <= 0 || height <= 0) return [];
        const left = worldX(info.lon, zoom) - width / 2, top = worldY(info.lat, zoom) - height / 2;
        const n = Math.pow(2, z), out = [];
        for (let ty = Math.floor(top / size); ty <= Math.floor((top + height) / size); ty++) {
            if (ty < 0 || ty >= n) continue;
            for (let tx = Math.floor(left / size); tx <= Math.floor((left + width) / size); tx++)
                out.push({path: z + "/" + (((tx % n) + n) % n) + "/" + ty, px: tx * size - left, py: ty * size - top});
        }
        return out;
    }
    readonly property int rz: src ? Math.max(0, Math.min(src.max_zoom, zoom - src.zoom_drop)) : 0
    readonly property real rsize: tile * Math.pow(2, zoom - rz)
    property var baseTiles: []
    property var radarTiles: []
    function regrid() { baseTiles = grid(zoom, tile); radarTiles = src ? grid(rz, rsize) : []; }

    Timer {
        interval: 500; repeat: true
        running: loop.running && loop.visible && loop.frames.length > 1
        onTriggered: {
            const last = loop.frames.length - 1;
            if (loop.fi === loop.latest() && loop.hold < 3) { loop.hold++; return; }
            loop.hold = 0;
            for (let k = 1; k <= last + 1; k++) {        // the next frame that's in
                const i = (loop.fi + k) % (last + 1), f = frameRep.itemAt(i);
                if (f && f.ready()) { loop.fi = i; return; }
            }
        }
    }

    Rectangle { anchors.fill: parent; color: "#14161b" }
    Repeater {                                   // the map
        model: loop.baseTiles
        delegate: Image {
            required property var modelData
            x: Math.round(modelData.px); y: Math.round(modelData.py)
            width: Math.ceil(loop.tile); height: width
            source: loop.info ? loop.info.tiles + "/base/" + modelData.path : ""
            asynchronous: true
            sourceSize: Qt.size(256, 256)
        }
    }
    Rectangle { anchors.fill: parent; color: "#09090b"; opacity: 0.62 }   // dimmed, so the rain stands out
    Repeater {                                   // the frames, one shown at a time
        id: frameRep
        model: loop.frames
        delegate: Item {
            id: frame
            required property var modelData
            required property int index
            anchors.fill: parent
            visible: index === loop.fi
            opacity: 0.85
            function ready() {
                if (tileRep.count !== loop.radarTiles.length) return false;
                for (let i = 0; i < tileRep.count; i++) {
                    const im = tileRep.itemAt(i);
                    if (!im || im.status === Image.Loading || im.status === Image.Null) return false;
                }
                return true;
            }
            Repeater {
                id: tileRep
                model: loop.radarTiles
                delegate: Image {
                    required property var modelData
                    x: Math.round(modelData.px); y: Math.round(modelData.py)
                    width: Math.ceil(loop.rsize); height: width
                    source: loop.src ? loop.info.tiles + "/radar/" + loop.src.id + "/" + frame.modelData.id + "/" + modelData.path : ""
                    asynchronous: true
                    smooth: true
                    sourceSize: Qt.size(loop.src.tile_px, loop.src.tile_px)
                }
            }
        }
    }
    Item {                                       // home
        visible: !!loop.info
        anchors.centerIn: parent
        width: 18 * loop.u; height: width
        Rectangle { anchors.centerIn: parent; width: parent.width + 10 * loop.u; height: width; radius: width / 2; color: Qt.rgba(0.22, 0.74, 0.97, 0.25) }
        Rectangle { anchors.fill: parent; radius: width / 2; color: "white"; border.color: "#38bdf8"; border.width: 4 * loop.u }
    }
    Text {                                       // the frame's time
        readonly property var f: loop.frames[loop.fi] || null
        visible: !!f && loop.showTime
        anchors { left: parent.left; bottom: parent.bottom; margins: 12 * loop.u }
        text: f ? f.label + (f.nowcast ? "  forecast" : "") : ""
        color: f && f.nowcast ? "#fbbf24" : "white"
        font.family: "Inter"; font.pixelSize: loop.textSize; font.weight: Font.DemiBold
        style: Text.Outline; styleColor: "#a0000000"
    }
}
