"""The agent loop: a spoken request -> model with tools (any OpenAI-compatible chat API with
tool calling) -> actions on the TV -> one short reply.

Each request is a fresh session, except an answer to a question the assistant just asked
(within ANSWER_WINDOW), which continues it. A long session is compacted: older turns are
summarised by the model into a few lines kept in the system prompt. Network calls retry
with backoff."""

import json
import os
import re
import time

import requests

from . import tools

PROMPT = os.path.join(os.path.dirname(__file__), "prompt.md")
# "who directed X", "X's IMDb rating", "what else has X been in", "Villeneuve's movies"...
MOVIE_FACTS = re.compile(
    r"\b(direct(ed|or|s)|imdb|rotten tomatoes|rated|rating|starr(ed|ing|s)|cast of|the cast|who plays|played by|"
    r"been in|acted in|filmography|written by|wrote|(movies|films|shows) (by|with|from)|'s (movies|films|shows|work))\b",
    re.I,
)
MAX_STEPS = 14
TOOL_RESULT_CHARS = 3000
COMPACT_CHARS = 36000  # about 10k tokens of history
KEEP_RECENT = 2  # requests kept verbatim when compacting
ANSWER_WINDOW = 120  # seconds to answer the assistant's question and keep its session
RETRY_DELAYS = (2, 5, 10)


class Cancelled(Exception):
    pass


class PicturesRefused(Exception):
    """The model server turned down a request with a picture in it (a model that reads text only)."""


# The screen, looked at on its own: behind pages of subtitles, a model barely looks at a picture
SEE = (
    "This is a TV screen right now, showing a show, film or video (a round bubble at the bottom may be the TV's assistant: "
    "leave it out). In at most three short lines: who is on screen (how many people, man or woman, roughly how old, "
    "clothes, what they're doing, who seems to be talking) and any words shown. Don't guess names."
)


def has_picture(messages):
    return any(isinstance(m.get("content"), list) for m in messages)


class Agent:
    def __init__(self, url, model, key, log):
        self.url, self.model, self.key, self.log = url.rstrip("/"), model, key, log
        self.turns = []  # [[messages of one request], ...]
        self.summary = ""
        self.last = 0.0
        self.asked = False  # the last reply was a question
        self.tool_list = None  # this request's tools: the same for each of its steps
        self.pictures = True  # the model takes pictures (until its server says otherwise)
        self.no_think = True  # the server takes chat_template_kwargs (llama.cpp, vLLM: not OpenAI's)

    # -------------------------------------------------------------- model calls
    def chat(self, messages, with_tools=True, cancel=None, quick=False, max_tokens=None):
        """quick: without the model's thinking first (a reasoning model can spend minutes thinking
        over a long text), where the server lets that be asked for."""
        body = {"model": self.model, "messages": messages}
        if max_tokens:
            body["max_tokens"] = max_tokens
        if with_tools:
            body["tools"] = self.tool_list or tools.schemas()
        if quick and self.no_think:
            body["chat_template_kwargs"] = {"enable_thinking": False}
        for attempt, delay in enumerate((0,) + RETRY_DELAYS):
            if delay:
                self.log(f"retrying the model in {delay}s")
                for _ in range(delay * 10):
                    if cancel and cancel.is_set():
                        raise Cancelled
                    time.sleep(0.1)
            try:
                r = requests.post(f"{self.url}/chat/completions", json=body, timeout=300, headers={"Authorization": f"Bearer {self.key}"})
                if r.status_code == 400 and "chat_template_kwargs" in body and "chat_template_kwargs" in r.text:
                    self.log("the model server doesn't take chat_template_kwargs: thinking stays on")
                    self.no_think = False
                    return self.chat(messages, with_tools, cancel, max_tokens=max_tokens)
                if r.status_code == 400 and "context" in r.text.lower() and with_tools:
                    raise OverflowError(r.text[:200])
                refused = r.status_code < 500 or re.search(r"image|vision|multimodal|mmproj", r.text, re.I)
                if r.status_code >= 400 and r.status_code != 429 and refused and has_picture(messages):
                    self.log(f"model HTTP {r.status_code} with a picture: {r.text[:200]}")
                    raise PicturesRefused
                if r.status_code >= 500 or r.status_code == 429:
                    self.log(f"model HTTP {r.status_code}: {r.text[:200]}")
                    continue
                r.raise_for_status()
                j = r.json()
                u = j.get("usage") or {}
                cached = (u.get("prompt_tokens_details") or {}).get("cached_tokens")
                if cached is None:  # llama.cpp's own numbers
                    cached = (j.get("timings") or {}).get("cache_n")
                self.log(
                    f"model: {u.get('prompt_tokens')} prompt tokens ({cached if cached is not None else '?'} cached), {u.get('completion_tokens')} out"
                )
                return j["choices"][0]["message"]
            except (requests.ConnectionError, requests.Timeout) as err:
                self.log(f"model unreachable: {err}")
        raise RuntimeError("The assistant model server isn't answering.")

    def warm(self):
        """Have the model server load the model, and read the instructions and tools every request
        starts with (its prompt cache keeps them), ahead of a question: when someone sits down at
        the TV. A model server that has been idle can take a minute to answer its first request."""
        self.tool_list = self.tool_list or tools.schemas()
        body = {
            "model": self.model,
            "messages": [self.system(), {"role": "user", "content": "(warming up: answer OK)"}],
            "tools": self.tool_list,
            "max_tokens": 1,
        }
        if self.no_think:
            body["chat_template_kwargs"] = {"enable_thinking": False}
        t = time.monotonic()
        try:
            r = requests.post(f"{self.url}/chat/completions", json=body, timeout=180, headers={"Authorization": f"Bearer {self.key}"})
        except (requests.ConnectionError, requests.Timeout) as err:
            self.log(f"warming the model: {err}")
            return False
        self.log(f"warmed the model: HTTP {r.status_code} in {time.monotonic() - t:.1f}s")
        return r.ok

    # -------------------------------------------------------------- memory
    def system(self):
        """Only what rarely changes, so the model server's prompt cache keeps it (with the tools,
        which change only with the home row): the time and the screen go in each request."""
        from couchbox import settings

        text = open(PROMPT).read().strip()
        notes = settings.get("voice.notes").strip()
        if notes:  # the household's own vocabulary (channel nicknames etc.)
            text += "\n\nAbout this household:\n" + notes
        if self.summary:
            text += "\n\nEarlier in this conversation:\n" + self.summary
        return {"role": "system", "content": text}

    @staticmethod
    def note():
        """The per-request context, after the user's words: what's on screen, and the time."""
        from couchbox import settings

        clock = "%H:%M" if settings.derived()["clock24"] else "%-I:%M %p"
        return f"[{tools.screen_summary()} Now: {time.strftime('%a %b %-d, ' + clock)}.]"

    def hint(self, text):
        """A nudge for requests models like to answer from memory (and get wrong): movie facts
        go to the movies tool. Added to that request only, so the cached prompt stays the same."""
        names = {t["function"]["name"] for t in self.tool_list}
        if "movies" in names and MOVIE_FACTS.search(text):
            return " This is a movie or TV fact: look it up with the movies tool, don't answer from memory."
        return ""

    def history(self):
        return [m for t in self.turns for m in t]

    def size(self):
        return len(json.dumps(self.history())) + len(self.summary)

    def compact(self, cancel=None):
        old, self.turns = self.turns[:-KEEP_RECENT], self.turns[-KEEP_RECENT:]
        if not old:
            return
        self.log(f"compacting {len(old)} earlier requests")
        transcript = []
        for m in (x for t in old for x in t):
            if m["role"] == "tool":
                transcript.append("result: " + m["content"][:600])
            elif m.get("tool_calls"):
                transcript.append("action: " + "; ".join(f"{c['function']['name']} {c['function']['arguments']}" for c in m["tool_calls"]))
            elif m.get("content"):
                transcript.append(f"{m['role']}: {m['content']}")
        msg = self.chat(
            [
                {"role": "system", "content": "You condense a TV assistant's conversation log."},
                {
                    "role": "user",
                    "content": ("Earlier summary:\n" + self.summary + "\n\n" if self.summary else "")
                    + "Log:\n"
                    + "\n".join(transcript)
                    + "\n\nWrite at most 8 short lines: what the user asked for, what is playing or open now, "
                    "and ids or names that may matter for follow-ups.",
                },
            ],
            with_tools=False,
            cancel=cancel,
        )
        self.summary = (msg.get("content") or "").strip()[:2000]

    # -------------------------------------------------------------- one request
    def run(self, text, status, cancel):
        """Handle one request. status(phase, line, note=None) updates the TV indicator."""
        if not (self.asked and time.time() - self.last < ANSWER_WINDOW):
            self.turns, self.summary = [], ""
        self.last = time.time()
        if self.size() > COMPACT_CHARS:
            status("thinking", "Tidying up memory")
            self.compact(cancel)
        self.tool_list = tools.schemas()
        turn = [{"role": "user", "content": f"{text}\n\n{self.note()}{self.hint(text)}"}]
        self.turns.append(turn)
        for step in range(MAX_STEPS):
            if cancel.is_set():
                raise Cancelled
            status("thinking", "Thinking")
            msg = self.step(turn, cancel)
            if cancel.is_set():
                raise Cancelled
            calls = msg.get("tool_calls") or []
            entry = {"role": "assistant", "content": msg.get("content") or ""}
            if calls:
                entry["tool_calls"] = calls
            turn.append(entry)
            if not calls:
                reply = re.sub(r"\n\s*\n+", "\n", (msg.get("content") or "Done.").strip())  # lines, not paragraphs
                self.asked = reply.endswith("?")
                self.last = time.time()
                self.log(f"reply: {reply}")
                return reply
            for c in calls:
                name = c["function"]["name"]
                try:
                    args = json.loads(c["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = None
                if not isinstance(args, dict):
                    result = "Error: the arguments weren't valid JSON."
                elif name == "say":
                    status("working", None, str(args.get("text", ""))[:200])
                    self.log(f"say: {args.get('text')}")
                    result = "Shown on the TV."
                else:
                    status("working", tools.status_text(name, args))
                    self.log(f"tool {name} {json.dumps(args)}")
                    result = tools.run_tool(name, args)
                self.log(f"  -> {result[:300]!r}")
                limit = tools.RESULT_CHARS.get(name, TOOL_RESULT_CHARS)
                content = str(result)[:limit]
                if getattr(result, "image", None):
                    status("working", "Looking at the screen")
                    seen = self.see(result.image, cancel)
                    self.log(f"  screen: {seen!r}")
                    content += f"\nOn screen now: {seen}" if seen else "\n(No picture of the screen.)"
                turn.append({"role": "tool", "tool_call_id": c.get("id", ""), "content": content})
        return "I couldn't finish that in time."

    def see(self, image, cancel=None):
        """What a picture of the screen shows, in a few lines ("" for a model that doesn't take
        pictures: then the answer comes from the text alone)."""
        if not self.pictures:
            return ""
        content = [{"type": "text", "text": SEE}, {"type": "image_url", "image_url": {"url": image}}]
        try:
            msg = self.chat([{"role": "user", "content": content}], with_tools=False, cancel=cancel, quick=True)
        except PicturesRefused:
            self.log("the model doesn't take pictures: answering from the text")
            self.pictures = False
            return ""
        except RuntimeError as err:
            self.log(f"looking at the screen: {err}")
            return ""
        return re.sub(r"\s*\n\s*", " ", (msg.get("content") or "").strip())[:600]

    def look(self, prompt, images):
        """Pictures and a question, outside any conversation (the home screen's "While you were
        out" captions). PicturesRefused when the model reads text only."""
        content = [{"type": "text", "text": prompt}] + [{"type": "image_url", "image_url": {"url": u}} for u in images]
        t = time.monotonic()
        msg = self.chat([{"role": "user", "content": content}], with_tools=False, quick=True, max_tokens=200)
        self.log(f"looked at {len(images)} camera pictures in {time.monotonic() - t:.1f}s")
        return (msg.get("content") or "").strip()

    def step(self, turn, cancel):
        """One model call on the whole conversation (compacted when it's too long for the model)."""
        quick = any(c["function"]["name"] in tools.QUICK for m in turn for c in m.get("tool_calls") or [])
        for _ in range(3):
            try:
                return self.chat([self.system()] + self.history(), cancel=cancel, quick=quick)
            except OverflowError:
                self.compact(cancel)
        return self.chat([self.system()] + self.history(), cancel=cancel, quick=quick)
