// couchbox-seerr: Seerr as a TV app (started by /usr/lib/couchbox/bin/couchbox-seerr), laid out like the
// website: the sidebar (Discover, Movies, Series, Requests), the search bar across the top,
// and the pages (Discover rows, movie and show details, people, grids, requests) with the
// request dialog. Remote: arrows move, OK opens or presses, Back goes back (and, on
// Discover, leaves the app). Up from a page's top reaches search, Left from a row's start
// reaches the sidebar. Seerr is reached through couchbox-voice's proxy, which holds the API key.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Window
import CouchKit

ApplicationWindow {
    id: win
    width: 1920
    height: 1080
    visible: true
    visibility: shot ? Window.Windowed : Window.FullScreen
    title: "Seerr"
    color: S.bg
    font.family: S.font

    readonly property var args: Qt.application.arguments
    function arg(name) { const i = args.indexOf(name); return i >= 0 ? args[i + 1] || "" : ""; }
    readonly property string shot: arg("--shot")
    readonly property real u: height / 1080
    onUChanged: S.u = u

    readonly property var sections: [["Discover", "✦"], ["Movies", "▤"], ["Series", "▭"], ["Requests", "◷"], ["Issues", "⚠"]]
    property int section: 0
    property var me: null
    property string query: ""
    property var typed: null                     // set while the keyboard pop-up types for a dialog

    Component.onCompleted: {
        S.u = u;
        S.get("/auth/me", r => me = r);
    }

    // ------------------------------------------------------------------ navigation
    Component { id: discoverC; DiscoverPage {} }
    Component { id: gridC; GridPage {} }
    Component { id: mediaC; MediaPage {} }
    Component { id: personC; PersonPage {} }
    Component { id: requestsC; RequestsPage {} }
    Component { id: peopleC; PeoplePage {} }
    Component { id: issuesC; IssuesPage {} }

    function showSection(i) {
        section = i;
        const page = i === 0 ? discoverC : i === 3 ? requestsC : i === 4 ? issuesC : gridC;
        const props = i === 1 ? {title: "Movies", path: "/discover/movies", mediaType: "movie", filters: true}
                    : i === 2 ? {title: "Series", path: "/discover/tv", mediaType: "tv", filters: true} : {};
        stack.clear();
        stack.push(page, props, StackView.Immediate);
        stack.forceActiveFocus();
    }
    function push(c, props) {
        stack.push(c, props);
        stack.forceActiveFocus();
    }
    function back() {
        if (keyboard.visible || dialog.visible || issue.visible || picker.visible) return;
        if (sidebar.activeFocus || searchBar.activeFocus) return stack.forceActiveFocus();
        if (stack.depth > 1) { stack.pop(); return stack.forceActiveFocus(); }
        if (section !== 0) return showSection(0);
        Qt.quit();
    }
    function search(text) {
        text = text.trim();
        query = text;
        if (text) push(gridC, {title: "Search Results for “" + text + "”", path: "/search?query=" + encodeURIComponent(text), empty: "Nothing found for “" + text + "”."});
    }

    Connections {
        target: S
        function onOpenMedia(type, id) { win.push(mediaC, {mediaType: type, tmdbId: id}); }
        function onOpenPerson(id) { win.push(personC, {personId: id}); }
        function onOpenGrid(title, path, type) { win.push(gridC, {title: title, path: path, mediaType: type}); }
        function onOpenRequests() { win.showSection(3); }
        function onOpenRequest(media) { dialog.open(media); }
        function onOpenIssue(media) { issue.open(media); }
        function onOpenPeople(title, path) { win.push(peopleC, {title: title, path: path}); }
        function onAskText(title, text, done) {
            win.typed = done;
            keyboard.title = title;
            keyboard.doneLabel = "Done";
            keyboard.open(text, win.activeFocusItem);
        }
        function onPick(title, options, current, done) { picker.open(title, options, current, done); }
        function onClosedDialog() { stack.forceActiveFocus(); }
        function onToast(text) { toast.show(text); }
    }

    // keys the pages didn't use: Up -> search, Left -> sidebar, Back -> back
    FocusScope {
        id: ui
        anchors.fill: parent
        focus: true
        Keys.onUpPressed: searchBar.forceActiveFocus()
        Keys.onLeftPressed: sidebar.forceActiveFocus()
        Keys.onEscapePressed: win.back()
        Keys.onBackPressed: win.back()
        Keys.onPressed: event => {                // typing on the phone starts a search
            if (!dialog.visible && !issue.visible && event.text.length === 1 && event.text > " " && !(event.modifiers & Qt.ControlModifier)) {
                keyboard.open(event.text, stack);
                event.accepted = true;
            }
        }

        StackView {
            id: stack
            x: 300 * win.u + S.gutter
            width: parent.width - x
            height: parent.height
            focus: true
            pushEnter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 160 } }
            pushExit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 120 } }
            popEnter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 160 } }
            popExit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 120 } }
            Component.onCompleted: push(discoverC, {}, StackView.Immediate)
        }

        // ------------------------------------------------------------------ search bar + avatar
        Rectangle {                              // pages scroll under the bar: dim them there
            x: 300 * win.u
            width: parent.width - x
            height: 104 * win.u
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(0.07, 0.09, 0.15, 0.99) }
                GradientStop { position: 0.82; color: Qt.rgba(0.07, 0.09, 0.15, 0.97) }
                GradientStop { position: 1.0; color: Qt.rgba(0.07, 0.09, 0.15, 0) }
            }
        }
        Rectangle {
            id: searchBar
            x: 300 * win.u + S.gutter
            y: 22 * win.u
            width: parent.width - x - 112 * win.u
            height: 58 * win.u
            radius: 12 * win.u
            color: activeFocus ? Qt.rgba(0.22, 0.25, 0.32, 0.95) : Qt.rgba(0.12, 0.16, 0.22, 0.7)
            border.color: activeFocus ? S.focus : S.line
            border.width: activeFocus ? 3 * win.u : 1
            Text {
                anchors { left: parent.left; leftMargin: 22 * win.u; verticalCenter: parent.verticalCenter }
                text: "⌕   " + (win.query || "Search Movies & TV")
                color: win.query ? S.text : S.dim
                font.family: S.font
                font.pixelSize: 23 * win.u
            }
            Keys.onReturnPressed: keyboard.open(win.query, searchBar)
            Keys.onEnterPressed: keyboard.open(win.query, searchBar)
            Keys.onDownPressed: stack.forceActiveFocus()
            Keys.onUpPressed: {}
        }
        RoundImage {
            anchors { right: parent.right; rightMargin: S.edge; verticalCenter: searchBar.verticalCenter }
            width: 48 * win.u
            height: width
            source: win.me && win.me.avatar ? (win.me.avatar.startsWith("http") ? win.me.avatar : seerrUrl + win.me.avatar) : ""
            sourceWidth: 80
        }

        // ------------------------------------------------------------------ sidebar
        Rectangle {
            width: 300 * win.u
            height: parent.height
            color: S.side
            Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: S.line }

            Row {                                    // the logo
                x: 32 * win.u
                y: 30 * win.u
                spacing: 18 * win.u
                Item {
                    width: 64 * win.u; height: width
                    Rectangle {
                        anchors.fill: parent; radius: width / 2
                        gradient: Gradient {
                            GradientStop { position: 0; color: "#a78bfa" }
                            GradientStop { position: 1; color: "#6d28d9" }
                        }
                    }
                    Rectangle { x: parent.width * 0.16; y: parent.height * 0.2; width: parent.width * 0.68; height: width; radius: width / 2; color: "#1e1b4b" }
                    Rectangle { x: parent.width * 0.3; y: parent.height * 0.3; width: parent.width * 0.2; height: width; radius: width / 2; color: "#c4b5fd"; opacity: 0.9 }
                }
                Text {
                    text: "seerr"
                    color: S.text
                    font.family: S.font
                    font.pixelSize: 54 * win.u
                    font.weight: Font.DemiBold
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            ListView {
                id: sidebar
                x: 24 * win.u
                y: 160 * win.u
                width: parent.width - 48 * win.u
                height: count * 72 * win.u
                interactive: false
                spacing: 12 * win.u
                model: win.sections.length
                currentIndex: win.section
                delegate: Rectangle {
                    required property int index
                    readonly property bool here: index === win.section
                    readonly property bool cur: ListView.isCurrentItem && sidebar.activeFocus
                    width: sidebar.width
                    height: 60 * win.u
                    radius: 10 * win.u
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0; color: here ? S.indigoDark : cur ? S.panel2 : "transparent" }
                        GradientStop { position: 1; color: here ? S.purple : cur ? S.panel2 : "transparent" }
                    }
                    border.color: cur ? S.focus : "transparent"
                    border.width: 3 * win.u
                    Row {
                        x: 18 * win.u
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 18 * win.u
                        Text { text: win.sections[index][1]; color: S.text; font.pixelSize: 24 * win.u; width: 28 * win.u; horizontalAlignment: Text.AlignHCenter }
                        Text { text: win.sections[index][0]; color: S.text; font.family: S.font; font.pixelSize: 25 * win.u; font.weight: Font.Medium }
                    }
                }
                Keys.onUpPressed: if (currentIndex > 0) currentIndex--
                Keys.onDownPressed: if (currentIndex < count - 1) currentIndex++
                Keys.onRightPressed: stack.forceActiveFocus()
                Keys.onReturnPressed: win.showSection(currentIndex)
                Keys.onEnterPressed: win.showSection(currentIndex)
                onActiveFocusChanged: if (!activeFocus) currentIndex = Qt.binding(() => win.section)
            }
        }
    }

    RequestDialog { id: dialog; anchors.fill: parent }
    IssueDialog { id: issue; anchors.fill: parent }
    Picker { id: picker; anchors.fill: parent }

    TextEntry {
        id: keyboard
        anchors.fill: parent
        title: "Search Movies & TV"
        accent: S.indigo; bg: S.bg; panel: S.panel; keyColor: S.panel2; line: S.line; ink: S.text; dim: S.dim
        onAccepted: t => {
            if (win.typed) { const done = win.typed; win.typed = null; done(t); }
            else win.search(t);
            title = "Search Movies & TV"; doneLabel = "Search";
        }
        onCanceled: { win.typed = null; title = "Search Movies & TV"; doneLabel = "Search"; }
    }

    Rectangle {                                  // notices ("Requested …")
        id: toast
        function show(t) { toastText.text = t; opacity = 1; toastTimer.restart(); }
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 48 * win.u }
        width: toastText.implicitWidth + 56 * win.u
        height: 72 * win.u
        radius: 14 * win.u
        color: S.panel2
        border.color: S.line
        opacity: 0
        z: 200
        Behavior on opacity { NumberAnimation { duration: 200 } }
        Text { id: toastText; anchors.centerIn: parent; color: S.text; font.family: S.font; font.pixelSize: 24 * win.u }
        Timer { id: toastTimer; interval: 3500; onTriggered: toast.opacity = 0 }
    }

    // ------------------------------------------------------------------ idle, off-screen tests
    // Like couchbox-memory does for the other apps: quit after an hour without use.
    onActiveFocusItemChanged: idle.restart()
    Timer { id: idle; interval: 60 * 60 * 1000; running: true; onTriggered: Qt.quit() }

    // --shot FILE [--open movie:ID | tv:ID | person:ID | people:movie:ID:cast | requests | movies | series | search:TEXT]
    //            [--dialog | --issue | --pick] [--keyboard] [--down N]
    Timer {
        running: !!win.shot
        interval: 1500
        onTriggered: {
            const o = win.arg("--open");
            if (o.startsWith("movie:") || o.startsWith("tv:")) S.openMedia(o.split(":")[0], parseInt(o.split(":")[1]));
            else if (o.startsWith("person:")) S.openPerson(parseInt(o.split(":")[1]));
            else if (o === "requests") win.showSection(3);
            else if (o === "movies") win.showSection(1);
            else if (o === "issues") win.showSection(4);
            else if (o === "series") win.showSection(2);
            else if (o.startsWith("people:")) S.openPeople("Cast", "people/" + o.slice(7).split(":").join("/"));
            else if (o.startsWith("search:")) win.search(o.slice(7));
            if (win.args.indexOf("--keyboard") >= 0) keyboard.open("dune", searchBar);
            downs = parseInt(win.arg("--down") || "0");
            shotTimer.start();
        }
    }
    property int downs: 0                        // --down N: move down N rows before the shot
    Timer {
        interval: 700
        repeat: true
        running: shotTimer.running && win.downs > 0
        onTriggered: if (stack.currentItem && stack.currentItem.move && win.downs > 0 && stack.currentItem.move(1)) win.downs--
    }
    Timer {
        id: shotTimer
        interval: 9000
        onTriggered: {
            if (win.args.indexOf("--dialog") >= 0 && stack.currentItem && stack.currentItem.d) {
                S.openRequest(stack.currentItem.d);
                return dialogShot.start();
            }
            if (win.args.indexOf("--issue") >= 0 && stack.currentItem && stack.currentItem.d) {
                S.openIssue(stack.currentItem.d);
                return dialogShot.start();
            }
            if (win.args.indexOf("--pick") >= 0) {
                S.pick("Genre", ["All Genres", "Action", "Adventure", "Animation", "Comedy", "Crime", "Documentary", "Drama"], 2, () => {});
                return dialogShot.start();
            }
            shooter.save(win.shot);
            Qt.quit();
        }
    }
    Timer { id: dialogShot; interval: 3000; onTriggered: { shooter.save(win.shot); Qt.quit(); } }
}
