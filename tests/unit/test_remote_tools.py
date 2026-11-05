"""couchbox-remote's button list and couchbox-input's injected keys: a press from the shell goes
through the remote's key map like a real one (Back still reaches the voice assistant and the
Frigate pop-up first)."""

import importlib.machinery
import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def load(name):
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_"), str(REPO / "bin" / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    m = importlib.util.module_from_spec(spec)
    loader.exec_module(m)
    return m


def test_remote_parses_buttons_holds_and_waits():
    r = load("couchbox-remote")
    assert r.parse(["down", "OK@1.2", "wait:2", "KEY_F5"]) == [
        ("key", "KEY_DOWN", 0.0),
        ("key", "KEY_SELECT", 1.2),
        ("wait", 2.0),
        ("key", "KEY_F5", 0.0),
    ]
    with pytest.raises(SystemExit):
        r.parse(["nope"])


def test_injected_keys_use_the_remotes_map():
    inp = load("couchbox-input")
    sections = inp.load_sections(REPO / "data/input/default.toml")
    target, label = inp.control_target(sections, "KEY_BACK")
    assert target == ("voice", inp.e.KEY_ESC) and "fire-remote" in label
    target, _ = inp.control_target(sections, "KEY_SELECT")
    assert target == ("popup", inp.e.KEY_ENTER)
    target, label = inp.control_target(sections, "KEY_F5")  # not in the map: the key itself
    assert target == inp.e.KEY_F5 and label == "injected KEY_F5"
    assert inp.control_target(sections, "KEY_NOPE")[0] is None
