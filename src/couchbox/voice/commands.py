"""Voice commands without a model (voice.mode = dictation): a few fixed phrases.

parse(text) -> (action, argument) or None
  "pause" / "stop"                 ("pause", "")
  "play" / "resume" / "continue"   ("play", "")
  "go home" / "home"               ("key", "home")
  "go back" / "back"               ("key", "back")
  "open youtube" / "launch twitch" ("open", "youtube")
  "volume up" / "turn it down" / "mute"   ("tv", "volume_up" | "volume_down" | "mute")
  "turn off the tv" / "tv off"     ("tv", "off")
  "search for cats" / "find cats" / "youtube cats"   ("search", "cats")
  "remember this as pet music"     ("remember", "pet music")
  "play pet music" / "start bedtime"   ("moment", "pet music"): the caller starts the Moment of
                                   that name, else parses it again with moments=False
  "stop the moment"                ("stop_moment", "")
Anything else is None: the caller says it didn't understand (or types it, when a text box is open).
"""

import re

_RULES: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"^(please )?(pause|stop|hold on)( it| that| the video| playback)?$"), "pause", ""),
    (re.compile(r"^(please )?(play|resume|continue|unpause|keep playing)( it| that| the video)?$"), "play", ""),
    (re.compile(r"^(go )?(to the )?home( screen)?$"), "key", "home"),
    (re.compile(r"^(go )?back$"), "key", "back"),
    (re.compile(r"^(turn (it|the volume) up|volume up|louder)$"), "tv", "volume_up"),
    (re.compile(r"^(turn (it|the volume) down|volume down|quieter|softer)$"), "tv", "volume_down"),
    (re.compile(r"^(mute|unmute)( the tv| it)?$"), "tv", "mute"),
    (re.compile(r"^(turn )?(off the tv|the tv off|tv off)$"), "tv", "off"),
]
_REMEMBER = re.compile(r"^(please )?(remember|save) (this|that|it|what'?s (on|playing))( one)? as (?P<name>.+)$")
_MOMENT = re.compile(r"^(please )?(play|start|put on) (?P<name>.+)$")
_STOP_MOMENT = re.compile(r"^(stop|end)( the)? moment$")
_OPEN = re.compile(r"^(open|launch|start|go to|switch to|show me)( the)? (?P<app>.+?)( app)?$")
_SEARCH = re.compile(r"^(search( youtube)? for|search|find|look up|youtube) (?P<q>.+)$")


def normalize(text: str) -> str:
    t = text.lower().strip()
    t = re.sub(r"[.!?,]+$", "", t)
    return re.sub(r"\s+", " ", t)


def parse(text: str, moments: bool = True) -> tuple[str, str] | None:
    t = normalize(text)
    if not t:
        return None
    m = _REMEMBER.match(t)
    if m:
        return "remember", m.group("name").strip()
    if _STOP_MOMENT.match(t):
        return "stop_moment", ""
    m = _MOMENT.match(t)
    if moments and m and m.group("name") not in ("it", "that", "the video"):
        return "moment", m.group("name").strip()
    for rx, action, arg in _RULES:
        if rx.match(t):
            return action, arg
    m = _SEARCH.match(t)
    if m:
        return "search", m.group("q").strip()
    m = _OPEN.match(t)
    if m:
        return "open", m.group("app").strip()
    return None


def match_app(spoken: str, names: list[str]) -> str | None:
    """The app name the user meant ("you tube", "second try" -> "2nd Try")."""
    s = re.sub(r"[^a-z0-9]", "", spoken.lower().replace("second", "2nd"))
    for n in names:
        if re.sub(r"[^a-z0-9]", "", n.lower()) == s:
            return n
    for n in names:
        k = re.sub(r"[^a-z0-9]", "", n.lower())
        if k and (k in s or s in k):
            return n
    return None
