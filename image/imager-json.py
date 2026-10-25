#!/usr/bin/env python3
"""The Raspberry Pi Imager repository entry for a release (rpi-imager.json).
Users add .../releases/latest/download/rpi-imager.json in Imager's "Content repository"."""

import datetime as dt
import json
import sys
from pathlib import Path

version, d = sys.argv[1].lstrip("v"), Path(sys.argv[2])
name = f"couchbox-{version}-rpi5.img"
xz = d / f"{name}.xz"
entry = {
    "name": f"Couchbox {version}",
    "description": "Open-source TV box: Plasma Bigscreen, native TV apps, HDMI-CEC, Fire TV remote. Set up on the TV after flashing.",
    "url": f"https://github.com/Supermaxman/couchbox/releases/download/v{version}/{name}.xz",
    "icon": "https://raw.githubusercontent.com/Supermaxman/couchbox/main/docs/icon.png",
    "website": "https://github.com/Supermaxman/couchbox",
    "release_date": dt.date.today().isoformat(),
    "extract_size": int((d / f"{name}.extract.size").read_text()) if (d / f"{name}.extract.size").exists() else 0,
    "extract_sha256": (d / f"{name}.extract.sha256").read_text().strip() if (d / f"{name}.extract.sha256").exists() else "",
    "image_download_size": xz.stat().st_size if xz.exists() else 0,
    "devices": ["pi5-64bit"],
    "init_format": "cloudinit",
}
print(json.dumps({"os_list": [entry]}, indent=2))
