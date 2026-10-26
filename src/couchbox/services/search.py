"""Search for the couchbox TV app: Google in a web view, made for the remote, plus a reader
and (when the voice assistant's model is set up) AI summaries.

  pages      the real google.com in Qt WebEngine (ui/search). Google's Custom Search JSON API
             is closed to new users (and ends in 2027), so there's no results API: the app
             shows Google's own results page and the pages it links to
  reader     reader.js (run in the page) picks the article out of a page: title, site, and
             its paragraphs, headings, lists and quotes. blocks() tidies that for the native
             reader view
  history    the last searches (~/.local/share/couchbox-search/history.json), for the start page
  AI         summaries and questions about the page, and the optional short answer above the
             results (Settings -> Apps -> Search), go to the voice assistant's model through
             couchboxd (assistant.complete), which holds its key. Without a model, none of it shows

Demo mode (tests, screenshots) answers with made-up pages and no network.
"""

import json
import os
import re
import urllib.parse
from pathlib import Path

HISTORY_MAX = 12
PAGE_CHARS = 12000  # of a page's text, for the model
SNIPPET_RESULTS = 8


def data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local/share")
    return Path(base) / "couchbox-search"


def looks_like_url(text: str) -> bool:
    t = text.strip()
    if " " in t or not t:
        return False
    if re.match(r"^[a-z][a-z0-9+.-]*://", t, re.I):
        return True
    return bool(re.match(r"^(localhost|[\w-]+(\.[\w-]+)+)(:\d+)?(/.*)?$", t)) and not t.endswith(".")


def address(text: str, lang: str = "en") -> str:
    """What to open for what was typed: an address as is, anything else as a Google search."""
    t = text.strip()
    if looks_like_url(t):
        return t if re.match(r"^[a-z][a-z0-9+.-]*://", t, re.I) else "https://" + t
    return "https://www.google.com/search?" + urllib.parse.urlencode({"q": t, "hl": lang})


def query_of(url: str) -> str:
    """The search in a Google results address ("" for any other page)."""
    u = urllib.parse.urlparse(url or "")
    if not re.match(r"^(www\.)?google\.[a-z.]+$", u.netloc) or u.path != "/search":
        return ""
    return urllib.parse.parse_qs(u.query).get("q", [""])[0]


def is_consent(url: str) -> bool:
    """Google's cookie choice page (shown in some countries before the results)."""
    return urllib.parse.urlparse(url or "").netloc.startswith("consent.")


# ------------------------------------------------------------------ history
class History:
    def __init__(self, path: Path | None = None):
        self.path = path or data_dir() / "history.json"

    def load(self) -> list[str]:
        try:
            items = json.loads(self.path.read_text())
            return [str(x) for x in items if isinstance(x, str)][:HISTORY_MAX]
        except (OSError, ValueError):
            return []

    def add(self, query: str) -> list[str]:
        q = " ".join(query.split())
        if not q:
            return self.load()
        items = [q] + [x for x in self.load() if x.lower() != q.lower()]
        items = items[:HISTORY_MAX]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(items))
        os.replace(tmp, self.path)
        return items

    def clear(self) -> list[str]:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
        return []


# ------------------------------------------------------------------ reader
BLOCK_KINDS = {"h", "p", "li", "quote", "pre"}
CITE = re.compile(r"\[(\d+|[a-z]|citation needed|note \d+)\]")  # Wikipedia's reference marks


def blocks(article: dict) -> dict:
    """reader.js's article, tidied for the reader view: empty and repeated blocks dropped,
    whitespace folded, very long pages cut."""
    out, seen, total = [], set(), 0
    for b in article.get("blocks") or []:
        kind = b.get("k") if b.get("k") in BLOCK_KINDS else "p"
        text = b.get("t") or ""
        text = text.strip() if kind == "pre" else " ".join(CITE.sub("", text).split())
        if not text or (kind != "pre" and len(text) < 2):
            continue
        key = (kind, text)
        if key in seen:
            continue
        seen.add(key)
        out.append({"k": kind, "t": text})
        total += len(text)
        if total > 200_000:
            break
    words = sum(len(b["t"].split()) for b in out)
    return {
        "title": " ".join((article.get("title") or "").split()),
        "site": " ".join((article.get("site") or "").split()),
        "url": article.get("url") or "",
        "blocks": out,
        "minutes": max(1, round(words / 230)) if words else 0,
    }


def page_text(article: dict, limit: int = PAGE_CHARS) -> str:
    """The article as plain text for the model (headings marked), cut at limit."""
    parts = []
    for b in blocks(article)["blocks"]:
        t = b["t"]
        parts.append(("## " + t) if b["k"] == "h" else ("- " + t) if b["k"] == "li" else t)
    text = "\n".join(parts)
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " …"


# ------------------------------------------------------------------ AI
class NoModel(Exception):
    pass


def ai_ready(s=None) -> bool:
    """The voice assistant's model is set up (its server and model name)."""
    from couchbox import settings

    s = s or settings.load()
    return bool(s["voice.llm.url"] and s["voice.llm.model"])


SYSTEM = (
    "You help someone reading the web on their TV, from across the room. Answer in plain text "
    "(no markdown, no tables, no links), short and clear. Use only the text you're given; if it "
    "doesn't say, say so."
)


def summary_messages(article: dict, question: str = "") -> list[dict]:
    a = blocks(article)
    head = f"Page: {a['title']}" + (f" ({a['site']})" if a["site"] else "")
    ask = (
        f"What does this page say about: {question.strip()}? Answer in up to 5 sentences."
        if question.strip()
        else "Summarize this page in 3 to 5 short bullet points (each starting with '• '), then one line on who wrote it or where it's from, if the page says."
    )
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"{head}\n\n{page_text(article)}\n\n{ask}"}]


def answer_messages(query: str, results: list[dict]) -> list[dict]:
    lines = []
    for i, r in enumerate(results[:SNIPPET_RESULTS], 1):
        lines.append(f"[{i}] {r.get('title', '')} — {r.get('site', '')}\n{r.get('snippet', '')}")
    ask = (
        f"Search: {query}\n\nResults:\n" + "\n\n".join(lines) + "\n\nAnswer the search in 2 or 3 sentences using only "
        "these results, and end with the numbers of the results you used, like [1][3]. If they don't answer it, say "
        "'The results don't say.'"
    )
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": ask}]


def ask_model(messages: list[dict], max_tokens: int = 500) -> str:
    """The model's answer, through couchboxd (which holds the key)."""
    from couchbox import ipc

    if not ai_ready():
        raise NoModel("The assistant isn't set up (Settings → Voice).")
    r = ipc.call("assistant.complete", timeout=120, messages=messages, max_tokens=max_tokens)
    return clean_answer(r.get("text", ""))


def clean_answer(text: str) -> str:
    """Model output for a plain TV panel: no thinking, no markdown emphasis or headers."""
    t = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    t = re.sub(r"^\s*#+\s*", "", t, flags=re.M)
    t = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: m.group(1) or m.group(2), t)
    t = re.sub(r"^\s*[-*]\s+", "• ", t, flags=re.M)
    return t.strip()


# ------------------------------------------------------------------ demo
DEMO_ARTICLE = {
    "title": "The Eiffel Tower: facts and figures",
    "site": "example.org",
    "url": "https://example.org/eiffel-tower",
    "blocks": [
        {"k": "p", "t": "The Eiffel Tower is a wrought-iron lattice tower on the Champ de Mars in Paris, France."},
        {"k": "h", "t": "How tall is it?"},
        {
            "k": "p",
            "t": "The tower is 330 metres (1,083 ft) tall, about the same height as an 81-storey building. Its height "
            "changed over the years as antennas were added at the top.",
        },
        {"k": "h", "t": "Building it"},
        {
            "k": "p",
            "t": "It was built between 1887 and 1889 as the entrance arch for the 1889 World's Fair. About 300 workers "
            "joined 18,038 pieces of iron with 2.5 million rivets.",
        },
        {"k": "li", "t": "Designed by Gustave Eiffel's engineering company"},
        {"k": "li", "t": "Opened on 31 March 1889"},
        {"k": "li", "t": "Repainted every seven years, with about 60 tonnes of paint"},
        {"k": "quote", "t": "I ought to be jealous of the tower. She is more famous than I am. — Gustave Eiffel"},
        {
            "k": "p",
            "t": "Today it is the most-visited paid monument in the world, with nearly seven million visitors a year.",
        },
    ],
}

DEMO_RESULTS = [
    {"title": "Eiffel Tower - Wikipedia", "site": "en.wikipedia.org", "snippet": "The tower is 330 metres (1,083 ft) tall…"},
    {"title": "Eiffel Tower facts", "site": "example.org", "snippet": "At 330 m, it was the tallest structure in the world until 1930."},
]

DEMO_SUMMARY = (
    "• The Eiffel Tower is a 330-metre wrought-iron tower in Paris.\n"
    "• It was built in 1887–1889 as the entrance to the 1889 World's Fair.\n"
    "• It's repainted every seven years and gets about seven million visitors a year.\n"
    "From example.org."
)
DEMO_ANSWER = "The Eiffel Tower is 330 metres (1,083 ft) tall, including the antennas at its top. [1][2]"
