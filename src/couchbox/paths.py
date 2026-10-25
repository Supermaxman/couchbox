"""Where Couchbox keeps things. COUCHBOX_ROOT relocates every path (tests, image builds)."""

import os
from pathlib import Path


def root() -> Path:
    return Path(os.environ.get("COUCHBOX_ROOT", "/"))


def _p(path: str) -> Path:
    return root() / path.lstrip("/")


def share() -> Path:
    """Package data: schema, app manifests, QML. COUCHBOX_SHARE points at a source tree."""
    if os.environ.get("COUCHBOX_SHARE"):
        return Path(os.environ["COUCHBOX_SHARE"])
    return _p("/usr/share/couchbox")


def etc() -> Path:
    return _p("/etc/couchbox")


def state() -> Path:
    return _p("/var/lib/couchbox")


def run() -> Path:
    return _p("/run/couchbox")


def schema_file() -> Path:
    return share() / "schema.json"


def settings_file() -> Path:
    return etc() / "settings.json"


def env_file() -> Path:
    return etc() / "couchbox.env"


def secrets_dir() -> Path:
    return state() / "secrets"


def socket_path() -> Path:
    return Path(os.environ.get("COUCHBOX_SOCKET", str(run() / "couchboxd.sock")))


def boot_firmware() -> Path:
    return _p("/boot/firmware")
