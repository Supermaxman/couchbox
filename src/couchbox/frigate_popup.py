"""The Frigate pop-up's rules: which of Frigate's review items pop up over whatever is on the TV
(once each), when a camera may pop again, how long a pop-up stays, and where the flag lives that
says one is showing. couchbox-frigate-popup (the TV user's service) runs them; couchbox-input
(root) only reads the flag. No Qt and no network here, so both can import it and tests can
drive it.

Settings (Frigate app → Pop-ups; media.frigate.popup.*):
  enabled    on or off
  cameras    camera names ([]: every camera)
  labels     Frigate's labels: person, car, package, dog, speech ... ([]: anything)
  severity   alert (alerts only) | any (alerts and detections)
  seconds    how long one shows; longer while its event goes on (until a few seconds after it
             ends), but never more than 3 times as long
  cooldown   seconds after a camera's pop-up closes (dismissed or timed out) before that
             camera can pop again
  position   top-right | top-left | bottom-right | bottom-left
  size       small | medium | large
  picture    live (the camera's video, muted) | snapshots (its picture, once a second: lighter)

The service's control socket (couchbox.appctl, site "frigate-popup"):
    {"op": "ping"}
    {"op": "status"}                      -> what's showing, cooldowns, sign-in, the settings
    {"op": "test", "camera": NAME}        -> show a camera now (NAME optional), labelled a test
    {"op": "key", "key": "ok" | "back"}   -> {"handled": bool}: couchbox-input's OK and Back
    {"op": "hide"}

While a pop-up shows, the service keeps a flag file next to its socket
($XDG_RUNTIME_DIR/couchbox/frigate-popup.shown). couchbox-input stats it on OK and Back and asks
the service only when it's there, so the keys cost nothing extra the rest of the time.
"""

SITE = "frigate-popup"
FLAG = "frigate-popup.shown"
PREFIX = "media.frigate.popup."
APP = "couchbox-frigate"  # the Frigate app's window (its Wayland app id)

WINDOW = 120  # look at review items from the last 2 minutes
FRESH = 30  # an item that has ended still pops if it started this recently
GRACE = 5  # a pop-up stays this long after its event ends
LONGEST = 3  # ... but never more than this many times its usual time
FORGET = 600  # a popped item not seen for this long is forgotten


def prefs(values):
    """The pop-up's settings (short keys) from settings.load()'s values."""
    return {k[len(PREFIX) :]: v for k, v in values.items() if k.startswith(PREFIX)}


def flag_path():
    """The flag file (the TV user's, also when root asks)."""
    from couchbox import appctl

    return appctl.sock_path(SITE).parent / FLAG


def is_frigate(window):
    """Whether the window in front (couchbox-mediakeys's or couchbox-active-window's report) is
    the Frigate app."""
    w = window or {}
    return any(str(w.get(k) or "").lower().removesuffix(".desktop") == APP for k in ("class", "app"))


def fresh(item, now):
    """Still going, or started in the last FRESH seconds."""
    return bool(item.get("live")) or now - (item.get("start") or 0) <= FRESH


def matches(item, p):
    """Whether a review item (frigate.py's _review_item) is one the household asked about."""
    if p.get("cameras") and item.get("camera") not in p["cameras"]:
        return False
    if p.get("severity", "alert") == "alert" and item.get("severity") != "alert":
        return False
    if p.get("labels") and not set(item.get("labelKeys") or ()) & set(p["labels"]):
        return False
    return True


def deadline(shown_at, seconds, now, live=False, end=0):
    """When a pop-up shown at shown_at closes: after `seconds`, or GRACE seconds after its event
    ends (still going: GRACE from now), whichever is later, but no later than LONGEST x seconds."""
    until = shown_at + seconds
    if live:
        until = max(until, now + GRACE)
    elif end:
        until = max(until, end + GRACE)
    return min(until, shown_at + LONGEST * seconds)


def seen(item):
    """What was seen, for the pop-up: "Person · Front Door", "Person, Dog (Max)", "Motion"."""
    what = ", ".join(k["label"] for k in item.get("kinds") or []) or "Motion"
    if item.get("names"):
        what += " (" + ", ".join(item["names"]) + ")"
    zones = ", ".join(item.get("zones") or [])
    return f"{what} · {zones}" if zones else what


class Picker:
    """Which item pops next: each review id once, the newest first, none from a camera that is
    cooling down after its last pop-up closed."""

    def __init__(self):
        self.popped = {}  # review id -> when it was last in Frigate's answer
        self.quiet = {}  # camera -> until when it can't pop

    def pick(self, items, p, now):
        best = None
        for x in items:
            if x["id"] in self.popped:
                self.popped[x["id"]] = now  # still listed: keep remembering it
                continue
            if not fresh(x, now) or not matches(x, p) or self.quiet.get(x["camera"], 0) > now:
                continue
            if best is None or (x.get("start") or 0) > (best.get("start") or 0):
                best = x
        self.popped = {k: t for k, t in self.popped.items() if now - t < FORGET}
        return best

    def mark(self, rid, now):
        """This item has had its turn (it popped, or was passed over for good)."""
        self.popped[rid] = now

    def closed(self, camera, now, cooldown):
        """A camera's pop-up was dismissed or timed out: it waits `cooldown` seconds."""
        if cooldown > 0:
            self.quiet[camera] = now + cooldown

    def cooling(self, now):
        """{camera: seconds left} for the cameras still cooling down."""
        self.quiet = {c: t for c, t in self.quiet.items() if t > now}
        return {c: round(t - now) for c, t in self.quiet.items()}
