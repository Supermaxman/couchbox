// Reader: a page's article as large native text (search.py's blocks). Up/Down scroll, Left/
// Right a screen at a time, Back returns to the page.
import QtQuick

FocusScope {
    id: r
    property var article: ({})                 // {title, site, url, blocks: [{k, t}], minutes}
    signal closed()

    function scroll(d) { flick.contentY = Math.max(0, Math.min(flick.contentHeight - flick.height, flick.contentY + d)); }
    function show(a) { article = a; flick.contentY = 0; }
    Keys.onUpPressed: scroll(-110 * S.u)
    Keys.onDownPressed: scroll(110 * S.u)
    Keys.onLeftPressed: scroll(-flick.height * 0.85)
    Keys.onRightPressed: scroll(flick.height * 0.85)
    Keys.onEscapePressed: closed()
    Keys.onBackPressed: closed()

    Rectangle { anchors.fill: parent; color: "#101215" }
    Flickable {
        id: flick
        anchors { top: parent.top; bottom: hint.top; bottomMargin: 22 * S.u; horizontalCenter: parent.horizontalCenter }
        width: Math.min(parent.width - 2 * S.edge, 1240 * S.u)
        contentWidth: width
        contentHeight: col.height + 120 * S.u
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        Behavior on contentY { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
        Column {
            id: col
            width: parent.width
            y: 70 * S.u
            spacing: 26 * S.u
            Text {
                width: parent.width
                text: (r.article.site || "") + (r.article.minutes ? "  ·  " + r.article.minutes + " min read" : "")
                color: S.accent; font.family: S.font; font.pixelSize: S.tMeta; font.weight: Font.DemiBold; elide: Text.ElideRight
            }
            Text {
                width: parent.width
                text: r.article.title || ""
                color: S.text; font.family: S.font; font.pixelSize: 56 * S.u; font.weight: Font.Bold; wrapMode: Text.WordWrap; lineHeight: 1.1
            }
            Rectangle { width: 120 * S.u; height: 4 * S.u; radius: 2 * S.u; color: S.line }
            Repeater {
                model: r.article.blocks || []
                Item {
                    required property var modelData
                    width: col.width
                    height: body.height + (modelData.k === "h" ? 16 * S.u : 0)
                    Rectangle {                            // quotes: a bar on the left
                        visible: modelData.k === "quote"
                        width: 6 * S.u; height: body.height; radius: 3 * S.u; color: S.accent
                    }
                    Text {
                        visible: modelData.k === "li"
                        text: "•"; color: S.accent; font.family: S.font; font.pixelSize: 34 * S.u; y: -2 * S.u
                    }
                    Text {
                        id: body
                        x: modelData.k === "li" ? 40 * S.u : modelData.k === "quote" ? 34 * S.u : 0
                        y: modelData.k === "h" ? 16 * S.u : 0
                        width: parent.width - x
                        text: modelData.t
                        textFormat: Text.PlainText
                        wrapMode: Text.Wrap
                        color: modelData.k === "h" ? S.text : modelData.k === "quote" ? S.text2 : "#e4e8ee"
                        font.family: modelData.k === "pre" ? "monospace" : S.font
                        font.pixelSize: modelData.k === "h" ? 40 * S.u : modelData.k === "pre" ? 26 * S.u : 34 * S.u
                        font.weight: modelData.k === "h" ? Font.Bold : Font.Normal
                        font.italic: modelData.k === "quote"
                        lineHeight: modelData.k === "h" ? 1.15 : 1.4
                    }
                }
            }
        }
    }
    Rectangle {                                    // how far along
        anchors { right: parent.right; rightMargin: 24 * S.u; top: flick.top; topMargin: 70 * S.u }
        width: 6 * S.u; radius: 3 * S.u; color: S.panel2
        height: flick.height - 140 * S.u
        visible: flick.contentHeight > flick.height
        Rectangle {
            width: parent.width; radius: parent.radius; color: S.accent
            height: Math.max(40 * S.u, parent.height * flick.height / flick.contentHeight)
            y: (parent.height - height) * Math.min(1, flick.contentY / Math.max(1, flick.contentHeight - flick.height))
        }
    }
    Text {
        id: hint
        anchors { bottom: parent.bottom; bottomMargin: 26 * S.u; horizontalCenter: parent.horizontalCenter }
        text: "▲ ▼  scroll      ◀ ▶  a screen at a time      Back  the page"
        color: S.faint; font.family: S.font; font.pixelSize: S.tMeta
    }
}
