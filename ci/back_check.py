#!/usr/bin/env python3
"""The remote's Back key (Escape) in every app, off screen with made-up data.

Each case opens a page, presses its keys, and is shot twice: as is, and with Back pressed
after. Back must change what's on screen ("moves": up a level, out of an overlay) or close
the app ("quits"), never do nothing.

  python3 ci/back_check.py [OUT]     (ci/screenshots.sh runs it, after its shots)
"""

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

ROUTE = 'to:{"place":{"name":"Ferry Building","lat":37.7955,"lon":-122.3937}}'

# name, app, arguments, keys before Back, what Back must do
CASES = [
    ("movies-title", "couchbox-movies", ["--open", "movie:101"], "", "moves"),
    ("movies-title-cast", "couchbox-movies", ["--open", "movie:101"], "down", "moves"),
    ("movies-person-from-title", "couchbox-movies", ["--open", "movie:101"], "down,ok", "moves"),
    ("movies-person", "couchbox-movies", ["--open", "person:303"], "", "moves"),
    ("movies-season", "couchbox-movies", ["--open", "season:201:1"], "", "moves"),
    ("movies-search", "couchbox-movies", ["--open", "search:harbor"], "", "moves"),
    ("movies-top", "couchbox-movies", ["--open", "top:movie"], "", "moves"),
    ("movies-home", "couchbox-movies", [], "", "quits"),
    ("weather-week", "couchbox-weather", ["--open", "week"], "down,down", "moves"),
    ("weather-day", "couchbox-weather", ["--open", "day:tomorrow"], "", "moves"),
    ("weather-alerts", "couchbox-weather", ["--open", "alerts"], "", "moves"),
    ("weather-radar", "couchbox-weather", ["--open", "radar"], "", "moves"),
    ("weather-today", "couchbox-weather", [], "", "quits"),
    ("search-keyboard", "couchbox-search", [], "ok", "moves"),
    ("search-results", "couchbox-search", ["--open", "search:eiffel tower height"], "", "moves"),
    ("search-toolbar", "couchbox-search", ["--open", "search:eiffel tower height"], "up", "moves"),
    ("search-reader", "couchbox-search", ["--open", "reader"], "", "moves"),
    ("search-summary", "couchbox-search", ["--open", "summary"], "", "moves"),
    ("search-start", "couchbox-search", [], "", "quits"),
    ("spotify-search", "couchbox-spotify", ["--open", "search:midnight"], "down", "moves"),
    ("spotify-library", "couchbox-spotify", ["--open", "library"], "", "moves"),
    ("spotify-album", "couchbox-spotify", ["--open", "album:al0"], "", "moves"),
    ("spotify-artist", "couchbox-spotify", ["--open", "artist:ar1"], "down", "moves"),
    ("spotify-now", "couchbox-spotify", ["--open", "now"], "", "moves"),
    ("spotify-menu", "couchbox-spotify", ["--open", "menu"], "", "moves"),
    ("spotify-picker", "couchbox-spotify", ["--open", "picker"], "", "moves"),
    ("spotify-home", "couchbox-spotify", [], "", "quits"),
    ("maps-place-actions", "couchbox-maps", [], "right,ok", "moves"),
    ("maps-search", "couchbox-maps", ["--open", "search:ferry"], "", "moves"),
    ("maps-directions", "couchbox-maps", ["--open", ROUTE], "", "moves"),
    ("maps-directions-steps", "couchbox-maps", ["--open", ROUTE], "down,down,down,down", "moves"),
    ("maps-directions-map", "couchbox-maps", ["--open", ROUTE], "right,ok,up", "moves"),
    ("maps-places", "couchbox-maps", [], "", "quits"),
    ("frigate-camera", "couchbox-frigate", [], "down,ok", "moves"),
    ("frigate-camera-strip", "couchbox-frigate", [], "down,ok,down", "moves"),
    ("frigate-review", "couchbox-frigate", ["--open", "review"], "", "moves"),
    ("frigate-recording", "couchbox-frigate", ["--open", "review"], "right,ok", "moves"),
    ("frigate-timeline", "couchbox-frigate", ["--open", "timeline"], "", "moves"),
    ("frigate-timeline-camera", "couchbox-frigate", ["--open", "timeline:driveway"], "", "moves"),
    ("frigate-live", "couchbox-frigate", [], "", "quits"),
    ("settings-page", "couchbox-settings", ["--page", "network", "--in"], "", "moves"),
    ("settings-access", "couchbox-settings", ["--page", "access", "--in"], "", "moves"),
    ("settings-menu", "couchbox-settings", [], "", "quits"),
    ("settings-dialog", "couchbox-settings", ["--page", "time", "--in"], "ok", "moves"),
    ("setup-step", "couchbox-setup", ["--step", "3"], "", "moves"),
]
STEP = 8  # compare every 8th pixel
MIN_CHANGED = 50  # samples: a moved focus ring alone changes a few hundred


def shoot(out, name, app, args, keys):
    cmd = ["python3", f"bin/{app}", "--demo", "--shot", f"{out}/{name}.png", *args]
    if keys:
        cmd += ["--keys", keys]
    with open(f"{out}/{name}.log", "w") as log:
        subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, timeout=120, check=False)
    return os.path.exists(f"{out}/{name}.png")


def changed(a, b):
    from PySide6.QtGui import QImage

    ia, ib = QImage(a), QImage(b)
    if ia.size() != ib.size():
        return 1 << 30
    return sum(1 for y in range(0, ia.height(), STEP) for x in range(0, ia.width(), STEP) if ia.pixel(x, y) != ib.pixel(x, y))


def check(out, case):
    name, app, args, keys, want = case
    if not shoot(out, f"{name}-before", app, args, keys):
        return f"!! {name}: no shot before Back (see {out}/{name}-before.log)"
    after = shoot(out, f"{name}-after", app, args, f"{keys},back" if keys else "back")
    if want == "quits":
        return f"ok {name}: Back closes the app" if not after else f"!! {name}: Back should close the app"
    if not after:
        return f"!! {name}: Back closed the app instead of going back"
    n = changed(f"{out}/{name}-before.png", f"{out}/{name}-after.png")
    return f"ok {name}: Back moved ({n})" if n >= MIN_CHANGED else f"!! {name}: Back did nothing"


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "build/back"
    os.makedirs(out, exist_ok=True)
    with ThreadPoolExecutor(max_workers=max(2, min(8, (os.cpu_count() or 2) // 2))) as pool:
        results = list(pool.map(lambda c: check(out, c), CASES))
    print("\n".join(results))
    sys.exit(1 if any(r.startswith("!!") for r in results) else 0)


if __name__ == "__main__":
    main()
