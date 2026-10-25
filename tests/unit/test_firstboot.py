import importlib.machinery
import importlib.util
import json
import tomllib
from pathlib import Path

from couchbox import paths, secrets, settings

REPO = Path(__file__).resolve().parents[2]


def load():
    loader = importlib.machinery.SourceFileLoader("firstboot", str(REPO / "bin/couchbox-firstboot"))
    spec = importlib.util.spec_from_loader("firstboot", loader)
    m = importlib.util.module_from_spec(spec)
    loader.exec_module(m)
    return m


PRESEED = """
hostname = "livingroom"
timezone = "Europe/Berlin"
[wifi]
ssid = "Home Net"
password = "test-fake-wifi-pw"
country = "DE"
[location]
name = "Berlin"
[updates]
mode = "manual"
[media]
jellyfin_url = "http://192.168.1.20:8096"
[voice]
mode = "dictation"
stt_url = "http://192.168.1.20:8000/v1"
llm_api_key = "test-fake-llm-key"
[ssh]
github_user = "someone"
[tailscale]
auth_key = "test-fake-ts-key"
[skip]
wizard = true
"""


def test_apply_preseed(box):
    fb = load()
    pending = fb.apply_preseed(tomllib.loads(PRESEED))
    s = settings.load()
    assert s["network.hostname"] == "livingroom" and s["time.timezone"] == "Europe/Berlin"
    assert s["updates.mode"] == "manual" and s["media.jellyfin.url"] == "http://192.168.1.20:8096"
    assert s["voice.mode"] == "dictation" and s["voice.stt.url"] == "http://192.168.1.20:8000/v1"
    assert s["ssh.enabled"] and s["tailscale.enabled"] and s["network.wifi_country"] == "DE"
    assert secrets.get("voice.llm.api_key") == "test-fake-llm-key"
    assert secrets.get("tailscale.auth_key") == "test-fake-ts-key"
    kf = box / "etc/NetworkManager/system-connections/couchbox-Home_Net.nmconnection"
    assert "ssid=Home Net" in kf.read_text() and "psk=test-fake-wifi-pw" in kf.read_text()
    assert {j["job"] for j in pending} == {"geocode", "ssh_github", "tailscale_up"}
    assert json.loads((paths.state() / "state/setup.json").read_text())["done"] is True


def test_bad_values_dont_lose_the_rest(box):
    fb = load()
    fb.apply_preseed({"hostname": "Not Valid!", "timezone": "Asia/Tokyo"})
    assert settings.get("time.timezone") == "Asia/Tokyo" and settings.get("network.hostname") == "couchbox"


def test_scrub_erases_only_secrets():
    fb = load()
    out = fb.scrub(PRESEED)
    assert "test-fake" not in out
    assert 'ssid = "Home Net"' in out and 'hostname = "livingroom"' in out
    assert tomllib.loads(out)["wifi"]["password"] == ""


def test_main_runs_once(box, runner):
    fb = load()
    boot = box / "boot/firmware"
    boot.mkdir(parents=True)
    (boot / "couchbox.toml").write_text(PRESEED)
    assert fb.main() == 0
    assert (paths.state() / "state/firstboot.done").exists()
    assert "test-fake-wifi-pw" not in (boot / "couchbox.toml").read_text()
