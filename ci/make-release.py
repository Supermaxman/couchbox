#!/usr/bin/env python3
"""Write release.json for a directory of release assets (then sign it: ssh-keygen -Y sign).

  ci/make-release.py VERSION DIR [--notes FILE] [--min-from VERSION]
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("version")
p.add_argument("dir")
p.add_argument("--notes", default="")
p.add_argument("--min-from", default="")
p.add_argument("--base", default="26.10")
a = p.parse_args()
v = a.version.lstrip("v")
d = Path(a.dir)
assets = {}
for f in sorted(d.iterdir()):
    if f.is_file() and not f.name.startswith("release.json") and f.name != "SHA256SUMS":
        h = hashlib.sha256()
        with open(f, "rb") as fh:
            for b in iter(lambda: fh.read(1 << 20), b""):
                h.update(b)
        assets[f.name] = {"sha256": h.hexdigest(), "size": f.stat().st_size}
commit = os.environ.get("GITHUB_SHA") or subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
m = {
    "schema": 1,
    "version": v,
    "channel": "beta" if "-" in v else "stable",
    "commit": commit,
    "date": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "base": {"os": "ubuntu", "version": a.base},
    "min_from": a.min_from or None,
    "assets": assets,
    "notes_md": Path(a.notes).read_text() if a.notes and Path(a.notes).exists() else "",
    "restart": ["services", "session"],
    "reboot": False,
    "next_key": None,
}
(d / "release.json").write_text(json.dumps(m, indent=2) + "\n")
(d / "SHA256SUMS").write_text("".join(f"{x['sha256']}  {n}\n" for n, x in assets.items()))
print(f"release.json: {v}, {len(assets)} assets")
