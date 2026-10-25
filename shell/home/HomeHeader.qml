// couchbox: top of the TV home screen. Replaces Bigscreen's HomeHeader.qml (6.7.5): the time and
// date on the left, Settings / Sound / Wi-Fi / Power on the right (no search, favourites editor,
// battery or KDE Connect: the home row comes from /etc/couchbox/home.tsv).
// Based on Bigscreen's HomeHeader.qml:
// SPDX-FileCopyrightText: 2015 Marco Martin <mart@kde.org>
// SPDX-FileCopyrightText: 2019 Aditya Mehra <aix.m@outlook.com>
// SPDX-FileCopyrightText: 2025 Devin Lin <devin@kde.org>
// SPDX-License-Identifier: GPL-2.0-or-later

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls

import org.kde.plasma.clock

import "indicators" as Indicators
import "couchbox" as Couch
import "couchbox/apps.js" as Apps

Controls.Control {
    id: root

    padding: 0
    implicitHeight: contentItem.implicitHeight

    // Up from the app row lands on the first button
    onActiveFocusChanged: if (activeFocus) settingsIndicator.forceActiveFocus()

    Clock {
        id: clock
        trackSeconds: false
    }

    // Weather in the middle (Open-Meteo, no key; the place is COUCHBOX_WEATHER in couchbox.env)
    Couch.Weather {
        anchors.horizontalCenter: parent.horizontalCenter
        y: 14
        place: Apps.weather
    }

    contentItem: RowLayout {
        spacing: 0

        ColumnLayout {
            Layout.alignment: Qt.AlignTop | Qt.AlignLeft
            spacing: 2

            Row {
                spacing: 8
                Text {
                    id: time
                    // "h" is 12-hour only when the same format has AP
                    text: Qt.formatTime(clock.dateTime, "h:mm AP").split(" ")[0]
                    color: Couch.Style.text
                    font.family: Couch.Style.font
                    font.pixelSize: 56
                    font.weight: Font.Light
                    font.letterSpacing: -1
                }
                Text {
                    anchors.baseline: time.baseline
                    text: Qt.formatTime(clock.dateTime, "AP")
                    color: Couch.Style.textDim
                    font.family: Couch.Style.font
                    font.pixelSize: 18
                    font.weight: Font.Medium
                }
            }
            Text {
                text: Qt.formatDate(clock.dateTime, "dddd, MMMM d")
                color: Couch.Style.textDim
                font.family: Couch.Style.font
                font.pixelSize: 17
                font.weight: Font.Medium
            }
        }

        Item { Layout.fillWidth: true }

        RowLayout {
            Layout.alignment: Qt.AlignTop | Qt.AlignRight
            Layout.topMargin: 10
            spacing: 14

            Indicators.Settings {
                id: settingsIndicator
                KeyNavigation.right: volumeIndicator
                KeyNavigation.tab: volumeIndicator
            }
            Indicators.Volume {
                id: volumeIndicator
                KeyNavigation.left: settingsIndicator
                KeyNavigation.backtab: settingsIndicator
                KeyNavigation.right: wifiIndicator
                KeyNavigation.tab: wifiIndicator
            }
            Indicators.Wifi {
                id: wifiIndicator
                KeyNavigation.left: volumeIndicator
                KeyNavigation.backtab: volumeIndicator
                KeyNavigation.right: shutdownIndicator
                KeyNavigation.tab: shutdownIndicator
            }
            Indicators.Shutdown {
                id: shutdownIndicator
                KeyNavigation.left: wifiIndicator
                KeyNavigation.backtab: wifiIndicator
            }
        }
    }
}
