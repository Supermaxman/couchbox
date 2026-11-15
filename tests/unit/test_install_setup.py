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
    api_setup._creds.clear()
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
    r = setup_api.setup_phone()  # not yet: Wi-Fi may still be coming up; the card says when
    assert r["mode"] == "waiting" and 25 <= r["eta"] <= 25 + setup_api.SCAN_SECONDS
    monkeypatch.setattr(setup_api, "_first_offline", 1.0)
    r = setup_api.setup_phone()
    assert r["mode"] == "hotspot" and r["ssid"].startswith("Couchbox-")
    assert r["wifi"] == f"WIFI:T:WPA;S:{r['ssid']};P:{r['password']};;"
    assert r["url"].startswith("http://10.42.0.1:8791/#t=")
    assert runner.ran("nmcli", "device", "wifi", "hotspot")
    # Wi-Fi power save off: with it on, an iPhone didn't see or join the setup Wi-Fi
    assert runner.ran("iw", "dev", "wlan0", "set", "power_save", "off")
    assert any(
        "802-11-wireless.powersave" in c and c[c.index("802-11-wireless.powersave") + 1] == "2"
        for c in runner.ran("nmcli", "connection", "modify")
    )
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


def test_saved_wifi_gets_longer_before_the_hotspot(setup_api, runner, monkeypatch):
    runner.answers = {
        ("ip", "-4", "-o", "route", "get"): (2, ""),
        ("nmcli", "-t", "-f", "DEVICE,TYPE", "device"): (0, "wlan0:wifi\n"),
        ("nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"): (0, "couchbox-Home:802-11-wireless\nlo:loopback\n"),
    }
    monkeypatch.setattr(setup_api, "_first_offline", setup_api.time.time() - 60)
    r = setup_api.setup_phone()  # Imager's Wi-Fi may still be joining
    assert r["mode"] == "waiting" and 60 <= r["eta"] <= 60 + setup_api.SCAN_SECONDS
    monkeypatch.setattr(setup_api, "_first_offline", setup_api.time.time() - 130)
    first = setup_api.setup_phone()
    assert first["mode"] == "hotspot"
    # a rescan takes it down and back up with the same name and password
    from couchbox.daemon import api

    api.wifi_scan(rescan=True, bounce=True)
    assert setup_api.setup_phone()["wifi"] == first["wifi"]
    assert len(runner.ran("nmcli", "device", "wifi", "hotspot")) == 2


def test_no_wifi_no_phone_card(setup_api, runner):
    runner.answers = {("ip", "-4", "-o", "route", "get"): (2, ""), ("nmcli", "-t", "-f", "DEVICE,TYPE", "device"): (0, "eth0:ethernet\n")}
    assert setup_api.setup_phone()["mode"] == "none"


# ------------------------------------------------------------------ install progress
def test_install_reports_each_stage(runner, tmp_path, monkeypatch):
    """Preparing, formatting (mkfs's own counters), copying (GB copied out of the total), making
    it bootable, and the whole install's percent across them: the screen always has something
    moving (it sat at 0% for minutes before)."""
    src = tmp_path / "src"
    (src / "etc").mkdir(parents=True)
    (src / "etc/fstab").write_text("LABEL=writable / ext4 defaults 0 1\n")
    monkeypatch.setattr(install_disk, "MOUNT", tmp_path / "mnt")
    monkeypatch.setattr(install_disk, "_used", lambda p: 4 * 10**9 if p == str(src) else 10**8)
    ran = []

    def mkfs(cmd, on_line, timeout):
        ran.append(cmd)
        for line in (
            "mke2fs 1.47.4",
            "Discarding device blocks:       0/62514774",
            "Discarding device blocks: 31257387/62514774",
            "Writing inode tables: 100/1908",
            "Writing inode tables: done                            ",
        ):
            on_line(line)

    monkeypatch.setattr(install_disk, "_run_progress", mkfs)
    monkeypatch.setattr(install_disk.time, "monotonic", iter(range(0, 10**6, 5)).__next__)
    runner.answers = {("lsblk", "-n", "-b", "-d", "-o", "SIZE"): (0, str(256 * 10**9))}
    seen = []
    install_disk.copy("/dev/nvme0n1", lambda st: seen.append(dict(st)), source=str(src))
    stages = [s["stage"] for s in seen]
    assert stages == sorted(stages, key=["prepare", "format", "copy", "finish"].index)
    assert stages[0] == "prepare" and stages[-1] == "finish"
    assert ran and ran[0][0] == "mkfs.ext4" and "-q" not in ran[0]
    fmt = [s["fraction"] for s in seen if s["stage"] == "format"]
    assert fmt[0] == 0 and 0.15 < fmt[2] < 0.25 and fmt[-1] == pytest.approx(0.9)
    copy = [s for s in seen if s["stage"] == "copy"]
    assert copy[0]["total"] == 4 * 10**9 and copy[0]["copied"] == 0 and copy[-1]["copied"] == 4 * 10**9
    percents = [s["percent"] for s in seen]
    assert percents == sorted(percents) and percents[-1] == 97


def test_mkfs_lines_to_fraction():
    f = install_disk.mkfs_fraction
    assert f("Discarding device blocks:       0/15728640") == 0
    assert f("Discarding device blocks: done                            ") == pytest.approx(0.4)
    assert f("Writing inode tables: 240/480") == pytest.approx(0.7)
    assert f("Creating journal (65536 blocks): done") == pytest.approx(0.97)
    assert f("Writing superblocks and filesystem accounting information: done") == pytest.approx(1.0)
    assert f("Creating filesystem with 15728640 4k blocks") is None
    assert install_disk.overall("copy", 0.5) == 54 and install_disk.overall("format", 0) == 2


def test_progress_follows_a_terminal_line(tmp_path):
    """mkfs rewrites its counter with backspaces: the line is what a terminal would show."""
    script = tmp_path / "fake-mkfs"
    script.write_text(
        "#!/bin/sh\nprintf 'mke2fs\\nWriting inode tables:   0/480\\b\\b\\b\\b\\b\\b\\b240/480\\b\\b\\b\\b\\b\\b\\bdone   \\n'\n"
    )
    script.chmod(0o755)
    lines = []
    install_disk._run_progress([str(script)], lines.append, timeout=10)
    assert any(x.endswith("240/480") for x in lines)
    assert install_disk.mkfs_fraction("Writing inode tables:   240/480") == pytest.approx(0.7)
    bad = tmp_path / "bad"
    bad.write_text("#!/bin/sh\necho 'mkfs: no such device'; exit 1\n")
    bad.chmod(0o755)
    with pytest.raises(install_disk.CommandError, match="no such device"):
        install_disk._run_progress([str(bad)], lines.append, timeout=10)


# ------------------------------------------------------------------ downloads wait on a stick
@pytest.mark.parametrize(
    "root, setup_done, held",
    [("usb", False, True), ("mmc", False, True), ("usb", True, False), ("nvme", False, False)],
)
def test_downloads_wait_while_setup_runs_from_a_stick(runner, monkeypatch, root, setup_done, held):
    from couchbox import paths

    monkeypatch.setattr(install_disk, "root_disk", lambda: {"path": "/dev/x", "tran": root})
    f = paths.state() / "state/setup.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"done": setup_done, "step": 3}))
    assert bool(install_disk.downloads_held()) is held


def test_downloads_allowed_command(monkeypatch, capsys):
    from couchbox import cli

    monkeypatch.setattr(install_disk, "downloads_held", lambda: "setup is running from the USB stick")
    with pytest.raises(SystemExit) as e:
        cli.main(["downloads-allowed"])
    assert e.value.code == 1 and "USB stick" in capsys.readouterr().out
    monkeypatch.setattr(install_disk, "downloads_held", lambda: "")
    cli.main(["downloads-allowed"])  # exit 0: the unit runs


def test_finishing_setup_starts_the_apps(runner, monkeypatch):
    from couchbox.daemon import api, api_extra

    api.setup_save(step=10, completed=[], done=True)
    assert runner.ran("systemctl", "start", "--no-block", "couchbox-apps.service")
    monkeypatch.setattr(install_disk, "downloads_held", lambda: "setup is running from the USB stick")
    assert api_extra.apps_install_status()["state"] == "held"


def test_units_ask_before_downloading():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    for unit in ("system/systemd/couchbox-apps.service", "system/systemd/couchbox-flatpak-update.service", "system/apt/couchbox-hold.conf"):
        assert "ExecCondition=/usr/bin/couchbox downloads-allowed" in (root / unit).read_text()
    mk = (root / "Makefile").read_text()
    assert "apt-daily.service.d/couchbox-hold.conf" in mk and "apt-daily-upgrade.service.d/couchbox-hold.conf" in mk
