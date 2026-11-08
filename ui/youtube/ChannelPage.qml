// A channel, as YouTube's TV app shows it: its banner across the top, fading into the page; the
// search pill; its picture, name, handle and subscribers, two lines of its description, and Play
// mix and Subscribe; under them its shelves (For you, Videos, Shorts, its playlists). Down into
// the second shelf, the banner and the header give way to the shelves. A page without a banner
// or a mix (a playlist) keeps the plain header: its name, its picture and name in a pill, the
// description beside it. The guide gives way to a back button (Left from the first card or the
// buttons); Back goes back.
import QtQuick

FocusScope {
    id: page
    objectName: "channel"
    property string channelId: ""
    property var head: ({})
    property bool loaded: false
    property string problem: ""
    readonly property string label: head.title || ""
    readonly property bool hero: !!(head.banner || head.mix)
    readonly property bool scrolled: feed.activeFocus && feed.index > 0
    readonly property real side: 96 * Y.u      // where the hero page starts (no guide on it)
    signal closed()

    Component.onCompleted: load()
    function load() {
        Y.call("channel", {id: channelId}, r => {
            loaded = true;
            head = r.header || {};
            feed.setPage(r);
            if (hero && head.mix) mixButton.forceActiveFocus();
            else if (hero) subButton.forceActiveFocus();
            else if (feed.count) feed.forceActiveFocus();
            else backButton.forceActiveFocus();
        }, e => { loaded = true; problem = e; backButton.forceActiveFocus(); });
    }
    function playMix() {
        const m = head.mix;
        Y.call("mix", {id: m.id, params: m.params || ""}, r => {
            const items = r.items || [];
            if (items.length) Y.playList(items.slice(1), items[0]);
            else Y.open({type: "video", id: m.id});
        }, e => Y.toast(e));
    }
    function subscribe() {
        if (!Y.signedIn) return Y.toast("Sign in to subscribe: the guide's picture, then Add account.");
        const on = !head.subscribed;
        Y.call("subscribe", {id: channelId, on: on}, () => { page.head = Object.assign({}, page.head, {subscribed: on}); }, e => Y.toast(e));
    }
    function firstButton() { (head.mix ? mixButton : subButton).forceActiveFocus(); }
    onActiveFocusChanged: if (activeFocus && !feed.activeFocus && !backButton.activeFocus && !buttons.activeFocus && !search.activeFocus)
        (hero ? buttons : feed.count ? feed : backButton).forceActiveFocus()
    Keys.onEscapePressed: closed()
    Keys.onBackPressed: closed()

    // ---- the hero header (a channel with a banner)
    Item {
        anchors.fill: parent
        visible: page.hero
        opacity: page.scrolled ? 0 : 1
        Behavior on opacity { NumberAnimation { duration: 220 } }
        Image {
            id: banner
            width: parent.width
            height: width * 9 / 16
            source: (page.head.banner || "").replace("=w1280-", "=w1920-")
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            opacity: status === Image.Ready ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 300 } }
        }
        Rectangle {                           // the banner fades into the page: from the left
            anchors.fill: banner
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: Qt.rgba(0.06, 0.06, 0.06, 0.85) }
                GradientStop { position: 0.6; color: Qt.rgba(0.06, 0.06, 0.06, 0.2) }
                GradientStop { position: 1.0; color: Qt.rgba(0.06, 0.06, 0.06, 0.1) }
            }
        }
        Rectangle {                           // and to the bottom
            anchors.fill: banner
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(0.06, 0.06, 0.06, 0.1) }
                GradientStop { position: 0.45; color: Qt.rgba(0.06, 0.06, 0.06, 0.25) }
                GradientStop { position: 0.88; color: Y.bg }
            }
        }
        Header {
            id: search
            x: page.side
            width: parent.width - page.side
            logo: false
            idle: "#26ffffff"
            onSearchAsked: Y.search("")
            onDown: page.firstButton()
        }
        RoundImage {
            x: page.side; y: 488 * Y.u
            width: 72 * Y.u; height: width
            source: page.head.avatar || ""
            fallback: page.head.title || ""
        }
        Text {
            x: 186 * Y.u; y: 484 * Y.u
            width: parent.width - x - page.side
            text: page.head.title || ""
            color: Y.text
            font.family: Y.font; font.pixelSize: 36 * Y.u; font.weight: Font.Bold
            elide: Text.ElideRight
        }
        Row {
            x: 186 * Y.u; y: 533 * Y.u
            spacing: 0
            Text {
                text: (page.head.lines || [])[0] || ""
                color: Y.text
                font.family: Y.font; font.pixelSize: 24 * Y.u
            }
            Text {
                text: (page.head.lines || []).slice(1).map(l => " • " + l).join("")
                color: Y.dim
                font.family: Y.font; font.pixelSize: 24 * Y.u
            }
        }
        Text {
            x: page.side; y: 600 * Y.u
            width: 845 * Y.u
            text: page.head.description || ""
            color: Y.text
            font.family: Y.font; font.pixelSize: 26 * Y.u
            lineHeight: 39 * Y.u; lineHeightMode: Text.FixedHeight
            wrapMode: Text.WordWrap
            maximumLineCount: 2
            elide: Text.ElideRight
        }
        FocusScope {
            id: buttons
            x: page.side; y: 726 * Y.u
            width: row.width; height: 72 * Y.u
            Row {
                id: row
                spacing: 24 * Y.u
                Pill {
                    id: mixButton
                    visible: !!page.head.mix
                    icon: "live"
                    label: "Play mix"
                    onPressed: page.playMix()
                    KeyNavigation.right: subButton
                }
                Pill {
                    id: subButton
                    label: page.head.subscribed ? "Subscribed" : "Subscribe"
                    onPressed: page.subscribe()
                    Keys.onLeftPressed: e => { if (mixButton.visible) mixButton.forceActiveFocus(); else backButton.forceActiveFocus(); }
                }
            }
            Keys.onLeftPressed: backButton.forceActiveFocus()
            Keys.onUpPressed: search.forceActiveFocus()
            Keys.onDownPressed: if (feed.count) feed.forceActiveFocus()
        }
    }

    // ---- the plain header (a playlist, a channel without a banner)
    Text {
        visible: !page.hero
        x: Y.left; y: 52 * Y.u
        text: page.head.title || ""
        color: Y.text
        font.family: Y.font; font.pixelSize: 50 * Y.u; font.weight: Font.Medium   // (YouTube's: Roboto Medium, not the pages' heavy titles)
    }
    Rectangle {
        id: pill
        x: Y.left; y: 120 * Y.u
        visible: !page.hero && !!page.head.title
        height: 72 * Y.u
        width: pillRow.implicitWidth + 44 * Y.u
        radius: height / 2
        color: Y.raised
        Row {
            id: pillRow
            x: 8 * Y.u
            anchors.verticalCenter: parent.verticalCenter
            spacing: 14 * Y.u
            RoundImage {
                width: 56 * Y.u; height: width
                anchors.verticalCenter: parent.verticalCenter
                source: page.head.avatar || ""
                fallback: page.head.title || ""
            }
            Text { text: page.head.title || ""; color: Y.text; font.family: Y.font; font.pixelSize: 28 * Y.u; font.weight: Font.Medium; anchors.verticalCenter: parent.verticalCenter }
        }
    }
    Text {
        visible: !page.hero
        anchors { left: pill.right; leftMargin: 48 * Y.u; verticalCenter: pill.verticalCenter }
        width: page.width - x - 108 * Y.u
        text: page.head.description || (page.head.lines || []).join(" • ")
        color: Y.text
        font.family: Y.font; font.pixelSize: 24 * Y.u
        elide: Text.ElideRight
    }

    Feed {
        id: feed
        y: !page.hero ? 205 * Y.u : page.scrolled ? 40 * Y.u : 870 * Y.u
        Behavior on y { enabled: page.hero; NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
        width: parent.width
        height: parent.height - y
        indent: page.hero ? page.side : Y.left
        boxed: true
        rowGap: 106 * Y.u                      // 115 px from a focused row to the next, as YouTube's
        onAtTop: if (page.hero) page.firstButton()
        onOpen: it => page.channelId.indexOf("VL") === 0 ? Y.playList(feed.itemsAfter(it), it) : Y.open(it)   // a playlist: in order
    }
    Connections {                             // Left off the first card: the back button, not the guide
        target: Y
        enabled: page.activeFocus
        function onToGuide() { backButton.forceActiveFocus(); }
    }
    Rectangle {
        id: backButton
        x: page.hero ? 12 * Y.u : 42 * Y.u
        y: page.hero && !page.scrolled && !feed.activeFocus ? 726 * Y.u : 504 * Y.u
        width: 72 * Y.u; height: width; radius: width / 2
        visible: !page.hero || activeFocus     // (the hero page: only while it has the focus)
        color: activeFocus ? Y.text : Y.raised
        Icon { anchors.centerIn: parent; name: "back"; size: 40 * Y.u; color: backButton.activeFocus ? Y.ink : Y.text }
        Keys.onReturnPressed: page.closed()
        Keys.onEnterPressed: page.closed()
        Keys.onRightPressed: if (page.hero) page.firstButton(); else if (feed.count) feed.forceActiveFocus()
        Keys.onDownPressed: if (page.hero && feed.count) feed.forceActiveFocus()
    }
    Text {
        visible: !page.loaded || !!page.problem
        x: Y.left; y: 260 * Y.u
        text: page.problem || ""
        color: Y.dim
        font.family: Y.font; font.pixelSize: Y.tMeta
    }
}
