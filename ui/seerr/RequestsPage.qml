// Requests, like the website's list: filter (All, Pending, Approved, Processing, Available,
// Failed) and sort, then one wide row per request (poster, title, seasons, status, who
// asked and when). OK on a row opens the movie or show.
import QtQuick

VPage {
    id: page
    readonly property var filters: [["all", "All"], ["pending", "Pending"], ["approved", "Approved"], ["processing", "Processing"],
                                    ["available", "Available"], ["failed", "Failed"]]
    readonly property var sorts: [["added", "Most Recent"], ["modified", "Last Modified"]]
    property int filter: 0
    property int sort: 0
    property int skip: 0
    property int total: 0
    property bool loading: false
    ListModel { id: model }

    function load(fresh) {
        if (loading) return;
        if (fresh) { model.clear(); skip = 0; total = 0; }
        if (!fresh && skip >= total) return;
        loading = true;
        S.get("/request?take=20&skip=" + skip + "&filter=" + filters[filter][0] + "&sort=" + sorts[sort][0], r => {
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
        text: "Requests"
        color: S.heading
        font.family: S.font
        font.pixelSize: 50 * S.u
        font.weight: Font.Bold
    }

    // filter and sort: Left/Right pick, OK on the sort flips it
    FocusScope {
        id: bar
        property bool stop: true
        y: 124 * S.u
        x: page.width - width - S.edge
        width: barRow.width
        height: barRow.height
        Row {
            id: barRow
            spacing: 10 * S.u
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
            Item { width: 20 * S.u; height: 1 }
            SButton {
                id: sortBtn
                text: "⇅  " + page.sorts[page.sort][1]
                onClicked: { page.sort = (page.sort + 1) % page.sorts.length; page.load(true); }
            }
        }
        Keys.onLeftPressed: event => {
            const kids = barRow.children.filter(c => c.text !== undefined);
            const i = kids.findIndex(c => c.activeFocus);
            if (i > 0) { kids[i - 1].forceActiveFocus(); event.accepted = true; } else event.accepted = false;
        }
        Keys.onRightPressed: event => {
            const kids = barRow.children.filter(c => c.text !== undefined);
            const i = kids.findIndex(c => c.activeFocus);
            if (i >= 0 && i < kids.length - 1) { kids[i + 1].forceActiveFocus(); event.accepted = true; } else event.accepted = false;
        }
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
            required property int index
            readonly property var q: JSON.parse(json)
            readonly property var media: q.media || {}
            readonly property string mediaType: q.type || media.mediaType || "movie"
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
            Keys.onRightPressed: event => { event.accepted = approveBtn.visible; if (event.accepted) approveBtn.forceActiveFocus(); }
            function decide(what) {
                S.call("POST", "/request/" + q.id + "/" + what, null, () => {
                    S.toast(what === "approve" ? "Approved." : "Declined.");
                    page.load(true);
                }, err => S.toast(err));
            }
            Row {                                   // pending: Approve / Decline (Right from the row)
                anchors { right: parent.right; rightMargin: 24 * S.u; verticalCenter: parent.verticalCenter }
                spacing: 12 * S.u
                visible: row.q.status === 1
                SButton {
                    id: approveBtn
                    visible: row.q.status === 1
                    kind: "success"; icon: "✓"; text: "Approve"
                    onClicked: row.decide("approve")
                    KeyNavigation.right: declineBtn
                    Keys.onLeftPressed: row.forceActiveFocus()
                }
                SButton {
                    id: declineBtn
                    kind: "danger"; icon: "✕"; text: "Decline"
                    onClicked: row.decide("decline")
                    KeyNavigation.left: approveBtn
                }
            }
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
                anchors { left: poster.right; leftMargin: 20 * S.u; verticalCenter: parent.verticalCenter }
                width: parent.width * 0.42
                spacing: 6 * S.u
                Text { text: row.info ? (row.info.releaseDate || row.info.firstAirDate || "").slice(0, 4) : ""; color: S.text2; font.family: S.font; font.pixelSize: 18 * S.u }
                Text { width: parent.width; elide: Text.ElideRight; text: row.info ? row.info.title || row.info.name : ""; color: S.text; font.family: S.font; font.pixelSize: 27 * S.u; font.weight: Font.Bold }
                Row {
                    visible: row.mediaType === "tv" && (row.q.seasons || []).length > 0
                    spacing: 6 * S.u
                    Text { text: "Seasons"; color: S.dim; font.family: S.font; font.pixelSize: 18 * S.u; font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter }
                    Repeater { model: (row.q.seasons || []).slice(0, 10); Pill { text: modelData.seasonNumber; color: S.indigoDark; size: 15 } }
                }
            }
            Column {
                anchors { left: parent.left; leftMargin: parent.width * 0.58; verticalCenter: parent.verticalCenter }
                spacing: 10 * S.u
                Row {
                    spacing: 10 * S.u
                    Text { text: "Status"; color: S.dim; font.family: S.font; font.pixelSize: 18 * S.u; font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter }
                    Pill { text: S.requestName(row.q); color: S.requestColor(row.q); size: 16 }
                }
                Text {
                    text: "Requested " + page.ago(row.q.createdAt) + (row.q.requestedBy ? " by " + row.q.requestedBy.displayName : "")
                    color: S.text2; font.family: S.font; font.pixelSize: 18 * S.u
                }
                Text {
                    visible: !!row.q.modifiedBy && row.q.updatedAt !== row.q.createdAt
                    text: row.q.modifiedBy ? "Modified " + page.ago(row.q.updatedAt) + " by " + row.q.modifiedBy.displayName : ""
                    color: S.dim; font.family: S.font; font.pixelSize: 18 * S.u
                }
            }
        }
    }

    Text {
        y: 320 * S.u
        anchors.horizontalCenter: parent.horizontalCenter
        visible: !page.loading && model.count === 0
        text: "No results."
        color: S.dim
        font.family: S.font
        font.pixelSize: 34 * S.u
    }
}
