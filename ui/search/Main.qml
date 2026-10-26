// couchbox-search: Google from the couch (started by /usr/lib/couchbox/bin/couchbox-search).
// The start page (a search field and the recent searches), then the real web in Qt WebEngine
// under a toolbar: the arrows move between links and scroll (js/keynav.js),
// OK opens, Back goes back, and Up at the top of a page reaches the toolbar (the search, Back,
// Forward, Reader, text size, and the assistant's Summarize and Ask when it's set up).
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Window
import QtWebEngine
import CouchKit

ApplicationWindow {
    id: win
    width: 1920
    height: 1080
    visible: true
    visibility: shot ? Window.Windowed : Window.FullScreen
    title: "Search"
    color: S.bg
    font.family: S.font

    readonly property var args: Qt.application.arguments
    function arg(name) { const i = args.indexOf(name); return i >= 0 ? args[i + 1] || "" : ""; }
    readonly property string shot: arg("--shot")
    readonly property real u: height / 1080
    onUChanged: S.u = u

    property string mode: "start"            // start | web
    property var status: ({ai: false, aiAnswer: false, history: [], zoom: 1.5})
    property string query: ""                // the search on screen (results page)
    property var answer: null                // the AI answer above the results: {text, sources} | null
    property bool answerBusy: false
    property var typed: null                 // the keyboard pop-up types for this
    property bool consent: false             // Google's cookie choice page is up
    property bool reading: false             // reader view up

    Component.onCompleted: {
        S.u = u;
        S.call("status", {}, st => { win.status = st; view.zoomFactor = st.zoom; openFromArgs(win.arg("--open")); });
        start.forceActiveFocus();
        publish();
    }

    // ------------------------------------------------------------------ actions
    function go(text) {
        const t = (text || "").trim();
        if (!t) return;
        S.call("address", {text: t}, r => {
            if (r.query) S.call("remember", {query: r.query}, h => win.status = Object.assign({}, win.status, {history: h.history}));
            win.mode = "web"; win.reading = false; panel.visible = false;
            win.answer = null;
            view.url = r.url;
            view.forceActiveFocus();
            publish();
        });
    }
    function openFromArgs(target) {
        if (!target) return;
        if (target.startsWith("search:")) go(target.slice(7));
        else if (target.startsWith("url:")) go(target.slice(4));
        else if (target === "reader") { go("eiffel tower height"); later(() => reader(), 600); }
        else if (target === "summary") { go("https://example.org/eiffel-tower"); later(() => summarize(""), 600); }
        else if (target === "home") toStart();
    }
    function later(fn, ms) { const t = Qt.createQmlObject("import QtQuick; Timer {}", win); t.interval = ms; t.triggered.connect(() => { fn(); t.destroy(); }); t.start(); }
    function toStart() {
        mode = "start"; reading = false; panel.visible = false; answer = null;
        view.stop();
        start.idx = 0; start.forceActiveFocus();
        S.call("status", {}, st => win.status = Object.assign({}, st, {zoom: view.zoomFactor}));
        publish();
    }
    function back() {
        if (reading) { reading = false; view.forceActiveFocus(); return; }
        if (panel.visible) { panel.visible = false; view.forceActiveFocus(); return; }
        if (view.canGoBack) { view.goBack(); view.forceActiveFocus(); return; }
        toStart();
    }
    function focusBar(i) { bar.idx = i === undefined ? 0 : i; bar.forceActiveFocus(); }
    function ask(title, current, done) {
        keyboard.title = title; keyboard.doneLabel = title.startsWith("Ask") ? "Ask" : "Search"; keyboard.password = false;
        win.typed = done;
        keyboard.open(current || "", win.activeFocusItem);
    }
    function zoom(d) {
        view.zoomFactor = Math.max(1.0, Math.min(2.5, Math.round((view.zoomFactor + d) * 100) / 100));
        S.call("zoom", {zoom: view.zoomFactor});
        toast.show("Text size " + Math.round(view.zoomFactor * 100) + "%");
    }
    function withArticle(done) {
        view.runJavaScript(backend.script("reader"), js => {
            if (typeof js !== "string") js = "";
            done(js);
        });
    }
    function reader() {
        withArticle(js => S.call("reader", {article: js}, a => {
            if (!a.blocks.length) return toast.show("There's no article on this page to read.");
            readerView.show(a); win.reading = true; readerView.forceActiveFocus(); publish();
        }, e => toast.show(e)));
    }
    function summarize(question) {
        panel.title = question ? "Ask about this page" : "Summary";
        panel.question = question || ""; panel.text = ""; panel.problem = ""; panel.busy = true;
        panel.visible = true; panel.forceActiveFocus();
        withArticle(js => S.call("summarize", {article: js, question: question || ""},
                                 r => { panel.busy = false; panel.text = r.text || "The assistant didn't answer."; },
                                 e => { panel.busy = false; panel.problem = e; }));
    }
    function pageLoaded() {
        view.runJavaScript(backend.script("keynav"));
        win.consent = /^https?:\/\/consent\./.test(view.url.toString());
        const q = queryOf(view.url.toString());
        win.query = q;
        if (q && status.ai && status.aiAnswer && (!answer || answer.query !== q) && !answerBusy) {
            answerBusy = true;
            answer = {query: q, text: "", sources: []};
            view.runJavaScript(backend.script("results"), js => {
                S.call("answer", {query: q, results: typeof js === "string" ? js : "[]"},
                       r => { win.answerBusy = false; win.answer = r.text ? {query: q, text: r.text, sources: r.sources} : null; },
                       e => { win.answerBusy = false; win.answer = null; });
            });
        } else if (!q) answer = null;
        publish();
    }
    function queryOf(url) {
        const m = /^https?:\/\/(www\.)?google\.[a-z.]+\/search\?(.*)$/.exec(url);
        if (!m) return "";
        for (const part of m[2].split("&")) if (part.startsWith("q=")) return decodeURIComponent(part.slice(2).replace(/\+/g, " "));
        return "";
    }
    function publish() {
        control.setState(JSON.stringify({page: mode === "start" ? "start" : reading ? "reader" : "web",
                                         url: mode === "web" ? view.url.toString() : "", title: mode === "web" ? view.title : "", query: win.query}));
    }

    Connections {
        target: control
        function onCommand(json) {
            const req = JSON.parse(json);
            if (req.op === "open") win.openFromArgs(req.target || "");
        }
        function onEvalJs(rid, code) { view.runJavaScript(code, r => control.pageRead(rid, JSON.stringify(r === undefined ? null : r))); }
        function onReadPage(rid) {
            if (win.mode !== "web") { control.pageRead(rid, ""); return; }
            win.withArticle(js => control.pageRead(rid, js));
        }
    }

    // ------------------------------------------------------------------ start page
    StartPage {
        id: start
        anchors.fill: parent
        visible: win.mode === "start"
        history: win.status.history || []
        ai: win.status.ai
        onAsk: win.ask("Search Google", "", t => win.go(t))
        onSearch: t => win.go(t)
        onForget: S.call("forget", {}, h => win.status = Object.assign({}, win.status, {history: h.history}))
        Keys.onEscapePressed: Qt.quit()
        Keys.onBackPressed: Qt.quit()
    }

    // ------------------------------------------------------------------ toolbar
    FocusScope {
        id: bar
        visible: win.mode === "web" && !win.reading
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: 112 * S.u
        property int idx: 0
        readonly property var buttons: {
            const b = [{id: "back", glyph: "←", text: "", on: view.canGoBack}, {id: "forward", glyph: "→", text: "", on: view.canGoForward},
                       {id: "reader", glyph: "≡", text: "Reader", on: true},
                       {id: "smaller", glyph: "", text: "A−", on: view.zoomFactor > 1.0}, {id: "bigger", glyph: "", text: "A+", on: view.zoomFactor < 2.5}];
            if (win.status.ai) b.push({id: "summarize", glyph: "✦", text: "Summarize", on: true, ai: true}, {id: "ask", glyph: "✦", text: "Ask", on: true, ai: true});
            return b;
        }
        function press(id) {
            if (id === "back") { if (view.canGoBack) view.goBack(); view.forceActiveFocus(); }
            else if (id === "forward") { if (view.canGoForward) view.goForward(); view.forceActiveFocus(); }
            else if (id === "reader") win.reader();
            else if (id === "smaller") win.zoom(-0.1);
            else if (id === "bigger") win.zoom(0.1);
            else if (id === "summarize") win.summarize("");
            else if (id === "ask") win.ask("Ask about this page", "", t => win.summarize(t));
        }
        Keys.onLeftPressed: idx = Math.max(0, idx - 1)
        Keys.onRightPressed: idx = Math.min(buttons.length, idx + 1)
        Keys.onDownPressed: view.forceActiveFocus()
        Keys.onReturnPressed: act()
        Keys.onEnterPressed: act()
        Keys.onEscapePressed: win.back()
        Keys.onBackPressed: win.back()
        function act() {
            if (idx === 0) win.ask("Search Google", win.query || (view.url.toString().startsWith("http") ? view.url.toString() : ""), t => win.go(t));
            else press(buttons[idx - 1].id);
        }

        Rectangle { anchors.fill: parent; color: S.bg }
        Rectangle {                              // the search / address
            id: field
            anchors { left: parent.left; leftMargin: S.edge; verticalCenter: parent.verticalCenter }
            width: parent.width - 2 * S.edge - tools.width - 24 * S.u
            height: 72 * S.u; radius: 36 * S.u
            readonly property bool sel: bar.activeFocus && bar.idx === 0
            color: sel ? S.panel2 : S.panel
            border.color: sel ? S.focus : S.line; border.width: (sel ? 3 : 1) * S.u
            Image { id: g2; x: 26 * S.u; anchors.verticalCenter: parent.verticalCenter; width: 30 * S.u; height: width; sourceSize: Qt.size(width, height); source: "icons/search.svg"; opacity: 0.7 }
            Text {
                anchors { left: g2.right; leftMargin: 18 * S.u; right: parent.right; rightMargin: 28 * S.u; verticalCenter: parent.verticalCenter }
                text: win.query || view.title || view.url.toString()
                color: win.query ? S.text : S.text2; font.family: S.font; font.pixelSize: 26 * S.u; elide: Text.ElideRight
            }
        }
        Row {
            id: tools
            anchors { right: parent.right; rightMargin: S.edge; verticalCenter: parent.verticalCenter }
            spacing: 12 * S.u
            Repeater {
                model: bar.buttons
                SButton {
                    required property var modelData
                    required property int index
                    glyph: modelData.glyph; text: modelData.text; ai: !!modelData.ai; on: modelData.on
                    border.color: bar.activeFocus && bar.idx === index + 1 ? (ai ? S.ai : S.focus) : S.line
                    border.width: (bar.activeFocus && bar.idx === index + 1 ? 3 : 1) * S.u
                    color: bar.activeFocus && bar.idx === index + 1 ? (ai ? "#3b2f63" : S.panel2) : S.panel
                }
            }
        }
        Rectangle {                              // loading
            anchors { left: parent.left; bottom: parent.bottom }
            height: 4 * S.u
            width: parent.width * view.loadProgress / 100
            color: S.accent
            visible: view.loading
        }
    }

    // ------------------------------------------------------------------ the AI answer, above the results
    Rectangle {
        id: answerBox
        visible: win.mode === "web" && !win.reading && !!win.answer && !!win.query
        anchors { left: parent.left; right: parent.right; top: bar.bottom; leftMargin: S.edge; rightMargin: S.edge; topMargin: 8 * S.u }
        height: visible ? answerCol.height + 40 * S.u : 0
        radius: S.radius
        color: "#16131f"; border.color: "#3a3157"; border.width: 1.5 * S.u
        Column {
            id: answerCol
            x: 30 * S.u; y: 20 * S.u
            width: parent.width - 60 * S.u
            spacing: 8 * S.u
            Row {
                spacing: 12 * S.u
                Image { width: 28 * S.u; height: width; sourceSize: Qt.size(width, height); source: "icons/spark.svg"; anchors.verticalCenter: parent.verticalCenter }
                Text { text: "AI answer"; color: S.ai; font.family: S.font; font.pixelSize: S.tMeta; font.weight: Font.Bold; anchors.verticalCenter: parent.verticalCenter }
                Text { text: "· written by the assistant from the results below; check them"; color: S.dim; font.family: S.font; font.pixelSize: 19 * S.u; anchors.verticalCenter: parent.verticalCenter }
            }
            Text {
                width: parent.width
                text: win.answerBusy ? "Reading the results…" : win.answer ? win.answer.text : ""
                color: win.answerBusy ? S.dim : "#ece9f7"
                font.family: S.font; font.pixelSize: 27 * S.u; wrapMode: Text.WordWrap; maximumLineCount: 4; elide: Text.ElideRight
                textFormat: Text.PlainText
            }
        }
    }

    // ------------------------------------------------------------------ Google's cookie choice
    Rectangle {
        id: consentBox
        visible: win.mode === "web" && win.consent && !win.reading
        anchors { left: parent.left; right: parent.right; top: answerBox.visible ? answerBox.bottom : bar.bottom; leftMargin: S.edge; rightMargin: S.edge; topMargin: 8 * S.u }
        height: visible ? 70 * S.u : 0
        radius: 12 * S.u; color: S.panel; border.color: S.line
        Text {
            anchors { fill: parent; leftMargin: 26 * S.u; rightMargin: 26 * S.u }
            verticalAlignment: Text.AlignVCenter
            text: "Google asks about cookies before searching. Pick a choice on the page with the arrows, then OK. Search keeps it."
            color: S.text2; font.family: S.font; font.pixelSize: S.tMeta; elide: Text.ElideRight
        }
    }

    // ------------------------------------------------------------------ the page
    FocusScope {
        id: pageArea
        visible: win.mode === "web"
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom
                  top: consentBox.visible ? consentBox.bottom : answerBox.visible ? answerBox.bottom : bar.bottom
                  topMargin: consentBox.visible || answerBox.visible ? 8 * S.u : 0 }
        // keys the page didn't use come here: Up at the very top (nothing above, nowhere to
        // scroll) is the toolbar; Back goes back
        Keys.onUpPressed: win.focusBar()
        Keys.onEscapePressed: win.back()
        Keys.onBackPressed: win.back()

        WebEngineView {
            id: view
            anchors.fill: parent
            focus: true
            backgroundColor: "white"
            audioMuted: muted
            zoomFactor: 1.5
            settings.spatialNavigationEnabled: false       // js/keynav.js moves between links
            settings.focusOnNavigationEnabled: true
            settings.playbackRequiresUserGesture: true
            settings.showScrollBars: true
            settings.javascriptCanOpenWindows: false
            profile: WebEngineProfile {
                id: profile
                storageName: "couchbox-search"
                offTheRecord: false
                httpCacheMaximumSize: 64 * 1024 * 1024
                // Chrome's own user agent (without "QtWebEngine"), so sites send their normal pages
                Component.onCompleted: httpUserAgent = httpUserAgent.replace(/ QtWebEngine\/[0-9.]+/, "")
            }
            onLoadingChanged: if (!loading) win.pageLoaded()
            onTitleChanged: win.publish()
            onNewWindowRequested: request => request.openIn(view)          // links that open a new window: here
            onFullScreenRequested: request => request.accept()
            onPermissionRequested: permission => permission.deny()      // location, camera, notifications: no
            onJavaScriptConsoleMessage: (level, message, line, source) => {
                if (message.startsWith("couchbox:")) console.log("page: " + message.slice(0, 80));
                if (message === "couchbox:top") win.focusBar();
                else if (message === "couchbox:back") win.back();
                else if (message.startsWith("couchbox:edit ")) {
                    let f = {};
                    try { f = JSON.parse(message.slice(14)); } catch (e) {}
                    keyboard.password = !!f.password;
                    keyboard.title = f.label || "Type"; keyboard.doneLabel = "Done";
                    win.typed = t => view.runJavaScript("couchboxSetText(" + JSON.stringify(t) + ", true)");
                    keyboard.open(f.text || "", view);
                }
            }
        }
    }

    AiPanel {
        id: panel
        visible: false
        anchors { right: parent.right; top: bar.bottom; bottom: parent.bottom; rightMargin: 28 * S.u; topMargin: 12 * S.u; bottomMargin: 28 * S.u }
        width: 720 * S.u
        z: 10
        onClosed: { visible = false; view.forceActiveFocus(); }
    }

    ReaderView {
        id: readerView
        anchors.fill: parent
        visible: win.reading
        z: 20
        onClosed: { win.reading = false; view.forceActiveFocus(); win.publish(); }
    }

    TextEntry {
        id: keyboard
        anchors.fill: parent
        z: 100
        title: "Search Google"
        accent: S.accent; bg: S.bg; panel: S.panel; keyColor: S.panel2; line: S.line; ink: S.text; dim: S.dim
        onAccepted: t => { if (win.typed) { const done = win.typed; win.typed = null; done(t); } }
        onCanceled: win.typed = null
    }

    Rectangle {                                  // notices
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
        Timer { id: toastTimer; interval: 3000; onTriggered: toast.opacity = 0 }
    }

    // ------------------------------------------------------------------ idle, off-screen tests
    // Quit after an hour without use.
    onActiveFocusItemChanged: idle.restart()
    Timer { id: idle; interval: 60 * 60 * 1000; running: true; onTriggered: Qt.quit() }

    // --shot FILE [--open search:TEXT | url:ADDRESS | reader | summary] [--keys k1,k2,...]
    Timer {
        running: !!win.shot
        interval: 2500
        onTriggered: {
            const keys = win.arg("--keys");
            if (keys) for (const k of keys.split(",")) shooter.press(k);
            shotTimer.start();
        }
    }
    Timer { id: shotTimer; interval: 2500; onTriggered: { shooter.save(win.shot); Qt.quit(); } }
}
