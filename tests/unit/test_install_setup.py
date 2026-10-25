"""Install to the SSD (target choice, boot config rewrite) and the setup hotspot."""

import json

import pytest

from couchbox import install_disk


def lsblk(*disks):
    return json.dumps({"blockdevices": list(disks)})


USB = {
    "name": "sda",
    "path": "/dev/sda",
    "type": "disk",
    "size": 32 * 10**9,
    "model": "Cruzer",
    "tran": "usb",
    "mountpoints": [None],
    "children": [{"name": "sda2", "path": "/dev/sda2", "type": "part", "mountpoints": ["/"]}],
}
NVME = {
    "name": "nvme0n1",
    "path": "/dev/nvme0n1",
    "type": "disk",
    "size": 256 * 10**9,
    "model": "PM9C1a",
    "tran": "nvme",
    "mountpoints": [None],
}
SMALL = {"name": "sdb", "path": "/dev/sdb", "type": "disk", "size": 8 * 10**9, "model": "Tiny", "tran": "usb", "mountpoints": [None]}
ZRAM = {"name": "zram0", "path": "/dev/zram0", "type": "disk", "size": 64 * 10**9, "mountpoints": ["[SWAP]"]}


@pytest.fixture
def from_usb(runner):
    runner.answers = {
        ("findmnt", "-n", "-o", "SOURCE", "/"): (0, "/dev/sda2\n"),
        ("lsblk", "-n", "-d", "-o", "PKNAME"): (0, "sda\n"),
        ("lsblk", "-J"): (0, lsblk(USB, NVME, SMALL, ZRAM)),
    }
    return runner


def test_targets_skip_the_boot_disk_small_and_virtual(from_usb):
    assert install_disk.root_disk()["tran"] == "usb"
    t = install_disk.targets()
    assert [x["path"] for x in t] == ["/dev/nvme0n1"]
    assert t[0]["label"] == "SSD PM9C1a (256 GB)"
    st = install_disk.status()
    assert st["booted_from"] == "usb" and st["can_install"]


def test_nothing_to_offer_when_running_from_the_ssd(runner):
    runner.answers = {
        ("findmnt", "-n", "-o", "SOURCE", "/"): (0, "/dev/nvme0n1p2\n"),
        ("lsblk", "-n", "-d", "-o", "PKNAME"): (0, "nvme0n1\n"),
        ("lsblk", "-J"): (0, lsblk(dict(NVME, children=[{"name": "nvme0n1p2", "mountpoints": ["/"]}]), dict(USB, children=[]))),
    }
    assert install_disk.status()["can_install"] is False


def test_encrypted_root_is_refused(runner):
    runner.answers = {("findmnt", "-n", "-o", "SOURCE", "/"): (0, "/dev/mapper/root\n")}
    with pytest.raises(install_disk.InstallError, match="before turning on encryption"):
        install_disk.start("/dev/nvme0n1")


def test_only_offered_drives(from_usb):
    with pytest.raises(install_disk.InstallError):
        install_disk.start("/dev/sda")  # the stick we run from
    with pytest.raises(install_disk.InstallError):
        install_disk.start("/dev/sdb")  # too small


def test_partition_names():
    assert install_disk.part("/dev/nvme0n1", 2) == "/dev/nvme0n1p2"
    assert install_disk.part("/dev/sda", 1) == "/dev/sda1"
    assert install_disk.part("/dev/loop3", 1) == "/dev/loop3p1"


def test_boot_config_points_at_the_new_drive():
    fstab = "LABEL=writable\t/\text4\tdefaults\t0\t1\nLABEL=system-boot /boot/firmware vfat defaults 0 1\n/swapfile none swap sw 0 0\n# LABEL=x / y\n"
    got = install_disk.fix_fstab(fstab, "abcd-02", "abcd-01")
    assert got.splitlines() == [
        "PARTUUID=abcd-02\t/\text4\tdefaults\t0\t1",
        "PARTUUID=abcd-01 /boot/firmware vfat defaults 0 1",
        "/swapfile none swap sw 0 0",
        "# LABEL=x / y",
    ]
    cl = "console=serial0,115200 multipath=off dwc_otg.lpm_enable=0 console=tty1 root=LABEL=writable rootfstype=ext4 rootwait fixrtc quiet splash\n"
    assert "root=PARTUUID=abcd-02 rootfstype" in install_disk.fix_cmdline(cl, "abcd-02")


# ------------------------------------------------------------------ setup hotspot
@pytest.fixture
def setup_api(runner):
    from couchbox.daemon import api_setup

    api_setup._hotspot.clear()
    api_setup._first_offline = 0
    yield api_setup
    api_setup._hotspot.clear()


def test_phone_card_online_uses_the_ip(setup_api, runner):
    runner.answers = {("ip", "-4", "-o", "route", "get"): (0, "1.1.1.1 via 192.168.1.1 dev wlan0 src 192.168.1.50 uid 0\n")}
    r = setup_api.setup_phone()
    assert r["mode"] == "lan" and r["url"].startswith("http://192.168.1.50:8791/#t=")


def test_offline_opens_a_hotspot_after_a_grace_period(setup_api, runner, monkeypatch):
    runner.answers = {
        ("ip", "-4", "-o", "route", "get"): (2, ""),
        ("nmcli", "-t", "-f", "DEVICE,TYPE", "device"): (0, "wlan0:wifi\neth0:ethernet\n"),
    }
    assert setup_api.setup_phone()["mode"] == "none"  # not yet: Wi-Fi may still be coming up
    monkeypatch.setattr(setup_api, "_first_offline", 1.0)
    r = setup_api.setup_phone()
    assert r["mode"] == "hotspot" and r["ssid"].startswith("Couchbox-")
    assert r["wifi"] == f"WIFI:T:WPA;S:{r['ssid']};P:{r['password']};;"
    assert r["url"].startswith("http://10.42.0.1:8791/#t=")
    assert runner.ran("nmcli", "device", "wifi", "hotspot")
    # Wi-Fi scans come from before the hotspot (the radio is busy)
    from couchbox.daemon import api

    runner.calls.clear()
    assert api.wifi_scan() == setup_api.cached_scan()
    assert not runner.ran("nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY,FREQ")
    # Ethernet comes up: the hotspot goes
    runner.answers[("ip", "-4", "-o", "route", "get")] = (0, "1.1.1.1 via 192.168.50.1 dev eth0 src 192.168.50.9\n")
    assert setup_api.setup_phone()["mode"] == "lan"
    assert not setup_api.hotspot_active() and runner.ran("nmcli", "connection", "delete", "id", "couchbox-setup")


def test_wifi_qr_escapes():
    from couchbox.daemon import api_setup

    assert api_setup.wifi_qr('a;b"c', "p:w\\") == 'WIFI:T:WPA;S:a\\;b\\"c;P:p\\:w\\\\;;'
