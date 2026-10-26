"""Every "run:" command in the shipped key maps is a Couchbox helper (bin/) or a system tool,
and couchbox-input puts its own folder on PATH so those bare names resolve."""

import pathlib
import shutil
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[2]


def commands(table):
    for value in table.values():
        if isinstance(value, dict):
            yield from commands(value)
        elif isinstance(value, str) and "run" in value:
            for part in value.split("+"):
                kind, _, cmd = part.partition(":")
                if kind in ("run", "run-repeat") and cmd:
                    yield cmd.split()[0]


def test_keymap_commands_exist():
    maps = sorted((ROOT / "data/input").glob("*.toml"))
    assert maps
    for m in maps:
        for name in commands(tomllib.loads(m.read_text())):
            assert (ROOT / "bin" / name).exists() or shutil.which(name), f"{m.name}: {name} not found"


def test_input_service_finds_couchbox_helpers():
    src = (ROOT / "bin/couchbox-input").read_text()
    assert 'os.environ["PATH"] = os.path.dirname(os.path.realpath(__file__))' in src
