#!/usr/bin/env python3
"""CI: the package data is consistent. Every setting has a type, label, page and a valid
default; every app manifest has the fields the home screen needs, a tile that exists and
requirements that are real settings; ids are unique."""

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
os.environ["COUCHBOX_SHARE"] = str(REPO / "data")
sys.path.insert(0, str(REPO / "src"))
from couchbox import settings  # noqa: E402

errors = []
sch = settings.schema()
for key, spec in sch["settings"].items():
    for f in ("type", "default", "page", "label"):
        if f not in spec:
            errors.append(f"setting {key}: no {f}")
    if spec.get("page") not in sch["pages"]:
        errors.append(f"setting {key}: unknown page {spec.get('page')}")
    try:
        settings.validate(key, spec["default"])
    except (settings.SettingsError, KeyError) as e:
        errors.append(f"setting {key}: bad default ({e})")
for name, spec in sch["secrets"].items():
    if spec.get("page") not in sch["pages"]:
        errors.append(f"secret {name}: unknown page")

ids = set()
for f in sorted((REPO / "data/apps").glob("*.json")):
    m = json.loads(f.read_text())
    if m.get("id") != f.stem:
        errors.append(f"{f.name}: id must be {f.stem}")
    if m["id"] in ids:
        errors.append(f"{f.name}: duplicate id")
    ids.add(m["id"])
    for field in ("name", "desktop", "kind"):
        if not m.get(field):
            errors.append(f"{f.name}: no {field}")
    if m.get("tile") and not (REPO / "shell/theme/tiles" / f"{m['tile']}.svg").exists():
        errors.append(f"{f.name}: tile {m['tile']}.svg missing")
    for r in m.get("requires", []):
        if r not in sch["settings"]:
            errors.append(f"{f.name}: requires unknown setting {r}")
    for r in m.get("requires_any", []):
        if r not in sch["settings"] and r.removeprefix("secret:") not in sch["secrets"]:
            errors.append(f"{f.name}: requires_any unknown setting or secret {r}")
    if m.get("kind") == "native" and m["desktop"].startswith("couchbox-") and m["id"] != "settings":
        if not (REPO / "system/applications" / m["desktop"]).exists():
            errors.append(f"{f.name}: {m['desktop']} missing from system/applications")

for e in errors:
    print("::error::" + e)
print(f"data: {len(sch['settings'])} settings, {len(ids)} apps, {len(errors)} problems")
sys.exit(1 if errors else 0)
