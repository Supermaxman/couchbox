"""Qt plumbing shared by Settings and the setup wizard: Backend (couchboxd over JSON-RPC, its
events, QR codes) and Shooter (--shot screenshots and --keys for tests)."""

import base64
import json
import os
import subprocess
import sys
import threading

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow  # noqa: F401  (grabWindow on the root window)

from couchbox import ipc, paths

TOPICS = ["settings", "secrets", "network", "remote", "updates", "encryption", "tailscale", "phone", "setup"]


class Backend(QObject):
    reply = Signal(int, str)
    event = Signal(str, str)

    @Slot(int, str, str)
    def call(self, rid, method, params):
        def work():
            try:
                out = {"result": ipc.call(method, **json.loads(params or "{}"))}
            except ipc.IpcError as e:
                out = {"error": str(e)}
            except Exception as e:  # noqa: BLE001
                out = {"error": f"{method}: {e}"}
            self.reply.emit(rid, json.dumps(out))

        threading.Thread(target=work, daemon=True).start()

    def listen(self, topics):
        def run():
            import time

            while True:
                try:
                    for ev in ipc.subscribe(topics):
                        self.event.emit(ev["topic"], json.dumps(ev["data"]))
                except (ipc.IpcError, OSError):
                    time.sleep(3)

        threading.Thread(target=run, daemon=True).start()

    @Slot(str, result=str)
    def qr(self, text):
        """A QR code as a data: URL (qrencode)."""
        try:
            png = subprocess.run(["qrencode", "-t", "PNG", "-s", "10", "-m", "1", "-o", "-", text], capture_output=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError):
            return ""
        return "data:image/png;base64," + base64.b64encode(png).decode()

    @Slot(str)
    def launch(self, name):
        subprocess.Popen([f"/usr/lib/couchbox/bin/{name}"], start_new_session=True)


class Shooter(QObject):
    window = None

    @Slot(str)
    def save(self, path):
        from couchbox import qtcheck

        qtcheck.clipped(self.window)
        self.window.grabWindow().save(path)

    @Slot(str)
    def press(self, name):
        from PySide6.QtCore import QCoreApplication, QEvent, Qt
        from PySide6.QtGui import QKeyEvent

        key = {
            "up": Qt.Key_Up,
            "down": Qt.Key_Down,
            "left": Qt.Key_Left,
            "right": Qt.Key_Right,
            "ok": Qt.Key_Return,
            "back": Qt.Key_Escape,
        }.get(name)
        if key is not None:
            for t in (QEvent.KeyPress, QEvent.KeyRelease):
                QCoreApplication.sendEvent(self.window, QKeyEvent(t, key, Qt.NoModifier))


def run(name: str, title: str, qml: str) -> int:
    """Start a couchboxd-backed QML app (share/ui/<qml>)."""
    if "--demo" in sys.argv:
        from couchbox import demo

        demo.start()
    if "--shot" in sys.argv:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ["QML_XHR_ALLOW_FILE_READ"] = "1"  # CouchKit reads the phone page's address
    app = QGuiApplication(sys.argv)
    app.setApplicationName(name)
    app.setApplicationDisplayName(title)
    app.setDesktopFileName(name)
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(paths.share() / "ui"))
    backend = Backend()
    shooter = Shooter()
    engine.rootContext().setContextProperty("backend", backend)
    engine.rootContext().setContextProperty("shooter", shooter)
    engine.load(QUrl.fromLocalFile(str(paths.share() / "ui" / qml)))
    if not engine.rootObjects():
        sys.exit(f"{qml} didn't load")
    shooter.window = engine.rootObjects()[0]
    backend.listen(TOPICS)
    return app.exec()
