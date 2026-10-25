"""Updates for Settings: status, check now, install now, roll back. The work itself runs
in couchbox-updater (a separate unit), so a daemon restart mid-install doesn't stop it."""

from typing import Any

from couchbox import updater
from couchbox.system import sh

from . import events
from .api import UserError, method


@method("updates.status", write=False)
def updates_status() -> dict[str, Any]:
    st = updater.status()
    active = sh(["systemctl", "is-active", "couchbox-updater.service"], check=False).stdout.strip()
    st["running"] = active in ("active", "activating")
    return st


@method("updates.check")
def updates_check() -> dict[str, Any]:
    try:
        m = updater.check()
    except (OSError, ValueError, updater.UpdateError) as e:
        raise UserError(f"Couldn't check for updates: {e}") from None
    st = updater.load_state()
    if m:
        st["available"] = m["version"]
        st["available_notes_md"] = m.get("notes_md", "")
        updater.save_state(st)
    events.publish("updates.changed", updater.status())
    return updates_status()


@method("updates.install")
def updates_install() -> dict[str, Any]:
    """Install the available update now (ignores the idle rules). Runs in the background."""
    sh(["systemctl", "start", "--no-block", "couchbox-updater-now.service"], check=False)
    return {"started": True}


@method("updates.rollback")
def updates_rollback() -> dict[str, Any]:
    sh(["systemd-run", "--unit=couchbox-rollback", "--collect", "/usr/lib/couchbox/bin/couchbox-updater", "rollback"], check=False)
    return {"started": True}


@method("updates.seen")
def updates_seen() -> dict[str, Any]:
    """The "what's new" note was shown."""
    st = updater.load_state()
    st.pop("just_updated", None)
    updater.save_state(st)
    return updates_status()
