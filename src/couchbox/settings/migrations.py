"""Settings file migrations: MIGRATIONS[n] turns version n values into version n+1.

Add one whenever a key is renamed or its meaning changes, with a test in
tests/unit/test_settings.py.
"""

from collections.abc import Callable
from typing import Any


def _youtube_one_tile(values: dict[str, Any]) -> dict[str, Any]:
    """1 -> 2: the YouTube (beta) tile (youtube-beta, Couchbox's own app) became the YouTube tile,
    VacuumTube its fallback. The tile keeps whichever of the two came first on the row and the
    beta's name (a box that renamed VacuumTube "YouTube (old)" doesn't keep that); YouTube is
    hidden or turned off only if both were."""
    v = dict(values)
    layout = list(v.get("home.layout") or [])
    if "youtube-beta" in layout:
        at = min(layout.index(x) for x in ("youtube", "youtube-beta") if x in layout)
        layout = [x for x in layout if x not in ("youtube", "youtube-beta")]
        layout.insert(at, "youtube")
        v["home.layout"] = layout
    names = dict(v.get("home.names") or {})
    if "youtube-beta" in names:
        beta = names.pop("youtube-beta")
        if beta and beta != "YouTube":
            names["youtube"] = beta
        else:
            names.pop("youtube", None)
        v["home.names"] = names
    for key in ("home.hidden", "apps.disabled"):
        ids = list(v.get(key) or [])
        if "youtube-beta" in ids or "youtube" in ids:
            both = "youtube-beta" in ids and "youtube" in ids
            ids = [x for x in ids if x not in ("youtube", "youtube-beta")] + (["youtube"] if both else [])
            v[key] = ids
    return v


MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {1: _youtube_one_tile}
