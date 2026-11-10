// No internet: YouTube's TV app's "No internet connection" panel (its NETWORK_ERROR_*_V2 strings
// and overlay, measured from its page): on the right over the page, darkened, the tips and
// Refresh. OK on Refresh closes it and asks for the page again (still offline: it comes back);
// Back closes it. The app takes it down by itself once the TV is online again (Main).
import QtQuick

FocusScope {
    id: panel
    objectName: "network"
    property var returnFocus: null
    readonly property bool shown: sheet.open
    signal refresh()
    visible: sheet.open || scrim.opacity > 0 || sheet.opacity > 0
    z: 160

    function show(back) {                     // back: what has the focus now (it gets it again)
        if (sheet.open) return;
        returnFocus = back || null;
        sheet.open = true;
        forceActiveFocus();
    }
    function close() {
        if (!sheet.open) return;
        sheet.open = false;
        if (returnFocus) returnFocus.forceActiveFocus();
        returnFocus = null;
    }
    Keys.onReturnPressed: e => { if (!e.isAutoRepeat) refresh(); }
    Keys.onEnterPressed: e => { if (!e.isAutoRepeat) refresh(); }
    Keys.onEscapePressed: close()
    Keys.onBackPressed: close()
    Keys.onUpPressed: {}
    Keys.onDownPressed: {}
    Keys.onLeftPressed: {}
    Keys.onRightPressed: {}

    // the page behind at 40% (black at 60%): in at once, out in 100 ms
    Rectangle {
        id: scrim
        anchors.fill: parent
        color: "black"
        opacity: sheet.open ? 0.6 : 0
        Behavior on opacity { enabled: !sheet.open; NumberAnimation { duration: 100; easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0, 0, 1, 1, 1] } }
    }
    // 684 x 1008 at (1200, 36), #181818, corners 36, 36 inside; in from the right and fading in,
    // 350 ms on YouTube's curve (0.2, 0, 0, 1); out the same way
    Rectangle {
        id: sheet
        property bool open: false
        x: 1200 * Y.u + (open ? 0 : width)
        y: 36 * Y.u
        width: 684 * Y.u
        height: 1008 * Y.u
        radius: 36 * Y.u
        color: "#181818"
        opacity: open ? 1 : 0
        Behavior on x { NumberAnimation { duration: 350; easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0, 0, 1, 1, 1] } }
        Behavior on opacity { NumberAnimation { duration: 350; easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0, 0, 1, 1, 1] } }

        Column {
            x: 36 * Y.u
            y: 36 * Y.u
            width: 612 * Y.u
            Text {
                width: parent.width
                text: "No internet connection"
                color: Y.text
                font.family: Y.font; font.pixelSize: 36 * Y.u; font.weight: Font.Black
                lineHeight: 48 * Y.u; lineHeightMode: Text.FixedHeight
                transform: Translate { y: -2 * Y.u }  // (Qt sets it 2 lower than the TV app's page)
            }
            Item { width: 1; height: 24 * Y.u }       // its 12 below, the messages' 12 above
            Text {
                width: 582 * Y.u
                text: "YouTube can’t connect to the internet right now. Try these troubleshooting tips:"
                color: Y.text
                font.family: Y.font; font.pixelSize: 30 * Y.u
                lineHeight: 42 * Y.u; lineHeightMode: Text.FixedHeight
                wrapMode: Text.WordWrap
                bottomPadding: 12 * Y.u
            }
            Repeater {
                model: ["Refresh the YouTube app", "Check your network settings", "Restart your wireless router", "Restart your device"]
                Item {
                    width: 582 * Y.u
                    height: 54 * Y.u
                    Text {                            // the bullet: 36 px, 36 before the text (its dot level with YouTube's)
                        y: -4 * Y.u
                        width: 36 * Y.u
                        text: "•"
                        color: Y.text
                        font.family: Y.font; font.pixelSize: 36 * Y.u
                        lineHeight: 36 * Y.u; lineHeightMode: Text.FixedHeight
                    }
                    Text {
                        x: 72 * Y.u
                        width: parent.width - x
                        text: modelData
                        color: Y.text
                        font.family: Y.font; font.pixelSize: 30 * Y.u
                        lineHeight: 42 * Y.u; lineHeightMode: Text.FixedHeight
                        elide: Text.ElideRight
                    }
                }
            }
            Item { width: 1; height: 36 * Y.u }
            Rectangle {                               // Refresh: focused, white
                objectName: "refresh"
                width: parent.width
                height: 96 * Y.u
                radius: height / 2
                color: Y.text
                Text {
                    anchors.centerIn: parent
                    text: "Refresh"
                    color: Y.ink
                    font.family: Y.font; font.pixelSize: 30 * Y.u; font.weight: Font.Medium
                }
            }
        }
    }
}
