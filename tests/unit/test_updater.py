import datetime as dt
import functools
import hashlib
import http.server
import json
import subprocess
import threading

import pytest

from couchbox import settings, updater
from couchbox.updater import Version


@pytest.mark.parametrize(
    "a,b",
    [
        ("0.1.0", "0.1.1"),
        ("0.1.9", "0.2.0"),
        ("1.0.0-beta.1", "1.0.0"),
        ("1.0.0-beta.2", "1.0.0-beta.10"),
        ("1.0.0-alpha", "1.0.0-beta"),
        ("1.0.0-beta.9", "1.0.0-beta.rc"),
        ("v1.2.3", "1.2.4"),
    ],
)
def test_version_order(a, b):
    assert Version.parse(a) < Version.parse(b)
    assert not Version.parse(b) < Version.parse(a)


def test_version_parse():
    assert str(Version.parse("v1.2.3-beta.4")) == "1.2.3-beta.4"
    assert Version.parse("1.2.3-beta.4").prerelease
    with pytest.raises(ValueError):
        Version.parse("1.2")


@pytest.mark.parametrize(
    "now,window,inside",
    [
        ("03:00", "02:00-06:00", True),
        ("07:00", "02:00-06:00", False),
        ("23:30", "22:00-04:00", True),
        ("12:00", "22:00-04:00", False),
    ],
)
def test_window(now, window, inside):
    assert updater._in_window(window, dt.datetime.fromisoformat(f"2026-11-01T{now}")) is inside


def test_idle_rules():
    s = settings.load()
    night = dt.datetime.fromisoformat("2026-11-01T03:00")
    noon = dt.datetime.fromisoformat("2026-11-01T12:00")
    kw = dict(playing=False, tv_on=False, input_age=10)
    assert updater.idle_reason(s, {}, night, **kw) == ""
    assert updater.idle_reason(s, {}, night, **{**kw, "playing": True}) == "something is playing"
    assert updater.idle_reason(s, {}, night, **{**kw, "tv_on": True}) == "the TV is in use"
    assert updater.idle_reason(s, {}, night, **{**kw, "tv_on": True, "input_age": 3600}) == ""
    assert updater.idle_reason(s, {}, noon, **kw).startswith("waiting for")
    # waited 3 days for a quiet night: any idle moment will do
    old = noon.timestamp() - 4 * 86400
    assert updater.idle_reason(s, {"pending_since": old}, noon, **kw) == ""


# ------------------------------------------------------------------ a fake release server
@pytest.fixture
def releases(tmp_path, monkeypatch):
    keydir = tmp_path / "keys"
    keydir.mkdir()
    key = keydir / "release"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    pub = (keydir / "release.pub").read_text().split()
    signers = keydir / "allowed_signers"
    signers.write_text(f'{updater.SIGNER} namespaces="{updater.NAMESPACE}" {pub[0]} {pub[1]}\n')
    monkeypatch.setenv("COUCHBOX_ALLOWED_SIGNERS", str(signers))
    www = tmp_path / "www"
    (www / "download").mkdir(parents=True)
    index = []

    def publish(version, prerelease=False, debs=None, sign_with=key, tamper=False, **extra):
        d = www / "download" / f"v{version}"
        d.mkdir()
        assets = {}
        for name, body in (debs or {f"couchbox_{version}_all.deb": b"deb " + version.encode()}).items():
            (d / name).write_bytes(body)
            assets[name] = {"sha256": hashlib.sha256(body).hexdigest(), "size": len(body)}
        m = {
            "schema": 1,
            "version": version,
            "channel": "beta" if prerelease else "stable",
            "assets": assets,
            "base": {"os": "ubuntu", "version": ""},
            "notes_md": f"notes {version}",
            **extra,
        }
        (d / "release.json").write_text(json.dumps(m))
        subprocess.run(
            ["ssh-keygen", "-q", "-Y", "sign", "-f", str(sign_with), "-n", updater.NAMESPACE, str(d / "release.json")], check=True
        )
        if tamper:
            (d / list(assets)[0]).write_bytes(b"evil")
        index.insert(0, {"tag": f"v{version}", "prerelease": prerelease})
        (www / "index.json").write_text(json.dumps(index))

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(www))
    handler.log_message = lambda *a: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("COUCHBOX_RELEASES_URL", f"http://127.0.0.1:{srv.server_port}")
    monkeypatch.setattr(updater, "__version__", "0.1.0")
    publish.keydir = keydir
    yield publish
    srv.shutdown()


def test_check_picks_newest_stable(releases):
    releases("0.1.0")
    releases("0.2.0")
    releases("0.3.0-beta.1", prerelease=True)
    m = updater.check()
    assert m["version"] == "0.2.0"
    settings.update({"updates.channel": "beta"})
    assert updater.check()["version"] == "0.3.0-beta.1"


def test_release_still_publishing_is_skipped(releases, tmp_path):
    releases("0.2.0")
    releases("0.3.0")
    for f in (tmp_path / "www/download/v0.3.0").iterdir():  # tagged, files not attached yet
        f.unlink()
    assert updater.check()["version"] == "0.2.0"


def test_nothing_newer(releases):
    releases("0.1.0")
    assert updater.check() is None


def test_bad_signature_is_refused(releases, tmp_path):
    other = tmp_path / "other"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(other)], check=True)
    releases("0.2.0", sign_with=other)
    with pytest.raises(updater.UpdateError, match="signature"):
        updater.check()


def test_tampered_asset_is_refused(releases):
    releases("0.2.0", tamper=True)
    m = updater.check()
    with pytest.raises(updater.UpdateError, match="doesn't match|expected"):
        updater.download(m)


def test_bad_versions_are_skipped(releases):
    releases("0.2.0")
    releases("0.3.0")
    assert updater.check({"bad": ["0.3.0"]})["version"] == "0.2.0"


def test_min_from_needs_a_stepping_stone(releases):
    releases("0.2.0")
    releases("0.5.0", min_from="0.2.0")
    assert updater.check()["version"] == "0.2.0"


def test_manual_mode_downloads_and_waits(releases, monkeypatch):
    releases("0.2.0")
    settings.update({"updates.mode": "manual"})
    called = []
    monkeypatch.setattr(updater, "install", lambda *a, **k: called.append(1))
    st = updater.run()
    assert st["available"] == "0.2.0" and not called
    assert (updater.updates_dir() / "0.2.0/couchbox_0.2.0_all.deb").exists()


def test_automatic_installs_when_idle(releases, monkeypatch):
    releases("0.2.0")
    monkeypatch.setattr(updater, "idle_reason", lambda s, st: "")
    applied = []
    monkeypatch.setattr(updater, "_apt_install", lambda debs: applied.append([d.name for d in debs]))
    monkeypatch.setattr(updater, "health_check", lambda: [])
    monkeypatch.setattr(updater, "ensure_rollback_set", lambda: True)
    st = updater.run()
    assert applied == [["couchbox_0.2.0_all.deb"]]
    assert st["just_updated"]["version"] == "0.2.0" and st["history"][-1]["event"] == "installed"


def test_automatic_waits_while_watching(releases, monkeypatch):
    releases("0.2.0")
    monkeypatch.setattr(updater, "idle_reason", lambda s, st: "something is playing")
    monkeypatch.setattr(updater, "install", lambda *a, **k: pytest.fail("installed while watching"))
    assert updater.run()["waiting"] == "something is playing"


def test_failed_health_check_rolls_back(releases, monkeypatch):
    releases("0.1.0")
    releases("0.2.0")
    # the running version's debs are kept for rollback
    updater.download({**updater.verify_manifest(*_fetch_manifest(releases, "0.1.0")), "_url": updater.base_url("") + "/download/v0.1.0"})
    monkeypatch.setattr(updater, "idle_reason", lambda s, st: "")
    applied = []
    monkeypatch.setattr(updater, "_apt_install", lambda debs: applied.append([d.name for d in debs]))
    monkeypatch.setattr(updater, "health_check", lambda: ["session: the TV interface isn't running"])
    with pytest.raises(updater.UpdateError, match="rolled back"):
        updater.run()
    assert applied == [["couchbox_0.2.0_all.deb"], ["couchbox_0.1.0_all.deb"]]
    st = updater.load_state()
    assert "0.2.0" in st["bad"] and st["history"][-1]["event"] == "rolled_back"
    # and it isn't offered again
    assert updater.check() is None


def _fetch_manifest(releases, version):
    base = updater.base_url("")
    return updater._get(f"{base}/download/v{version}/release.json"), updater._get(f"{base}/download/v{version}/release.json.sig")
