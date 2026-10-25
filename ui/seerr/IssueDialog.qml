// "Report an Issue", like the website's: the kind of problem (Video, Audio, Subtitles,
// Other), for shows the season and episode, and what's wrong (typed with the keyboard
// pop-up or the phone). Seerr notifies whoever handles issues.
import QtQuick

FocusScope {
    id: dlg
    visible: false
    z: 50
    property var d: null
    readonly property bool tv: !!d && d.name !== undefined && d.title === undefined
    readonly property var kinds: [[1, "Video"], [2, "Audio"], [3, "Subtitles"], [4, "Other"]]
    property int kind: 0
    property int season: 0                   // 0: all seasons
    property int episode: 0                  // 0: all episodes
    property string message: ""
    property bool sending: false
    readonly property var seasons: d && d.seasons ? d.seasons.filter(s => s.seasonNumber > 0) : []
    readonly property int episodes: season > 0 ? ((seasons.find(s => s.seasonNumber === season) || {}).episodeCount || 0) : 0

    function open(media) {
        d = media; kind = 0; season = 0; episode = 0; message = ""; sending = false;
        visible = true;
        Qt.callLater(() => body.focusFirst());
    }
    function close() { visible = false; S.closedDialog(); }
    function send() {
        if (sending) return;
        if (!message.trim()) { S.askText("What's wrong?", message, t => message = t); return; }
        sending = true;
        S.call("POST", "/issue", {issueType: kinds[kind][0], message: message.trim(), mediaId: d.mediaInfo.id,
                                  problemSeason: season, problemEpisode: season ? episode : 0}, () => {
            S.toast("Thanks, the issue was reported.");
            close();
        }, err => { sending = false; S.toast("Couldn't report it: " + err); });
    }

    Keys.onEscapePressed: close()
    Keys.onBackPressed: close()

    Rectangle { anchors.fill: parent; color: Qt.rgba(0.04, 0.05, 0.09, 0.75) }

    Rectangle {
        anchors.centerIn: parent
        width: 980 * S.u
        height: Math.min(parent.height - 80 * S.u, content.height + 80 * S.u)
        radius: 16 * S.u
        color: S.panel
        border.color: S.line
        border.width: 1

        VPage {
            id: body
            anchors.fill: parent
            anchors.margins: 40 * S.u
            bottomPad: 0
            Column {
                id: content
                width: body.width
                spacing: 24 * S.u
                Column {
                    spacing: 8 * S.u
                    Text { text: "Report an Issue"; color: S.heading; font.family: S.font; font.pixelSize: 38 * S.u; font.weight: Font.Bold }
                    Text { text: dlg.d ? dlg.d.title || dlg.d.name : ""; color: S.text; font.family: S.font; font.pixelSize: 27 * S.u; font.weight: Font.DemiBold }
                }

                Text { text: "What kind of problem?"; color: S.text2; font.family: S.font; font.pixelSize: 22 * S.u; font.weight: Font.DemiBold }
                FocusScope {                         // Video / Audio / Subtitles / Other
                    property bool stop: true
                    width: kindRow.width
                    height: kindRow.height
                    Row {
                        id: kindRow
                        spacing: 14 * S.u
                        Repeater {
                            model: dlg.kinds.length
                            SButton {
                                required property int index
                                focus: index === dlg.kind
                                text: dlg.kinds[index][1]
                                kind: index === dlg.kind ? "primary" : ""
                                onActiveFocusChanged: if (activeFocus) dlg.kind = index
                            }
                        }
                    }
                    Keys.onLeftPressed: event => { event.accepted = dlg.kind > 0; if (event.accepted) dlg.kind--; }
                    Keys.onRightPressed: event => { event.accepted = dlg.kind < dlg.kinds.length - 1; if (event.accepted) dlg.kind++; }
                    onActiveFocusChanged: if (activeFocus) kindRow.children[dlg.kind].forceActiveFocus()
                }

                // shows: which season and episode (Left/Right)
                Repeater {
                    model: dlg.tv ? ["Season", "Episode"] : []
                    Column {
                        id: pickRow
                        required property string modelData
                        readonly property bool isSeason: modelData === "Season"
                        visible: isSeason || dlg.season > 0
                        spacing: 10 * S.u
                        width: content.width
                        Text { text: pickRow.modelData; color: S.text2; font.family: S.font; font.pixelSize: 22 * S.u; font.weight: Font.DemiBold }
                        Rectangle {
                            property bool stop: true
                            width: parent.width
                            height: 62 * S.u
                            radius: 10 * S.u
                            color: activeFocus ? S.panel2 : S.bg
                            border.color: activeFocus ? S.focus : S.line
                            border.width: activeFocus ? 3 * S.u : 1
                            Text {
                                anchors { left: parent.left; leftMargin: 20 * S.u; verticalCenter: parent.verticalCenter }
                                text: pickRow.isSeason ? (dlg.season ? "Season " + dlg.season : "All Seasons")
                                                       : (dlg.episode ? "Episode " + dlg.episode : "All Episodes")
                                color: S.text; font.family: S.font; font.pixelSize: 23 * S.u
                            }
                            Text { anchors { right: parent.right; rightMargin: 20 * S.u; verticalCenter: parent.verticalCenter } text: "‹  ›"; color: S.dim; font.pixelSize: 28 * S.u }
                            function step(d) {
                                if (pickRow.isSeason) {
                                    const nums = [0].concat(dlg.seasons.map(s => s.seasonNumber));
                                    const i = nums.indexOf(dlg.season);
                                    dlg.season = nums[(i + d + nums.length) % nums.length];
                                    dlg.episode = 0;
                                } else {
                                    const n = dlg.episodes + 1;
                                    dlg.episode = (dlg.episode + d + n) % n;
                                }
                            }
                            Keys.onLeftPressed: step(-1)
                            Keys.onRightPressed: step(1)
                        }
                    }
                }

                Text { text: "What's wrong?"; color: S.text2; font.family: S.font; font.pixelSize: 22 * S.u; font.weight: Font.DemiBold }
                Rectangle {                          // OK: type it
                    property bool stop: true
                    width: parent.width
                    height: Math.max(110 * S.u, msg.implicitHeight + 36 * S.u)
                    radius: 10 * S.u
                    color: activeFocus ? S.panel2 : S.bg
                    border.color: activeFocus ? S.focus : S.line
                    border.width: activeFocus ? 3 * S.u : 1
                    Text {
                        id: msg
                        x: 20 * S.u; y: 18 * S.u
                        width: parent.width - 40 * S.u
                        wrapMode: Text.WordWrap
                        text: dlg.message || "Press OK to describe the problem (or type it on your phone)"
                        color: dlg.message ? S.text : S.dim
                        font.family: S.font
                        font.pixelSize: 22 * S.u
                    }
                    Keys.onReturnPressed: S.askText("What's wrong?", dlg.message, t => dlg.message = t)
                    Keys.onEnterPressed: S.askText("What's wrong?", dlg.message, t => dlg.message = t)
                }

                FocusScope {
                    property bool stop: true
                    width: parent.width
                    height: 60 * S.u
                    Row {
                        anchors.right: parent.right
                        spacing: 14 * S.u
                        SButton { id: cancelBtn; text: "Cancel"; onClicked: dlg.close(); KeyNavigation.right: sendBtn }
                        SButton {
                            id: sendBtn
                            focus: true
                            kind: "warning"
                            text: dlg.sending ? "Reporting…" : "Report Issue"
                            enabled2: !dlg.sending
                            KeyNavigation.left: cancelBtn
                            onClicked: dlg.send()
                        }
                    }
                }
            }
        }
    }
}
