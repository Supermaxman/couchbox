// Issues, like the website's list: Open / Resolved / All, newest first; one row per issue
// (poster, title, the kind of problem, season and episode, status, who reported it and when).
// OK on a row opens the movie or show.
import QtQuick

VPage {
    id: page
    readonly property var filters: [["open", "Open"], ["resolved", "Resolved"], ["all", "All"]]
    readonly property var kinds: ({1: "Video", 2: "Audio", 3: "Subtitles", 4: "Other"})
    property int filter: 0
    property int skip: 0
    property int total: 0
    property bool loading: false
    ListModel { id: model }

    function load(fresh) {
        if (loading) return;
        if (fresh) { model.clear(); skip = 0; total = 0; }
        if (!fresh && skip >= total) return;
        loading = true;
        S.get("/issue?take=20&skip=" + skip + "&sort=added&filter=" + filters[filter][0], r => {
            for (const q of r.results || []) model.append({json: JSON.stringify(q)});
            skip += (r.results || []).length;
            total = r.pageInfo ? r.pageInfo.results : 0;
            loading = false;
        }, err => { loading = false; S.toast(err); });
    }
    Component.onCompleted: load(true)

    function ago(t) {
        const s = (Date.now() - new Date(t).getTime()) / 1000;
        if (s < 3600) return Math.max(1, Math.round(s / 60)) + " minutes ago";
        if (s < 86400) return Math.round(s / 3600) + " hours ago";
        if (s < 86400 * 60) return Math.round(s / 86400) + " days ago";
        return S.date(t);
    }

    Text {
        y: 120 * S.u
        text: "Issues"
        color: S.heading
        font.family: S.font
        font.pixelSize: 50 * S.u
        font.weight: Font.Bold
    }

    FocusScope {
        id: bar
        property bool stop: true
        y: 124 * S.u
        x: page.width - width - S.edge
        width: barRow.width
        height: barRow.height
        Row {
            id: barRow
            spacing: 12 * S.u
            Repeater {
                model: page.filters.length
                SButton {
                    required property int index
                    focus: index === page.filter
                    text: page.filters[index][1]
                    kind: index === page.filter ? "primary" : ""
                    onActiveFocusChanged: if (activeFocus && page.filter !== index) { page.filter = index; page.load(true); }
                }
            }
        }
        Keys.onLeftPressed: event => { event.accepted = page.filter > 0; if (event.accepted) barRow.children[page.filter - 1].forceActiveFocus(); }
        Keys.onRightPressed: event => { event.accepted = page.filter < page.filters.length - 1; if (event.accepted) barRow.children[page.filter + 1].forceActiveFocus(); }
    }

    ListView {
        id: list
        property bool stop: count > 0
        y: 210 * S.u
        width: page.width - S.edge
        height: contentHeight
        interactive: false
        spacing: 18 * S.u
        model: model
        focus: true
        onCurrentIndexChanged: if (currentIndex > count - 5) page.load(false)
        delegate: Rectangle {
            id: row
            required property string json
            readonly property var q: JSON.parse(json)
            readonly property var media: q.media || {}
            readonly property string mediaType: media.mediaType || "movie"
            property var info: null
            width: list.width
            height: 180 * S.u
            radius: 12 * S.u
            color: S.panel
            clip: true
            border.color: activeFocus ? S.focus : S.line
            border.width: activeFocus ? 4 * S.u : 1
            focus: ListView.isCurrentItem
            Component.onCompleted: if (media.tmdbId) S.details(mediaType, media.tmdbId, r => info = r)
            Keys.onReturnPressed: S.openMedia(mediaType, media.tmdbId)
            Keys.onEnterPressed: S.openMedia(mediaType, media.tmdbId)
            Image {
                anchors.fill: parent
                source: row.info ? S.img(row.info.backdropPath, "w780") : ""
                sourceSize.width: 800
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                opacity: 0.25
            }
            Image {
                id: poster
                x: 20 * S.u; y: 15 * S.u
                width: 100 * S.u; height: 150 * S.u
                source: row.info ? S.img(row.info.posterPath, "w300_and_h450_face") : ""
                sourceSize.width: 160
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
            }
            Column {
                anchors { left: poster.right; leftMargin: 24 * S.u; verticalCenter: parent.verticalCenter }
                width: parent.width * 0.4
                spacing: 8 * S.u
                Text { width: parent.width; elide: Text.ElideRight; text: row.info ? row.info.title || row.info.name : ""; color: S.text; font.family: S.font; font.pixelSize: 28 * S.u; font.weight: Font.Bold }
                Row {
                    spacing: 10 * S.u
                    Pill { text: page.kinds[row.q.issueType] || "Other"; color: S.line; size: 16 }
                    Pill { visible: !!row.q.problemSeason; text: "Season " + row.q.problemSeason + (row.q.problemEpisode ? " · Episode " + row.q.problemEpisode : ""); color: S.indigoDark; size: 16 }
                }
                Text {
                    width: parent.width
                    visible: !!text
                    text: row.q.comments && row.q.comments.length ? "“" + row.q.comments[0].message + "”" : ""
                    elide: Text.ElideRight
                    color: S.text2; font.family: S.font; font.pixelSize: 19 * S.u; font.italic: true
                }
            }
            Column {
                anchors { left: parent.left; leftMargin: parent.width * 0.6; verticalCenter: parent.verticalCenter }
                spacing: 10 * S.u
                Row {
                    spacing: 10 * S.u
                    Text { text: "Status"; color: S.dim; font.family: S.font; font.pixelSize: 19 * S.u; font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter }
                    Pill { text: row.q.status === 2 ? "Resolved" : "Open"; color: row.q.status === 2 ? S.green : S.yellow; fg: row.q.status === 2 ? S.text : "#111827"; size: 16 }
                }
                Text {
                    text: "Opened " + page.ago(row.q.createdAt) + (row.q.createdBy ? " by " + row.q.createdBy.displayName : "")
                    color: S.text2; font.family: S.font; font.pixelSize: 19 * S.u
                }
            }
        }
    }

    Text {
        y: 340 * S.u
        anchors.horizontalCenter: parent.horizontalCenter
        visible: !page.loading && model.count === 0
        text: page.filter === 0 ? "No open issues." : "No issues."
        color: S.dim
        font.family: S.font
        font.pixelSize: 30 * S.u
    }
}
