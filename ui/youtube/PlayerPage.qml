// The player, laid out as YouTube's TV app's: the title and channel top left; the time and
// chapter, the progress bar (cut into the video's chapters) and the length; the controls (the
// channel, Description, the bell | previous, play/pause, next | like, dislike, comments, Ask,
// save, Thanks | captions, settings); and the related videos under them, rows of three.
// The remote:
//   OK            with the controls hidden: show them (it doesn't pause); on them: the focused one
//   Left / Right  back / forward 10 s (the bar shows)      Rewind / Fast-forward: the same (MPRIS)
//   Up / Down     show the controls; Down again: the related videos; Up from the controls: the bar,
//                 with the chapters' pictures above it; Up again picks a chapter (Left / Right, OK)
//   Back          from the related videos to the controls, then hide them, then leave the player
// Description and comments open beside the video; the settings menu has quality, speed and
// captions (CC turns captions on and off). At the end, Up next (the queue first) after a countdown.
// Streams: ytstream.py (yt-dlp), H.264 up to 1080p60; at the end the next video plays.
// Signed in: like and dislike, the channel's panel (Subscribe / Subscribed, Go to channel), the
// bell's notification levels, Save (Watch later, playlists); it starts where YouTube says this
// profile left off, and reports what's watched (History, resume on every device).
import QtQuick
import QtQuick.Controls
import QtQuick.Effects

FocusScope {
    id: player
    objectName: "player"
    // the controls' keys land here (the player handles them): the focus comes back to it, not
    // to whichever panel or row had it last
    Item { id: ctl; objectName: "controls"; focus: true }
    function focusDetail() { return {mode: mode, button: (controls[button] || {}).key || "", panel: panel, position: Math.round(pos), scrub: Math.round(scrub), paused: !!video.paused, row: related.index, rows: related.count,
                                          captions: captionsOn, speed: speed, live: live, ending: ending, videoId: videoId,
                                          card: panel === "description" ? description.index : -1,
                                          subscribed: !!v.subscribed, startAt: Math.round(startAt), duration: Math.round(video.duration || 0),
                                          height: s ? Math.min(s.height || 0, s.width || s.height || 0) : 0, fps: s ? Math.round(s.fps || 0) : 0,
                                          itags: s ? (s.itags || []).join("+") : "", decoded: video.videoInfo(), message: message, signInOffer: signInOffer,
                                          panelItem: panel && panel !== "description" && panel !== "comments" ? ((optionsFor(panel)[sidePanel.index] || {}).label || "") : "",
                                          comments: panel === "comments" ? comments.focusDetail() : null, subText: video.subText ? video.subText() : ""}; }
    // the position, read four times a second as well as on mpv's notices: the clock and the bar
    // follow from the first frame
    property real pos: video.position
    Timer { interval: 250; repeat: true; running: player.visible && !!player.s; onTriggered: player.pos = video.position }
    Connections { target: video; function onPositionChanged() { player.pos = video.position; player.sponsorCheck(); } }

    // ------------------------------------------------------------------ SponsorBlock
    // The video's marked parts (ytextras: all kinds; the bar shows them); the kinds chosen in
    // Settings are skipped once each as playback enters them, with a notice and OK to undo.
    property var segments: []
    property var skippedOnce: ({})
    property var skipNotice: null              // {label, from} while the notice shows
    function sponsorCheck() {
        const st = Y.settings;
        if (!st.sponsorblock || !segments.length || video.paused || !s || live) return;
        for (let i = 0; i < segments.length; i++) {
            const g = segments[i];
            if (g.action !== "skip" || !(st.skip || {})[g.category] || skippedOnce[i]) continue;
            if (pos >= g.start && pos < g.end - 0.5) {
                skippedOnce[i] = true;
                skipNotice = {label: g.label, from: pos};
                video.seekTo(g.end);
                noticeTimer.restart();
                return;
            }
        }
    }
    function undoSkip() {
        if (!skipNotice) return;
        video.seekTo(skipNotice.from);
        skipNotice = null;
    }
    Timer { id: noticeTimer; interval: 6000; onTriggered: player.skipNotice = null }
    // DeArrow's title for this video, when that's on (ytextras.branding)
    property string brandTitle: ""
    // Return YouTube Dislike's count, when that's on
    property int dislikes: -1
    property string videoId: ""
    property real startAt: 0
    property var seed: ({})                    // the card it was opened from (title while loading)
    property var meta: ({})                    // watch: {video, related, next}
    property var s: null                       // stream: {url, live, duration, chapters, ...}
    property string message: ""
    // a guest YouTube won't play to (its bot check, "sign in"): OK offers Who's watching
    readonly property bool signInOffer: !Y.signedIn && /\bbot\b|sign in|signed in|login/i.test(message)
    property string mode: "controls"           // hidden | bar | controls | related
    property int button: 4                     // the focused control (index into controls)
    readonly property var video: Y.video
    readonly property var v: meta.video || {}
    readonly property bool live: !!(s && s.live) || !!v.live || seed.type === "live"
    // the chapters: the watch page's (with pictures) or yt-dlp's
    readonly property var chapters: meta.chapters && meta.chapters.length ? meta.chapters : s ? s.chapters || [] : []
    property int chapterPick: 0                // the chapter picked in the strip (Up from the bar)
    property real speed: 1
    property string captionsOn: ""             // the captions shown (their name), "" none
    property bool ending: false                // the end screen is up
    readonly property real duration: video.duration || (s ? s.duration : 0) || 0
    // scrubbing (Left / Right with the controls hidden, or Up to the bar): only the bar, the
    // chapters' pictures over it and the hint show, as on YouTube's TV app
    readonly property bool seeking: mode === "bar" || mode === "chapters"
    // scrubbing (Left / Right on the bar, not live): where it would go, shown on the bar and in
    // the frame; OK goes there, as does a moment's pause (as YouTube's: a tap of Right skips on);
    // Up (no chapters) and Back leave it where it was (-1: nothing pending)
    property real scrub: -1
    readonly property real shownPos: scrub >= 0 ? scrub : pos
    Timer { id: scrubCommit; interval: 2000; onTriggered: player.commitScrub() }
    function scrubBy(d) {
        scrub = Math.max(0, Math.min(Math.max(0, duration - 1), (scrub >= 0 ? scrub : pos) + d));
        scrubCommit.restart();
        if (mode === "hidden") mode = "bar";
        hide.restart();
    }
    function commitScrub() {
        scrubCommit.stop();
        if (scrub < 0) return;
        const to = scrub;
        scrub = -1;
        video.seekTo(to);
    }
    function cancelScrub() { scrubCommit.stop(); scrub = -1; }
    readonly property int chapter: Y.chapterAt(chapters, shownPos)
    readonly property bool watching: !!s && !video.paused && !video.ended   // keeps the app from idling out
    readonly property string label: brandTitle || v.title || (s ? s.title : "") || seed.title || ""
    property string panel: ""                  // "" | channel | notify | save: a panel beside the video
    property var saveOptions: []
    property string cpn: ""                    // this playback's id in YouTube's reports
    property bool reported: false
    property real lastReport: 0
    signal finished()
    signal openChannel(string id)

    function start(id, at) {
        if (s && reported) report(video.ended ? "end" : "pause");     // the one before
        videoId = id;
        startAt = at || 0;
        s = null; meta = {}; message = ""; waitLeft = 0; pos = 0; panel = ""; reported = false; lastReport = 0;
        related.rows = []; related.index = 0; cancelScrub();   // (not the last video's row while this one's comes: it was, for a live one)
        cpn = "";
        const abc = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
        for (let i = 0; i < 16; i++) cpn += abc[Math.floor(Math.random() * 64)];
        mode = "controls"; button = 4; ending = false; captionsOn = ""; captionsOffHere = false; autoCaptionsDone = false;
        // the next video (Up next's countdown, a card): the controls take the focus back from the
        // end screen, which hides (focus left on it went nowhere: the box check's steps 26-27)
        if (player.activeFocus && !ctl.activeFocus) ctl.forceActiveFocus();
        if (speed !== 1) video.setSpeed(speed);
        showControls();
        Y.call("stream", {id: id}, r => {
            if (!player || player.videoId !== id) return;   // (closed meanwhile, or another video)
            s = r;
            // where this profile left off: the card's (a part-watched card's red bar) unless told
            if (!player.startAt && !r.live) player.startAt = Y.resumeAt(Y.progressOf(player.seed), r.duration || player.seed.duration);
            waitLeft = r.wait || 0;            // YouTube holds some streams back for as long as their ads
            if (waitLeft <= 0) begin();
            showControls();
        }, e => { if (player && player.videoId === id) message = e || "This video can't be played."; });
        segments = []; skippedOnce = ({}); skipNotice = null; brandTitle = ""; dislikes = -1;
        Y.call("segments", {id: id}, r => { if (player && player.videoId === id) player.segments = r.segments || []; }, () => {});
        if (Y.settings.dearrow) Y.call("branding", {id: id}, r => { if (player && player.videoId === id) player.brandTitle = r.title || ""; }, () => {});
        if (Y.settings.dislikes) Y.call("votes", {id: id}, r => { if (player && player.videoId === id && r.dislikes !== undefined) player.dislikes = r.dislikes; }, () => {});
        Y.call("watch", {id: id}, r => {
            if (!player || player.videoId !== id) return;   // (closed meanwhile, or another video)
            meta = r;
            // YouTube's own resume point for this profile, when the card didn't have one
            if (r.start > 0 && !player.startAt) {
                player.startAt = r.start;
                if (player.s && video.position < r.start - 5) video.seekTo(r.start);
            }
            const rows = [];
            const rel = r.related || [];
            for (let i = 0; i < rel.length; i += 3) rows.push({kind: "shelf", title: "", items: rel.slice(i, i + 3), more: ""});
            related.rows = rows;
            mprisUpdate();
            const n = upNext();                // what plays next: its stream ready for the end
            if (n && !n.item.live) Y.call("prefetch", {id: n.item.id}, () => {}, () => {});
        }, () => {});
    }
    function begin() {
        if (s.url.indexOf("demo://") === 0) video.load(s.url, startAt);
        else video.loadWith(s.url, startAt, s.opts || "");
        autoCaptionsLater.restart();
        begin2();
    }
    property int waitLeft: 0
    Timer {
        interval: 1000; repeat: true; running: player.waitLeft > 0
        onTriggered: { player.waitLeft--; if (player.waitLeft <= 0) player.begin(); }
    }
    // a page opened over the player (its channel): the video paused where it is, playing again on
    // the way back if it was (the same file: nothing reloaded)
    property bool resumeOnReturn: false
    function leaveFor() { resumeOnReturn = !video.paused && !video.ended; video.setPaused(true); }
    StackView.onActivated: { if (resumeOnReturn) { resumeOnReturn = false; video.setPaused(false); } showControls(); }
    Component.onCompleted: { video.setRateHold(true); start(videoId, startAt); }   // (the TV's rate kept between videos)
    function noteSeen() {                       // the cards' red bars, for the way back
        if (videoId && s && !s.live && duration > 0 && pos > 0) Y.noteSeen(videoId, video.ended ? 1 : pos / duration);
    }
    Component.onDestruction: {
        video.setRateHold(false);
        video.setSubtitleShown(true);
        noteSeen();
        if (s && reported) report(video.ended ? "end" : "pause");
        Y.videoSide = false;
        video.stop();
        if (typeof mpris !== "undefined" && mpris) mpris.update(false, false, "", "", 0, 0);
    }
    // what plays next: the queue first (a card's menu: Play next, Add to queue), then YouTube's Up next
    function upNext() {
        if (Y.queue.length) return {item: Y.queue[0], queued: true};
        const rel = meta.related || [];
        const n = rel.find(x => x.id === meta.next) || rel[0];
        return n ? {item: n, queued: false} : null;
    }
    function playNext() {
        const n = upNext();
        if (!n) { finished(); return; }
        noteSeen();
        if (n.queued) Y.queue = Y.queue.slice(1);
        seed = n.item;
        // YouTube's "Video paused. Continue watching?": autoplay, and no key for 2 hours (not with
        // VacuumTube's "Block continue watching")
        askContinue = !Y.settings.block_continue && Date.now() - Y.lastKey > 2 * 3600 * 1000;
        start(n.item.id, 0);
    }
    property bool askContinue: false
    function begin2() { if (askContinue) video.setPaused(true); }
    function showEnd() {
        const n = upNext();
        if (!n) { mode = "controls"; showControls(); return; }
        endScreen.next = n.item;
        endScreen.queued = n.queued;
        endScreen.seconds = meta.countdown || 5;
        ending = true;
        endScreen.begin();
        Qt.callLater(() => endScreen.forceActiveFocus());
    }

    // ------------------------------------------------------------------ the remote's media keys (MPRIS)
    function mprisUpdate() {
        if (typeof mpris === "undefined" || !mpris) return;
        mpris.update(!!s && player.duration > 0, video.paused, player.label, v.channel || (s ? s.channel : ""), player.duration, video.position);
    }
    Connections {
        target: typeof mpris !== "undefined" ? mpris : null
        ignoreUnknownSignals: true
        function onCommand(name, arg) {
            if (name === "playpause") video.togglePause();
            else if (name === "play") video.setPaused(false);
            else if (name === "pause") video.setPaused(true);
            else if (name === "seek" || name === "previous") player.skip(arg);
            else if (name === "seekto") video.seekTo(arg);
            else if (name === "next") player.playNext();
            else if (name === "stop") player.finished();
            player.showControls();
        }
    }
    Timer { interval: 5000; repeat: true; running: !!player.s; onTriggered: player.mprisUpdate() }
    Connections {
        target: video
        function onPausedChanged() { player.mprisUpdate(); if (video.paused) player.showControls(); }
        function onEndedChanged() { if (video.ended && !player.live) player.showEnd(); }
        function onErrorChanged() { if (video.error) player.message = video.error; }
    }

    // ------------------------------------------------------------------ history (signed in)
    function report(event) {
        if (!Y.signedIn || !s || s.live) return;
        Y.call("report", {id: videoId, cpn: cpn, event: event, position: video.position, duration: player.duration}, () => {}, () => {});
    }
    Connections {
        target: video
        function onPositionChanged() {
            if (!player.s) return;
            if (!player.reported && video.position > Math.max(1, player.startAt)) { player.reported = true; player.lastReport = video.position; player.report("start"); }
            else if (player.reported && !video.paused && Math.abs(video.position - player.lastReport) >= 10) { player.lastReport = video.position; player.report("progress"); }
        }
        function onPausedChanged() { if (player.reported) player.report(video.paused ? "pause" : "progress"); }
    }

    // ------------------------------------------------------------------ signed in: like, subscribe, save
    function signInFirst(what) { Y.toast("Sign in to " + what + ": the guide's picture, then Add account."); }
    function rate(status) {
        if (!Y.signedIn) return signInFirst("rate videos");
        const now = v.like === status ? "none" : status;
        Y.call("like", {id: videoId, status: now}, () => {
            meta = Object.assign({}, meta, {video: Object.assign({}, v, {like: now})});
            Y.toast(now === "like" ? "Added to Liked videos" : now === "dislike" ? "You dislike this video" : "Rating removed");
        });
    }
    function subscribe(on) {
        if (!Y.signedIn) return signInFirst("subscribe");
        Y.call("subscribe", {id: v.channelId, on: on}, () => {
            meta = Object.assign({}, meta, {video: Object.assign({}, v, {subscribed: on, notify: on ? (v.notify || "personalized") : ""})});
            Y.toast(on ? "Subscribed to " + v.channel : "Unsubscribed from " + v.channel);
            if (!on && panel === "notify") panel = "";
        });
    }
    function openPanel(which) {
        if (which === "save") {
            if (!Y.signedIn) return signInFirst("save videos");
            Y.call("saveOptions", {id: videoId}, r => { if (player) { player.saveOptions = r.playlists || []; player.panel = "save"; } });
            return;
        }
        if (which === "notify" && !Y.signedIn) return signInFirst("choose notifications");
        panel = which;
        if (which === "comments") { comments.token = (meta.details || {}).commentsToken || ""; comments.count = (meta.details || {}).comments || ""; comments.load(); }
    }
    onPanelChanged: {
        Y.videoSide = !!panel;
        const checked = optionsFor(panel).findIndex(o => o.checked);     // the current choice, as YouTube's does
        sidePanel.index = checked >= 0 && panel !== "save" ? checked : 0;
        // the panel takes the focus now (keys pressed right after go to it), and again once it's
        // surely shown (an item can't take it while hidden); closed, the controls have it again, on
        // the button that opened it
        const target = panel === "description" ? description : panel === "comments" ? comments : panel ? sidePanel : null;
        if (panel === "description") description.index = 0;
        if (target) { target.forceActiveFocus(); Qt.callLater(() => { if (player.panel && !target.activeFocus) target.forceActiveFocus(); }); }
        else { ctl.forceActiveFocus(); mode = "controls"; hide.restart(); }
    }
    readonly property var notifyLevels: [
        {level: "all", label: "All", icon: "bell-all-filled"}, {level: "personalized", label: "Personalized", icon: "bell"},
        {level: "none", label: "None", icon: "bell-off"}
    ]
    // the panel's rows (a function, so onPanelChanged reads them for the new panel, not the last)
    readonly property var panelOptions: optionsFor(panel)
    function optionsFor(p) {
        if (p === "channel")
            return [{label: v.subscribed ? "Subscribed" : "Subscribe", trailing: v.subscribed ? ({all: "bell-all", none: "bell-off"})[v.notify] || "bell" : ""},
                    {label: "Go to channel"}];
        if (p === "notify") {
            const have = (v.notifyOptions || []).map(o => o.level);
            return notifyLevels.filter(l => have.length === 0 || have.indexOf(l.level) >= 0)
                .map(l => ({label: l.label, icon: l.icon, checked: v.notify === l.level, level: l.level}))
                .concat([{label: "Unsubscribe", icon: "unsubscribe", level: "unsubscribe"}]);
        }
        if (p === "save")
            return saveOptions.map(o => ({label: o.title, icon: o.id === "WL" ? "history" : "list", checked: o.saved, id: o.id}));
        if (p === "settings")
            return [{label: "Quality", value: qualityLabel, icon: "settings"}, {label: "Playback speed", value: speed === 1 ? "Normal" : speed + "×", icon: "speed"},
                    {label: "Captions", value: captionsOn || "Off", icon: "cc"}];
        if (p === "quality")
            return [{label: "Auto", checked: !s || !s.maxHeight || s.maxHeight >= 1080, h: 1080}]
                .concat(((s && s.heights) || []).map(h => ({label: h + "p", checked: s.maxHeight === h && h < 1080, h: h})));
        if (p === "speed")
            return [0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2].map(x => ({label: x === 1 ? "Normal" : x + "×", checked: speed === x, x: x}));
        if (p === "captions")
            return [{label: "Off", checked: !captionsOn}].concat(((s && s.captions) || []).map(c => ({label: c.name, checked: captionsOn === c.name, c: c})));
        return [];
    }
    readonly property string qualityLabel: s && s.height ? "Auto (" + Math.min(s.height, s.width || s.height) + "p" + (s.fps > 30 ? Math.round(s.fps) : "") + ")" : "Auto"
    function setQuality(h) {
        const id = videoId, at = video.position;
        Y.call("stream", {id: id, max_height: h}, r => {
            if (!player || player.videoId !== id) return;   // (closed meanwhile, or another video)
            s = r;
            if (r.url.indexOf("demo://") === 0) video.load(r.url, at); else video.loadWith(r.url, at, r.opts || "");
            if (captionsOn) { const c = (r.captions || []).find(x => x.name === captionsOn); if (c) player.addCaptions(c); }
        }, e => Y.toast(e));
    }
    // a caption track, fetched by the app (with retries: YouTube answers "429 Too Many Requests" at
    // times) and given to mpv as a file
    function addCaptions(c) {
        const id = videoId;
        Y.call("captions", {url: c.url}, r => { if (player && player.videoId === id && r.path) video.addSubtitleTrack(r.path, c.name); },
               e => { if (player && player.videoId === id) { Y.toast("Captions aren't available right now."); if (captionsOn === c.name) captionsOn = ""; } });
    }
    // captions, as Settings → Captions has them: English first (the video's own, automatic, then
    // translated), else the video's language; turned off with CC, off for the rest of the video
    property bool captionsOffHere: false
    property bool autoCaptionsDone: false
    function preferredCaptions(list) {
        const en = c => String(c.lang || "").split("-")[0] === "en";
        return list.find(c => en(c) && !c.auto) || list.find(c => en(c) && c.auto && !c.translated) || list.find(c => en(c) && c.translated)
            || list.find(c => !c.auto) || list.find(c => c.auto && !c.translated) || null;
    }
    function autoCaptions() {
        if (autoCaptionsDone || !s || s.live || captionsOn || captionsOffHere || Y.settings.captions_always === false) return;
        autoCaptionsDone = true;
        const c = preferredCaptions(s.captions || []);
        if (c) setCaptions(c);
    }
    Connections {                              // once the video has opened (mpv takes a caption file then)
        target: video
        function onDurationChanged() { if (video.duration > 0) player.autoCaptions(); }
    }
    Timer { id: autoCaptionsLater; interval: 1500; onTriggered: if (video.duration > 0) player.autoCaptions() }   // (a preloaded one: opened already)
    function setCaptions(c) {
        if (!c) { video.setSubtitle(0); captionsOn = ""; return; }
        const have = video.subtitles.find(t => t.title === c.name);
        if (have) video.setSubtitle(have.id); else addCaptions(c);
        captionsOn = c.name;
    }
    function toggleCaptions() {
        if (captionsOn) { captionsOffHere = true; return setCaptions(null); }
        const c = preferredCaptions((s && s.captions) || []);
        if (!c) return Y.toast("No captions for this video.");
        captionsOffHere = false;
        setCaptions(c);
        Y.toast("Captions: " + c.name);
    }
    function panelPick(i) {
        const o = panelOptions[i];
        if (panel === "channel") {
            if (i === 0) { if (v.subscribed) openPanel("notify"); else subscribe(true); }
            else { panel = ""; leaveFor(); player.openChannel(v.channelId); }
        } else if (panel === "notify") {
            if (o.level === "unsubscribe") { subscribe(false); return; }
            const opt = (v.notifyOptions || []).find(x => x.level === o.level);
            if (!opt) return;
            Y.call("notify", {params: opt.params, level: o.level}, () => {
                meta = Object.assign({}, meta, {video: Object.assign({}, v, {notify: o.level})});
            });
        } else if (panel === "settings") {
            panel = ["quality", "speed", "captions"][i];
        } else if (panel === "quality") {
            setQuality(o.h); panel = "";
        } else if (panel === "speed") {
            speed = o.x; video.setSpeed(o.x); panel = "";
        } else if (panel === "captions") {
            captionsOffHere = !o.c;
            setCaptions(o.c || null); panel = "";
        } else if (panel === "save") {
            const add = !o.checked;
            Y.call("save", {id: videoId, playlist: o.id, add: add}, () => {
                saveOptions = saveOptions.map(x => x.id === o.id ? Object.assign({}, x, {saved: add}) : x);
                Y.toast((add ? "Saved to " : "Removed from ") + o.label);
            });
        }
    }

    // ------------------------------------------------------------------ the overlay
    readonly property bool shown: mode !== "hidden" || video.paused || !!message || !s
    function showControls() {
        if (mode === "hidden") { mode = "controls"; }
        hide.restart();
    }
    Timer { id: hide; interval: 5000; onTriggered: if (!video.paused && player.mode !== "related" && player.mode !== "chapters" && !!player.s && !player.ending && !player.panel) player.mode = "hidden" }
    function skip(d) {
        if (!s) return;
        video.seek(d);                         // a live stream too: back into its DVR window and forward again
        if (live && duration > 0) Y.toast(duration - pos - d > 8 ? Y.clock(duration - pos - d) + " behind live" : "Live");   // (the edge itself is a few seconds behind)
        if (mode === "hidden") mode = "bar";
        hide.restart();
    }
    function back() {
        if (panel === "quality" || panel === "speed" || panel === "captions") { panel = "settings"; return; }
        if (panel) { panel = ""; return; }
        if (mode === "chapters") { mode = "bar"; hide.restart(); return; }
        if (scrub >= 0) { cancelScrub(); mode = "hidden"; return; }   // Back: the scrub undone, the video where it was
        if (mode === "related") { mode = "controls"; hide.restart(); return; }
        // the controls up: Back only hides them (still loading, they can't hide: it leaves)
        if (mode !== "hidden" && s && !message) { mode = "hidden"; return; }
        finished();
    }
    // captions above the controls while they're up (YouTube's: never under the scrim or the related row)
    readonly property bool captionsHigh: mode !== "hidden" || !!panel
    onCaptionsHighChanged: video.setSubtitlePosition(captionsHigh ? 58 : 100)
    // ...and out of the way of the related row and the seek frames (they'd sit over them)
    readonly property bool captionsShown: mode !== "related" && !seeking
    onCaptionsShownChanged: video.setSubtitleShown(captionsShown)
    onModeChanged: {
        if (mode === "related") related.forceActiveFocus();      // now: the next key (even right after) goes to the row
        else { if (!panel) ctl.forceActiveFocus(); related.index = 0; }   // the row folds back (an open panel keeps the focus)
    }
    Connections {
        target: related
        function onAtTop() { player.mode = "controls"; hide.restart(); }
    }

    // the controls, left to right
    readonly property var controls: [
        {key: "channel"}, {key: "description", label: "Description"}, {key: "bell", icon: "bell"},
        {key: "prev", icon: "prev"}, {key: "play"}, {key: "next", icon: "next"},
        {key: "like", icon: "like"}, {key: "dislike", icon: "dislike"}, {key: "comments", icon: "comments-round"},
        {key: "ask", icon: "sparkle"}, {key: "save", icon: "save"}, {key: "thanks", icon: "thanks"},
        {key: "cc", icon: "cc"}, {key: "settings", icon: "settings"}
    ]
    function act(key) {
        if (key === "play") video.togglePause();
        else if (key === "prev") { if (video.position > 5 || !s) video.seekTo(0); }
        else if (key === "next") playNext();
        else if (key === "channel") { if (v.channelId || (s && s.channelId)) openPanel("channel"); }
        else if (key === "like" || key === "dislike") rate(key);
        else if (key === "save") openPanel("save");
        else if (key === "bell") { if (!Y.signedIn) signInFirst("subscribe"); else if (v.subscribed) openPanel("notify"); else subscribe(true); }
        else if (key === "settings") openPanel("settings");
        else if (key === "description") openPanel("description");
        else if (key === "comments") openPanel("comments");
        else if (key === "cc") toggleCaptions();
        else Y.toast(({ask: "Ask", thanks: "Thanks"})[key] + " isn't on TVs yet.");
    }

    Keys.onPressed: e => {
        const k = e.key;
        if (askContinue) {                     // "Continue watching?": OK plays on; Back leaves
            if (k === Qt.Key_Return || k === Qt.Key_Enter) { askContinue = false; video.setPaused(false); showControls(); }
            else if (k === Qt.Key_Escape || k === Qt.Key_Back) { askContinue = false; finished(); }
            e.accepted = true;
            return;
        }
        if (k === Qt.Key_Escape || k === Qt.Key_Back) { if (!e.isAutoRepeat) back(); e.accepted = true; return; }
        if (signInOffer && (k === Qt.Key_Return || k === Qt.Key_Enter)) { if (!e.isAutoRepeat) Y.whoIsWatching(); e.accepted = true; return; }
        // a keyboard's (VacuumTube's) keys: P / D faster and slower, A normal speed, C captions, M sound
        const speeds = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2];
        if ((k === Qt.Key_P || k === Qt.Key_D || k === Qt.Key_A) && !(e.modifiers & Qt.ControlModifier)) {
            const i = speeds.indexOf(speed);
            speed = k === Qt.Key_A ? 1 : speeds[Math.max(0, Math.min(speeds.length - 1, (i < 0 ? 3 : i) + (k === Qt.Key_P ? 1 : -1)))];
            video.setSpeed(speed);
            Y.toast("Playback speed: " + (speed === 1 ? "Normal" : speed + "×"));
            e.accepted = true;
            return;
        }
        if (k === Qt.Key_C && !(e.modifiers & Qt.ControlModifier)) { toggleCaptions(); e.accepted = true; return; }
        if (k === Qt.Key_M && !(e.modifiers & Qt.ControlModifier)) { Y.toast(video.toggleMute() ? "Sound off" : "Sound on"); e.accepted = true; return; }
        if (k === Qt.Key_MediaTogglePlayPause || k === Qt.Key_MediaPlay || k === Qt.Key_MediaPause || k === Qt.Key_Space) {
            video.togglePause(); showControls();
        } else if (k === Qt.Key_AudioRewind || k === Qt.Key_MediaPrevious) {
            skip(-10);
        } else if (k === Qt.Key_AudioForward || k === Qt.Key_MediaNext) {
            skip(10);
        } else if (mode === "hidden") {
            if ((k === Qt.Key_Return || k === Qt.Key_Enter) && skipNotice) undoSkip();       // the notice's undo
            else if (k === Qt.Key_Return || k === Qt.Key_Enter) { mode = "controls"; button = 4; hide.restart(); }
            else if (k === Qt.Key_Left) { if (live) skip(-10); else scrubBy(-10); }
            else if (k === Qt.Key_Right) { if (live) skip(10); else scrubBy(10); }
            else if (k === Qt.Key_Up) { mode = "bar"; hide.restart(); }
            else if (k === Qt.Key_Down) { mode = "controls"; button = 4; hide.restart(); }
            else return;
        } else if (mode === "bar") {
            if (k === Qt.Key_Left) { if (live) skip(-10); else scrubBy(-10); }
            else if (k === Qt.Key_Right) { if (live) skip(10); else scrubBy(10); }
            else if ((k === Qt.Key_Return || k === Qt.Key_Enter) && scrub >= 0) { commitScrub(); mode = "hidden"; }   // there, playing
            else if (k === Qt.Key_Return || k === Qt.Key_Enter) { video.togglePause(); hide.restart(); }
            else if (k === Qt.Key_Down) { commitScrub(); mode = "controls"; hide.restart(); }
            // Up: the chapters (when it has some: "Press up to view chapters"), else back to the video
            else if (k === Qt.Key_Up) {
                if (chapters.length > 1) { scrubCommit.stop(); chapterPick = Math.max(0, chapter); mode = "chapters"; hide.restart(); }
                else { cancelScrub(); mode = "hidden"; }
            }
            else return;
        } else if (mode === "chapters") {
            hide.restart();
            if (k === Qt.Key_Left) chapterPick = Math.max(0, chapterPick - 1);
            else if (k === Qt.Key_Right) chapterPick = Math.min(chapters.length - 1, chapterPick + 1);
            else if (k === Qt.Key_Return || k === Qt.Key_Enter) { cancelScrub(); video.seekTo(chapters[chapterPick].start); mode = "bar"; }
            else if (k === Qt.Key_Down) { mode = "bar"; if (scrub >= 0) scrubCommit.restart(); }
            else return;
        } else if (mode === "controls") {
            hide.restart();
            if (k === Qt.Key_Left) button = Math.max(0, button - 1);
            else if (k === Qt.Key_Right) button = Math.min(controls.length - 1, button + 1);
            else if (k === Qt.Key_Up) { if (!live) mode = "bar"; }
            else if (k === Qt.Key_Down) { if (related.count) mode = "related"; }
            else if (k === Qt.Key_Return || k === Qt.Key_Enter) act(controls[button].key);
            else return;
        } else {
            return;
        }
        e.accepted = true;
    }

    // the video's place: the whole screen, or left of a panel
    readonly property rect place: Y.videoSide ? Qt.rect(54 * Y.u, 219 * Y.u, 1146 * Y.u, 645 * Y.u) : Qt.rect(0, 0, width, height)
    // the stand-in for the video while it loads (and off screen, the demo): its thumbnail
    Image {
        x: player.place.x; y: player.place.y; width: player.place.width; height: player.place.height
        visible: !player.s || !hasVideo
        source: player.seed.thumb || ""
        fillMode: Image.PreserveAspectCrop
        sourceSize: Y.sz(width, height)
        asynchronous: true
    }
    Rectangle {
        x: player.place.x; y: player.place.y; width: player.place.width; height: player.place.height
        visible: !hasVideo && !(player.seed.thumb)
        gradient: Gradient {
            GradientStop { position: 0; color: Qt.hsla(Y.hue(player.label), 0.35, 0.22, 1) }
            GradientStop { position: 1; color: Qt.hsla((Y.hue(player.label) + 0.2) % 1, 0.45, 0.08, 1) }
        }
    }

    Corners {                                  // the inset video's rounded corners
        visible: Y.videoSide
        x: player.place.x; y: player.place.y; width: player.place.width; height: player.place.height
        r: 28 * Y.u
    }
    DescriptionPanel {
        id: description
        objectName: "description"
        visible: player.panel === "description"
        v: player.v
        // with Return YouTube Dislike on: the dislikes beside the likes
        d: player.dislikes < 0 ? player.meta.details || {} : Object.assign({}, player.meta.details || {}, {
            facts: ((player.meta.details || {}).facts || []).slice(0, 1).concat([{value: Y.count(player.dislikes) || "0", label: "Dislikes"}],
                                                                              ((player.meta.details || {}).facts || []).slice(1))})
        chapters: player.chapters
        onOpenChannel: { player.panel = ""; player.leaveFor(); player.openChannel(player.v.channelId); }
        onOpenComments: player.openPanel("comments")
        onSeekTo: t => { video.seekTo(t); player.panel = ""; }
        onClosed: player.panel = ""
    }
    CommentsPanel {
        id: comments
        objectName: "comments"
        visible: player.panel === "comments"
        onClosed: player.panel = ""
    }
    PlayerPanel {
        id: sidePanel
        objectName: "panel"
        visible: !!player.panel && player.panel !== "description" && player.panel !== "comments"
        options: player.panelOptions
        avatar: player.panel === "channel" ? player.v.avatar || "" : ""
        name: player.panel === "channel" ? player.v.channel || "" : ""
        line: player.panel === "channel" ? [player.v.handle || "", player.v.subscribers || ""].filter(x => !!x).join(" · ") : ""
        title: ({notify: "Notifications", save: "Save video to…", settings: "Settings", quality: "Quality", speed: "Playback speed", captions: "Captions"})[player.panel] || ""
        subtitle: player.panel === "notify" ? "You'll get notified in the mobile app or on YouTube.com based on your account settings"
                : player.panel === "quality" ? "Auto picks the best this TV plays smoothly, up to 1080p at 60 frames a second" : ""
        onPicked: i => player.panelPick(i)
        onClosed: player.back()                // Quality, speed or captions: back to the settings menu; else closed
    }

    Item {
        id: overlay
        anchors.fill: parent
        opacity: player.shown && !player.panel ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 220 } }

        // the scrim, as YouTube's TV app has it with the controls (or the related row) up: the
        // video dimmed by about half, and from y 560 down a dark blue-violet, #08051e at the bottom
        Rectangle { anchors.fill: parent; color: player.mode === "related" ? "#c7000000" : "#85000000"; Behavior on color { ColorAnimation { duration: 220 } } }   // (the related row: all of it dimmed)
        Rectangle {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            height: 520 * Y.u
            gradient: Gradient {
                GradientStop { position: 0; color: "#0008051e" }
                GradientStop { position: 0.5; color: "#c708051e" }
                GradientStop { position: 1; color: "#ff08051e" }
            }
        }

        Item {
            id: sheet
            width: parent.width
            height: parent.height
            y: player.mode === "related" ? -480 * Y.u : 0
            Behavior on y { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }

            Column {                           // the title and channel
                x: 96 * Y.u; y: 96 * Y.u
                width: parent.width - 2 * x
                spacing: 12 * Y.u
                opacity: player.mode === "related" || player.seeking ? 0 : 1
                Behavior on opacity { NumberAnimation { duration: 180 } }
                Text {
                    width: Math.min(parent.width, implicitWidth)
                    text: player.label
                    color: Y.text
                    font.family: Y.font; font.pixelSize: 42 * Y.u; font.weight: Font.DemiBold
                    elide: Text.ElideRight
                    style: Text.Raised; styleColor: "#40000000"
                }
                Row {
                    spacing: 12 * Y.u
                    Rectangle {
                        visible: player.live
                        width: liveT.implicitWidth + 16 * Y.u; height: liveT.implicitHeight + 4 * Y.u; radius: 4 * Y.u
                        color: "#cc0000"
                        anchors.verticalCenter: parent.verticalCenter
                        Text { id: liveT; anchors.centerIn: parent; text: "LIVE"; color: "white"; font.family: Y.font; font.pixelSize: 22 * Y.u; font.weight: Font.Bold }
                    }
                    Text {
                        text: [player.v.channel || (player.s ? player.s.channel : "") || (player.seed.lines || [])[0] || "",
                               player.v.views || "", player.v.date || ""].filter(x => !!x).join(" • ")
                        color: Y.text
                        font.family: Y.font; font.pixelSize: Y.tMeta
                    }
                }
            }

            // ---------------------------------------------------------------- time, chapter, bar
            Item {
                id: barArea
                x: 96 * Y.u; y: 655 * Y.u
                width: parent.width - 192 * Y.u
                height: 70 * Y.u
                opacity: player.mode === "related" ? 0 : 1
                visible: !player.message
                Behavior on opacity { NumberAnimation { duration: 180 } }
                Rectangle {                    // live: the red badge where the time would be
                    visible: player.live
                    width: liveBar.implicitWidth + 20 * Y.u; height: 34 * Y.u; radius: 6 * Y.u
                    color: "#cc0000"
                    Text { id: liveBar; anchors.centerIn: parent; text: "LIVE"; color: "white"; font.family: Y.font; font.pixelSize: 22 * Y.u; font.weight: Font.Bold }
                }
                Rectangle {
                    visible: player.live
                    y: 59 * Y.u; width: parent.width; height: 6 * Y.u; radius: 3 * Y.u
                    color: Y.red
                }
                Text {
                    visible: !player.seeking
                    x: player.live ? liveBar.implicitWidth + 34 * Y.u : 0      // (beside the LIVE badge)
                    y: 5 * Y.u
                    text: player.live ? (player.duration - player.pos > 8 ? Y.clock(player.duration - player.pos) + " behind live" : "")
                                      : Y.clock(player.shownPos) + (player.chapter >= 0 ? " • " + player.chapters[player.chapter].title : "")
                    color: "#babac0"
                    font.family: Y.font; font.pixelSize: 24 * Y.u; font.weight: Font.Medium
                }
                Text {
                    visible: !player.seeking
                    anchors.right: parent.right
                    y: 5 * Y.u
                    // VacuumTube's "Show remaining time": the time left instead of the length
                    text: player.live ? "" : Y.settings.remaining_time ? "-" + Y.clock(Math.max(0, player.duration - player.pos)) : Y.clock(player.duration)
                    color: Y.dim
                    font.family: Y.font; font.pixelSize: 24 * Y.u; font.weight: Font.Medium
                }
                Item {                         // the bar, cut at the chapters
                    id: bar
                    visible: !player.live
                    y: 55 * Y.u
                    width: parent.width
                    height: 8 * Y.u
                    readonly property real frac: player.duration > 0 ? Math.min(1, player.shownPos / player.duration) : 0
                    readonly property var cuts: {
                        const d = player.duration, c = player.chapters;
                        if (!(d > 0) || c.length < 2) return [{a: 0, b: 1}];
                        const out = [];
                        for (let i = 0; i < c.length; i++)
                            out.push({a: Math.min(1, Math.max(0, c[i].start / d)), b: Math.min(1, i + 1 < c.length ? c[i + 1].start / d : 1)});
                        return out;
                    }
                    Repeater {
                        model: bar.cuts
                        Item {
                            required property var modelData
                            required property int index
                            readonly property real gapPx: index < bar.cuts.length - 1 ? 5 * Y.u : 0   // the last ends at the bar's end
                            x: modelData.a * bar.width
                            width: Math.max(1, (modelData.b - modelData.a) * bar.width - gapPx)
                            height: bar.height
                            Rectangle { anchors.fill: parent; radius: height / 2; color: "#5affffff" }
                            Rectangle {
                                width: Math.max(0, Math.min(parent.width, bar.frac * bar.width - parent.x))
                                height: parent.height
                                radius: height / 2
                                color: player.mode === "bar" || player.mode === "chapters" ? Y.red : Y.text   // (solid: YouTube's seek bar)
                            }
                        }
                    }
                    Repeater {                 // SponsorBlock's parts, in its colours
                        model: Y.settings.sponsorblock && player.duration > 0 ? player.segments : []
                        Rectangle {            // (at least 8 px wide, inside the bar, its end rounded at the bar's end)
                            required property var modelData
                            readonly property real w: Math.max(8 * Y.u, (Math.min(modelData.end, player.duration) - modelData.start) / player.duration * bar.width)
                            x: Math.max(0, Math.min(modelData.start / player.duration * bar.width, bar.width - w))
                            width: w
                            height: bar.height
                            radius: x + width >= bar.width - 1 || x <= 0 ? height / 2 : 0
                            color: Y.segmentColors[modelData.category] || Y.sponsor
                        }
                    }
                    Rectangle {                // the playhead while seeking
                        visible: player.mode === "bar" || player.mode === "chapters"
                        x: bar.frac * bar.width - width / 2
                        anchors.verticalCenter: parent.verticalCenter
                        width: 32 * Y.u; height: width; radius: width / 2
                        color: Y.text
                    }
                }
            }

            // ---------------------------------------------------------------- the chapters, while seeking
            // A strip of the chapters' pictures over the bar, the current one over the playhead (its
            // title white and bold, its time under it; the others' titles grey, cut short); Up
            // picks one (Left / Right, OK plays from it).
            // Without chapters: the storyboard's frame at the playhead (when YouTube has one) and the
            // time under it.
            Item {
                id: frameAt
                visible: player.seeking && player.chapters.length <= 1 && !player.live
                width: parent.width; height: parent.height
                readonly property var sb: player.s ? player.s.storyboard : null
                readonly property real cardW: 336 * Y.u
                readonly property real anchorX: Math.max(96 * Y.u + cardW / 2, Math.min(width - 96 * Y.u - cardW / 2, barArea.x + bar.frac * bar.width))
                readonly property var sheet: sb ? sb.sheets.find(g => player.shownPos >= g.start && player.shownPos < g.end) || sb.sheets[sb.sheets.length - 1] : null
                readonly property int tile: sheet && sb ? Math.min(sb.cols * sb.rows - 1, Math.floor((player.shownPos - sheet.start) / Math.max(0.001, sheet.end - sheet.start) * sb.cols * sb.rows)) : 0
                Item {
                    visible: !!frameAt.sheet && !!frameAt.sb
                    x: frameAt.anchorX - frameAt.cardW / 2; y: 387 * Y.u
                    width: frameAt.cardW; height: 189 * Y.u
                    clip: true
                    layer.enabled: visible             // its corners rounded (8 px), as YouTube's
                    layer.effect: MultiEffect { maskEnabled: true; maskSource: frameMask; maskThresholdMin: 0.5; maskSpreadAtMin: 1.0 }
                    Image {
                        source: frameAt.sheet ? frameAt.sheet.url : ""
                        width: frameAt.sb ? frameAt.sb.cols * parent.width : 0
                        height: frameAt.sb ? frameAt.sb.rows * parent.height : 0
                        x: frameAt.sb ? -(frameAt.tile % frameAt.sb.cols) * parent.width : 0
                        y: frameAt.sb ? -Math.floor(frameAt.tile / frameAt.sb.cols) * parent.height : 0
                        asynchronous: true
                        cache: true
                        smooth: true
                    }
                }
                Rectangle {
                    id: frameMask
                    width: frameAt.cardW; height: 189 * Y.u; radius: 8 * Y.u
                    visible: false
                    layer.enabled: true
                }
                Text {
                    x: frameAt.anchorX - width / 2
                    y: 649 * Y.u - height / 2
                    text: Y.clock(player.shownPos)
                    color: Y.text; font.family: Y.font; font.pixelSize: 26 * Y.u; font.weight: Font.Medium
                    style: Text.Raised; styleColor: "#60000000"
                }
            }
            Item {
                id: strip
                visible: player.seeking && player.chapters.length > 1
                width: parent.width
                height: parent.height
                readonly property int cur: player.mode === "chapters" ? player.chapterPick : Math.max(0, player.chapter)
                readonly property real cardW: 336 * Y.u
                readonly property real pitch: cardW + 18 * Y.u
                // where the current chapter's middle sits: over the playhead, kept on the screen
                readonly property real anchorX: Math.max(96 * Y.u + cardW / 2, Math.min(width - 96 * Y.u - cardW / 2, barArea.x + bar.frac * bar.width))
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    y: 340 * Y.u - height / 2
                    text: player.mode === "chapters" ? "OK plays from the chapter" : "Press up to view chapters"
                    color: Y.text; font.family: Y.font; font.pixelSize: 24 * Y.u
                    style: Text.Raised; styleColor: "#80000000"
                }
                Repeater {
                    model: player.chapters
                    Item {
                        id: chap
                        required property var modelData
                        required property int index
                        readonly property bool cur: index === strip.cur
                        readonly property bool picking: cur && player.mode === "chapters"
                        x: strip.anchorX - strip.cardW / 2 + (index - strip.cur) * strip.pitch
                        y: 387 * Y.u
                        visible: x > -strip.cardW && x < strip.width
                        width: strip.cardW; height: 290 * Y.u
                        Behavior on x { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
                        Rectangle {
                            width: parent.width; height: 189 * Y.u; radius: 12 * Y.u
                            color: Qt.hsla(Y.hue(chap.modelData.title), 0.45, 0.28, 1)
                            RoundImage {
                                anchors.fill: parent
                                radius: 12 * Y.u
                                cover: true
                                source: chap.modelData.thumb || ""
                                visible: !!chap.modelData.thumb
                            }
                            Rectangle {                // picking: the focus ring
                                visible: chap.picking
                                x: -Y.ring; y: -Y.ring
                                width: parent.width + 2 * Y.ring; height: parent.height + 2 * Y.ring
                                radius: parent.radius + Y.ring
                                color: "transparent"
                                border.color: Y.text; border.width: Y.ring
                            }
                        }
                        Text {
                            y: 226 * Y.u - height / 2
                            width: parent.width
                            horizontalAlignment: chap.cur ? Text.AlignHCenter : Text.AlignLeft
                            text: chap.modelData.title
                            color: chap.cur ? Y.text : Y.soft
                            font.family: Y.font; font.pixelSize: 24 * Y.u; font.weight: chap.cur ? Font.Bold : Font.Medium
                            elide: Text.ElideRight
                            style: Text.Raised; styleColor: "#60000000"
                        }
                        Text {
                            visible: chap.cur
                            y: 262 * Y.u - height / 2
                            width: parent.width
                            horizontalAlignment: Text.AlignHCenter
                            text: Y.clock(player.mode === "chapters" ? chap.modelData.start : player.shownPos)
                            color: Y.text; font.family: Y.font; font.pixelSize: 24 * Y.u
                            style: Text.Raised; styleColor: "#60000000"
                        }
                    }
                }
            }

            // ---------------------------------------------------------------- the controls
            Item {
                id: row
                x: 96 * Y.u; y: 741 * Y.u
                width: parent.width - 192 * Y.u
                height: 96 * Y.u
                opacity: player.mode === "related" || player.seeking ? 0 : 1
                Behavior on opacity { NumberAnimation { duration: 180 } }
                readonly property bool live: player.mode === "controls" && player.activeFocus
                function on(i) { return live && player.button === i; }

                Row {                          // the channel, Description, the bell
                    spacing: 14 * Y.u
                    anchors.verticalCenter: parent.verticalCenter
                    Rectangle {
                        width: 72 * Y.u; height: width; radius: width / 2
                        color: row.on(0) ? Y.text : "#1fffffff"
                        RoundImage {
                            anchors { fill: parent; margins: row.on(0) ? 5 * Y.u : 0 }
                            source: player.v.avatar || ""
                            fallback: player.v.channel || ""
                        }
                    }
                    Rectangle {
                        width: descT.implicitWidth + 66 * Y.u; height: 72 * Y.u; radius: height / 2
                        color: row.on(1) ? Y.text : "#1fffffff"
                        Text { id: descT; anchors.centerIn: parent; text: "Description"; color: row.on(1) ? Y.ink : Y.text; font.family: Y.font; font.pixelSize: 26 * Y.u; font.weight: Font.Medium }
                    }
                    CtlButton {                // the bell when subscribed (its level), else Subscribe
                        visible: !Y.signedIn || !!player.v.subscribed
                        icon: ({all: "bell-all", none: "bell-off"})[player.v.notify] || "bell"
                        on: row.on(2)
                    }
                    Rectangle {
                        visible: Y.signedIn && !player.v.subscribed
                        width: subT.implicitWidth + 64 * Y.u; height: 72 * Y.u; radius: height / 2
                        color: row.on(2) ? Y.text : "#1fffffff"
                        Text { id: subT; anchors.centerIn: parent; text: "Subscribe"; color: row.on(2) ? Y.ink : Y.text; font.family: Y.font; font.pixelSize: 26 * Y.u; font.weight: Font.Medium }
                    }
                }
                Row {                          // previous, play/pause, next
                    anchors.centerIn: parent
                    spacing: 18 * Y.u
                    CtlButton { icon: "prev"; on: row.on(3); anchors.verticalCenter: parent.verticalCenter }
                    CtlButton {
                        icon: video.paused || !player.s ? "play" : "pause"
                        big: true
                        on: row.on(4)
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    CtlButton { icon: "next"; on: row.on(5); anchors.verticalCenter: parent.verticalCenter }
                }
                Row {                          // like ... Thanks | captions, settings
                    anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                    spacing: 14 * Y.u
                    Rectangle {
                        width: actions.implicitWidth; height: 72 * Y.u; radius: height / 2
                        color: "#1fffffff"
                        Row {
                            id: actions
                            Repeater {
                                model: ["like", "dislike", "comments", "sparkle", "save", "thanks"]
                                CtlButton {
                                    required property string modelData
                                    required property int index
                                    icon: modelData === "like" && player.v.like === "like" ? "like-filled"
                                        : modelData === "dislike" && player.v.like === "dislike" ? "dislike-filled" : modelData
                                    on: row.on(6 + index)
                                    plain: true
                                }
                            }
                        }
                    }
                    Rectangle {
                        width: tools.implicitWidth; height: 72 * Y.u; radius: height / 2
                        color: "#1fffffff"
                        Row {
                            id: tools
                            CtlButton { icon: "cc"; on: row.on(12); plain: true; marked: !!player.captionsOn }   // (outlined; on: a bar under it)
                            CtlButton { icon: "settings"; on: row.on(13); plain: true }
                        }
                    }
                }
            }

            // ---------------------------------------------------------------- related videos
            Feed {
                id: related
                objectName: "related"
                y: 948 * Y.u
                width: parent.width
                height: 532 * Y.u             // opened, it ends at y 1000: the next row doesn't peek in
                indent: 96 * Y.u
                cardW: 552 * Y.u
                fixed: true
                behind: "transparent"          // over the video: no corners painted
                visible: player.mode !== "hidden" && !player.seeking
                onOpen: it => Y.open(it)
            }
        }

        Rectangle {                            // why it won't play: a card over the picture, not bare text
            visible: !!player.message
            anchors.centerIn: parent
            width: Math.min(parent.width * 0.66, whyText.paintedWidth + 120 * Y.u)
            height: whyText.paintedHeight + 90 * Y.u
            radius: 24 * Y.u
            color: "#e6121212"
            border.color: "#33ffffff"; border.width: 2 * Y.u
        }
        Text {                                 // loading, or why it won't play
            id: whyText
            visible: !player.s || !!player.message || player.waitLeft > 0
            anchors.centerIn: parent
            width: parent.width * 0.6
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: player.signInOffer ? "YouTube wants you signed in to play this.\nOK: sign in or choose an account · Back to go back."
                : player.message ? player.message + "\nBack to go back."
                : player.waitLeft > 0 ? "Starting in " + player.waitLeft + " s (YouTube holds it back as long as its ads would play)" : "Loading…"
            color: Y.text
            font.family: Y.font; font.pixelSize: 32 * Y.u
            style: Text.Raised; styleColor: "#80000000"
        }
    }
    Rectangle {                                // "Video paused. Continue watching?"
        visible: player.askContinue
        anchors.fill: parent
        color: "#b3000000"
        Column {
            anchors.centerIn: parent
            spacing: 36 * Y.u
            Text { anchors.horizontalCenter: parent.horizontalCenter; text: "Video paused. Continue watching?"; color: Y.text; font.family: Y.font; font.pixelSize: 44 * Y.u; font.weight: Font.Bold }
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                width: yesT.implicitWidth + 96 * Y.u; height: 80 * Y.u; radius: height / 2
                color: Y.text
                Text { id: yesT; anchors.centerIn: parent; text: "Yes"; color: Y.ink; font.family: Y.font; font.pixelSize: 30 * Y.u; font.weight: Font.Medium }
            }
        }
    }
    Rectangle {                                // SponsorBlock: what was skipped, OK (controls hidden) undoes it
        visible: !!player.skipNotice && !player.panel && !player.ending
        anchors { right: parent.right; rightMargin: 96 * Y.u; top: parent.top; topMargin: 96 * Y.u }
        height: 72 * Y.u
        width: noticeRow.implicitWidth + 56 * Y.u
        radius: height / 2
        color: "#e6212121"
        Row {
            id: noticeRow
            anchors.centerIn: parent
            spacing: 16 * Y.u
            Rectangle { width: 16 * Y.u; height: width; radius: width / 2; anchors.verticalCenter: parent.verticalCenter
                        color: player.skipNotice ? Y.segmentColors[(player.segments.find(g => g.label === player.skipNotice.label) || {}).category] || Y.sponsor : Y.sponsor }
            Text { text: player.skipNotice ? "Skipped: " + player.skipNotice.label : ""; color: Y.text; font.family: Y.font; font.pixelSize: 26 * Y.u; font.weight: Font.Medium; anchors.verticalCenter: parent.verticalCenter }
            Text { visible: player.mode === "hidden"; text: "OK to undo"; color: Y.dim; font.family: Y.font; font.pixelSize: 26 * Y.u; anchors.verticalCenter: parent.verticalCenter }
        }
    }
    EndScreen {
        id: endScreen
        objectName: "endscreen"
        anchors.fill: parent
        visible: player.ending
        onPlayNow: { player.ending = false; ctl.forceActiveFocus(); player.playNext(); }
        onCancel: { player.ending = false; player.mode = "controls"; player.button = 3; ctl.forceActiveFocus(); player.showControls(); }
    }
    Rectangle {                                // buffering
        id: busy
        visible: !!player.s && video.buffering && !video.paused
        anchors.centerIn: parent
        width: 96 * Y.u; height: width; radius: width / 2
        color: "#80000000"
        border.color: Y.text; border.width: 6 * Y.u
        RotationAnimation on rotation { running: busy.visible; from: 0; to: 360; duration: 1200; loops: Animation.Infinite }
        Rectangle { width: 22 * Y.u; height: width; radius: width / 2; color: Y.red; x: parent.width / 2 - width / 2; y: -4 * Y.u }
    }
}
