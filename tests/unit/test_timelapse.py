"""Timelapse (couchbox.timelapse): the speeds offered, Frigate's export asked for, the file brought over."""

import datetime
import os
import time

from couchbox import timelapse

H = 3600


def at(hour, minute=0, day=18):
    return datetime.datetime(2026, 11, day, hour, minute).timestamp()


def test_the_speeds_make_a_sensible_length():
    hour = {s["speed"] for s in timelapse.speeds(H)}
    assert hour == {2, 5, 10, 30, 60, 120, 300}  # 2x: half an hour; 600x would be 6 s
    day = timelapse.speeds(24 * H)
    assert [s["speed"] for s in day] == [60, 120, 300, 600, 1200]  # every frame of a day would take Frigate too long
    assert day[-1]["lengthLabel"] == "1 min 12 s"
    assert all(s["ready"] <= timelapse.SLOWEST for s in day)


def test_the_times_offered():
    spans = {s["key"]: s for s in timelapse.spans(at(17, 30))}
    assert list(spans) == ["hour", "3h", "today", "yesterday"]
    assert spans["yesterday"]["start"] == at(0, day=17) and spans["yesterday"]["end"] == at(0)
    assert spans["today"]["start"] == at(0) and spans["today"]["end"] == at(17, 30)
    assert spans["hour"]["hours"] == "4:30 PM – 5:30 PM" and spans["yesterday"]["hours"] == "Tuesday, all day"
    best = spans["yesterday"]["speeds"][spans["yesterday"]["best"]]
    assert best["speed"] == 1200  # about a minute and a half, the closest
    early = [s["key"] for s in timelapse.spans(at(2))]
    assert early == ["hour", "3h", "yesterday"]  # today so far: no more than the last 3 hours yet


def test_frigate_reads_only_keyframes_when_fast():
    fast_in, fast_out = timelapse.ffmpeg_args(600)
    assert "-skip_frame nokey" in fast_in and "setpts=0.001667*PTS" in fast_out and "-r 24" in fast_out
    slow_in, slow_out = timelapse.ffmpeg_args(2)
    assert "skip_frame" not in slow_in and "setpts=0.500000*PTS" in slow_out


class Reply:
    def __init__(self, code=200, body=None, data=b""):
        self.status_code, self.body, self.data = code, body, data
        self.ok = code < 400
        self.content = b"x" if body is not None else data
        self.headers = {"Content-Length": str(len(data))} if data else {}

    def json(self):
        return self.body

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(self.status_code)

    def iter_content(self, n):
        yield self.data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeFrigate:
    def __init__(self, fail=False):
        self.calls, self.polls, self.fail = [], 0, fail

    def request(self, method, path, stream=False, **kw):
        self.calls.append((method, path, kw.get("json")))
        if path.startswith("/api/export/custom/"):
            return Reply(202, {"success": True, "export_id": "yard_ab12"})
        if path == "/api/exports/yard_ab12":
            self.polls += 1
            if self.fail:
                return Reply(404, {"success": False})
            return Reply(200, {"in_progress": self.polls < 2, "video_path": "/media/frigate/exports/yard_x_ab12.mp4"})
        if path == "/api/jobs/export/yard_ab12":
            return Reply(
                200, {"status": "failed", "error_message": "no recordings"} if self.fail else {"status": "running", "progress_percent": 50}
            )
        if path == "/exports/yard_x_ab12.mp4":
            return Reply(200, data=b"mp4 bytes")
        if path == "/api/exports/delete":
            return Reply(200, {"success": True})
        return Reply(404, {})


def wait(job):
    for _ in range(100):
        if job.state()["state"] in ("ready", "failed"):
            return job.state()
        time.sleep(0.05)
    raise AssertionError(job.state())


def test_made_by_frigate_then_brought_over_and_taken_off_frigate(tmp_path, monkeypatch):
    monkeypatch.setattr(timelapse, "POLL", 0)
    f = FakeFrigate()
    st = wait(timelapse.Job(f, "yard", at(0, day=17), at(0), 1200, home=tmp_path).begin())
    assert st["state"] == "ready" and open(st["file"], "rb").read() == b"mp4 bytes"
    method, path, body = f.calls[0]
    assert path == f"/api/export/custom/yard/start/{int(at(0, day=17))}/end/{int(at(0))}"
    assert body["ffmpeg_output_args"].startswith("-vf setpts=0.000833*PTS") and body["name"] == timelapse.NAME
    for _ in range(50):  # (taken off Frigate's Exports page once the file is here)
        if f.calls[-1][1] == "/api/exports/delete":
            break
        time.sleep(0.05)
    assert f.calls[-1] == ("POST", "/api/exports/delete", {"ids": ["yard_ab12"]})
    again = FakeFrigate()  # the same one again: already on the TV
    assert wait(timelapse.Job(again, "yard", at(0, day=17), at(0), 1200, home=tmp_path).begin())["file"] == st["file"]
    assert again.calls == []


def test_frigate_failing_says_why(tmp_path, monkeypatch):
    monkeypatch.setattr(timelapse, "POLL", 0)
    st = wait(timelapse.Job(FakeFrigate(fail=True), "yard", at(8), at(9), 60, home=tmp_path).begin())
    assert st["state"] == "failed" and "no recordings" in st["error"]


def test_only_the_last_few_stay(tmp_path):
    for i in range(4):
        p = tmp_path / f"cam-{i}.mp4"
        p.write_bytes(b"x")
        t = time.time() - 100 + i
        os.utime(p, (t, t))
    timelapse.prune(tmp_path)
    assert sorted(p.name for p in tmp_path.glob("*.mp4")) == ["cam-2.mp4", "cam-3.mp4"]
