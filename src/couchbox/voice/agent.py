"""The agent loop: a spoken request -> model with tools (any OpenAI-compatible chat API with
tool calling) -> actions on the TV -> one short reply.

Each request is a fresh session, except an answer to a question the assistant just asked
(within ANSWER_WINDOW), which continues it. A long session is compacted: older turns are
summarised by the model into a few lines kept in the system prompt. Network calls retry
with backoff."""

import json
import os
import time

import requests

from . import tools

PROMPT = os.path.join(os.path.dirname(__file__), "prompt.md")
MAX_STEPS = 14
TOOL_RESULT_CHARS = 3000
COMPACT_CHARS = 36000  # about 10k tokens of history
KEEP_RECENT = 2  # requests kept verbatim when compacting
ANSWER_WINDOW = 120  # seconds to answer the assistant's question and keep its session
RETRY_DELAYS = (2, 5, 10)


class Cancelled(Exception):
    pass


class Agent:
    def __init__(self, url, model, key, log):
        self.url, self.model, self.key, self.log = url.rstrip("/"), model, key, log
        self.turns = []  # [[messages of one request], ...]
        self.summary = ""
        self.last = 0.0
        self.asked = False  # the last reply was a question

    # -------------------------------------------------------------- model calls
    def chat(self, messages, with_tools=True, cancel=None):
        body = {"model": self.model, "messages": messages}
        if with_tools:
            body["tools"] = tools.schemas()
        for attempt, delay in enumerate((0,) + RETRY_DELAYS):
            if delay:
                self.log(f"retrying the model in {delay}s")
                for _ in range(delay * 10):
                    if cancel and cancel.is_set():
                        raise Cancelled
                    time.sleep(0.1)
            try:
                r = requests.post(f"{self.url}/chat/completions", json=body, timeout=300, headers={"Authorization": f"Bearer {self.key}"})
                if r.status_code == 400 and "context" in r.text.lower() and with_tools:
                    raise OverflowError(r.text[:200])
                if r.status_code >= 500 or r.status_code == 429:
                    self.log(f"model HTTP {r.status_code}: {r.text[:200]}")
                    continue
                r.raise_for_status()
                return r.json()["choices"][0]["message"]
            except (requests.ConnectionError, requests.Timeout) as err:
                self.log(f"model unreachable: {err}")
        raise RuntimeError("The assistant model server isn't answering.")

    # -------------------------------------------------------------- memory
    def system(self):
        from couchbox import settings

        text = open(PROMPT).read().strip()
        st = settings.load()
        off = tools.disabled_tools(st)
        if off:
            text += "\n\nNot set up on this box (don't mention or use): " + ", ".join(sorted(off)) + "."
        if st["voice.notes"].strip():  # the household's own vocabulary (channel nicknames etc.)
            text += "\n\nAbout this household:\n" + st["voice.notes"].strip()
        text += "\n\nApps on the home screen: " + ", ".join(n for _, n in tools.home_apps()) + "."
        text += "\nNow: " + time.strftime("%A %B %-d, " + ("%H:%M" if settings.derived(st)["clock24"] else "%-I:%M %p")) + "."
        if self.summary:
            text += "\n\nEarlier in this conversation:\n" + self.summary
        return {"role": "system", "content": text}

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
        turn = [{"role": "user", "content": f"{text}\n\n[{tools.screen_summary()}]"}]
        self.turns.append(turn)
        for step in range(MAX_STEPS):
            if cancel.is_set():
                raise Cancelled
            status("thinking", "Thinking")
            try:
                msg = self.chat([self.system()] + self.history(), cancel=cancel)
            except OverflowError:
                self.compact(cancel)
                msg = self.chat([self.system()] + self.history(), cancel=cancel)
            if cancel.is_set():
                raise Cancelled
            calls = msg.get("tool_calls") or []
            entry = {"role": "assistant", "content": msg.get("content") or ""}
            if calls:
                entry["tool_calls"] = calls
            turn.append(entry)
            if not calls:
                reply = (msg.get("content") or "Done.").strip()
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
                turn.append({"role": "tool", "tool_call_id": c.get("id", ""), "content": result[:TOOL_RESULT_CHARS]})
        return "I couldn't finish that in time."
