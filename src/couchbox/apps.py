"""The apps registry: one manifest per app (share/apps/<id>.json), plus the user's websites
(settings home.web_apps). The home screen, Settings, voice and the memory manager read it.

Manifest fields:
  id, name, desktop (the .desktop id the TV shell launches), tile (share/tiles/<tile>.svg),
  kind (native | flatpak | web | system), requires (settings that must be set),
  default_order, default_visible, unofficial, hideable (default true), settings_page
"""

import json
from dataclasses import dataclass, field
from typing import Any

from couchbox import paths, settings


@dataclass
class App:
    id: str
    name: str
    desktop: str
    kind: str = "native"
    tile: str = ""
    icon: str = ""
    url: str = ""
    requires: list[str] = field(default_factory=list)
    default_order: int = 500
    default_visible: bool = True
    unofficial: bool = False
    hideable: bool = True
    settings_page: str = ""

    def available(self, s: dict[str, Any]) -> bool:
        """Installed requirements met (its settings are set) and not turned off."""
        if self.id in s["apps.disabled"]:
            return False
        return all(s.get(k) for k in self.requires)

    def missing(self, s: dict[str, Any]) -> list[str]:
        return [k for k in self.requires if not s.get(k)]

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def _manifests() -> list[App]:
    out = []
    d = paths.share() / "apps"
    for f in sorted(d.glob("*.json")):
        m = json.loads(f.read_text())
        out.append(App(**{k: v for k, v in m.items() if k in App.__dataclass_fields__}))
    return out


def all_apps(s: dict[str, Any] | None = None) -> list[App]:
    s = s or settings.load()
    apps = _manifests()
    for w in s["home.web_apps"]:
        apps.append(
            App(
                id=w["id"],
                name=w["name"],
                desktop=f"couchbox-web-{w['id']}.desktop",
                kind="web",
                url=w["url"],
                icon="applications-internet",
                default_order=900,
            )
        )
    return apps


def get(app_id: str, s: dict[str, Any] | None = None) -> App | None:
    return next((a for a in all_apps(s) if a.id == app_id), None)


def home_row(s: dict[str, Any] | None = None) -> list[App]:
    """The home row, left to right: the user's order first, then the rest by default order.
    Hidden and unavailable apps are left out; Settings is always last."""
    s = s or settings.load()
    apps = {a.id: a for a in all_apps(s)}
    order = [i for i in s["home.layout"] if i in apps]
    rest = sorted((a for a in apps.values() if a.id not in order), key=lambda a: (a.default_order, a.name))
    hidden = set(s["home.hidden"])
    row = []
    for a in [apps[i] for i in order] + rest:
        if not a.hideable:
            continue
        if a.id in hidden or not a.available(s):
            continue
        if a.id not in s["home.layout"] and not a.default_visible:
            continue
        row.append(a)
    row += [a for a in apps.values() if not a.hideable]
    names = s["home.names"]
    for a in row:
        if a.id in names:
            a.name = names[a.id]
    return row


def move(layout: list[str], app_id: str, to_index: int, s: dict[str, Any] | None = None) -> list[str]:
    """A new home.layout with app_id moved to to_index of the visible row."""
    s = s or settings.load()
    current = [a.id for a in home_row(s) if a.hideable]
    if app_id not in current:
        raise settings.SettingsError(f"{app_id} isn't on the home row")
    current.remove(app_id)
    current.insert(max(0, min(to_index, len(current))), app_id)
    # keep ids the user ordered that are hidden right now, after the visible ones
    return current + [i for i in layout if i not in current]
