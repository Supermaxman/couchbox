"""Display modes the TV offers (from its EDID, via the kernel's DRM connectors)."""

import re
from typing import Any

from couchbox import paths

from .api import method


def connectors() -> list[dict[str, Any]]:
    out = []
    for c in sorted((paths.root() / "sys/class/drm").glob("card*-HDMI-A-*")):
        try:
            status = (c / "status").read_text().strip()
            modes = (c / "modes").read_text().split()
        except OSError:
            continue
        out.append({"name": re.sub(r"^card\d+-", "", c.name), "connected": status == "connected", "modes": list(dict.fromkeys(modes))})
    return out


@method("display.modes", write=False)
def display_modes() -> dict[str, Any]:
    conns = connectors()
    sizes = []
    for c in conns:
        if c["connected"]:
            sizes = [m for m in c["modes"] if not m.endswith("i")]
    # what the box can choose; refresh rates come from kscreen in the session
    choices = [f"{m}@60" for m in sizes if m in ("1920x1080", "1280x720", "2560x1440")]
    choices += [f"{m}@30" for m in sizes if m == "3840x2160"]
    return {"connectors": conns, "choices": choices or ["1920x1080@60", "1280x720@60"]}
