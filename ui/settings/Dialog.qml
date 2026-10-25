// A message or a question over the page: text, an optional QR code, and buttons
// (Left/Right choose, OK presses, Back closes).
import QtQuick
import QtQuick.Window

FocusScope {
    id: dlg
    visible: false
    z: 70
    property string title: ""
    property string text: ""
    property string qr: ""
    property string extra: ""
    property var buttons: ["OK"]
    property int current: 0
    property var done: null
    property var returnFocus: null

    function show(t, body, q, x, btns, cb) {
        title = t; text = body; qr = q || ""; extra = x || ""; buttons = btns || ["OK"]; done = cb || null;
        current = buttons.length - 1;
        returnFocus = Window.activeFocusItem;
        visible = true;
        forceActiveFocus();
    }
    function close(i) {
        visible = false;
        if (returnFocus) returnFocus.forceActiveFocus();
        const cb = done; done = null;
        if (cb && i >= 0) cb(i);
    }
    Keys.onLeftPressed: current = Math.max(0, current - 1)
    Keys.onRightPressed: current = Math.min(buttons.length - 1, current + 1)
    Keys.onReturnPressed: close(current)
    Keys.onEnterPressed: close(current)
    Keys.onEscapePressed: close(-1)
    Keys.onBackPressed: close(-1)

    Rectangle { anchors.fill: parent; color: Qt.rgba(0.02, 0.03, 0.05, 0.8) }
    Rectangle {
        anchors.centerIn: parent
        width: Math.min(parent.width - 200 * T.u, (dlg.qr ? 1300 : 960) * T.u)
        height: content.height + 80 * T.u
        radius: 24 * T.u
        color: T.panel
        border.color: T.line
        Row {
            id: content
            x: 48 * T.u; y: 40 * T.u
            spacing: 48 * T.u
            Rectangle {
                visible: dlg.qr !== ""
                width: 360 * T.u; height: width; radius: 16 * T.u
                color: "white"
                Image { anchors.fill: parent; anchors.margins: 14 * T.u; source: dlg.qr; smooth: false }
            }
            Column {
                width: parent.parent.width - 96 * T.u - (dlg.qr ? 408 * T.u : 0)
                spacing: 20 * T.u
                Text {
                    width: parent.width
                    text: dlg.title
                    color: T.text
                    wrapMode: Text.WordWrap
                    font.family: T.font; font.pixelSize: 36 * T.u; font.weight: Font.Bold
                }
                Text {
                    width: parent.width
                    text: dlg.text
                    color: T.text
                    wrapMode: Text.WordWrap
                    textFormat: Text.PlainText
                    lineHeight: 1.15
                    font.family: T.font; font.pixelSize: 25 * T.u
                }
                Text {
                    width: parent.width
                    visible: dlg.extra !== ""
                    text: dlg.extra
                    color: T.dim
                    wrapMode: Text.WrapAnywhere
                    font.family: T.font; font.pixelSize: 21 * T.u
                }
                Row {
                    spacing: 16 * T.u
                    topPadding: 10 * T.u
                    Repeater {
                        model: dlg.buttons
                        Rectangle {
                            required property string modelData
                            required property int index
                            readonly property bool cur: index === dlg.current
                            width: label.implicitWidth + 64 * T.u; height: 66 * T.u; radius: 12 * T.u
                            color: cur ? T.accent : T.panel2
                            Text {
                                id: label
                                anchors.centerIn: parent
                                text: modelData
                                color: parent.cur ? T.accentInk : T.text
                                font.family: T.font; font.pixelSize: 24 * T.u; font.weight: Font.DemiBold
                            }
                        }
                    }
                }
            }
        }
    }
}
