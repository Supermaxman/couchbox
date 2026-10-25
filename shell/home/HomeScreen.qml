// couchbox: the TV home screen. Replaces Bigscreen's HomeScreen.qml (6.7.5): a clock and a few
// settings buttons at the top, and one row of app tiles in the order of /etc/couchbox/home.tsv.
// Installed by couchbox-home.
// Based on Bigscreen's HomeScreen.qml:
// SPDX-FileCopyrightText: 2015 Marco Martin <mart@kde.org>
// SPDX-FileCopyrightText: 2019 Aditya Mehra <aix.m@outlook.com>
// SPDX-FileCopyrightText: 2025 Devin Lin <devin@kde.org>
// SPDX-License-Identifier: GPL-2.0-or-later

import QtQuick
import QtQuick.Window

import org.kde.plasma.plasmoid

import "couchbox" as Couch

Item {
    id: root

    readonly property real margin: Math.round(width * 0.05)

    // Read by main.qml: no blur or extra darkening, the wallpaper is already calm.
    readonly property bool blurBackground: false
    readonly property bool darkenBackground: false

    property real zoomScale: 1

    transform: Scale {
        origin.x: root.width / 2
        origin.y: root.height / 2
        xScale: root.zoomScale
        yScale: root.zoomScale
    }

    states: [
        State {
            name: "focused"
            when: root.Window.activeFocusItem !== null
            PropertyChanges { target: root; opacity: 1; zoomScale: 1 }
            StateChangeScript { script: home.forceActiveFocus() }
        },
        State {
            name: "unfocused"
            when: root.Window.activeFocusItem === null
            PropertyChanges { target: root; opacity: 0; zoomScale: 1.04 }
            StateChangeScript {
                // HACK (from Bigscreen): xwaylandvideobridge interferes with the shell's focus
                script: Plasmoid.executeCommand("pkill -f xwaylandvideobridge")
            }
        }
    ]

    transitions: [
        Transition {
            to: "focused"
            ParallelAnimation {
                OpacityAnimator { duration: 250 }
                NumberAnimation { target: root; property: "zoomScale"; duration: 500; easing.type: Easing.OutExpo }
            }
        }
    ]

    HomeHeader {
        id: header
        anchors {
            top: parent.top
            left: parent.left
            right: parent.right
            topMargin: Math.round(root.margin * 0.8)
            leftMargin: root.margin
            rightMargin: root.margin
        }
        KeyNavigation.down: home
        KeyNavigation.tab: home
    }

    Couch.Home {
        id: home
        z: -1   // its glow goes behind the header
        anchors {
            top: parent.top
            topMargin: Math.round(root.height * 0.54 - home.tileHeight / 2)
            left: parent.left
            right: parent.right
            bottom: parent.bottom
            leftMargin: root.margin
            rightMargin: root.margin
        }
        navigationUp: header
        KeyNavigation.backtab: header
    }
}
