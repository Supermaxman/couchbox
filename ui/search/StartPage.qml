// The start page: a big search field (OK: the keyboard pop-up, or type on a phone), and the
// recent searches. Up/Down move, OK searches.
import QtQuick

FocusScope {
    id: page
    property var history: []
    property bool ai: false
    property int idx: 0                      // 0 the field, 1.. the recent searches, last: clear them
    signal ask()                             // open the keyboard
    signal search(string text)
    signal forget()

    readonly property int count: 1 + history.length + (history.length ? 1 : 0)
    onHistoryChanged: if (idx >= count) idx = count - 1
    Keys.onUpPressed: idx = Math.max(0, idx - 1)
    Keys.onDownPressed: idx = Math.min(count - 1, idx + 1)
    Keys.onReturnPressed: act()
    Keys.onEnterPressed: act()
    function act() {
        if (idx === 0) ask();
        else if (idx <= history.length) search(history[idx - 1]);
        else forget();
    }

    Column {
        anchors { horizontalCenter: parent.horizontalCenter; top: parent.top; topMargin: 150 * S.u }
        width: Math.min(parent.width - 2 * S.edge, 1180 * S.u)
        spacing: 22 * S.u

        Row {
            spacing: 22 * S.u
            Rectangle {
                width: 84 * S.u; height: width; radius: 20 * S.u; color: S.accent
                Image { anchors.centerIn: parent; width: 52 * S.u; height: width; sourceSize: S.sz(width, height); source: "icons/search.svg" }
            }
            Text { text: "Search"; color: S.text; font.family: S.font; font.pixelSize: 64 * S.u; font.weight: Font.Bold; anchors.verticalCenter: parent.verticalCenter }
        }
        Item { width: 1; height: 8 * S.u }
        Rectangle {                              // the field
            width: parent.width; height: 104 * S.u; radius: 52 * S.u
            color: page.idx === 0 && page.activeFocus ? S.panel2 : S.panel
            border.color: page.idx === 0 && page.activeFocus ? S.focus : S.line
            border.width: (page.idx === 0 && page.activeFocus ? 4 : 1.5) * S.u
            Image { id: glass; x: 36 * S.u; anchors.verticalCenter: parent.verticalCenter; width: 40 * S.u; height: width; sourceSize: S.sz(width, height); source: "icons/search.svg"; opacity: 0.7 }
            Text {
                anchors { left: glass.right; leftMargin: 24 * S.u; right: parent.right; rightMargin: 40 * S.u; verticalCenter: parent.verticalCenter }
                text: "Search Google or type an address"
                color: S.dim; font.family: S.font; font.pixelSize: 32 * S.u; elide: Text.ElideRight
            }
        }
        Text {
            width: parent.width
            text: "OK to type with the remote or your phone. With the assistant, say “Google” and what you're looking for."
            color: S.faint; font.family: S.font; font.pixelSize: S.tMeta; wrapMode: Text.WordWrap
            leftPadding: 40 * S.u
        }
        Item { width: 1; height: 18 * S.u }
        Text {
            visible: page.history.length > 0
            text: "Recent"
            color: S.dim; font.family: S.font; font.pixelSize: S.tMeta; font.weight: Font.DemiBold; font.capitalization: Font.AllUppercase; font.letterSpacing: 2 * S.u
        }
        Repeater {
            model: page.history
            Rectangle {
                required property string modelData
                required property int index
                readonly property bool sel: page.activeFocus && page.idx === index + 1
                width: parent.width; height: 74 * S.u; radius: 12 * S.u
                color: sel ? S.panel2 : "transparent"
                border.color: sel ? S.focus : "transparent"; border.width: 3 * S.u
                scale: sel ? 1.02 : 1
                Behavior on scale { NumberAnimation { duration: 120 } }
                Image { id: clock; x: 26 * S.u; anchors.verticalCenter: parent.verticalCenter; width: 30 * S.u; height: width; sourceSize: S.sz(width, height); source: "icons/history.svg"; opacity: 0.6 }
                Text {
                    anchors { left: clock.right; leftMargin: 22 * S.u; right: parent.right; rightMargin: 26 * S.u; verticalCenter: parent.verticalCenter }
                    text: modelData; color: S.text2; font.family: S.font; font.pixelSize: S.tBody; elide: Text.ElideRight
                }
            }
        }
        Rectangle {
            visible: page.history.length > 0
            readonly property bool sel: page.activeFocus && page.idx === page.count - 1
            width: forgetText.implicitWidth + 52 * S.u; height: 60 * S.u; radius: 30 * S.u
            color: sel ? S.panel2 : "transparent"
            border.color: sel ? S.focus : S.line; border.width: (sel ? 3 : 1) * S.u
            Text { id: forgetText; anchors.centerIn: parent; text: "Clear recent searches"; color: S.dim; font.family: S.font; font.pixelSize: S.tMeta }
        }
    }
}
