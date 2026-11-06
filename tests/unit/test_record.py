"""couchbox-record: the stream's size and pipeline, the export clips, and a whole recording (start,
status, one at a time, stop, a crashed recorder, the length cap) against stand-ins for KWin's
helper, GStreamer and ffprobe."""

import importlib.machinery
import importlib.util
import json
import os
import pwd
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
RECORD = REPO / "bin" / "couchbox-record"


def load(name):
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_"), str(REPO / "bin" / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    m = importlib.util.module_from_spec(spec)
    loader.exec_module(m)
    return m


rec = load("couchbox-record")


def test_parses_the_helpers_line():
    s = rec.parse_stream("node=55 serial=61 width=1920 height=1080 output=HDMI-A-1")
    assert s == {"node": 55, "serial": 61, "width": 1920, "height": 1080, "output": "HDMI-A-1"}
    with pytest.raises(rec.Failed):
        rec.parse_stream("hello")


def test_size_follows_the_screen():
    assert rec.fit(3840, 2160, 1920) == (1920, 1080)  # a 4K TV, recorded at 1080p
    assert rec.fit(1280, 720, 1920) == (1280, 720)  # never wider than the screen
    assert rec.fit(1920, 1080, 1279) == (1278, 718)  # even, for the encoder
    assert rec.fit(0, 0, 1280) == (1280, 720)


def test_pipeline():
    stream = {"node": 55, "serial": 61}
    cmd = rec.pipeline(stream, (1280, 720), 30, False, "/home/tv/Videos/my clip.mp4", 600)
    assert cmd[:3] == ["gst-launch-1.0", "-e", "pipewiresrc"]
    assert "target-object=61" in cmd and "pulsesrc" not in cmd
    assert cmd[-1] == "location=/home/tv/Videos/my clip.mp4"  # one word: gst-launch escapes it
    text = " ".join(cmd)
    assert "video/x-raw,format=I420,width=1280,height=720" in text
    # KWin asked for 30 at most; an idle screen's frames repeated on the clock, so the file lasts as long as the recording
    assert "max-framerate=30/1" in text and "compositor start-time-selection=first ! video/x-raw,framerate=30/1" in text
    assert "videorate" not in text and "keepalive" not in text
    assert "speed-preset=ultrafast pass=qual quantizer=23 key-int-max=60" in text
    assert f"reserved-max-duration={660 * 10**9}" in text  # room for the index past the cap
    old_kwin = rec.pipeline({"node": 55, "serial": 0}, (1280, 720), 30, True, "/tmp/a.mp4", 10, "veryfast", 20)
    assert "path=55" in old_kwin and "pulsesrc" in old_kwin and "speed-preset=veryfast" in old_kwin


def test_export_commands():
    gif = rec.export_command("/v/a.mp4", "/v/a.gif", "gif")
    vf = gif[gif.index("-vf") + 1]
    assert vf.startswith("fps=12,scale=w=min(640\\,iw):h=-2") and "palettegen=stats_mode=diff" in vf
    assert "paletteuse=dither=bayer" in vf and "-an" in gif
    webm = rec.export_command("/v/a.mp4", "/v/a.webm", "webm", 480, fps=24, start=2, seconds=5)
    assert webm[webm.index("-ss") + 1] == "2" and webm[webm.index("-t") + 1] == "5" and "libvpx-vp9" in webm
    mp4 = rec.export_command("/v/a.mp4", "/v/a-small.mp4", "mp4")
    assert "libx264" in mp4 and "+faststart" in mp4 and "-ss" not in mp4
    assert mp4[mp4.index("-vf") + 1].startswith("scale=w=min(1280\\,iw)")  # 720p at most


HELPER = """#!/usr/bin/python3
import sys
print("node=55 serial=61 width=1920 height=1080 output=HDMI-A-1", flush=True)
sys.stdin.read()
"""
GST = """#!/usr/bin/python3
import signal, sys, time
out = [a for a in sys.argv if a.startswith("location=")][0][9:]
stop = []
signal.signal(signal.SIGINT, lambda *_: stop.append(1))
with open(out, "wb") as f:
    while not stop:
        f.write(b"x" * 1000)
        f.flush()
        time.sleep(0.05)
"""
FFPROBE = """#!/bin/sh
[ -s "$7" ] && echo 1.5
"""
FFMPEG = """#!/bin/sh
echo "$@" > "$(dirname "$0")/ffmpeg.args"
for last; do :; done
head -c 2048 /dev/zero > "$last"
"""


@pytest.fixture
def box(tmp_path, monkeypatch):
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    for name, body in (("couchbox-screencast", HELPER), ("gst-launch-1.0", GST), ("ffprobe", FFPROBE), ("ffmpeg", FFMPEG)):
        (bin_ / name).write_text(body)
        (bin_ / name).chmod(0o755)
    run = tmp_path / "run"
    run.mkdir(mode=0o700)
    monkeypatch.setenv("PATH", f"{bin_}:{os.environ['PATH']}")
    monkeypatch.setenv("COUCHBOX_SCREENCAST", str(bin_ / "couchbox-screencast"))
    monkeypatch.setenv("COUCHBOX_TV_USER", pwd.getpwuid(os.getuid()).pw_name)  # no sudo
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(run))
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def cli(*args):
    return subprocess.run([sys.executable, str(RECORD), *args], capture_output=True, text=True, timeout=60)


def state(box):
    return json.loads((box / "run/couchbox-record/state.json").read_text())


def test_a_recording(box):
    r = cli("start", "--width", "1280")
    assert r.returncode == 0, r.stderr
    assert "recording" in r.stdout and "1280x720" in r.stdout
    s = state(box)
    assert s["state"] == "recording" and s["file"].startswith(str(box / "Videos/couchbox/couchbox-"))
    assert cli("start").returncode == 1  # one at a time
    st = cli("status")
    assert st.returncode == 0 and "recording" in st.stdout and "1280x720 at 30 fps, no sound" in st.stdout
    r = cli("stop")
    assert r.returncode == 0, r.stderr
    assert r.stdout.startswith(s["file"] + " (0:01") and "stopped" in r.stdout
    assert state(box)["plays"] is True
    assert cli("status").returncode == 1 and cli("stop").returncode == 1


def test_a_crashed_recorder_still_leaves_its_file(box):
    out = box / "crash.mp4"
    assert cli("start", str(out)).returncode == 0
    s = state(box)
    os.kill(s["pid"], signal.SIGKILL)
    time.sleep(0.3)
    assert "stopped unexpectedly" in cli("status").stdout
    r = cli("stop")
    assert r.returncode == 0, r.stderr
    assert str(out) in r.stdout and state(box)["plays"]
    time.sleep(0.3)
    for pid in (s["gst"], s["helper"]):  # nothing left running (or only a zombie, gone with its parent)
        assert not rec.alive(pid, "gst-launch") and not rec.alive(pid, "couchbox-screencast")


def test_stops_by_itself_at_its_length(box):
    assert cli("start", str(box / "short.mp4"), "--seconds", "1").returncode == 0
    for _ in range(50):
        if state(box)["state"] == "done":
            break
        time.sleep(0.1)
    assert state(box)["reason"] == "reached 1 s"


def test_start_refuses_what_it_cant_do(box, monkeypatch):
    (box / "x.mp4").write_bytes(b"")
    assert "already exists" in cli("start", str(box / "x.mp4")).stderr
    monkeypatch.setenv("COUCHBOX_SCREENCAST", str(box / "none"))
    assert "missing" in cli("start").stderr


def test_export(box):
    src = box / "Videos/clip.mp4"
    src.parent.mkdir()
    src.write_bytes(b"x")
    r = cli("export", str(src), "--mp4", "--from", "2", "--to", "7.5")
    assert r.returncode == 0, r.stderr
    assert r.stdout.startswith(f"{box}/Videos/clip-small.mp4 (2 KB)")
    args = (box / "bin/ffmpeg.args").read_text().split()
    assert args[args.index("-ss") + 1] == "2" and args[args.index("-t") + 1] == "5.5"
    assert cli("export", str(src), "--from", "5", "--to", "3").returncode == 1
