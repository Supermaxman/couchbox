// The comments beside the video: who, when, the text, its likes and replies; more load as the
// list nears its end. Up and Down move (the list glides under the focus; a comment keeps its size
// whether focused or not). OK on a comment with replies, or one cut short, opens it: the comment
// whole, then its replies (more as the list nears its end), sliding in over the comments; Back
// slides back to the comments, on the same one, or closes.
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
    property var thread: null                 // the comment open: {replies}
    property int gen: 0                       // which load an answer is for (the player moved on, Back...)
    property var keys: ({})                   // the comments in the list (a page repeating one: once)
    property var replyKeys: ({})
    readonly property var curList: thread ? replies : comments
    function focusDetail() { return {comments: curList.count, thread: !!thread, at: curList.currentIndex, replies: thread ? Math.max(0, replyModel.count - 1) : 0,
                                     withReplies: firstWithReplies()}; }
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
    function row(c, parent) {
        return {key: c.id || [c.author, c.time, String(c.text || "").slice(0, 80)].join("|"), author: c.author || "", photo: c.photo || "",
                text: c.text || "", time: c.time || "", likes: String(c.likes || ""), replies: c.replies || 0,
                repliesToken: c.repliesToken || "", pinned: !!c.pinned, isParent: !!parent};
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
        if (!token) { problem = "Comments are turned off for this video."; return; }
        fetchComments(token);
    }
    function fetchComments(t) {
        loading = true;
        const g = gen;
        Y.call("comments", {token: t}, r => {
            if (!panel || panel.gen !== g) return;   // (another video meanwhile)
            loading = false;
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
            addTo(replyModel, replyKeys, r.items);
            replyMore = r.more || "";
            if (replyModel.count === 1) replyProblem = "No replies to show.";
        }, e => { if (panel && panel.gen === g && panel.thread === th) { panel.replyLoading = false; if (replyModel.count === 1) panel.replyProblem = e; } });
    }
    function openComment() {
        if (thread) return;
        const i = comments.currentIndex, c = commentModel.get(i), card = comments.currentItem;
        if (!c || !(c.repliesToken || (card && card.cut))) return;
        replyModel.clear();
        const p = row(c, true);
        p.key = c.key;
        replyModel.append(p);
        replyKeys = {}; replyKeys[c.key] = true;   // (a page of replies starting with it: not twice)
        replyMore = ""; replyProblem = "";
        thread = {replies: c.replies || 0};
        replies.currentIndex = 0;
        replies.positionViewAtBeginning();
        if (c.repliesToken) fetchReplies(c.repliesToken);
    }
    function back() {
        if (!thread) { closed(); return; }
        thread = null; replyLoading = false;
    }
    function down() {
        const l = curList;
        l.incrementCurrentIndex();
        if (thread) { if (l.currentIndex >= replyModel.count - 3 && replyMore && !replyLoading) fetchReplies(replyMore); }
        else if (l.currentIndex >= commentModel.count - 3 && more && !loading) fetchComments(more);
    }
    Keys.onUpPressed: curList.decrementCurrentIndex()
    Keys.onDownPressed: down()
    Keys.onReturnPressed: e => { if (!e.isAutoRepeat) openComment(); }
    Keys.onEnterPressed: e => { if (!e.isAutoRepeat) openComment(); }
    Keys.onEscapePressed: back()
    Keys.onBackPressed: back()
    Keys.onLeftPressed: {}
    Keys.onRightPressed: {}

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
    Head { opacity: panel.repliesA; x: 48 * Y.u * (1 - panel.t); title: panel.thread && panel.thread.replies ? "Replies" : "Comment"
           count: panel.thread && panel.thread.replies ? String(panel.thread.replies) : "" }

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
        opacity: panel.repliesA
        x: 48 * Y.u * (1 - panel.t)
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
