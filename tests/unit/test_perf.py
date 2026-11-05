"""Settings → System's "Right now": loads between two samples, the fan, and apps named by their unit."""

import pytest

from couchbox import paths, perf


def write(root, rel, text):
    p = root / rel.lstrip("/")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


@pytest.fixture
def box(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "root", lambda: tmp_path)
    perf._last.clear()
    write(tmp_path, "/sys/class/thermal/cooling_device2/type", "pwm-fan\n")
    write(tmp_path, "/sys/class/thermal/cooling_device2/cur_state", "2\n")
    write(tmp_path, "/sys/class/thermal/cooling_device2/max_state", "4\n")
    write(tmp_path, "/sys/devices/platform/cooling_fan/hwmon/hwmon3/fan1_input", "6577\n")
    write(tmp_path, "/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq", "2400000\n")
    return tmp_path


def state(root, cpu_busy, cpu_idle, gpu_ns, twitch_jiffies):
    write(root, "/proc/stat", f"cpu  {cpu_busy} 0 0 {cpu_idle} 0 0 0 0 0 0\n")
    write(root, "/sys/class/drm/card0/device/gpu_stats", f"queue timestamp jobs runtime\nrender 1 2 {gpu_ns}\n")
    write(root, "/proc/123/stat", f"123 (python3) S 1 1 1 0 -1 0 0 0 0 0 {twitch_jiffies} 0 0 0\n")
    write(root, "/proc/123/cgroup", "0::/user.slice/user-1001.slice/user@1001.service/app.slice/app-couchbox\\x2dtwitch@ab12.service\n")


def test_two_samples_give_loads_and_the_busiest_app(box, monkeypatch):
    t = iter([100.0, 102.0])
    monkeypatch.setattr(perf.time, "monotonic", lambda: next(t))
    monkeypatch.setattr(perf.os, "cpu_count", lambda: 4)
    state(box, 1000, 9000, 0, 0)
    first = perf.sample()
    assert "cpu_pct" not in first and first["fan"] == {"step": 2, "steps": 4, "rpm": 6577} and first["cpu_mhz"] == 2400
    state(box, 1300, 9700, int(1.16e9), 2 * perf.HZ)  # 2 s: 300 of 1000 jiffies busy; GPU 1.16 s; Twitch 2 s of CPU
    s = perf.sample()
    assert s["cpu_pct"] == 30 and s["gpu_pct"] == 58
    assert s["apps"] == [{"name": "Twitch", "pct": 25}]  # 1 core of 4


def test_unit_names():
    assert perf.unit_name("app-flatpak-rocks.shy.VacuumTube-2179559093.scope") == "YouTube"
    assert perf.unit_name("app-couchbox\\x2djellyfin@0f51.service") == "Jellyfin"
    assert perf.unit_name("plasma-kwin_wayland.service") == "Screen (KWin)"
    assert perf.unit_name("couchboxd.service") == "Couchboxd"
    assert perf.unit_name("session-3.scope") == "Logins"
