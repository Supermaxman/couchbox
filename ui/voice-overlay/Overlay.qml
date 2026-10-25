// couchbox-voice indicator: a pill at the bottom of the TV, above every app, that shows what the
// voice assistant is doing (listening, what it heard, each action, its reply). Polls the
// couchbox-voice service on 127.0.0.1:8790; hidden (unmapped) while idle so it costs nothing.
// Run in the TV session by couchbox-voice-overlay.service: qml6 Overlay.qml
import QtQuick
import QtQuick.Window
import QtQuick.Shapes
import org.kde.layershell 1.0 as LayerShell

Window {
    id: win
    width: Screen.width
    height: 240
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus
    visible: false

    LayerShell.Window.scope: "couchbox-voice"
    LayerShell.Window.layer: LayerShell.Window.LayerOverlay
    LayerShell.Window.anchors: LayerShell.Window.AnchorBottom | LayerShell.Window.AnchorLeft | LayerShell.Window.AnchorRight
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityNone
    LayerShell.Window.exclusionZone: -1

    readonly property string font: "Inter"
    readonly property color accent: "#7aa2ff"
    readonly property real textMax: win.width * 0.62 - 140
    property var st: ({ phase: "idle", heard: "", status: "", reply: "" })
    property bool shown: false
    property bool busy: st.phase === "transcribing" || st.phase === "thinking" || st.phase === "working"

    function poll() {
        const x = new XMLHttpRequest();
        x.onreadystatechange = function () {
            if (x.readyState !== XMLHttpRequest.DONE)
                return;
            let s = null;
            try { s = JSON.parse(x.responseText); } catch (e) { }
            if (!s) { shown = false; return; }
            st = s;
            const age = s.now - s.t;
            // long enough to read; a question waits for the answer (hold the mic button)
            const linger = s.question ? 120 : Math.min(8, 3 + (s.reply || "").length / 25);
            shown = s.phase !== "idle" && !((s.phase === "done" || s.phase === "error") && age > linger);
        };
        x.open("GET", "http://127.0.0.1:8790/state");
        x.send();
    }

    onShownChanged: {
        if (shown) { win.visible = true; pill.opacity = 1; pill.lift = 0; }
        else { pill.opacity = 0; pill.lift = 24; hideTimer.restart(); }
    }

    Timer { interval: 120; running: true; repeat: true; onTriggered: win.poll() }
    Timer { id: hideTimer; interval: 320; onTriggered: if (!win.shown) win.visible = false }

    Rectangle {
        id: pill
        property real lift: 24
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 48 - lift
        width: Math.min(win.width * 0.62, Math.max(420, row.implicitWidth + 56))
        height: row.implicitHeight + 36
        radius: height / 2 > 44 ? 28 : height / 2
        color: Qt.rgba(0.07, 0.08, 0.10, 0.90)
        border.color: Qt.rgba(1, 1, 1, 0.10)
        border.width: 1
        opacity: 0
        Behavior on opacity { NumberAnimation { duration: 260; easing.type: Easing.OutCubic } }
        Behavior on lift { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
        Behavior on width { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
        Behavior on height { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }

        // soft accent glow along the top edge while working
        Rectangle {
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 18 }
            height: 2
            radius: 1
            color: win.st.phase === "error" ? "#ff6b6b" : win.accent
            opacity: win.busy || win.st.phase === "listening" ? 0.9 : 0
            Behavior on opacity { NumberAnimation { duration: 300 } }
        }

        Row {
            id: row
            anchors.verticalCenter: parent.verticalCenter
            anchors.left: parent.left
            anchors.leftMargin: 24
            spacing: 18

            // ---- state icon: bars (listening), spinner (busy), dot (done / error)
            Item {
                id: icon
                width: 44; height: 44
                anchors.verticalCenter: parent.verticalCenter

                Rectangle {
                    anchors.fill: parent
                    radius: width / 2
                    color: win.st.phase === "error" ? "#3a1c20" : Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.16)
                }
                Row {
                    anchors.centerIn: parent
                    spacing: 3
                    visible: win.st.phase === "listening"
                    Repeater {
                        model: 5
                        Rectangle {
                            required property int index
                            width: 4; radius: 2
                            anchors.verticalCenter: parent.verticalCenter
                            color: win.accent
                            height: 6
                            SequentialAnimation on height {
                                running: win.st.phase === "listening"
                                loops: Animation.Infinite
                                PauseAnimation { duration: index * 90 }
                                NumberAnimation { to: 22 - Math.abs(2 - index) * 4; duration: 260; easing.type: Easing.InOutSine }
                                NumberAnimation { to: 6; duration: 260; easing.type: Easing.InOutSine }
                            }
                        }
                    }
                }
                Shape {
                    anchors.centerIn: parent
                    width: 26; height: 26
                    visible: win.busy
                    preferredRendererType: Shape.CurveRenderer
                    RotationAnimation on rotation { running: win.busy; from: 0; to: 360; duration: 900; loops: Animation.Infinite }
                    ShapePath {
                        strokeColor: win.accent
                        strokeWidth: 3
                        fillColor: "transparent"
                        capStyle: ShapePath.RoundCap
                        PathAngleArc { centerX: 13; centerY: 13; radiusX: 11; radiusY: 11; startAngle: 0; sweepAngle: 250 }
                    }
                }
                Text {
                    anchors.centerIn: parent
                    visible: win.st.phase === "done" || win.st.phase === "error"
                    text: win.st.phase === "error" ? "!" : win.st.question ? "?" : "✓"
                    color: win.st.phase === "error" ? "#ff8a8a" : win.accent
                    font.family: win.font
                    font.pixelSize: 22
                    font.weight: Font.DemiBold
                }
            }

            Column {
                anchors.verticalCenter: parent.verticalCenter
                spacing: 4

                Text {
                    width: Math.min(implicitWidth, win.textMax)
                    visible: text !== ""
                    text: win.st.heard ? "“" + win.st.heard + "”" : ""
                    color: Qt.rgba(1, 1, 1, 0.55)
                    font.family: win.font
                    font.pixelSize: 17
                    elide: Text.ElideRight
                }
                Text {
                    width: Math.min(implicitWidth, win.textMax)
                    visible: text !== "" && win.st.phase !== "done" && win.st.phase !== "error"
                    text: win.st.note || ""
                    color: "#c9d6ff"
                    font.family: win.font
                    font.pixelSize: 20
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                    elide: Text.ElideRight
                }
                Text {
                    width: Math.min(implicitWidth, win.textMax)
                    text: win.st.phase === "done" || win.st.phase === "error" ? win.st.reply
                          : win.st.phase === "listening" ? "Listening…"
                          : (win.st.status || "Thinking") + "…"
                    color: win.st.phase === "error" ? "#ffb4b4" : "#f5f6f8"
                    font.family: win.font
                    font.pixelSize: 22
                    font.weight: Font.Medium
                    wrapMode: Text.WordWrap
                    maximumLineCount: 3
                    elide: Text.ElideRight
                }
                Text {
                    visible: win.st.phase === "done" && win.st.question
                    text: "Hold the mic button to answer"
                    color: win.accent
                    font.family: win.font
                    font.pixelSize: 15
                    font.weight: Font.Medium
                }
            }
        }
    }
}
