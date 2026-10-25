// Voice: what the remote's mic button does, and the OpenAI-compatible servers it uses.
import QtQuick

SettingsPage {
    id: p
    title: "Voice"
    subtitle: "Hold the remote's mic button and speak. Speech-to-text and the assistant run on servers you choose (any OpenAI-compatible API, on your own network or a service)."
    property string sttResult: ""
    property string llmResult: ""
    function testStt() {
        sttResult = "Testing…";
        T.call("voice.test_stt", {}, r => p.sttResult = r.message, e => p.sttResult = e);
    }
    function testLlm() {
        llmResult = "Testing…";
        T.call("voice.test_llm", {}, r => p.llmResult = r.message, e => p.llmResult = e);
    }
    function pickModel() {
        T.call("voice.models", {}, models => {
            if (!models.length) return T.askText(T.label("voice.llm.model"), T.settings["voice.llm.model"], false, x => T.set("voice.llm.model", x));
            T.pick("Assistant model", models.map(m => ({label: m, value: m})), T.settings["voice.llm.model"], m => T.set("voice.llm.model", m));
        });
    }
    rows: {
        T.rev;
        const s = T.settings;
        const mode = s["voice.mode"];
        return [
            T.row("voice.mode", {help: mode === "off" ? "The mic button shows how to set voice up."
                                 : mode === "dictation" ? "Speech goes into text boxes and searches, plus: pause, play, home, back, open <app>, volume, search for …"
                                 : "Ask for anything: “keep playing my show”, “new videos from …”. Needs both servers below."}),
            T.section("Speech-to-text"),
            T.row("voice.stt.url"),
            T.row("voice.stt.model"),
            T.secretRow("voice.stt.api_key", {help: "Only if the server needs one."}),
            T.row("voice.language"),
            T.action("Test speech-to-text", testStt, {value: sttResult, tone: sttResult.startsWith("Works") ? "good" : sttResult && sttResult !== "Testing…" ? "bad" : ""}),
            T.section("Assistant"),
            T.row("voice.llm.url"),
            T.row("voice.llm.model", {act: pickModel}),
            T.secretRow("voice.llm.api_key"),
            T.action("Test the assistant", testLlm, {value: llmResult, tone: llmResult.startsWith("Works") ? "good" : llmResult && llmResult !== "Testing…" ? "bad" : ""}),
            T.row("voice.notes", {help: "Tell the assistant about your household: nicknames for channels, who likes what."}),
        ];
    }
}
