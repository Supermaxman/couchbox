# Dev probe (not shipped; ci/box-probe/run.sh puts this folder on PYTHONPATH): with CBPROBE=DIR in
# the environment, a Couchbox Qt app logs every frame it shows and every key it gets.
#   DIR/frames.csv: t_ns (CLOCK_MONOTONIC as the frame goes to the screen), anim_ms (the animation
#                   clock: how far a running animation had moved for that frame)
#   DIR/keys.csv:   t_ns, p or r (press, release), key, autorepeat
#   DIR/video.csv:  every 2 s while the app has a player: t_ns, position, paused, the file's and the
#                   shown frame rate, mpv's dropped / decoder-dropped / late / mistimed frames, A/V sync
import os
import sys

_dir = os.environ.get("CBPROBE")
if _dir:
    try:
        import time

        from PySide6.QtCore import QEvent, QObject, QTimer, QVariantAnimation
        from PySide6.QtGui import QGuiApplication

        _state = {"wins": set(), "keep": []}

        class _Keys(QObject):
            def __init__(self, out):
                super().__init__()
                self.out = out

            def eventFilter(self, obj, ev):
                t = ev.type()
                if t == QEvent.KeyPress or t == QEvent.KeyRelease:
                    self.out.write(f"{time.monotonic_ns()},{'p' if t == QEvent.KeyPress else 'r'},{ev.key()},{int(ev.isAutoRepeat())}\n")
                return False

        def _attach():
            for w in QGuiApplication.topLevelWindows():
                if id(w) in _state["wins"] or not hasattr(w, "frameSwapped"):
                    continue
                _state["wins"].add(id(w))
                n = len(_state["wins"])
                frames = open(os.path.join(_dir, f"frames{'' if n == 1 else n}.csv"), "w", buffering=1 << 16)
                keys = open(os.path.join(_dir, f"keys{'' if n == 1 else n}.csv"), "w", buffering=1)
                clock = _state["clock"]

                def swapped(frames=frames, clock=clock):
                    frames.write(f"{time.monotonic_ns()},{clock.currentTime()}\n")

                w.frameSwapped.connect(swapped)
                f = _Keys(keys)
                w.installEventFilter(f)
                _state["keep"] += [frames, keys, f, swapped]
                t = QTimer()
                t.setInterval(1000)
                t.timeout.connect(frames.flush)
                t.start()
                _state["keep"].append(t)

        _exec = QGuiApplication.exec

        def _run():
            clock = QVariantAnimation()
            clock.setStartValue(0.0)
            clock.setEndValue(1.0)
            clock.setDuration(24 * 3600 * 1000)
            clock.start()
            _state["clock"] = clock
            _attach()
            again = QTimer()
            again.setInterval(500)
            again.timeout.connect(_attach)
            again.start()
            _state["keep"].append(again)

            # the video's own counters, every 2 s (when the app has a player): DIR/video.csv
            def _video():
                mod = sys.modules.get("couchbox.player")
                for p in list(getattr(mod, "_players", [])) if mod else []:
                    try:
                        m = p.mpv
                        row = [
                            time.monotonic_ns(),
                            m.time_pos,
                            m.pause,
                            m.container_fps,
                            m.estimated_vf_fps,
                            m.frame_drop_count,
                            m.decoder_frame_drop_count,
                            m.vo_delayed_frame_count,
                            m.mistimed_frame_count,
                            m.avsync,
                            m.total_avsync_change,
                        ]
                        _state["video"].write(",".join("" if x is None else str(x) for x in row) + "\n")
                        _state["video"].flush()
                    except Exception:  # noqa: BLE001
                        pass

            _state["video"] = open(os.path.join(_dir, "video.csv"), "w")
            vt = QTimer()
            vt.setInterval(2000)
            vt.timeout.connect(_video)
            vt.start()
            _state["keep"].append(vt)
            with open(os.path.join(_dir, "info.txt"), "w") as f:
                f.write(f"loop={os.environ.get('QSG_RENDER_LOOP', '')} argv={sys.argv}\n")
            return _exec()

        QGuiApplication.exec = staticmethod(_run)
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"cbprobe: {e!r}\n")
