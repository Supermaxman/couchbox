// The rain radar: the last two hours (and what's coming, when the source has it) as a loop over
// a dimmed map, around the town. OK plays and pauses, Left/Right step a frame, Up/Down zoom,
// Back goes to the sidebar. Tiles come from radar.py's relay, newest frame first; the loop plays
// what's in and grows as the older frames arrive. New frames every five minutes.
import QtQuick

FocusScope {
    id: page
    property var info: null                  // radar.py's frames(): source, frames, tiles, lat, lon, name
    property string problem: ""
    property int zoom: 8
    readonly property int minZoom: 4
    readonly property int maxZoom: 10
    property int fi: 0                       // the frame shown
    property bool playing: true
    property int loaded: 0                   // frames in, counting back from the newest
    property real now: Date.now() / 1000
    readonly property var frames: info ? info.frames : []
    readonly property var src: info ? info.source : null
    readonly property int first: Math.max(0, frames.length - Math.max(1, loaded))   // the oldest frame in
    readonly property real tile: 288 * W.u   // a map tile on screen (256 px drawn a bit larger)

    function load(force) {
        W.call("radar", {force: !!force}, d => {
            problem = "";
            loaded = 0;
            info = d;
            fi = latest();
        }, e => { if (!info) problem = e; });
    }
    function latest() {                      // the newest frame that isn't a forecast
        for (let i = frames.length - 1; i >= 0; i--) if (!frames[i].nowcast) return i;
        return Math.max(0, frames.length - 1);
    }
    onVisibleChanged: if (visible && !info) load(false)
    Timer { interval: 5 * 60 * 1000; repeat: true; running: page.visible; onTriggered: page.load(false) }

    Keys.onReturnPressed: playing = !playing
    Keys.onEnterPressed: playing = !playing
    Keys.onLeftPressed: { playing = false; fi = Math.max(0, fi - 1); }
    Keys.onRightPressed: { playing = false; fi = Math.min(frames.length - 1, fi + 1); }
    Keys.onUpPressed: setZoom(zoom + 1)
    Keys.onDownPressed: setZoom(zoom - 1)
    function setZoom(z) {
        z = Math.max(minZoom, Math.min(maxZoom, z));
        if (z === zoom) return;
        zoom = z;
    }

    // the loop: a frame every half second, a pause on the newest
    property int hold: 0
    Timer {
        interval: 500; repeat: true
        running: page.visible && page.playing && page.frames.length > 1
        onTriggered: {
            page.now = Date.now() / 1000;
            if (page.fi === page.frames.length - 1 && page.hold < 3) { page.hold++; return; }
            page.hold = 0;
            page.fi = page.fi >= page.frames.length - 1 ? page.first : page.fi + 1;
        }
    }

    // ------------------------------------------------------------------ projection (as Maps)
    function worldX(lo, z) { return (lo + 180) / 360 * Math.pow(2, z) * tile; }
    function worldY(la, z) {
        const r = Math.max(-85.05, Math.min(85.05, la)) * Math.PI / 180;
        return (1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2 * Math.pow(2, z) * tile;
    }
    // tiles of size `size` on screen at zoom z covering the page, centred on the town: [{path, px, py}]
    function grid(z, size) {
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
    // radar tiles a zoom or two out from the map's (fewer requests; the data is coarser anyway)
    readonly property int rz: src ? Math.max(0, Math.min(src.max_zoom, zoom - src.zoom_drop)) : 0
    readonly property real rsize: tile * Math.pow(2, zoom - rz)
    // worked out once things settle (not on each of the changes a new frame list or zoom makes)
    property var baseTiles: []
    property var radarTiles: []
    function regrid() { baseTiles = grid(zoom, tile); radarTiles = src ? grid(rz, rsize) : []; }
    onInfoChanged: Qt.callLater(regrid)
    onZoomChanged: Qt.callLater(regrid)
    onWidthChanged: Qt.callLater(regrid)
    onHeightChanged: Qt.callLater(regrid)
    onTileChanged: Qt.callLater(regrid)
    onRadarTilesChanged: loaded = 0

    clip: true
    Rectangle { anchors.fill: parent; color: "#14161b" }

    Item {                                       // the map
        anchors.fill: parent
        Repeater {
            model: page.baseTiles
            delegate: Image {
                required property var modelData
                x: Math.round(modelData.px); y: Math.round(modelData.py)
                width: Math.ceil(page.tile); height: width
                source: page.info ? page.info.tiles + "/base/" + modelData.path : ""
                asynchronous: true
                sourceSize: Qt.size(256, 256)
                opacity: status === Image.Ready ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: 150 } }
            }
        }
    }

    Rectangle {                                  // OpenStreetMap's tiles are light: dim them so the rain stands out
        anchors.fill: parent
        color: "#09090b"; opacity: 0.62
    }

    Repeater {                                   // the frames, one shown at a time
        id: frameRep
        model: page.frames
        delegate: Item {
            id: frame
            required property var modelData
            required property int index
            readonly property bool wanted: index === page.fi || index >= page.frames.length - page.loaded - 1
            anchors.fill: parent
            visible: index === page.fi
            opacity: 0.85
            function ready() {
                if (tileRep.count !== page.radarTiles.length) return false;
                for (let i = 0; i < tileRep.count; i++) {
                    const im = tileRep.itemAt(i);
                    if (!im || im.status === Image.Loading || im.status === Image.Null) return false;
                }
                return true;
            }
            Repeater {
                id: tileRep
                model: page.radarTiles
                delegate: Image {
                    required property var modelData
                    x: Math.round(modelData.px); y: Math.round(modelData.py)
                    width: Math.ceil(page.rsize); height: width
                    source: frame.wanted && page.src ? page.info.tiles + "/radar/" + page.src.id + "/" + frame.modelData.id + "/" + modelData.path : ""
                    asynchronous: true
                    smooth: true
                    sourceSize: Qt.size(page.src ? page.src.tile_px : 256, page.src ? page.src.tile_px : 256)
                }
            }
        }
    }
    Timer {                                      // the next frame back once this one is in
        interval: 250; repeat: true
        running: page.visible && page.loaded < page.frames.length
        onTriggered: {
            const f = frameRep.itemAt(page.frames.length - 1 - page.loaded);
            if (f && f.ready()) page.loaded++;
        }
    }

    Item {                                       // home
        visible: !!page.info
        x: page.width / 2 - width / 2; y: page.height / 2 - height / 2
        width: 30 * W.u; height: width
        Rectangle { anchors.centerIn: parent; width: parent.width + 14 * W.u; height: width; radius: width / 2; color: Qt.rgba(0.22, 0.74, 0.97, 0.25) }
        Rectangle { anchors.fill: parent; radius: width / 2; color: "white"; border.color: W.accent; border.width: 7 * W.u }
    }

    // ------------------------------------------------------------------ what's on the map
    Rectangle {                                  // the frame: time, the loop, play or paused
        id: card
        visible: !!page.info
        x: 40 * W.u; y: 40 * W.u
        width: 560 * W.u; height: cardCol.implicitHeight + 52 * W.u
        radius: W.radius
        color: Qt.rgba(0.04, 0.04, 0.05, 0.86)
        border.color: page.activeFocus ? W.line : "transparent"
        readonly property var f: page.frames[page.fi] || null
        Column {
            id: cardCol
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 28 * W.u; topMargin: 24 * W.u }
            spacing: 12 * W.u
            Row {
                spacing: 16 * W.u
                Text { id: rtitle; text: "Radar"; color: W.text; font.family: W.font; font.pixelSize: W.tTitle; font.weight: Font.Bold }
                Text {
                    anchors.baseline: rtitle.baseline
                    width: cardCol.width - rtitle.width - 16 * W.u
                    text: page.info ? page.info.name : ""
                    color: W.dim; font.family: W.font; font.pixelSize: W.tMeta; elide: Text.ElideRight
                }
            }
            Row {
                spacing: 18 * W.u
                Text { id: when; text: card.f ? card.f.label : ""; color: W.text; font.family: W.font; font.pixelSize: 54 * W.u; font.weight: Font.DemiBold }
                Text {
                    anchors.baseline: when.baseline
                    text: {
                        if (!card.f) return "";
                        const m = Math.round((card.f.time - page.now) / 60);
                        if (card.f.nowcast) return "forecast, in " + m + " min";
                        return m >= -2 ? "just now" : -m < 60 ? -m + " min ago" : Math.floor(-m / 60) + " h " + (-m % 60) + " min ago";
                    }
                    color: card.f && card.f.nowcast ? W.warm : W.dim; font.family: W.font; font.pixelSize: W.tBody
                }
            }
            Item {                               // the loop: a tick a frame
                width: parent.width; height: 34 * W.u
                Image {
                    id: playIcon
                    anchors.verticalCenter: parent.verticalCenter
                    width: 30 * W.u; height: width; sourceSize: W.sz(width, height)
                    source: W.glyph(page.playing ? "pause" : "play")
                }
                Row {
                    anchors { left: playIcon.right; leftMargin: 18 * W.u; right: parent.right; verticalCenter: parent.verticalCenter }
                    spacing: 4 * W.u
                    Repeater {
                        model: page.frames
                        delegate: Rectangle {
                            required property var modelData
                            required property int index
                            width: (cardCol.width - 48 * W.u - 4 * W.u * (page.frames.length - 1)) / Math.max(1, page.frames.length)
                            height: index === page.fi ? 18 * W.u : 8 * W.u
                            anchors.verticalCenter: parent.verticalCenter
                            radius: 3 * W.u
                            color: index === page.fi ? W.accent : modelData.nowcast ? W.warm : W.text2
                            opacity: index === page.fi ? 1 : index >= page.first ? 0.55 : 0.18
                        }
                    }
                }
            }
        }
    }

    Rectangle {                                  // keys
        visible: !!page.info
        anchors { right: parent.right; top: parent.top; margins: 40 * W.u }
        width: keysText.implicitWidth + 44 * W.u; height: 58 * W.u; radius: 29 * W.u
        color: Qt.rgba(0.04, 0.04, 0.05, 0.8)
        Text {
            id: keysText
            anchors.centerIn: parent
            text: "OK " + (page.playing ? "pause" : "play") + "   ◀ ▶ step   ▲ ▼ zoom"
            color: W.text2; font.family: W.font; font.pixelSize: W.tMeta
        }
    }

    Rectangle {                                  // the legend and where the pictures come from
        visible: !!page.src
        anchors { left: parent.left; bottom: parent.bottom; margins: 40 * W.u }
        width: 560 * W.u; height: legendCol.implicitHeight + 40 * W.u
        radius: W.radius
        color: Qt.rgba(0.04, 0.04, 0.05, 0.86)
        Column {
            id: legendCol
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 24 * W.u; topMargin: 18 * W.u }
            spacing: 10 * W.u
            Row {
                width: parent.width; height: 18 * W.u
                Repeater {
                    model: page.src ? page.src.legend : []
                    delegate: Rectangle {
                        required property var modelData
                        width: legendCol.width / page.src.legend.length; height: parent.height
                        color: modelData
                    }
                }
            }
            Item {
                width: parent.width; height: lightText.implicitHeight
                Text { id: lightText; text: "Light"; color: W.dim; font.family: W.font; font.pixelSize: W.tSmall }
                Text { anchors.horizontalCenter: parent.horizontalCenter; text: "Moderate"; color: W.dim; font.family: W.font; font.pixelSize: W.tSmall }
                Text { anchors.right: parent.right; text: "Heavy"; color: W.dim; font.family: W.font; font.pixelSize: W.tSmall }
            }
            Text {
                width: parent.width
                text: page.src ? page.src.attribution : ""
                color: W.faint; font.family: W.font; font.pixelSize: 16 * W.u; wrapMode: Text.WordWrap
            }
        }
    }

    Text {
        anchors.centerIn: parent
        visible: !page.info
        width: Math.min(implicitWidth, parent.width - 120 * W.u)
        horizontalAlignment: Text.AlignHCenter
        text: page.problem || "Getting the radar…"
        color: page.problem ? W.text : W.faint; font.family: W.font; font.pixelSize: 32 * W.u; wrapMode: Text.WordWrap
    }
}
