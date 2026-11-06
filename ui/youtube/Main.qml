// couchbox-yt: YouTube as a native TV app (started by /usr/lib/couchbox/bin/couchbox-yt), laid out
// like YouTube's TV app. The guide on the left picks the page (Home, the tabs, Search...);
// channels and the player open on top of the pages, and Back goes back down. Left from a page's
// first column, or Back, goes to the guide; Back from the guide goes Home, and from Home's guide
// leaves the app. With accounts on the TV it starts on "Who's watching" (ProfilesPage); Add
// account shows a code for youtube.com/activate (SignInPage). The back end is
// couchbox.services.youtube, ytauth and ytstream, through Backend's threads.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Window
import CouchPlayer

ApplicationWindow {
    id: win
    width: 1920
    height: 1080
    visible: true
    visibility: shot ? Window.Windowed : Window.FullScreen
    title: "YouTube"
    color: Y.bg
    font.family: Y.font

    readonly property var args: Qt.application.arguments
    function arg(name) { const i = args.indexOf(name); return i >= 0 ? args[i + 1] || "" : ""; }
    readonly property string shot: arg("--shot")
    readonly property real u: height / 1080
    onUChanged: Y.u = u

    property string section: "home"
    property bool ready: false
    readonly property bool playing: stack.depth > 0 && stack.currentItem && stack.currentItem.videoId !== undefined
    readonly property var tabs: ({music: 1, gaming: 1, news: 1, podcasts: 1, movies: 1, live: 1, sports: 1})
    property bool picking: false               // "Who's watching" is up
    property bool shortsFromGuide: false       // Shorts opened from the guide: Back returns to it
    // Library's tiles that need no account (a guest's Library shows them over its sign-in note)
    readonly property var guestTiles: [{title: "Movies & TV", id: "FEstorefront", colors: ["#7a5600", "#d6a10a"]},
                                       {title: "Podcasts", id: "FEtopics_podcasts", colors: ["#6a0f6a", "#b0209a"]}]
    property bool pickedAtStart: false         // ... as the app started (Back there leaves the app)
    property string pendingOpen: ""            // asked for (control socket) before the app was ready

    Component.onCompleted: {
        Y.u = u;
        Y.video = video;
        Y.shot = !!shot;
        Y.call("status", {}, r => {
            guide.entries = r.guide;
            if (r.settings) Y.settings = r.settings;
            win.homeCopy = r.homeCopy || null;
            ready = true;
            const o = pendingOpen || arg("--open");
            const want = args.indexOf("--profile") >= 0 ? arg("--profile") : null;
            const profiles = r.profiles || [];
            const cur = profiles.find(p => p.id === r.current);
            if (want === "pick" || (want === null && !r.demo && profiles.length && !o)) { pickedAtStart = true; showProfiles(); }
            else if (want !== null) win.use(want, o);
            else if (r.demo) win.started(cur || null, o);            // the demo: as its first profile
            else win.use(profiles.find(p => p.id === r.last) ? r.last : "", o);
        }, e => { problem.text = e; });
    }
    // watch as a profile ("" a guest), then Home (or what --open asked for)
    function use(pid, then) {
        Y.call("use", {id: pid || ""}, r => started(r.profile || null, then), e => { Y.toast(e); started(null, then); });
    }
    function started(profile, then) {
        Y.profile = profile;
        picking = false;
        stack.clear(StackView.Immediate);
        home.loaded = false;
        if (libraryL.item) libraryL.item.loaded = false;
        if (subscriptionsL.item) subscriptionsL.item.loaded = false;
        homeLater = !!then && then.indexOf("video:") === 0;   // straight into a video: Home when it's left
        const id = profile ? profile.id : "guest";              // Home's copy from last time, if it's this profile's
        home.copy = homeCopy && homeCopy.profile === id ? homeCopy.page : null;
        homeCopy = null;
        choose("home");
        focusPage();
        if (then) openTarget(then);
        updateState();
    }
    property bool homeLater: false
    property string afterPick: ""              // what Who's watching opens once a profile is picked
    property var homeCopy: null                // (status: Home as it was, for the profile the app starts as)
    function showProfiles() {
        picking = true;
        profilesPage.load(Y.profile ? Y.profile.id : "");
        profilesPage.forceActiveFocus();
        updateState();
    }

    // ------------------------------------------------------------------ pages
    // Home is made at the start; the other pages the first time they're shown (Loaders: the app's
    // QML took ~770 ms to load on the box, every page made up front)
    function pg(l) { if (!l.active) l.active = true; return l.item; }
    function page(key) {
        if (key === "home") return home;
        if (key === "search") return pg(searchL);
        if (tabs[key]) return pg(tabL);
        if (key === "settings") return pg(settingsL);
        if (key === "subscriptions" && Y.signedIn) return pg(subscriptionsL);
        if (key === "library" && Y.signedIn) return pg(libraryL);
        return message;
    }
    function entry(key) { return (guide.entries || []).find(e => e.key === key) || {key: key, label: key, browse: ""}; }
    function choose(key) {
        if (key === "shorts") return;          // no page of its own: the one behind stays (OK opens the player)
        section = key;
        guide.section = key;
        const e = entry(key);
        if (key === "home") { if (!home.loaded && !homeLater) home.load(); }
        else if (key === "search") { const sp = pg(searchL); sp.begin(sp.query); }
        else if (tabs[key]) { const t = pg(tabL); t.key = key; t.browseId = e.browse; t.label = e.label; t.loaded = false; t.load(); }
        else if (key === "subscriptions" && Y.signedIn) { const sb = pg(subscriptionsL); if (!sb.loaded) sb.load(); }
        else if (key === "library" && Y.signedIn) { const lb = pg(libraryL); if (!lb.loaded) lb.load(); }
        else if (key === "settings") pg(settingsL).load();
        else {
            message.key = key;
            message.facts = [];
            message.action = "";
            message.tiles = key === "library" && !Y.signedIn ? win.guestTiles : [];
            if (key === "shorts") { message.title = ""; message.body = ""; }   // OK on it opens the Shorts player (onEnter)
            else if (key === "subscriptions" || key === "library") {
                message.title = e.label;
                message.body = key === "library" ? "Sign in to see your history, Watch later, playlists and the videos you've liked." : "Sign in to see the latest from the channels you subscribe to.";
                message.action = "Sign in";
            }
        }
        updateState();
    }
    function focusPage() {
        if (picking) profilesPage.forceActiveFocus();
        else if (stack.depth) stack.currentItem.forceActiveFocus();
        else if (section === "search") pg(searchL).forceActiveFocus();
        else page(section).forceActiveFocus();
    }
    function push(c, props) {
        stack.push(c, props, StackView.Immediate);
        stack.currentItem.forceActiveFocus();
        updateState();
    }
    function pop() {
        if (win.playing && Y.queueAuto) { Y.queue = []; Y.queueAuto = false; }   // a playlist's rest ends with its player
        if (stack.depth > 1) stack.pop(StackView.Immediate);
        else stack.clear(StackView.Immediate);            // pop() never takes the last page off
        if (!stack.depth && homeLater) { homeLater = false; if (section === "home" && !home.loaded) home.load(); }
        if (!stack.depth && shortsFromGuide) {                // back on the guide, on Shorts
            shortsFromGuide = false;
            guide.forceActiveFocus();
            guide.cur = Math.max(0, guide.list.findIndex(e => e.key === "shorts"));
        }
        else focusPage();
        updateState();
    }
    function play(id, at, seed) {
        // one player at a time: a new video replaces what's playing (and what was opened over it).
        // With no player under them, the pages stay (Back from the video returns to them). (pop()
        // never takes the last page off: looping on it with no player in the stack never ended.)
        let player = -1;
        for (let i = 0; i < stack.depth; i++) if (stack.get(i, StackView.DontLoad).videoId !== undefined) player = i;
        while (player >= 0 && stack.depth > player + 1) stack.pop(StackView.Immediate);
        if (win.playing && !stack.currentItem.start) stack.pop(StackView.Immediate);       // Shorts: a video replaces it
        if (win.playing) { stack.currentItem.seed = seed || {}; stack.currentItem.start(id, at || 0); stack.currentItem.forceActiveFocus(); updateState(); return; }
        push(playerC, {videoId: id, startAt: at || 0, seed: seed || {}});
    }
    function back() {
        if (picking) {
            if (pickedAtStart) Qt.quit();
            else { picking = false; guide.forceActiveFocus(); }   // opened from the guide's picture: back to it
            return;
        }
        if (stack.depth) { pop(); return; }
        if (guide.activeFocus) {
            // Back from the guide goes Home first (also when it's only been moved off Home)
            if (section !== "home" || guide.keyAt(guide.cur) !== "home") { choose("home"); guide.sync(); return; }
            Qt.quit();
            return;
        }
        if (section === "search" && searchL.item && searchL.item.back()) return;
        if (section === "search") { choose("home"); guide.forceActiveFocus(); return; }
        guide.forceActiveFocus();
    }
    // a setting that changes what the pages hold (Hide Shorts, DeArrow): they load again next time
    property var lastSettings: ({})
    Connections {
        target: Y
        function onSettingsChanged() {
            const a = win.lastSettings, b = Y.settings;
            if (a.hide_shorts !== undefined && (a.hide_shorts !== b.hide_shorts || a.dearrow !== b.dearrow)) {
                home.loaded = false;
                for (const l of [tabL, subscriptionsL, libraryL]) if (l.item) l.item.loaded = false;
            }
            win.lastSettings = b;
        }
    }
    Connections {
        target: Y
        function onOpen(it) {
            if (!it || !it.id) return;
            if (it.type === "short" || it.type === "shorts") win.push(shortsC, {startId: it.type === "short" ? it.id : ""});
            else if (it.type === "video" || it.type === "live") win.play(it.id, it.start || 0, it);
            else if (it.type === "channel" || it.type === "game") win.push(channelC, {channelId: it.id});
            else if (it.type === "playlist") win.push(channelC, {channelId: "VL" + it.id});
            else if (it.type === "browse") win.push(channelC, {channelId: it.id});
            else if (it.type === "search") Y.search(it.id);
        }
        function onToast(t) { toast.show(t); }
        function onToGuide() {
            if (stack.depth || win.picking) return;
            const sb = subscriptionsL.item;
            if (sb && win.page(win.section) === sb && sb.feedFocused) sb.toChannels();
            else guide.forceActiveFocus();
        }
        function onWhoIsWatching() {
            // from a video YouTube wouldn't play to a guest: once an account is picked, that video
            win.afterPick = win.playing && stack.currentItem.signInOffer ? "video:" + stack.currentItem.videoId : "";
            win.pickedAtStart = false; win.showProfiles();
        }
        function onSignIn() { win.push(signInC, {}); }
        function onOpenList(title, id) { win.push(listC, {title: title, browseId: id}); }
        function onCardMenu(it, back) { cardMenu.open(it, back); }
        function onSearch(q) {
            win.choose("search");
            if (q) pg(searchL).search(q);
            pg(searchL).forceActiveFocus();
        }
    }

    // --open / a second launch / the voice assistant: video:ID[@SECONDS], search:TEXT, channel:ID,
    // browse:ID, home, and typing:TEXT (Search's keys with that typed: screenshots)
    function openTarget(o) {
        if (!ready) { pendingOpen = o; return; }   // (still starting: once it's ready)
        if (picking) {                             // Who's watching is up: as the last profile watching
            pickedAtStart = false;
            Y.call("profiles", {}, r => win.use((r.profiles || []).some(p => p.id === r.last) ? r.last : "", o), () => win.use("", o));
            return;
        }
        const i = o.indexOf(":"), k = i < 0 ? o : o.slice(0, i), rest = i < 0 ? "" : o.slice(i + 1);
        if (k === "video") {
            const m = rest.match(/^([\w-]{1,20})(?:@(\d+(?:\.\d+)?))?$/);
            if (m) play(m[1], m[2] ? parseFloat(m[2]) : 0, {});
        } else if (k === "search") { stack.clear(StackView.Immediate); Y.search(rest); }
        else if (k === "typing") { stack.clear(StackView.Immediate); choose("search"); pg(searchL).begin(rest); pg(searchL).forceActiveFocus(); }
        else if (k === "channel" || k === "browse") { stack.clear(StackView.Immediate); push(channelC, {channelId: rest}); }
        else if (k === "home" || tabs[k] || k === "settings" || k === "subscriptions" || k === "library") { stack.clear(StackView.Immediate); choose(k); focusPage(); }
        else if (k === "profiles") { pickedAtStart = false; showProfiles(); }
        else if (k === "as") win.use(rest === "guest" ? "" : rest, "home");   // watch as a profile (the box check)
        else if (k === "shorts") { stack.clear(StackView.Immediate); push(shortsC, {startId: rest}); }
        else if (k === "signin") push(signInC, {});
    }
    function updateState() {
        const cur = stack.depth ? stack.currentItem : null;
        const st = {page: picking ? "profiles" : cur ? (cur.videoId !== undefined ? "player" : cur.browseId !== undefined ? "list" : "channel") : section,
                    profile: Y.profile ? Y.profile.name : "guest"};
        if (cur && cur.label) st.showing = cur.label;
        if (win.playing) {
            st.playing = cur.label; st.paused = video.paused; st.position = Math.round(video.position);
            st.videoId = cur.videoId || ""; st.duration = Math.round(video.duration || 0);    // for couchbox-yt-cast
        }
        control.setState(JSON.stringify(st));
    }
    Connections {
        target: backend
        function onEvent(name, js) {
            const d = JSON.parse(js || "{}");
            if (name === "signedIn") {
                toast.show((d.name || "The account") + " is signed in to YouTube.");
                if (win.picking) profilesPage.load(d.account + ":");
                else if (!Y.signedIn) win.use(d.account + ":", "");          // a guest: watch as the new account
            } else if (name === "signInExpired") {
                // nothing to say unless the sign-in page is up (it shows it)
            } else if (name === "signedOut") {
                toast.show((d.name || "An account") + " was signed out of YouTube. Sign in again from Who's watching.");
            }
        }
    }
    Connections {
        target: control
        function onCommand(js) {
            const c = JSON.parse(js);
            if (c.op === "open") { if (c.target) win.openTarget(c.target); win.raise(); win.requestActivate(); }
            else if (c.op === "media" && win.playing) {
                const a = c.action, n = Number(c.seconds || 10);
                if (a === "play") video.setPaused(false);
                else if (a === "pause") video.setPaused(true);
                else if (a === "toggle") video.togglePause();
                else if (a === "forward") video.seek(n);
                else if (a === "back") video.seek(-n);
                else if (a === "seek") video.seekTo(n);
                else if (a === "restart") video.seekTo(0);
                stack.currentItem.showControls();
            }
            win.updateState();
        }
    }

    // ------------------------------------------------------------------ layout
    FocusScope {
        id: ui
        anchors.fill: parent
        focus: true
        // Back acts once per press (a held key's repeats don't run through the pages)
        Keys.onEscapePressed: e => { if (!e.isAutoRepeat) win.back(); }
        Keys.onBackPressed: e => { if (!e.isAutoRepeat) win.back(); }

        // the video, under everything: shown while the player is the page on top
        MpvVideo {
            id: video
            readonly property bool placed: Y.videoRect.width > 0          // Shorts
            x: placed ? Y.videoRect.x : Y.videoSide ? 54 * Y.u : 0
            y: placed ? Y.videoRect.y : Y.videoSide ? 219 * Y.u : 0
            width: warming ? 2 : placed ? Y.videoRect.width : Y.videoSide ? 1146 * Y.u : parent.width
            height: warming ? 2 : placed ? Y.videoRect.height : Y.videoSide ? 645 * Y.u : parent.height
            visible: win.playing || warming
            // once Home shows, before any video: mpv's output made (a 2-pixel moment of black, muted)
            property bool warming: false
            Timer {
                running: Y.homeShown && !win.shot && !win.playing && !video.warmed
                interval: 1500
                onTriggered: { video.warmed = true; if (win.playing) return; video.warming = true; video.warmUp(); warmEnd.start(); }
            }
            property bool warmed: false
            Timer { id: warmEnd; interval: 2500; onTriggered: video.warming = false }
        }

        Item {
            id: pages
            width: parent.width
            height: parent.height
            visible: !stack.depth
            // the open guide pushes the page to the right, as YouTube's does
            x: guide.open ? Y.guideOpen - Y.left : 0
            Behavior on x { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
            BrowsePage { id: home; objectName: "home"; anchors.fill: parent; key: "home"; browseId: "FEtopics"; visible: win.section === "home" }
            Loader { id: tabL; anchors.fill: parent; active: false; visible: !!win.tabs[win.section]
                     sourceComponent: BrowsePage { objectName: "tab"; key: "music" } }
            Loader { id: searchL; anchors.fill: parent; active: false; visible: win.section === "search"
                     sourceComponent: SearchPage {} }
            MessagePage { id: message; objectName: "message"; anchors.fill: parent; visible: win.page(win.section) === message }
            Loader { id: subscriptionsL; anchors.fill: parent; active: false; visible: win.section === "subscriptions" && Y.signedIn
                     sourceComponent: SubscriptionsPage { objectName: "subscriptions" } }
            Loader { id: settingsL; anchors.fill: parent; active: false; visible: win.section === "settings"
                     sourceComponent: SettingsPage {} }
            Loader { id: libraryL; anchors.fill: parent; active: false; visible: win.section === "library" && Y.signedIn
                     sourceComponent: LibraryPage { objectName: "library" } }
        }
        Guide {
            id: guide
            height: parent.height
            visible: !stack.depth
            onChosen: key => win.choose(key)
            onEnter: {
                if (guide.keyAt(guide.cur) === "shorts") { win.shortsFromGuide = true; Y.open({type: "shorts", id: "-"}); }
                else win.focusPage();
            }
            pinned: win.section === "settings" && !stack.depth && !win.picking
            onOpenChanged: Y.pushed = open
            onActiveFocusChanged: Y.dimmed = activeFocus
        }

        StackView {
            id: stack
            anchors.fill: parent
            visible: depth > 0
        }
        ProfilesPage {
            id: profilesPage
            anchors.fill: parent
            visible: win.picking && !stack.depth
            onChosen: p => { const then = p ? win.afterPick : ""; win.afterPick = ""; win.use(p ? p.id : "", then); }
            onAddAccount: win.push(signInC, {})
            onSignOut: p => Y.call("signOut", {account: p.account}, () => {
                toast.show(p.name + " is signed out on this TV.");
                if (Y.profile && Y.profile.account === p.account) Y.profile = null;
                profilesPage.load("");
            })
            onClosed: win.back()
        }
    }
    Component { id: channelC; ChannelPage { onClosed: win.pop() } }
    Component { id: listC; ListPage { onClosed: win.pop() } }
    Component { id: shortsC; ShortsPage { onClosed: win.pop() } }
    CardMenu {
        id: cardMenu
        anchors.fill: parent
        onPicked: (k, it) => {
            if (k === "next") { Y.queue = [it].concat(Y.queue); toast.show("Plays next: " + it.title); }
            else if (k === "queue") { Y.queue = Y.queue.concat([it]); toast.show("Added to the queue (" + Y.queue.length + ")"); }
            else if (k === "later") {
                if (!Y.signedIn) toast.show("Sign in to save videos: the guide's picture, then Add account.");
                else Y.call("save", {id: it.id, playlist: "WL", add: true}, () => toast.show("Saved to Watch later"));
            } else if (k === "channel") win.push(channelC, {channelId: it.channelId});
        }
    }
    Component {
        id: signInC
        SignInPage {
            onClosed: {
                win.pop();
                if (win.picking) { profilesPage.load(""); profilesPage.forceActiveFocus(); }
            }
        }
    }
    Component {
        id: playerC
        PlayerPage {
            onFinished: win.pop()
            onOpenChannel: id => win.push(channelC, {channelId: id})
        }
    }

    Text {
        id: problem
        anchors.centerIn: parent
        color: Y.dim
        font.family: Y.font; font.pixelSize: 32 * Y.u
    }

    Rectangle {                                  // notices
        id: toast
        function show(t) { toastText.text = t; opacity = 1; toastTimer.restart(); }
        anchors.horizontalCenter: parent.horizontalCenter
        y: win.playing ? 56 * win.u : parent.height - height - 56 * win.u   // playing: at the top, clear of the captions
        width: Math.min(toastText.implicitWidth + 64 * win.u, parent.width * 0.8)
        height: 76 * win.u
        radius: height / 2
        color: "#f2212121"
        opacity: 0
        z: 200
        Behavior on opacity { NumberAnimation { duration: 200 } }
        Text {
            id: toastText
            anchors.centerIn: parent
            width: parent.width - 48 * win.u
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            color: Y.text
            font.family: Y.font; font.pixelSize: 26 * win.u
        }
        Timer { id: toastTimer; interval: 3500; onTriggered: toast.opacity = 0 }
    }

    // ------------------------------------------------------------------ idle, off-screen tests
    // Quit after half an hour without use, unless a video is playing.
    onActiveFocusItemChanged: { idle.restart(); updateState(); }
    // VacuumTube's "Pause on blur": another window in front pauses the video
    onActiveChanged: if (!active && Y.settings.pause_on_blur && win.playing) video.setPaused(true)

    // what has the focus, for the control socket's "focus" op (ci/yt-box-check.sh): the named
    // items from the page down to the focused one, whether it's on screen, and the page's details
    // the card (or Library tile) the focus is on: what it is, not what it's called
    function focusedCard(it) {
        for (let p = it; p; p = p.parent) {
            const c = p.currentItem;
            if (c && c.item !== undefined && c.kind !== undefined) {
                const x = c.item || {};
                const len = String(x.duration || "").split(":").reduce((n, p) => n * 60 + (parseInt(p) || 0), 0);
                return {type: x.type || "video", id: x.id || "", progress: x.progress || 0, live: !!x.live, duration: len};
            }
            if (c && c.modelData && c.modelData.colors) return {type: "tile", id: c.modelData.id || "", title: c.modelData.title || ""};
        }
        return null;
    }
    function focusState() {
        const names = [];
        let it = win.activeFocusItem, shown = !!it;
        for (let p = it; p; p = p.parent) {
            if (p.objectName) names.unshift(p.objectName);
            if (!p.visible || p.opacity === 0) shown = false;
        }
        const cur = stack.depth ? stack.currentItem : null;
        const st = {focus: names.join("/"), item: String(it).split("(")[0], shown: shown, section: section, guideOpen: guide.open,
                    toast: toast.opacity > 0 ? toastText.text : "", queue: Y.queue.length,
                    signedIn: Y.signedIn, profile: Y.profile ? Y.profile.id : "", card: focusedCard(it),
                    guideAt: guide.activeFocus ? (guide.cur < 0 ? "who" : guide.keyAt(guide.cur)) : ""};
        if (picking) st.detail = profilesPage.focusDetail();
        else if (cur && cur.focusDetail) st.detail = cur.focusDetail();
        else if (!cur && page(section).focusDetail) st.detail = page(section).focusDetail();
        return st;
    }
    Timer {
        interval: 300; repeat: true; running: !win.shot
        onTriggered: { const st = win.focusState(); control.setFocus(JSON.stringify(st)); win.cardFocused(st.card); }
    }
    // a video card that keeps the focus: its stream now, for OK (looked at again right after a key)
    function cardFocused(c) {
        const id = c && (c.type === "video" || c.type === "short") && !c.live ? c.id : "";
        if (id !== win.focusedVideo) { win.focusedVideo = id; win.focusedCardInfo = c || null; if (id) prefetch.restart(); }
    }
    property var focusedCardInfo: null
    // ... and the video itself opened in mpv (paused, muted, reading little ahead): OK then only plays it
    function preloadFocused() {
        const id = win.focusedVideo, c = win.focusedCardInfo;
        if (!id || win.playing || !c || c.type !== "video") return;
        Y.call("stream", {id: id}, r => {
            if (win.focusedVideo !== id || win.playing || !r.url || r.live || r.wait > 0 || r.url.indexOf("demo://") === 0) return;
            video.preload(r.url, Y.resumeAt(c.progress, r.duration || c.duration), r.opts || "");
        }, () => {});
    }
    Connections { target: keyfilter; function onPressed() { Qt.callLater(() => win.cardFocused(win.focusedCard(win.activeFocusItem))); } }
    property string focusedVideo: ""
    Timer { id: prefetch; interval: 600; onTriggered: if (win.focusedVideo && !win.playing) { Y.call("prefetch", {id: win.focusedVideo}, () => {}, () => {}); preload.restart(); } }
    Timer { id: preload; interval: 400; onTriggered: win.preloadFocused() }
    Timer { interval: 1000; repeat: true; running: win.playing && !win.shot; onTriggered: win.updateState() }   // the position, for casting
    Timer {
        id: idle
        interval: 30 * 60 * 1000
        running: !win.shot
        onTriggered: if (win.playing && stack.currentItem.watching) restart(); else Qt.quit()
    }

    // --shot FILE [--open ...] [--keys k1,k2,...]
    Timer {
        running: !!win.shot
        interval: 2000
        onTriggered: {
            const keys = win.arg("--keys");
            // the presses as the box delivers them (press, release, gaps, repeats): Shooter.run
            shotTimer.interval = (keys ? shooter.run(keys) : 0) + 1500;
            shotTimer.start();
        }
    }
    Timer { id: shotTimer; interval: 1500; onTriggered: { shooter.note(win.shot + ".focus.json", JSON.stringify(win.focusState())); shooter.save(win.shot); Qt.quit(); } }
}
