// "Request Movie" / "Request Series", like the website's: seasons to pick (shows), the
// quality profile and folder (Advanced), Cancel / Request. Seerr approves it at once (the
// API key is an admin's).
import QtQuick

FocusScope {
    id: dlg
    visible: false
    z: 50
    property var d: null
    readonly property bool tv: !!d && d.name !== undefined && d.title === undefined
    property var server: null                // /service/sonarr|radarr/<id>
    property int profile: 0                  // index into server.profiles
    property int folder: 0
    property bool sending: false
    property int picked: 0                   // seasons switched on
    property int canPick: 0                  // seasons that can be requested
    ListModel { id: seasons }

    function setOn(i, v) {
        seasons.setProperty(i, "on", v);
        picked = chosen().length;
    }

    function seasonStatus(n) {
        const info = d && d.mediaInfo;
        if (!info) return 0;
        const s = (info.seasons || []).find(s => s.seasonNumber === n);
        let st = s ? s.status : 0;
        for (const r of info.requests || [])
            if (r.status !== 3 && (r.seasons || []).some(x => x.seasonNumber === n)) st = Math.max(st, 2);
        return st;
    }

    function open(media) {
        d = media;
        server = null; profile = 0; folder = 0; sending = false;
        seasons.clear();
        if (tv)
            for (const s of (d.seasons || []).filter(s => s.seasonNumber > 0))
                seasons.append({n: s.seasonNumber, count: s.episodeCount || 0, st: seasonStatus(s.seasonNumber), on: false});
        picked = 0;
        canPick = requestable();
        const kind = tv ? "sonarr" : "radarr";
        S.get("/service/" + kind, list => {
            const def = list.find(x => x.isDefault && !x.is4k) || list[0];
            if (!def) return;
            S.get("/service/" + kind + "/" + def.id, r => {
                const anime = tv && (d.keywords || []).some(k => k.id === 210024);
                const want = anime && def.activeAnimeProfileId ? def.activeAnimeProfileId : def.activeProfileId;
                profile = Math.max(0, (r.profiles || []).findIndex(p => p.id === want));
                const dir = anime && def.activeAnimeDirectory ? def.activeAnimeDirectory : def.activeDirectory;
                folder = Math.max(0, (r.rootFolders || []).findIndex(f => f.path === dir));
                r.serverId = def.id;
                server = r;
            });
        });
        visible = true;
        Qt.callLater(() => body.focusFirst());
    }
    function close() { visible = false; S.closedDialog(); }

    function chosen() {
        const out = [];
        for (let i = 0; i < seasons.count; i++) if (seasons.get(i).on) out.push(seasons.get(i).n);
        return out;
    }
    function requestable() {
        let n = 0;
        for (let i = 0; i < seasons.count; i++) if (seasons.get(i).st < 2) n++;
        return n;
    }
    function send() {
        if (sending || tv && !chosen().length) return;
        const body = {mediaType: tv ? "tv" : "movie", mediaId: d.id, is4k: false};
        if (tv) {
            body.seasons = chosen();
            if (d.externalIds && d.externalIds.tvdbId) body.tvdbId = d.externalIds.tvdbId;
        }
        if (server) {
            body.serverId = server.serverId;
            const p = (server.profiles || [])[profile];
            if (p) body.profileId = p.id;
            const f = (server.rootFolders || [])[folder];
            if (f) body.rootFolder = f.path;
        }
        sending = true;
        S.call("POST", "/request", body, () => {
            S.toast("Requested " + (d.title || d.name) + ".");
            S.requested(tv ? "tv" : "movie", d.id);
            close();
        }, err => { sending = false; S.toast("Couldn't request it: " + err); });
    }

    Keys.onEscapePressed: close()
    Keys.onBackPressed: close()

    Rectangle { anchors.fill: parent; color: Qt.rgba(0.04, 0.05, 0.09, 0.75) }

    Rectangle {
        id: box
        anchors.centerIn: parent
        width: 980 * S.u
        height: Math.min(parent.height - 80 * S.u, content.height + 80 * S.u)
        radius: 12 * S.u
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
                spacing: 18 * S.u
                Column {
                    spacing: 6 * S.u
                    Text { text: dlg.tv ? "Request Series" : "Request Movie"; color: S.heading; font.family: S.font; font.pixelSize: 38 * S.u; font.weight: Font.Bold }
                    Text { text: dlg.d ? dlg.d.title || dlg.d.name : ""; color: S.text; font.family: S.font; font.pixelSize: 27 * S.u; font.weight: Font.DemiBold }
                }
                Rectangle {
                    width: parent.width
                    height: 66 * S.u
                    radius: 8 * S.u
                    color: Qt.rgba(0.39, 0.4, 0.95, 0.15)
                    border.color: S.indigo
                    border.width: 1
                    Text {
                        anchors { left: parent.left; leftMargin: 20 * S.u; verticalCenter: parent.verticalCenter }
                        text: "ⓘ   This request will be approved automatically."
                        color: S.text; font.family: S.font; font.pixelSize: 21 * S.u
                    }
                }

                // seasons (shows): OK switches one; the top row switches all
                Rectangle {
                    visible: dlg.tv
                    width: parent.width
                    height: seasonCol.height
                    radius: 8 * S.u
                    color: Qt.rgba(0.07, 0.09, 0.15, 0.5)
                    border.color: S.line
                    border.width: 1
                    Column {
                        id: seasonCol
                        width: parent.width
                        Rectangle {                // header: all seasons
                            id: allRow
                            property bool stop: dlg.tv && dlg.canPick > 0
                            width: parent.width
                            height: 64 * S.u
                            color: activeFocus ? S.panel2 : Qt.rgba(0.22, 0.25, 0.32, 0.5)
                            border.color: activeFocus ? S.focus : "transparent"
                            border.width: 3 * S.u
                            radius: 8 * S.u
                            Toggle {
                                x: 24 * S.u; anchors.verticalCenter: parent.verticalCenter
                                on: dlg.canPick > 0 && dlg.picked === dlg.canPick
                            }
                            Text { x: 120 * S.u; anchors.verticalCenter: parent.verticalCenter; text: "SEASON"; color: S.dim; font.family: S.font; font.pixelSize: 18 * S.u; font.weight: Font.DemiBold; font.letterSpacing: 1 }
                            Text { x: 380 * S.u; anchors.verticalCenter: parent.verticalCenter; text: "# OF EPISODES"; color: S.dim; font.family: S.font; font.pixelSize: 18 * S.u; font.weight: Font.DemiBold; font.letterSpacing: 1 }
                            Text { x: 650 * S.u; anchors.verticalCenter: parent.verticalCenter; text: "STATUS"; color: S.dim; font.family: S.font; font.pixelSize: 18 * S.u; font.weight: Font.DemiBold; font.letterSpacing: 1 }
                            function flip() {
                                const all = dlg.picked !== dlg.canPick;
                                for (let i = 0; i < seasons.count; i++) if (seasons.get(i).st < 2) dlg.setOn(i, all);
                            }
                            Keys.onReturnPressed: flip()
                            Keys.onEnterPressed: flip()
                        }
                        Repeater {
                            model: seasons
                            Rectangle {
                                id: srow
                                required property int index
                                required property int n
                                required property int count
                                required property int st
                                required property bool on
                                property bool stop: true
                                width: seasonCol.width
                                height: 66 * S.u
                                color: activeFocus ? S.panel2 : "transparent"
                                border.color: activeFocus ? S.focus : "transparent"
                                border.width: 3 * S.u
                                radius: 8 * S.u
                                Rectangle { width: parent.width; height: 1; color: S.line; visible: !srow.activeFocus }
                                Toggle { x: 24 * S.u; anchors.verticalCenter: parent.verticalCenter; on: srow.on || srow.st >= 2; enabled2: srow.st < 2 }
                                Text { x: 120 * S.u; anchors.verticalCenter: parent.verticalCenter; text: "Season " + srow.n; color: S.text; font.family: S.font; font.pixelSize: 22 * S.u }
                                Text { x: 380 * S.u; anchors.verticalCenter: parent.verticalCenter; text: srow.count; color: S.text; font.family: S.font; font.pixelSize: 22 * S.u }
                                Pill {
                                    x: 650 * S.u; anchors.verticalCenter: parent.verticalCenter
                                    text: srow.st >= 2 ? S.statusName(srow.st) : "Not Requested"
                                    color: srow.st >= 2 ? S.statusColor(srow.st) : S.indigoDark
                                    size: 13
                                }
                                Keys.onReturnPressed: if (st < 2) dlg.setOn(index, !on)
                                Keys.onEnterPressed: if (st < 2) dlg.setOn(index, !on)
                            }
                        }
                    }
                }

                // Advanced: quality profile and folder (Left/Right change them)
                Text { text: "Advanced"; color: S.text; font.family: S.font; font.pixelSize: 27 * S.u; font.weight: Font.DemiBold; visible: !!dlg.server }
                Repeater {
                    model: dlg.server ? [["Quality Profile", "profiles"], ["Root Folder", "rootFolders"]] : []
                    Column {
                        id: opt
                        required property var modelData
                        readonly property var list: dlg.server[modelData[1]] || []
                        visible: list.length > (modelData[1] === "rootFolders" ? 1 : 0)
                        spacing: 8 * S.u
                        width: content.width
                        Text { text: opt.modelData[0]; color: S.text2; font.family: S.font; font.pixelSize: 20 * S.u; font.weight: Font.DemiBold }
                        Rectangle {
                            property bool stop: true
                            width: parent.width
                            height: 62 * S.u
                            radius: 8 * S.u
                            color: activeFocus ? S.panel2 : S.bg
                            border.color: activeFocus ? S.focus : S.line
                            border.width: activeFocus ? 3 * S.u : 1
                            readonly property int at: opt.modelData[1] === "profiles" ? dlg.profile : dlg.folder
                            function step(d) {
                                const n = opt.list.length;
                                const i = (at + d + n) % n;
                                if (opt.modelData[1] === "profiles") dlg.profile = i; else dlg.folder = i;
                            }
                            Text {
                                anchors { left: parent.left; leftMargin: 16 * S.u; verticalCenter: parent.verticalCenter }
                                text: {
                                    const it = opt.list[parent.at];
                                    if (!it) return "";
                                    const def = opt.modelData[1] === "profiles" ? dlg.server.server && it.id === dlg.server.server.activeProfileId : false;
                                    return (it.name || it.path) + (def ? " (Default)" : "");
                                }
                                color: S.text; font.family: S.font; font.pixelSize: 22 * S.u
                            }
                            Text { anchors { right: parent.right; rightMargin: 16 * S.u; verticalCenter: parent.verticalCenter } text: "‹  ›"; color: S.dim; font.pixelSize: 27 * S.u }
                            Keys.onLeftPressed: step(-1)
                            Keys.onRightPressed: step(1)
                        }
                    }
                }

                FocusScope {
                    id: actions
                    property bool stop: true
                    width: parent.width
                    height: 64 * S.u
                    Row {
                        anchors.right: parent.right
                        spacing: 12 * S.u
                        SButton { id: cancelBtn; text: "Cancel"; onClicked: dlg.close(); KeyNavigation.right: sendBtn }
                        SButton {
                            id: sendBtn
                            focus: true
                            kind: "primary"
                            enabled2: !dlg.sending && (!dlg.tv || dlg.picked > 0)
                            text: dlg.sending ? "Requesting…" : !dlg.tv ? "Request" : dlg.picked ? "Request " + dlg.picked + (dlg.picked === 1 ? " Season" : " Seasons") : "Select Season(s)"
                            KeyNavigation.left: cancelBtn
                            onClicked: dlg.send()
                        }
                    }
                }
            }
        }
    }
}
