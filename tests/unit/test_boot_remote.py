"""couchbox-boot-remote: the remote types the disk passphrase on the boot screen's keyboard and
answers the unlock's password request; other times its keys show or hide the log."""

import os
import stat
import subprocess
import time
from pathlib import Path

import pytest

HELPER = Path(__file__).resolve().parents[2] / "bin/couchbox-boot-remote"


def script(path: Path, body: str) -> None:
    path.write_text("#!/bin/bash\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def boot(tmp_path):
    run, ask, bin_ = tmp_path / "run", tmp_path / "ask", tmp_path / "bin"
    for d in (run, ask, bin_):
        d.mkdir()
    said = tmp_path / "said"
    script(bin_ / "plymouth", f'printf "%s\\n" "${{2#--status=}}" >> {said}\n')
    # the unlock takes the answer: its request goes away
    script(tmp_path / "reply", f"cat > {tmp_path}/answer; rm -f {ask}/ask.*\n")
    env = dict(
        os.environ,
        PATH=f"{bin_}:{os.environ['PATH']}",
        COUCHBOX_BOOT_RUN=str(run),
        COUCHBOX_BOOT_ASK=str(ask),
        COUCHBOX_BOOT_REPLY=str(tmp_path / "reply"),
    )
    procs = []

    class Boot:
        path = tmp_path

        def pace(self, net: bool) -> None:
            (run / "pace").write_text(f"101:42:170:{int(net)}\n")
            (run / "wifi").write_text(Path("/proc/uptime").read_text().split()[0] + "\n")

        def ask(self, n: int) -> None:
            (ask / f"ask.{n}").write_text(f"[Ask]\nSocket={ask}/sck.{n}\nId=cryptsetup:/dev/disk/by-uuid/x\n")

        def start(self) -> None:
            procs.append(subprocess.Popen([str(HELPER), "run"], env=env))
            until(lambda: (run / "remote-keys").exists())

        def keys(self, *names: str) -> None:
            with open(run / "remote-keys", "w") as f:
                for k in names:
                    f.write(k + "\n")
                    f.flush()
                    time.sleep(0.05)

        def said(self) -> list[str]:
            return said.read_text().split() if said.exists() else []

    yield Boot()
    for p in procs:
        p.kill()
        p.wait()


def until(cond, seconds: float = 5) -> None:
    end = time.time() + seconds
    while not cond():
        assert time.time() < end, "timed out"
        time.sleep(0.05)


def test_the_remote_types_the_passphrase_and_unlocks(boot):
    boot.pace(net=False)  # no network unlock: the passphrase is wanted at once
    boot.ask(1)
    boot.start()
    until(lambda: "cb:osk:1:0:0:0:0:0:0" in boot.said())
    # b, then o one row down, then Shift (the nearest key below 2), then A at the top left
    boot.keys("RIGHT", "SELECT", "DOWN", "SELECT", "DOWN", "DOWN", "SELECT", "UP", "UP", "UP", "SELECT")
    until(lambda: "cb:osk:1:0:0:1:3:0:0" in boot.said())
    boot.keys("BACK", "SELECT")  # Back deletes
    boot.keys("DOWN", "DOWN", "DOWN", *["RIGHT"] * 5, "SELECT")  # Unlock
    until(lambda: (boot.path / "answer").exists())
    assert (boot.path / "answer").read_text() == "boA"
    # asked again: it was wrong; the field empties and says so
    boot.ask(2)
    until(lambda: "cb:osk:1:0:0:0:0:1:0" in boot.said())  # and Shift is off again


def test_before_the_passphrase_is_wanted_keys_show_the_log(boot):
    boot.pace(net=True)  # network unlock under way: not stuck yet
    boot.ask(1)
    boot.start()
    until(lambda: "cb:osk:0:0:0:0:0:0:0" in boot.said())
    boot.keys("DOWN", "r:DOWN", "SELECT")  # a held key's repeats don't toggle it again
    until(lambda: boot.said().count("cb:log") == 2)
    time.sleep(0.6)
    assert boot.said().count("cb:log") == 2
    assert "cb:remote" in boot.said()


def test_a_network_that_gave_up_wants_the_passphrase(boot):
    boot.pace(net=True)
    (boot.path / "run/net-down").touch()
    boot.ask(1)
    boot.start()
    until(lambda: "cb:osk:1:0:0:0:0:0:0" in boot.said())
    boot.keys("MENU")  # Menu shows the log over the keyboard
    until(lambda: "cb:log" in boot.said())


def test_the_symbols_page_types_every_other_character(boot):
    boot.pace(net=False)
    boot.ask(1)
    boot.start()
    until(lambda: "cb:osk:1:0:0:0:0:0:0" in boot.said())
    boot.keys("DOWN", "DOWN", "DOWN", "RIGHT", "SELECT")  # #+= (next to Shift)
    until(lambda: "cb:osk:1:3:1:0:0:0:1" in boot.said())
    boot.keys("UP", "UP", "UP", *["RIGHT"] * 8, "SELECT")  # up to 3, then right to !
    boot.keys("DOWN", "SELECT")  # \ below it
    boot.keys("DOWN", *["LEFT"] * 10, "SELECT")  # " at the start of the last row
    boot.keys("DOWN", "RIGHT", "SELECT")  # abc: back to the letters
    boot.keys("UP", "UP", "UP", "LEFT", "LEFT", "SELECT")  # a
    boot.keys("DOWN", "DOWN", "DOWN", *["RIGHT"] * 5, "SELECT")  # Unlock
    until(lambda: (boot.path / "answer").exists())
    assert (boot.path / "answer").read_text() == '!\\"a'
