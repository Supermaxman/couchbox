"""couchbox-memory's open-files guard: an app past FD_RAISE open files gets its hard limit (an
mpv-style leak of one per frame then can't crash it within minutes), and a climbing one is logged."""

import importlib.machinery
import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TV = 1001


def load():
    loader = importlib.machinery.SourceFileLoader("couchbox_memory", str(REPO / "bin/couchbox-memory"))
    spec = importlib.util.spec_from_loader("couchbox_memory", loader)
    m = importlib.util.module_from_spec(spec)
    loader.exec_module(m)
    return m


@pytest.fixture
def mem(monkeypatch):
    m = load()
    box = {"files": {}, "limits": {}}

    def fd_table(pid):
        if pid not in box["files"]:
            raise FileNotFoundError(f"/proc/{pid}/status")
        return max(64, 1 << box["files"][pid].bit_length())

    monkeypatch.setattr(m, "fd_table", fd_table)
    monkeypatch.setattr(m, "open_files", lambda pid: box["files"][pid])

    def prlimit(pid, res, new=None):
        if new is None:
            return box["limits"][pid]
        box["limits"][pid] = new

    monkeypatch.setattr(m.resource, "prlimit", prlimit)
    return m, box


def test_a_leaking_app_gets_its_hard_limit_and_is_logged(mem):
    m, box = mem
    box["files"] = {10: 40, 11: 900, 12: 5000}
    box["limits"] = {10: (1024, 524288), 11: (1024, 524288), 12: (1024, 524288)}
    plist = [(10, 1, "qml6", TV), (11, 1, "python3", TV), (12, 1, "root-thing", 0)]
    logs, warned = [], {}
    out = m.guard_files(TV, plist, warned, logs.append)
    assert box["limits"] == {10: (1024, 524288), 11: (524288, 524288), 12: (1024, 524288)}
    assert list(out) == [11] and out[11] == ("python3", 900, 524288)
    assert len(logs) == 1 and "raised its limit from 1024 to 524288" in logs[0]


def test_one_still_climbing_is_logged_at_half_then_every_20_percent(mem):
    m, box = mem
    box["files"], box["limits"] = {11: 300000}, {11: (524288, 524288)}
    plist, logs, warned = [(11, 1, "jellyfin-deskto", TV)], [], {}
    m.guard_files(TV, plist, warned, logs.append)
    box["files"][11] = 330000  # +10%: not again yet
    m.guard_files(TV, plist, warned, logs.append)
    box["files"][11] = 370000
    m.guard_files(TV, plist, warned, logs.append)
    assert len(logs) == 2 and all("leaking?" in line for line in logs)
    m.guard_files(TV, [], warned, logs.append)  # it quit
    assert warned == {}


def test_gone_processes_are_skipped(mem):
    m, box = mem
    assert m.guard_files(TV, [(99, 1, "gone", TV)], {}, print) == {}
