// couchbox: the screen shown while an app starts. Changed from Bigscreen 6.7.5: a dark background,
// and home-row apps show their tile (the "icon" is then the tile's PNG path).
// SPDX-FileCopyrightText: 2015 Marco Martin <notmart@gmail.com>
// SPDX-FileCopyrightText: 2025 Devin Lin <devin@kde.org>
// SPDX-License-Identifier: LGPL-2.0-or-later

import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Effects

import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.extras as PlasmaExtras
import org.kde.kirigami as Kirigami
import org.kde.plasma.components as PC3
import org.kde.plasma.private.nanoshell as NanoShell
import org.kde.plasma.plasmoid
import org.kde.bigscreen as Bigscreen

NanoShell.FullScreenOverlay {
    id: window

    Connections {
        target: Plasmoid

        function onShowAppLaunchScreenRequested(appName, icon) {
            window.open(appName, icon);
        }
    }

    function open(windowName, windowIcon) {
        window.visible = false;
        window.title = windowName;
        window.icon = windowIcon;
        window.state = "open";
        window.showMaximized();
    }

    property alias state: windowRoot.state
    property alias icon: icon.source

    color: "transparent"

    onVisibleChanged: {
        if (!visible) {
            window.state = "closed";
        } else {
            windowRoot.forceActiveFocus();
        }
    }
    onActiveChanged: {
        if (!active) {
            window.state = "closed";
            window.close();
        }
    }

    FocusScope {
        id: windowRoot
        anchors.fill: parent

        Bigscreen.BackHandler.onActivated: {
            window.state = "closed";
            window.close();
        }

        Rectangle {
            id: background
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0; color: "#13151c" }
                GradientStop { position: 1; color: "#07080b" }
            }
        }

        Item {
            id: iconParent
            readonly property bool isTile: String(icon.source).endsWith(".png")
            anchors.centerIn: background
            width: isTile ? Math.round(background.width * 0.34) : Kirigami.Units.iconSizes.enormous
            height: isTile ? Math.round(width * 9 / 16) : width

            Image {
                id: tileImage
                anchors.fill: parent
                visible: iconParent.isTile
                source: !iconParent.isTile ? "" : String(icon.source).startsWith("/") ? "file://" + icon.source : icon.source
                sourceSize.width: 800
                sourceSize.height: 450
                smooth: true
                mipmap: true
            }

            Kirigami.Icon {
                id: icon
                anchors.fill: parent
                visible: !iconParent.isTile
            }

            MultiEffect {
                anchors.fill: parent
                source: iconParent.isTile ? tileImage : icon
                shadowEnabled: true
                shadowBlur: 1.0
                shadowVerticalOffset: 12
                shadowColor: "#c0000000"
            }

            PC3.BusyIndicator {
                id: loadingIndicator
                anchors.top: parent.bottom
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.topMargin: Kirigami.Units.gridUnit * 2

                implicitHeight: Kirigami.Units.iconSizes.smallMedium
                implicitWidth: Kirigami.Units.iconSizes.smallMedium
            }
        }

        state: 'closed'
        states: [
            State {
                name: "closed"
                PropertyChanges {
                    target: windowRoot
                    opacity: 0
                }
                PropertyChanges {
                    target: window
                    visible: false
                }
            },
            State {
                name: "open"
                PropertyChanges {
                    target: windowRoot
                    opacity: 1
                }
            }
        ]

        transitions: [
            Transition {
                from: "closed"
                SequentialAnimation {
                    PropertyAnimation {
                        target: windowRoot
                        duration: Kirigami.Units.longDuration
                        easing.type: Easing.InOutQuad
                        properties: "opacity"
                    }
                }
            }
        ]
    }
}
