// couchbox: the round buttons at the top of the home screen. Replaces Bigscreen's
// AbstractIndicator.qml (6.7.5): a plain icon that turns into a white disc when focused,
// with its name underneath (instead of a tooltip).
// Based on Bigscreen's AbstractIndicator.qml:
// SPDX-FileCopyrightText: 2019 Aditya Mehra <aix.m@outlook.com>
// SPDX-FileCopyrightText: 2019 Marco Martin <mart@kde.org>
// SPDX-License-Identifier: GPL-2.0-or-later

import QtQuick
import QtQuick.Layouts
import org.kde.plasma.components as PlasmaComponents
import org.kde.bigscreen as Bigscreen
import org.kde.kirigami as Kirigami

import "../couchbox" as Couch

PlasmaComponents.ToolButton {
    id: button

    Kirigami.Theme.inherit: false
    Kirigami.Theme.colorSet: Kirigami.Theme.Complementary

    implicitWidth: 44
    implicitHeight: 44
    Layout.preferredWidth: 44
    Layout.preferredHeight: 44
    padding: 11

    background: Rectangle {
        radius: width / 2
        color: button.activeFocus ? "white" : (button.hovered ? Qt.rgba(1, 1, 1, 0.12) : "transparent")
        scale: button.activeFocus ? 1.08 : 1
        Behavior on color { ColorAnimation { duration: Couch.Style.duration } }
        Behavior on scale { NumberAnimation { duration: Couch.Style.duration } }
    }

    contentItem: Kirigami.Icon {
        source: button.icon.name
        isMask: true
        color: button.activeFocus ? "#111318" : Qt.rgba(1, 1, 1, 0.78)
    }

    Text {
        anchors { top: parent.bottom; topMargin: 8; horizontalCenter: parent.horizontalCenter }
        text: button.text
        color: Couch.Style.text
        font.family: Couch.Style.font
        font.pixelSize: 12
        font.weight: Font.Medium
        opacity: button.activeFocus ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Couch.Style.duration } }
    }

    Keys.onReturnPressed: (event) => clicked()
    Keys.onEnterPressed: (event) => clicked()

    onClicked: (event) => {
        Bigscreen.NavigationSoundEffects.playClickedSound();
    }

    Keys.onPressed: (event) => {
        switch (event.key) {
        case Qt.Key_Down:
        case Qt.Key_Right:
        case Qt.Key_Left:
        case Qt.Key_Tab:
        case Qt.Key_Backtab:
            Bigscreen.NavigationSoundEffects.playMovingSound();
            break;
        default:
            break;
        }
    }
}
