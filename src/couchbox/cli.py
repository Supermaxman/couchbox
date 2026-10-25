"""couchbox: the command line.

  couchbox version
  couchbox config list | get KEY | set KEY VALUE | reset KEY | env | schema
  couchbox secret set NAME [VALUE|-] | clear NAME | status
  couchbox home rebuild [--restart] | row | move APP INDEX | hide APP | show APP
  couchbox doctor [--json] [--post-update] [--container]
  couchbox update status | check | install | rollback
  couchbox pair-remote [ADDRESS]
  couchbox wifi list | join SSID | forget SSID
  couchbox phone-url
  couchbox import-mtv [PATH]       settings from the mtv prototype (/etc/mtv)
  couchbox install-to-disk [DEVICE] copy a USB stick / SD card system to the SSD

Changes go through couchboxd when it's running (so they take effect), else straight to
the files (root, e.g. in an image build).
"""

import argparse
import getpass
import json
import os
import sys
import time
from typing import Any

from couchbox import __version__, ipc, settings


def _call(method: str, **params: Any) -> Any:
    try:
        return ipc.call(method, **params)
    except ipc.IpcError as e:
        if e.code in (-32001,) and os.geteuid() == 0:
            return None  # daemon not running: caller falls back to direct
        sys.exit(f"couchbox: {e}")


def _parse_value(key: str, raw: str) -> Any:
    t = settings.spec(key)["type"]
    if t in ("list", "object"):
        try:
            return json.loads(raw)
        except ValueError:
            if t == "list":
                return [x for x in raw.replace(",", " ").split() if x]
            raise
    return raw


def _print(obj: Any) -> None:
    if isinstance(obj, (dict, list)):
        print(json.dumps(obj, indent=2))
    elif obj is not None:
        print(obj)


def cmd_config(a) -> None:
    if a.action == "list":
        vals = settings.load()
        changed = settings.changed()
        for k, v in vals.items():
            print(f"{'*' if k in changed else ' '} {k} = {json.dumps(v)}")
    elif a.action == "get":
        _print(settings.get(a.key))
    elif a.action == "set":
        value = _parse_value(a.key, a.value)
        r = _call("settings.set", changes={a.key: value})
        if r is None:
            settings.update({a.key: value})
            from couchbox.daemon import apply

            apply.apply({a.key: settings.get(a.key)}, settings.load())
        else:
            for n in r.get("notes", []):
                print(n)
    elif a.action == "reset":
        if _call("settings.reset", key=a.key) is None:
            settings.reset(a.key)
    elif a.action == "env":
        for k, v in sorted(settings.env().items()):
            print(f"{k}={v}")
    elif a.action == "schema":
        _print(settings.schema())


def cmd_secret(a) -> None:
    if a.action == "status":
        r = _call("secrets.status")
        from couchbox import secrets

        _print(r if r is not None else secrets.status())
    elif a.action == "set":
        value = (
            a.value
            if a.value not in (None, "-")
            else (sys.stdin.readline().strip() if not sys.stdin.isatty() else getpass.getpass(f"{a.name}: "))
        )
        if _call("secrets.set", name=a.name, value=value) is None:
            from couchbox import secrets

            secrets.put(a.name, value)
    elif a.action == "clear":
        if _call("secrets.clear", name=a.name) is None:
            from couchbox import secrets

            secrets.clear(a.name)


def cmd_home(a) -> None:
    if a.action == "rebuild":
        r = _call("home.rebuild", restart_shell=a.restart)
        if r is None:
            from couchbox import home

            r = home.build(restart_shell=a.restart)
        for i, x in enumerate(r["apps"]):
            print(f"{i}: {x['name']} ({x['app']})")
    elif a.action == "row":
        from couchbox import apps

        for i, x in enumerate(apps.home_row()):
            print(f"{i}: {x.name} ({x.id})")
    elif a.action == "move":
        _call("home.move", app=a.args[0], index=int(a.args[1]))
    elif a.action in ("hide", "show"):
        _call("home.hide", app=a.args[0], hidden=a.action == "hide")


def cmd_doctor(a) -> None:
    from couchbox import doctor

    r = doctor.run(post_update=a.post_update, container=a.container)
    if a.json:
        print(json.dumps(r))
    else:
        mark = {"ok": "✓", "warn": "!", "fail": "✗"}
        for c in r["checks"]:
            print(f"{mark[c['status']]} {c['name']:<26} {c['detail']}")
    sys.exit(1 if r["status"] == "fail" else 0)


def cmd_update(a) -> None:
    if a.action == "status":
        _print(_call("updates.status"))
    elif a.action == "check":
        st = _call("updates.check")
        print(f"Update available: {st['available']}" if st.get("available") else f"Up to date ({st['version']}).")
    elif a.action == "install":
        _call("updates.install")
        print("Installing in the background: journalctl -fu couchbox-updater-now")
    elif a.action == "rollback":
        _call("updates.rollback")
        print("Rolling back in the background: journalctl -fu couchbox-rollback")


def cmd_pair(a) -> None:
    _call("remote.pair_start", seconds=45, address=a.address or "")
    print("Looking for a remote. Hold Home on the Fire TV remote for ~10 s until its light blinks.")
    for ev in ipc.subscribe(["remote"]):
        d = ev["data"]
        st = d.get("state")
        if st == "found":
            print(f"Found {d.get('name')} ({d.get('address')})")
        elif st == "pairing":
            print(f"Pairing (attempt {d.get('attempt')})")
        elif st == "paired":
            print(f"Paired {d.get('name')}. Press a few buttons.")
            return
        elif st in ("failed", "stopped"):
            sys.exit(f"Not paired: {d.get('reason', st)}. Hold Home ~10 s and try again.")


def cmd_wifi(a) -> None:
    if a.action == "list":
        for n in _call("network.wifi_scan"):
            print(f"{'*' if n['connected'] else ' '} {n['signal']:3d}% {n['band']:<7} {'🔒' if n['secure'] else '  '} {n['ssid']}")
    elif a.action == "join":
        pw = getpass.getpass(f"Password for {a.ssid} (empty if open): ")
        _print(_call("network.wifi_connect", ssid=a.ssid, password=pw))
    elif a.action == "forget":
        _call("network.wifi_forget", ssid=a.ssid)


def cmd_import_mtv(a) -> None:
    from couchbox import migrate_mtv

    changes, secrets_ = migrate_mtv.read(a.path)
    print(json.dumps({"settings": changes, "secrets": sorted(secrets_)}, indent=2))
    if a.dry_run:
        return
    if _call("settings.set", changes=changes) is None:
        settings.update(changes)
    for n, v in secrets_.items():
        if _call("secrets.set", name=n, value=v) is None:
            from couchbox import secrets

            secrets.put(n, v)
    print("Imported.")


def cmd_install(a) -> None:
    st = _call("install.status")
    if not a.device:
        print(f"Running from: {st['booted_from'] or '?'}")
        for t in st["targets"]:
            print(f"  {t['path']}  {t['label']}")
        if not st["targets"]:
            print("No drive to install to (only offered when running from a USB stick or SD card).")
        return
    if input(f"Erase {a.device} and copy this system onto it? Type YES: ") != "YES":
        sys.exit("Not installed.")
    _call("install.start", device=a.device)
    for ev in ipc.subscribe(["install"]):
        d = ev["data"]
        print(f"\r{d.get('step', '')}: {d.get('percent', 0)}%   ", end="", flush=True)
        if d.get("state") == "failed":
            sys.exit(f"\nFailed: {d.get('error')}")
        if d.get("state") == "done":
            print("\nDone. " + ("Reboot to run from it." if d.get("next") == "restart" else "Shut down, take out the SD card, power on."))
            return


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="couchbox", description="Couchbox TV box")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("version")
    c = sub.add_parser("config")
    c.add_argument("action", choices=["list", "get", "set", "reset", "env", "schema"])
    c.add_argument("key", nargs="?")
    c.add_argument("value", nargs="?")
    s = sub.add_parser("secret")
    s.add_argument("action", choices=["set", "clear", "status"])
    s.add_argument("name", nargs="?")
    s.add_argument("value", nargs="?")
    h = sub.add_parser("home")
    h.add_argument("action", choices=["rebuild", "row", "move", "hide", "show"])
    h.add_argument("args", nargs="*")
    h.add_argument("--restart", action="store_true")
    d = sub.add_parser("doctor")
    d.add_argument("--json", action="store_true")
    d.add_argument("--post-update", action="store_true")
    d.add_argument("--container", action="store_true")
    u = sub.add_parser("update")
    u.add_argument("action", choices=["status", "check", "install", "rollback"])
    pr = sub.add_parser("pair-remote")
    pr.add_argument("address", nargs="?")
    w = sub.add_parser("wifi")
    w.add_argument("action", choices=["list", "join", "forget"])
    w.add_argument("ssid", nargs="?")
    sub.add_parser("phone-url")
    im = sub.add_parser("import-mtv")
    im.add_argument("path", nargs="?", default="/etc/mtv")
    im.add_argument("--dry-run", action="store_true")
    ins = sub.add_parser("install-to-disk")
    ins.add_argument("device", nargs="?")
    a = p.parse_args(argv)

    if a.cmd == "version":
        print(__version__)
    elif a.cmd == "config":
        if a.action in ("get", "set", "reset") and not a.key or a.action == "set" and a.value is None:
            p.error("config get/reset need KEY; set needs KEY VALUE")
        try:
            cmd_config(a)
        except settings.SettingsError as e:
            sys.exit(f"couchbox: {e}")
    elif a.cmd == "secret":
        cmd_secret(a)
    elif a.cmd == "home":
        cmd_home(a)
    elif a.cmd == "doctor":
        cmd_doctor(a)
    elif a.cmd == "update":
        cmd_update(a)
    elif a.cmd == "pair-remote":
        cmd_pair(a)
    elif a.cmd == "wifi":
        cmd_wifi(a)
    elif a.cmd == "phone-url":
        print(_call("phone.pairing")["url"])
    elif a.cmd == "import-mtv":
        cmd_import_mtv(a)
    elif a.cmd == "install-to-disk":
        cmd_install(a)


if __name__ == "__main__":
    t = time.time()
    main()
