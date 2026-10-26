// What the assistant's model wrote about the page (Summarize, Ask), on the right, clearly
// marked as AI. Up/Down scroll, Back closes.
import QtQuick

FocusScope {
    id: p
    property string title: "Summary"
    property string question: ""
    property string text: ""
    property bool busy: false
    property string problem: ""
    signal closed()
    Keys.onUpPressed: flick.contentY = Math.max(0, flick.contentY - 90 * S.u)
    Keys.onDownPressed: flick.contentY = Math.max(0, Math.min(flick.contentHeight - flick.height, flick.contentY + 90 * S.u))
    Keys.onEscapePressed: closed()
    Keys.onBackPressed: closed()
    Keys.onReturnPressed: closed()

    Rectangle {
        anchors.fill: parent
        color: "#16131f"
        border.color: p.activeFocus ? S.ai : "#3a3157"; border.width: (p.activeFocus ? 3 : 1.5) * S.u
        radius: S.radius
    }
    Row {
        id: head
        x: 34 * S.u; y: 30 * S.u
        spacing: 14 * S.u
        Image { width: 34 * S.u; height: width; sourceSize: Qt.size(width, height); source: "icons/spark.svg"; anchors.verticalCenter: parent.verticalCenter }
        Text { text: p.title; color: S.text; font.family: S.font; font.pixelSize: S.tHead; font.weight: Font.Bold; anchors.verticalCenter: parent.verticalCenter }
    }
    Text {
        id: label
        anchors { left: parent.left; right: parent.right; top: head.bottom; leftMargin: 34 * S.u; rightMargin: 34 * S.u; topMargin: 10 * S.u }
        text: "Written by the assistant from this page. It can be wrong."
        color: S.ai; font.family: S.font; font.pixelSize: 19 * S.u; wrapMode: Text.WordWrap
    }
    Text {
        id: q
        visible: !!p.question
        anchors { left: label.left; right: label.right; top: label.bottom; topMargin: 18 * S.u }
        text: "“" + p.question + "”"
        color: S.text2; font.family: S.font; font.pixelSize: S.tMeta; font.italic: true; wrapMode: Text.WordWrap
    }
    Flickable {
        id: flick
        anchors { left: label.left; right: label.right; top: q.visible ? q.bottom : label.bottom; topMargin: 24 * S.u; bottom: foot.top; bottomMargin: 16 * S.u }
        contentHeight: body.height
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        Behavior on contentY { NumberAnimation { duration: 140 } }
        Text {
            id: body
            width: flick.width
            text: p.busy ? "Reading the page…" : p.problem ? p.problem : p.text
            color: p.busy || p.problem ? S.dim : "#ece9f7"
            font.family: S.font; font.pixelSize: 28 * S.u; wrapMode: Text.Wrap; lineHeight: 1.35
            textFormat: Text.PlainText
        }
    }
    Text {
        id: foot
        anchors { left: label.left; bottom: parent.bottom; bottomMargin: 24 * S.u }
        text: "Back closes"
        color: S.faint; font.family: S.font; font.pixelSize: 19 * S.u
    }
}
