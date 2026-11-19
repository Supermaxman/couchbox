"""Timelapse, the Frigate app's page: a camera's recordings sped up, 2x to 1200x, over the last
hour, the last 3 hours, today so far or yesterday.

Frigate makes it (its export with our own speed: POST /api/export/custom/..., ffmpeg's setpts),
the TV brings the file over and plays it from the disk (seeking in it works there), and the
export is then taken off Frigate's Exports page. From KEYFRAMES_FROM up Frigate reads only the
recordings' keyframes (one every 2-3 s), so a whole day takes a few minutes; slower speeds read
every frame and are offered for the last hour only.

Files (the TV user's):
  ~/.cache/couchbox-frigate/timelapse/*.mp4   the last KEEP timelapses
"""

import datetime
import os
import threading
import time
from pathlib import Path
from typing import Any

SPEEDS = (2, 5, 10, 30, 60, 120, 300, 600, 1200)
KEYFRAMES_FROM = 60  # speeds from here read only the keyframes
FPS = 24  # the Pi decodes Frigate's 1440p at about 45 frames a second: room to spare
BITRATE = "-b:v 8M -maxrate 12M -bufsize 16M"
SHORTEST = 10  # seconds of video
LONGEST = 30 * 60
SLOWEST = 8 * 60  # the longest wait for Frigate to make one
READ_ALL = 15  # how much faster than real time Frigate reads every frame (measured on mserv)
READ_KEYS = 300  # ... only the keyframes (a whole day: 4 min)
BEST = 90  # the speed first offered makes about this much video
KEEP = 2
POLL = 1.0  # seconds between asking Frigate how far along it is
NAME = "Couchbox timelapse"


def cache_dir(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".cache/couchbox-frigate/timelapse"


# ------------------------------------------------------------------ what's offered
def length_label(seconds: float) -> str:
    """ "45 s", "1 min 12 s", "24 min"."""
    s = int(round(seconds))
    if s < 60:
        return f"{s} s"
    m, s = divmod(s, 60)
    return f"{m} min" + (f" {s} s" if s and m < 10 else "")


def making_seconds(span: float, speed: int) -> float:
    return span / (READ_KEYS if speed >= KEYFRAMES_FROM else READ_ALL)


def speeds(span: float) -> list[dict[str, Any]]:
    """The speeds offered for span seconds of recordings: each {speed, label, length, lengthLabel,
    ready}, the video neither too short nor too long, nor too slow for Frigate to make."""
    out = []
    for sp in SPEEDS:
        length = span / sp
        ready = making_seconds(span, sp)
        if SHORTEST <= length <= LONGEST and ready <= SLOWEST:
            out.append({"speed": sp, "label": f"{sp}x", "length": length, "lengthLabel": length_label(length), "ready": ready})
    return out


def clock(t: float) -> str:
    d = datetime.datetime.fromtimestamp(t)
    return f"{d.hour % 12 or 12}:{d.minute:02d} {'AM' if d.hour < 12 else 'PM'}"


def spans(now: float | None = None) -> list[dict[str, Any]]:
    """The times offered: [{key, label, hours, start, end, speeds, best}] (hours: "4:34 PM – 5:34
    PM", "Tuesday, all day"; best: the index of the speed first offered). Today so far only once
    there's more of it than the last 3 hours."""
    now = time.time() if now is None else now
    midnight = datetime.datetime.combine(datetime.date.fromtimestamp(now), datetime.time()).timestamp()
    yesterday = datetime.datetime.combine(datetime.date.fromtimestamp(now) - datetime.timedelta(days=1), datetime.time()).timestamp()
    rows = [("hour", "Last hour", now - 3600, now), ("3h", "Last 3 hours", now - 3 * 3600, now)]
    if now - midnight > 3 * 3600 + 600:
        rows.append(("today", "Today so far", midnight, now))
    rows.append(("yesterday", "Yesterday", yesterday, midnight))
    out = []
    for key, label, start, end in rows:
        sp = speeds(end - start)
        if sp:
            best = min(range(len(sp)), key=lambda i: abs(sp[i]["length"] - BEST))
            hours = f"{datetime.date.fromtimestamp(start):%A}, all day" if key == "yesterday" else f"{clock(start)} – {clock(end)}"
            out.append({"key": key, "label": label, "hours": hours, "start": int(start), "end": int(end), "speeds": sp, "best": best})
    return out


def ffmpeg_args(speed: int) -> tuple[str, str]:
    """Frigate's custom export's (input, output) ffmpeg arguments for a speed."""
    inp = "-an -skip_frame nokey" if speed >= KEYFRAMES_FROM else "-an"
    return inp, f"-vf setpts={1 / speed:.6f}*PTS -r {FPS} {BITRATE}"


# ------------------------------------------------------------------ making one
class Job:
    """One timelapse being made: Frigate's export, then the file brought over. state() answers
    {state: making | fetching | ready | failed, percent, file, error}."""

    def __init__(self, f: Any, camera: str, start: float, end: float, speed: int, home: Path | None = None):
        self.f, self.camera, self.start, self.end, self.speed = f, camera, int(start), int(end), int(speed)
        self.d = cache_dir(home)
        self.file = self.d / f"{camera}-{self.start}-{self.end}-{self.speed}x.mp4"
        self.st: dict[str, Any] = {"state": "making", "percent": 0.0, "file": "", "error": ""}
        self.export_id = ""
        self.cancelled = False
        self.lock = threading.Lock()

    def state(self) -> dict[str, Any]:
        with self.lock:
            return dict(self.st)

    def _set(self, **kw: Any) -> None:
        with self.lock:
            self.st.update(kw)

    def begin(self) -> "Job":
        threading.Thread(target=self._run, daemon=True).start()
        return self

    def cancel(self) -> None:
        self.cancelled = True

    def _run(self) -> None:
        try:
            if self.file.exists():
                self._set(state="ready", percent=100.0, file=str(self.file))
                return
            path = self._export()
            if self.cancelled:
                return
            self._fetch(path)
            if not self.cancelled:
                self._set(state="ready", percent=100.0, file=str(self.file))
        except Exception as err:  # noqa: BLE001 - said on the page
            self._set(state="failed", error=str(err) or err.__class__.__name__)
        finally:
            self._forget()

    def _export(self) -> str:
        """Ask Frigate for it and wait; the file's path on Frigate's web server."""
        inp, out = ffmpeg_args(self.speed)
        r = self.f.request(
            "POST",
            f"/api/export/custom/{self.camera}/start/{self.start}/end/{self.end}",
            json={"name": NAME, "source": "recordings", "ffmpeg_input_args": inp, "ffmpeg_output_args": out, "cpu_fallback": True},
        )
        body = r.json() if r.content else {}
        if not r.ok or not body.get("export_id"):
            if r.status_code == 503:
                raise RuntimeError("Frigate is busy with other exports. Try again in a few minutes.")
            if r.status_code == 400:
                raise RuntimeError("Frigate kept no recordings of that camera then.")
            raise RuntimeError(body.get("message") or f"Frigate said {r.status_code}.")
        self.export_id = body["export_id"]
        while not self.cancelled:
            ex = self.f.request("GET", f"/api/exports/{self.export_id}")
            row = ex.json() if ex.ok else {}
            if ex.ok and row.get("in_progress") is False:
                return "/exports/" + os.path.basename(row["video_path"])
            job = self.f.request("GET", f"/api/jobs/export/{self.export_id}")
            j = job.json() if job.ok else {}
            if j.get("status") in ("failed", "cancelled") or (not ex.ok and not job.ok):
                self.export_id = ""  # (Frigate removes a failed one itself)
                raise RuntimeError("Frigate couldn't make it" + (f": {j['error_message']}" if j.get("error_message") else "."))
            self._set(percent=round(float(j.get("progress_percent") or 0) * 0.9, 1))
            time.sleep(POLL)
        return ""

    def _fetch(self, path: str) -> None:
        self._set(state="fetching", percent=90.0)
        self.d.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_suffix(".part")
        with self.f.request("GET", path, stream=True, timeout=(8, 120)) as r:
            r.raise_for_status()
            total = int(r.headers.get("Content-Length") or 0)
            got = 0
            with open(tmp, "wb") as out:
                for chunk in r.iter_content(512 * 1024):
                    if self.cancelled:
                        break
                    out.write(chunk)
                    got += len(chunk)
                    if total:
                        self._set(percent=round(90 + 10 * got / total, 1))
        if self.cancelled:
            tmp.unlink(missing_ok=True)
            return
        os.replace(tmp, self.file)
        prune(self.d, keep=self.file)

    def _forget(self) -> None:
        """Take it off Frigate's Exports page (it's on the TV now, or wasn't wanted)."""
        if not self.export_id:
            return
        for _ in range(30):  # (a cancelled one finishes first: Frigate won't delete one in progress)
            try:
                r = self.f.request("POST", "/api/exports/delete", json={"ids": [self.export_id]})
                if r.ok or r.status_code in (403, 404):
                    return
            except Exception:  # noqa: BLE001 - left on Frigate's Exports page
                return
            time.sleep(POLL * 10)


def prune(d: Path, keep: Path | None = None) -> None:
    """Only the last KEEP timelapses stay on the TV."""
    files = sorted((p for p in d.glob("*.mp4")), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in files[KEEP:]:
        if p != keep:
            p.unlink(missing_ok=True)
    for p in d.glob("*.part"):
        if time.time() - p.stat().st_mtime > 3600:
            p.unlink(missing_ok=True)


class Demo:
    """--demo: made up, a minute's making in 20 s (screenshots)."""

    def __init__(self, *a: Any, **kw: Any):
        self.t0 = time.time()

    def begin(self) -> "Demo":
        return self

    def cancel(self) -> None:
        pass

    def state(self) -> dict[str, Any]:
        p = min(100.0, (time.time() - self.t0) * 5 + 34)
        if p >= 100:
            return {"state": "ready", "percent": 100.0, "file": "demo:recording", "error": ""}
        return {"state": "making" if p < 90 else "fetching", "percent": round(p, 1), "file": "", "error": ""}
