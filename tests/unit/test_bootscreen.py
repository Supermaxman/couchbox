"""The boot screen: theme on, and a test boot with the splash when the theme changed."""

import shutil
import subprocess

from couchbox import bootscreen

CMDLINE = "console=serial0,115200 console=tty1 root=/dev/mapper/root rootwait rd.neednet=1\n"


def setup_box(box, runner):
    theme = box / bootscreen.THEME
    theme.mkdir(parents=True)
    (theme / "couchbox.plymouth").write_text("[Plymouth Theme]\nName=Couchbox\n")
    (theme / "couchbox.script").write_text("# v1\n")
    fw = box / "boot/firmware"
    (fw / "current").mkdir(parents=True)
    (fw / "current/cmdline.txt").write_text(CMDLINE)

    plain = runner.__class__.__call__

    def call(self, cmd, input, timeout):  # flash-kernel writes new/ from current/, like piboot's
        if cmd[0] == "flash-kernel":
            shutil.copytree(fw / "current", fw / "new", dirs_exist_ok=True)
            self.calls.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return plain(self, cmd, input, timeout)

    runner.__class__ = type("PibootRunner", (runner.__class__,), {"__call__": call})
    runner.answers[("linux-version", "list")] = (0, "7.3.0-1004-raspi\n7.3.0-1006-raspi\n")
    runner.answers[("linux-version", "sort")] = (0, "7.3.0-1004-raspi\n7.3.0-1006-raspi\n")
    return fw


def test_splash_args_are_added_once():
    out = bootscreen.with_splash("root=/dev/mapper/root quiet rd.neednet=1 video=HDMI-A-1:3840x2160@30\n")
    assert out == (
        "root=/dev/mapper/root quiet rd.neednet=1 splash loglevel=3 vt.global_cursor_default=0"
        " plymouth.ignore-serial-consoles rd.driver.export video=HDMI-A-1:1920x1080@60 video=HDMI-A-2:1920x1080@60\n"
    )
    assert bootscreen.with_splash(out) == out


def test_plymouth_waits_2_s_for_a_display():
    ubuntu = "# Administrator customizations go in this file\n#[Daemon]\n"
    assert bootscreen.with_device_timeout(ubuntu) == ubuntu + "[Daemon]\nDeviceTimeout=2\n"
    mine = "[Daemon]\nTheme=x\nDeviceTimeout = 8\n[Other]\nA=1\n"
    assert bootscreen.with_device_timeout(mine) == "[Daemon]\nTheme=x\nDeviceTimeout=2\n[Other]\nA=1\n"
    assert bootscreen.with_device_timeout(bootscreen.with_device_timeout(mine)) == bootscreen.with_device_timeout(mine)


def test_first_apply_makes_a_test_boot_with_the_splash(box, runner):
    fw = setup_box(box, runner)
    assert bootscreen.apply() == "test boot ready (7.3.0-1006-raspi)"
    assert runner.ran("dracut", "--force", "--kver", "7.3.0-1006-raspi")
    assert runner.ran("update-alternatives", "--quiet", "--set", "default.plymouth")
    new = (fw / "new/cmdline.txt").read_text()
    assert new.startswith(CMDLINE.strip() + " quiet splash")
    assert (fw / "current/cmdline.txt").read_text() == CMDLINE  # the known-good boot is untouched
    assert "DeviceTimeout=2" in (box / bootscreen.CONF).read_text()


def test_nothing_to_do_once_the_test_boot_is_current(box, runner):
    fw = setup_box(box, runner)
    bootscreen.apply()
    shutil.rmtree(fw / "current")
    (fw / "new").rename(fw / "current")  # piboot-try kept it
    runner.calls.clear()
    assert bootscreen.apply() == "up to date"
    assert not runner.ran("dracut")


def test_a_changed_theme_rebuilds(box, runner):
    fw = setup_box(box, runner)
    bootscreen.apply()
    shutil.rmtree(fw / "current")
    (fw / "new").rename(fw / "current")
    (box / bootscreen.THEME / "couchbox.script").write_text("# v2\n")
    runner.calls.clear()
    assert bootscreen.apply().startswith("test boot ready")
    assert runner.ran("dracut")


def test_no_theme_or_no_piboot_leaves_the_boot_alone(box, runner):
    assert bootscreen.apply() == "no theme"
    theme = box / bootscreen.THEME
    theme.mkdir(parents=True)
    (theme / "couchbox.plymouth").write_text("")
    assert bootscreen.apply() == "no piboot layout"
    assert not runner.ran("dracut")


INFO = """[General]
Name=Amazon Remote
Appearance=0x0180

[LongTermKey]
Key={key}
Authenticated=0

[ConnectionParameters]
MinInterval={interval}
"""


def test_a_new_remote_pairing_rebuilds_but_bluetoothd_s_own_notes_dont(box, runner):
    fw = setup_box(box, runner)
    info = box / bootscreen.BLUETOOTH / "AA:AA:AA:AA:AA:AA/BB:BB:BB:BB:BB:BB/info"
    info.parent.mkdir(parents=True)
    info.write_text(INFO.format(key="0011", interval=6))
    bootscreen.apply()
    shutil.rmtree(fw / "current")
    (fw / "new").rename(fw / "current")
    runner.calls.clear()
    info.write_text(INFO.format(key="0011", interval=9))  # bluetoothd rewrote something else
    assert bootscreen.apply() == "up to date"
    info.write_text(INFO.format(key="2233", interval=9))  # paired again
    assert bootscreen.apply().startswith("test boot ready")


def test_encrypted_means_crypttab_names_a_disk(box):
    assert not bootscreen.encrypted()
    tab = box / "etc/crypttab"
    tab.parent.mkdir(parents=True, exist_ok=True)
    tab.write_text("# <target name> <source device> <key file> <options>\n")
    assert not bootscreen.encrypted()
    tab.write_text("root UUID=8087 none luks,discard\n")
    assert bootscreen.encrypted()


def test_image_build_puts_the_splash_on_the_current_boot(box, runner):
    fw = setup_box(box, runner)
    assert bootscreen.apply(image=True) == "splash on the boot command line"
    assert (fw / "current/cmdline.txt").read_text().startswith(CMDLINE.strip() + " quiet splash")
    assert runner.ran("update-alternatives", "--quiet", "--set", "default.plymouth")
    assert not runner.ran("dracut") and not (fw / "new").exists()
    assert bootscreen.needs_rebuild()  # the box's first update brings the themed initrd as a test boot
