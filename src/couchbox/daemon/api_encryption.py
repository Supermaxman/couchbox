"""Disk encryption for Settings → Security."""

from typing import Any

from couchbox import encryption
from couchbox.system import CommandError

from . import events
from .api import UserError, method


def _ue(fn):
    def w(*a, **kw):
        try:
            return fn(*a, **kw)
        except CommandError as e:
            raise UserError(str(e)) from None

    w.__name__ = fn.__name__
    return w


@method("encryption.status", write=False)
def enc_status() -> dict[str, Any]:
    return encryption.status()


@method("encryption.check_tang")
@_ue
def enc_check_tang(url: str) -> dict[str, Any]:
    return encryption.check_tang(url)


@method("encryption.encrypt")
@_ue
def enc_encrypt(passphrase: str, tang: list[str] | None = None, wifi: bool = False) -> dict[str, Any]:
    st = encryption.start_encrypt(passphrase, tang or [], bool(wifi))
    events.publish("encryption.changed", st)
    return st


@method("encryption.finish")
@_ue
def enc_finish(passphrase: str) -> dict[str, Any]:
    """Re-encryption finished while the passphrase was lost (a reboot mid-way): set it now."""
    import json
    import os

    p = encryption.pending_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"passphrase": passphrase, "tang": [], "wifi": False}, f)
    return encryption.finish()


@method("encryption.change_passphrase")
@_ue
def enc_change(old: str, new: str) -> dict[str, Any]:
    encryption.change_passphrase(old, new)
    return encryption.status()


@method("encryption.set_tang")
@_ue
def enc_set_tang(passphrase: str, urls: list[str]) -> dict[str, Any]:
    dev = encryption.root_device()
    encryption.unbind_tang(dev)
    if urls:
        encryption.bind_tang(dev, urls, passphrase)
    encryption.rebuild_initrd(network=bool(urls))
    return encryption.status()


@method("encryption.set_wifi")
@_ue
def enc_set_wifi(enabled: bool) -> dict[str, Any]:
    encryption.write_wifi_conf(bool(enabled))
    st = encryption.status()
    encryption.rebuild_initrd(network=bool(st.get("tang")))
    return encryption.status()


def refresh_initrd_wifi() -> None:
    """Wi-Fi changed: keep the initrd's copy current when Wi-Fi unlock is on."""
    st = encryption.status()
    if st.get("state") == "encrypted" and st.get("wifi_at_boot"):
        encryption.write_wifi_conf(True)
        encryption.rebuild_initrd(network=bool(st.get("tang")))
