"""The Search app's back end: what typed text opens, the recent searches, the reader's
tidying, and the model's prompts and answers (through couchboxd's assistant.complete)."""

import json

import pytest

from couchbox import settings
from couchbox.services import search


def test_typed_text_opens_an_address_or_a_google_search():
    assert search.address("example.org") == "https://example.org"
    assert search.address("http://192.168.1.20:8080/x") == "http://192.168.1.20:8080/x"
    assert search.address("localhost:8971") == "https://localhost:8971"
    u = search.address("how tall is the eiffel tower")
    assert u.startswith("https://www.google.com/search?") and "q=how+tall+is+the+eiffel+tower" in u
    assert search.address("e.g.").startswith("https://www.google.com/search?")
    assert search.query_of(u) == "how tall is the eiffel tower"
    assert search.query_of("https://example.org/search?q=x") == ""
    assert search.is_consent("https://consent.google.com/ml?continue=x")


def test_history_keeps_the_newest_once(tmp_path):
    h = search.History(tmp_path / "h.json")
    assert h.load() == []
    h.add("pizza dough")
    h.add("Eiffel  tower")
    assert h.add("PIZZA DOUGH") == ["PIZZA DOUGH", "Eiffel tower"]
    for i in range(20):
        h.add(f"q{i}")
    assert len(h.load()) == search.HISTORY_MAX and h.load()[0] == "q19"
    assert h.clear() == [] and h.load() == []


def test_reader_blocks_are_tidied():
    a = search.blocks(
        {
            "title": "  A   title ",
            "site": "example.org",
            "blocks": [
                {"k": "p", "t": "One  two[12]\nthree[citation needed]"},
                {"k": "p", "t": "One two three"},
                {"k": "x", "t": "odd kind"},
                {"k": "h", "t": ""},
                {"k": "pre", "t": "  code\n  here"},
            ],
        }
    )
    assert a["title"] == "A title"
    assert a["blocks"] == [{"k": "p", "t": "One two three"}, {"k": "p", "t": "odd kind"}, {"k": "pre", "t": "code\n  here"}]
    assert a["minutes"] == 1
    assert search.page_text(search.DEMO_ARTICLE).startswith("The Eiffel Tower is a wrought-iron")
    assert "## How tall is it?" in search.page_text(search.DEMO_ARTICLE)
    assert len(search.page_text(search.DEMO_ARTICLE, 100)) <= 102


def test_prompts_carry_the_page_or_the_results():
    m = search.summary_messages(search.DEMO_ARTICLE)
    assert m[0]["role"] == "system" and "330 metres" in m[1]["content"] and "bullet" in m[1]["content"]
    m = search.summary_messages(search.DEMO_ARTICLE, "when was it built?")
    assert "when was it built?" in m[1]["content"]
    m = search.answer_messages("eiffel tower height", search.DEMO_RESULTS)
    assert "[1] Eiffel Tower - Wikipedia" in m[1]["content"] and "Search: eiffel tower height" in m[1]["content"]


def test_answers_are_cleaned_for_the_tv():
    t = search.clean_answer("<think>hmm</think>\n## Summary\n- **Tall**: 330 m\n* Old")
    assert t == "Summary\n• Tall: 330 m\n• Old"


def test_ask_model_goes_through_couchboxd(monkeypatch):
    with pytest.raises(search.NoModel):
        search.ask_model([{"role": "user", "content": "hi"}])
    settings.update({"voice.llm.url": "http://llm.example/v1", "voice.llm.model": "m"})
    seen = {}

    def call(method, timeout=30, **params):
        seen.update(method=method, **params)
        return {"text": "**Yes.**"}

    from couchbox import ipc

    monkeypatch.setattr(ipc, "call", call)
    assert search.ask_model([{"role": "user", "content": "hi"}], max_tokens=50) == "Yes."
    assert seen["method"] == "assistant.complete" and seen["max_tokens"] == 50


class Resp:
    def __init__(self, status, body):
        self.status_code, self.body = status, body
        self.text = json.dumps(body)

    def json(self):
        return self.body


def test_assistant_complete_calls_the_model(monkeypatch):
    import requests

    from couchbox.daemon import api, api_assistant

    with pytest.raises(api.UserError):
        api_assistant.complete([{"role": "user", "content": "hi"}])
    settings.update({"voice.llm.url": "http://llm.example/v1/", "voice.llm.model": "m"})
    sent = {}

    def post(url, json=None, timeout=None, headers=None):
        sent.update(url=url, body=json)
        return Resp(200, {"choices": [{"message": {"content": "ready"}}]})

    monkeypatch.setattr(requests, "post", post)
    msgs = [{"role": "system", "content": "s"}, {"role": "tool", "content": "dropped"}, {"role": "user", "content": "hi"}]
    assert api_assistant.complete(msgs, max_tokens=99999) == {"text": "ready"}
    assert sent["url"] == "http://llm.example/v1/chat/completions"
    assert [m["role"] for m in sent["body"]["messages"]] == ["system", "user"]
    assert sent["body"]["max_tokens"] == 4000 and "tools" not in sent["body"]
    monkeypatch.setattr(requests, "post", lambda *a, **k: Resp(200, {"choices": [{"message": {"content": ""}, "finish_reason": "length"}]}))
    with pytest.raises(api.UserError, match="ran out of room"):
        api_assistant.complete([{"role": "user", "content": "hi"}])
    monkeypatch.setattr(requests, "post", lambda *a, **k: Resp(500, {}))
    with pytest.raises(api.UserError):
        api_assistant.complete([{"role": "user", "content": "hi"}])
    with pytest.raises(api.UserError):
        api_assistant.complete([{"role": "user", "content": "x" * 70000}])
    assert api.METHODS["assistant.complete"].write is True
