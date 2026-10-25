"""Shared test fixtures: every test gets its own fake filesystem root (COUCHBOX_ROOT) and a
share directory built from the repo's data/, so nothing touches the real system."""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def box(tmp_path, monkeypatch):
    root = tmp_path / "root"
    share = root / "usr/share/couchbox"
    share.mkdir(parents=True)
    shutil.copy(REPO / "data/schema.json", share / "schema.json")
    shutil.copytree(REPO / "data/apps", share / "apps")
    monkeypatch.setenv("COUCHBOX_ROOT", str(root))
    monkeypatch.delenv("COUCHBOX_SHARE", raising=False)
    monkeypatch.setenv("COUCHBOX_SOCKET", str(tmp_path / "couchboxd.sock"))
    monkeypatch.setenv("COUCHBOX_TV_HOME", str(root / "home/tv"))
    from couchbox import settings

    settings._schema_cache.clear()
    return root


class FakeRunner:
    """Records commands; answers from a {prefix tuple: (rc, stdout)} table."""

    def __init__(self, answers=None):
        self.calls = []
        self.answers = answers or {}

    def __call__(self, cmd, input, timeout):
        cmd = list(cmd)
        self.calls.append(cmd)
        for prefix, (rc, out) in sorted(self.answers.items(), key=lambda kv: -len(kv[0])):
            if tuple(cmd[: len(prefix)]) == prefix:
                return subprocess.CompletedProcess(cmd, rc, out, "")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    def ran(self, *prefix):
        return [c for c in self.calls if tuple(c[: len(prefix)]) == prefix]


@pytest.fixture
def runner(monkeypatch):
    from couchbox import system

    r = FakeRunner()
    monkeypatch.setattr(system, "RUNNER", r)
    return r
