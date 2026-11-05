// The top of Home and the guide's tabs: the search pill (OK: Search) and the YouTube mark.
import QtQuick

FocusScope {
    id: header
    property string query: ""
    property real pillW: 720 * Y.u
    signal searchAsked()
    signal down()
    width: parent ? parent.width : 0
    height: 170 * Y.u
    Rectangle {
        id: pill
        y: 66 * Y.u
        width: header.pillW
        height: 72 * Y.u
        radius: height / 2
        color: header.activeFocus ? Y.text : Y.raised
        Behavior on width { NumberAnimation { duration: 160 } }
        Text {
            anchors { left: parent.left; leftMargin: 34 * Y.u; right: parent.right; rightMargin: 34 * Y.u; verticalCenter: parent.verticalCenter }
            text: header.query || "Search"
            color: header.activeFocus ? Y.ink : header.query ? Y.text : "#bfbfbf"
            font.family: Y.font; font.pixelSize: 34 * Y.u; font.weight: Font.Medium
            elide: Text.ElideRight
        }
    }
    Logo {                                    // it stays put while the open guide pushes the page right
        premium: !!(Y.profile && Y.profile.premium)
        anchors { right: parent.right; rightMargin: 108 * Y.u + (Y.pushed ? Y.guideOpen - Y.left : 0) }
        y: 76 * Y.u
    }
    Keys.onReturnPressed: searchAsked()
    Keys.onEnterPressed: searchAsked()
    Keys.onDownPressed: down()
    Keys.onLeftPressed: Y.toGuide()
}
