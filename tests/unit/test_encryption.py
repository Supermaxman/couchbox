import json

from couchbox import encryption, paths


def setup_runner(runner, *, luks=True, image_key_ok=True, reencrypt=False, tang=False):
    runner.answers[("findmnt", "-no", "SOURCE", "/")] = (0, "/dev/mapper/root\n" if luks else "/dev/nvme0n1p2\n")
    runner.answers[("cryptsetup", "status")] = (0, "  type:    LUKS2\n  device:  /dev/nvme0n1p2\n")
    meta = {
        "keyslots": {"0": {}, "1": {}},
        "tokens": {"0": {"type": "clevis", "keyslots": ["1"]}} if tang else {},
        "config": {"requirements": {"mandatory": ["online-reencrypt-v2"]}} if reencrypt else {},
    }
    runner.answers[("cryptsetup", "luksDump")] = (0, json.dumps(meta))
    runner.answers[("cryptsetup", "open", "--test-passphrase")] = (0 if image_key_ok else 2, "")
    runner.answers[("systemctl", "is-active", "couchbox-reencrypt.service")] = (3, "inactive\n")
    runner.answers[("clevis", "luks", "list")] = (
        0,
        '1: sss \'{"t":1,"pins":{"tang":[{"url":"http://tang.lan:7500"}]}}\'\n' if tang else "",
    )


def test_plain_root(runner):
    setup_runner(runner, luks=False)
    st = encryption.status()
    assert st["state"] == "plain" and st["device"] == "/dev/nvme0n1p2"


def test_unprotected_image(box, runner):
    setup_runner(runner)
    encryption.image_key().parent.mkdir(parents=True)
    encryption.image_key().write_text("k")
    assert encryption.status()["state"] == "unprotected"


def test_encrypting_shows_progress(box, runner):
    setup_runner(runner, reencrypt=True)
    encryption.progress_file().parent.mkdir(parents=True, exist_ok=True)
    encryption.progress_file().write_text(json.dumps({"percent": 42.5, "eta_s": 600}))
    st = encryption.status()
    assert st["state"] == "encrypting" and st["percent"] == 42.5


def test_encrypted_with_tang(box, runner):
    setup_runner(runner, image_key_ok=False, tang=True)
    st = encryption.status()
    assert st["state"] == "encrypted" and st["network_unlock"] == 1 and st["tang"] == ["http://tang.lan:7500"]


def test_start_refuses_short_passphrase_and_keeps_it_off_disk(box, runner):
    setup_runner(runner)
    encryption.image_key().parent.mkdir(parents=True)
    encryption.image_key().write_text("k")
    import pytest

    with pytest.raises(encryption.CommandError, match="8 characters"):
        encryption.start_encrypt("short", [], False)
    encryption.start_encrypt("long enough phrase", ["http://tang.lan:7500"], True)
    pending = encryption.pending_file()
    assert str(pending).startswith(str(paths.run()))  # /run: tmpfs, never the disk
    assert oct(pending.stat().st_mode)[-3:] == "600"
    assert runner.ran("systemctl", "start", "--no-block", "couchbox-reencrypt.service")


def test_crypttab(box, runner):
    runner.answers[("cryptsetup", "luksUUID")] = (0, "1234-abcd\n")
    ct = box / "etc/crypttab"
    ct.parent.mkdir(parents=True, exist_ok=True)
    ct.write_text("root\tUUID=old\t/etc/couchbox/luks/image.key\tluks,discard\nswap\t/dev/x\tnone\tswap\n")
    encryption.set_crypttab("/dev/nvme0n1p2", keyfile=None)
    assert ct.read_text() == "swap\t/dev/x\tnone\tswap\nroot\tUUID=1234-abcd\tnone\tluks,discard\n"
