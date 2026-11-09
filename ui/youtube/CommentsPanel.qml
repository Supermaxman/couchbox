// The comments beside the video, laid out as YouTube's TV app's (measured in VacuumTube): first
// YouTube's "Open the YouTube mobile app to add comments and replies" row, then who, when, the
// text, its likes and replies; more load as the list nears its end. Up and Down move (the list
// glides under the focus; a comment keeps its size whether focused or not). OK on any comment
// opens its own page: the comment whole with Like, Dislike and Report under it (the focus on Like;
// Left and Right between them, OK presses), the mobile-app row, then its replies (more as the list
// nears its end), sliding in over the comments. OK on a reply opens that one's page the same way.
// Back goes back a page (on the same comment), or closes.
import QtQuick

FocusScope {
    id: panel
    property bool open: false                 // shown: it slides in from the right (PlayerPage)
    property string token: ""                 // the first page's continuation (the watch page's)
    property string count: ""
    property string more: ""                  // the comments' next page
    property string replyMore: ""             // the open comment's replies' next page
    property bool loading: false              // a page of comments on its way
    property bool replyLoading: false
    property string problem: ""
    property string replyProblem: ""
    property var thread: null                 // the comment open: {replies, key, token}
    property var acts: null                   // its Like and Dislike (from its page): {like, unlike, dislike, undislike, counts}
    property int button: 0                    // its button with the focus: 0 Like, 1 Dislike, 2 Report
    property int pendingVote: -1              // OK on a button before its page came: pressed when it does
    property var stack: []                    // the pages under this one (a reply opened from a comment's page)
    property real nest: 1                     // a page over a page: it slides in (0 -> 1)
    property int nestDir: 1                   // ... from the right (opening), from the left (Back)
    property int gen: 0                       // which load an answer is for (the player moved on, Back...)
    property var keys: ({})                   // the comments in the list (a page repeating one: once)
    property var replyKeys: ({})
    readonly property var curList: thread ? replies : comments
    function focusDetail() {
        const p = thread ? replyModel.get(0) : null;
        return {comments: curList.count, thread: !!thread, at: curList.currentIndex, replies: thread ? Math.max(0, replyModel.count - 2) : 0,
                withReplies: firstWithReplies(), depth: thread ? stack.length + 1 : 0, kind: (curList.currentIndex >= 0 && (thread ? replyModel : commentModel).count) ? ((thread ? replyModel : commentModel).get(curList.currentIndex) || {}).kind || "" : "",
                head: p ? {button: curList.currentIndex === 0 ? ["like", "dislike", "report"][button] : "", vote: p.vote, likes: p.likes, ready: !!acts} : null};
    }
    function firstWithReplies() {
        const m = thread ? replyModel : commentModel;
        for (let i = 0; i < m.count; i++) if (m.get(i).repliesToken) return i;
        return -1;
    }
    signal closed()
    x: 1254 * Y.u
    width: 612 * Y.u
    height: parent ? parent.height : 0

    // opening: in from the right; closing: out, quicker
    visible: open || opacity > 0
    opacity: open ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: panel.open ? Y.tPanel : Y.tOut; easing.type: Easing.OutCubic } }
    transform: Translate {
        x: panel.open ? 0 : 56 * Y.u
        Behavior on x { NumberAnimation { duration: Y.tPanel; easing.type: Easing.OutCubic } }
    }

    ListModel { id: commentModel }
    ListModel { id: replyModel }
    // one shape for every comment (a ListModel's roles are its first item's)
    readonly property var roles: ["key", "kind", "author", "photo", "text", "time", "likes", "replies", "repliesToken", "pinned", "isParent", "vote", "open"]
    readonly property string handoffText: "Open the YouTube mobile app to add comments and replies."
    function handoffRow(text) { return row({key: "handoff", kind: "handoff", text: text || handoffText}, false); }
    // OK on that row: what YouTube's TV app's panel says, in a line (it names the account's address: not here)
    function handoffNote() { Y.toast("To add comments and replies, open YouTube on your phone, signed in to the same account as this TV."); }
    function row(c, parent) {
        return {key: c.key || c.id || [c.author, c.time, String(c.text || "").slice(0, 80)].join("|"), kind: c.kind || "comment", author: c.author || "", photo: c.photo || "",
                text: c.text || "", time: c.time || "", likes: String(c.likes || ""), replies: c.replies || 0,
                repliesToken: c.repliesToken || "", pinned: !!c.pinned, isParent: !!parent, vote: c.vote || "",
                open: c.open || c.repliesToken || ""};
    }
    function rowsOf(model) {
        const out = [];
        for (let i = 0; i < model.count; i++) { const o = model.get(i), r = {}; for (const k of roles) r[k] = o[k]; out.push(r); }
        return out;
    }
    function addTo(model, seen, items) {
        for (const c of items || []) {
            const r = row(c, false);
            if (seen[r.key]) continue;
            seen[r.key] = true;
            model.append(r);
        }
    }

    function load() {
        gen++;
        commentModel.clear(); replyModel.clear(); keys = {}; replyKeys = {};
        more = ""; replyMore = ""; problem = ""; replyProblem = ""; loading = false; replyLoading = false;
        flip.enabled = false; thread = null; flip.enabled = true;   // (on the comments at once)
        stack = []; acts = null; pendingVote = -1; nestIn.stop(); nest = 1;
        if (!token) { problem = "Comments are turned off for this video."; return; }
        fetchComments(token);
    }
    function fetchComments(t) {
        loading = true;
        const g = gen;
        Y.call("comments", {token: t}, r => {
            if (!panel || panel.gen !== g) return;   // (another video meanwhile)
            loading = false;
            if (!commentModel.count && r.handoff && (r.items || []).length) { commentModel.append(handoffRow(r.handoff)); keys["handoff"] = true; }
            addTo(commentModel, keys, r.items);
            if (comments.currentIndex < 0 && commentModel.count) comments.currentIndex = 0;
            more = r.more || "";
            if (!commentModel.count) problem = "No comments yet.";
        }, e => { if (panel && panel.gen === g) { panel.loading = false; if (!commentModel.count) panel.problem = e; } });
    }
    function fetchReplies(t) {
        replyLoading = true;
        const g = gen, th = thread;
        Y.call("comments", {token: t}, r => {
            if (!panel || panel.gen !== g || panel.thread !== th) return;   // (Back meanwhile, or another one)
            replyLoading = false;
            const p = replyModel.get(0);
            if (r.head && p && (!r.head.id || r.head.id === p.key)) {   // the comment itself: its buttons, its count and vote now
                if (r.head.actions) acts = r.head.actions;
                replyModel.setProperty(0, "likes", String(r.head.likes || ""));
                replyModel.setProperty(0, "vote", r.head.vote || "");
                if (r.head.text) replyModel.setProperty(0, "text", r.head.text);
            }
            if (r.handoff && replyModel.count > 1) replyModel.setProperty(1, "text", r.handoff);
            addTo(replyModel, replyKeys, r.items);
            replyMore = r.more || "";
            if (replyModel.count === 2 && th.replies) replyProblem = "No replies to show.";
            if (pendingVote >= 0 && acts) { button = pendingVote; pendingVote = -1; vote(); }
        }, e => { if (panel && panel.gen === g && panel.thread === th) { panel.replyLoading = false; if (replyModel.count === 2) panel.replyProblem = e; } });
    }
    function openComment() {
        const l = curList, m = thread ? replyModel : commentModel;
        const i = l.currentIndex, c = m.get(i), card = l.currentItem;
        if (c && c.kind === "handoff") { handoffNote(); return; }
        if (!c || (thread && i === 0) || !(c.open || (card && card.cut))) return;
        const p = row(c, true);
        if (thread) {   // a reply's own page, over this one (Back: this one again, on the same reply)
            stack = stack.concat([{rows: rowsOf(replyModel), keys: replyKeys, more: replyMore, problem: replyProblem, thread: thread,
                                   acts: acts, at: i, button: button}]);
            slide(1);
        }
        replyModel.clear();
        replyModel.append(p);
        replyModel.append(handoffRow(""));         // (there from the start: nothing moves when its page comes)
        replyKeys = {handoff: true}; replyKeys[p.key] = true;   // (a page of replies starting with it: not twice)
        replyMore = ""; replyProblem = ""; replyLoading = false;
        acts = null; button = 0; pendingVote = -1;
        thread = {replies: c.replies || 0, key: p.key, token: p.open};
        replies.currentIndex = 0;
        replies.positionViewAtBeginning();
        if (p.open) fetchReplies(p.open);
    }
    function back() {
        if (!thread) { closed(); return; }
        if (stack.length) {   // the page under this one, as it was
            const st = stack[stack.length - 1];
            stack = stack.slice(0, -1);
            slide(-1);
            replyModel.clear();
            for (const r of st.rows) replyModel.append(r);
            replyKeys = st.keys; replyMore = st.more; replyProblem = st.problem; replyLoading = false;
            acts = st.acts; button = st.button; pendingVote = -1;
            thread = st.thread;
            replies.currentIndex = st.at;
            replies.positionViewAtIndex(st.at, ListView.Contain);
            if (!acts && thread.token) fetchReplies(thread.token);   // (it hadn't come when the reply was opened)
            return;
        }
        thread = null; replyLoading = false; pendingVote = -1;
    }
    function slide(dir) { nestDir = dir; nestIn.restart(); }
    NumberAnimation { id: nestIn; target: panel; property: "nest"; from: 0; to: 1; duration: Y.tPanel; easing.type: Easing.OutCubic }

    // Like or Dislike on the open comment (again: taken back), at once on screen; YouTube told after
    // (refused: as it was, and why)
    function vote() {
        const p = replyModel.get(0);
        if (!thread || !p) return;
        if (button === 2) return Y.toast("Reporting comments isn't on TVs yet.");
        if (!Y.signedIn) return Y.toast("Sign in to like comments: the guide's picture, then Add account.");
        if (!acts) { pendingVote = button; return; }   // (its page on the way: pressed when it comes)
        const which = button === 0 ? "like" : "dislike", undo = p.vote === which;
        const name = (undo ? "un" : "") + which, action = acts[name];
        if (!action) return Y.toast("YouTube doesn't allow that on this comment.");
        const counts = acts.counts || {};
        const before = {vote: p.vote, likes: p.likes};
        setVote(p.key, {vote: undo ? "" : which, likes: name in counts ? String(counts[name] || "") : p.likes});
        Y.call("commentVote", {action: action}, () => {}, e => { if (panel) { panel.setVote(p.key, before); Y.toast(e); } });
    }
    // a comment's vote and likes wherever it's shown: this page, the comments, the pages under this one
    function setVote(key, v) {
        for (const m of [replyModel, commentModel])
            for (let i = 0; i < m.count; i++)
                if (m.get(i).key === key) { m.setProperty(i, "vote", v.vote); m.setProperty(i, "likes", v.likes); }
        stack = stack.map(st => Object.assign({}, st, {rows: st.rows.map(r => r.key === key ? Object.assign({}, r, v) : r)}));
    }
    function press() {
        if (thread && replies.currentIndex === 0) vote();
        else openComment();
    }
    function side(d) {
        if (thread && replies.currentIndex === 0) button = Math.max(0, Math.min(2, button + d));
    }
    function down() {
        const l = curList;
        l.incrementCurrentIndex();
        if (thread) { if (l.currentIndex >= replyModel.count - 3 && replyMore && !replyLoading) fetchReplies(replyMore); }
        else if (l.currentIndex >= commentModel.count - 3 && more && !loading) fetchComments(more);
    }
    Keys.onUpPressed: curList.decrementCurrentIndex()
    Keys.onDownPressed: down()
    Keys.onReturnPressed: e => { if (!e.isAutoRepeat) press(); }
    Keys.onEnterPressed: e => { if (!e.isAutoRepeat) press(); }
    Keys.onEscapePressed: back()
    Keys.onBackPressed: back()
    Keys.onLeftPressed: side(-1)
    Keys.onRightPressed: side(1)

    // the comments (0) or a comment's replies (1): one slides out to the left as the other comes in
    // (the one leaving gone in the first half, the one coming in the last two thirds: never both)
    property real t: thread ? 1 : 0
    readonly property real commentsA: thread ? Math.max(0, 1 - t * 2) : Math.min(1, Math.max(0, (0.65 - t) / 0.65))
    readonly property real repliesA: thread ? Math.min(1, Math.max(0, (t - 0.35) / 0.65)) : Math.max(0, t * 2 - 1)
    Behavior on t { id: flip; NumberAnimation { duration: Y.tPanel; easing.type: Easing.OutCubic } }
    // loading's placeholders breathe (one clock for all of them)
    property real pulse: 1
    SequentialAnimation on pulse {
        running: panel.visible && (panel.loading || panel.replyLoading) && !Y.shot
        loops: Animation.Infinite
        NumberAnimation { to: 0.45; duration: 700; easing.type: Easing.InOutSine }
        NumberAnimation { to: 1; duration: 700; easing.type: Easing.InOutSine }
        onRunningChanged: if (!running) panel.pulse = 1
    }

    Head { opacity: panel.commentsA; x: -48 * Y.u * panel.t; title: "Comments"; count: panel.count }
    Head { opacity: panel.repliesA; x: 48 * Y.u * (1 - panel.t); title: "Replies" }   // (YouTube's: no count)

    CommentList {
        id: comments
        objectName: "commentList"
        y: 120 * Y.u
        width: panel.width
        height: panel.height - y - 30 * Y.u
        model: commentModel
        opacity: panel.commentsA
        x: -48 * Y.u * panel.t
        live: !panel.thread
        focused: panel.activeFocus || !panel.open
        busy: panel.loading
        note: panel.problem
        pulse: panel.pulse
    }
    CommentList {
        id: replies
        objectName: "replyList"
        y: 120 * Y.u
        width: panel.width
        height: panel.height - y - 30 * Y.u
        model: replyModel
        replies: true
        opacity: panel.repliesA * panel.nest
        x: 48 * Y.u * (1 - panel.t) + 48 * Y.u * (1 - panel.nest) * panel.nestDir
        button: panel.button
        live: !!panel.thread
        focused: panel.activeFocus || !panel.open
        busy: panel.replyLoading
        note: panel.replyProblem
        pulse: panel.pulse
    }

    component Head: Row {
        property string title
        property string count
        y: 40 * Y.u
        spacing: 14 * Y.u
        visible: opacity > 0
        Text { id: ht; text: parent.title; color: Y.text; font.family: Y.font; font.pixelSize: 36 * Y.u; font.weight: Font.Bold }
        Text { text: parent.count; color: Y.dim; font.family: Y.font; font.pixelSize: 32 * Y.u; anchors.baseline: ht.baseline }
    }
}
