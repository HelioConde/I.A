"use strict";
/* Node-only contract tests. No browser/mic/network/Windows/model required. */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const script = fs.readFileSync(path.join(__dirname, "../chat/luna-call.js"), "utf8");
const IDS = [
  "voiceCallCore", "voiceCallState", "voiceCallDetail", "voiceCallTranscript",
  "voiceCallAnswer", "startVoiceCall", "endVoiceCall", "muteVoiceCall",
  "interruptVoiceCall", "openVoiceCall", "closeVoiceCall", "voiceCallPanel",
  "retryVoiceCall", "testVoiceCallMic", "testVoiceCallTts",
  "messageInput",
];

function harness() {
  const controls = new Map(IDS.map(id => [id, {
    id, textContent:"", value:"", disabled:false, hidden:false, dataset:{},
    listeners:{},
    addEventListener(name, fn) { this.listeners[name] = fn; },
    dispatchEvent() {},
    click() { if (this.disabled) return; const fn = this.listeners.click; return fn?.(); },
  }]));
  const recognition = [];
  const timers = new Map();
  let nextTimer = 0;
  let cancellation = 0;
  let sent = 0;
  let speechCancel = 0;
  const utterances = [];
  let sending = false;
  class FakeSpeech {
    static available() { return Promise.resolve("available"); }
    constructor() { this.processLocally = false; this.started = false; this.aborted = false; recognition.push(this); }
    start() { this.started = true; }
    stop() { this.onend?.(); }
    abort() { this.aborted = true; this.onend?.(); }
  }
  FakeSpeech.prototype.processLocally = true;
  class FakeUtterance {
    constructor(text) { this.text = text; }
  }
  const listeners = new Map();
  const w = {
    SpeechRecognition: FakeSpeech,
    micStateForCall: {available:true},
    SpeechSynthesisUtterance: FakeUtterance,
    lunaAppState: {sending:false},
    speechSynthesis: {
      getVoices() { return [{localService:true, lang:"pt-BR"}]; },
      speak(utterance) { utterances.push(utterance); },
      cancel() { speechCancel++; },
    },
    addEventListener(type, listener) {
      (listeners.get(type) || (listeners.set(type, []), listeners.get(type))).push(listener);
    },
    dispatchEvent(event) { for (const listener of listeners.get(event.type) || []) listener(event); },
    stopVoiceCallMessage: async () => { cancellation++; },
    sendVoiceCallMessage: async () => { sent++; w.lunaAppState.sending=true; },
  };
  const context = {
    window:w,
    document: {getElementById(id) { const control=controls.get(id); assert.ok(control,"Missing DOM: "+id); return control; }},
    SpeechSynthesisUtterance:FakeUtterance,
    CustomEvent:class { constructor(type, options) { this.type=type; this.detail=options?.detail; }},
    Event:class { constructor(type, options) { this.type=type; this.bubbles=options?.bubbles; }},
    setTimeout(fn,ms) { const id=++nextTimer; timers.set(id,{fn,ms}); return id; },
    clearTimeout(id) { timers.delete(id); },
    queueMicrotask,
  };
  vm.runInNewContext(script, context, {filename:"luna-call.js"});
  return {
    w, controls, recognition, utterances, timers,
    get sent() {return sent;},
    get cancellation() {return cancellation;},
    get speechCancel() {return speechCancel;},
    set sending(value) { sending=value; w.lunaAppState.sending=value; },
    click(id) { return controls.get(id).click(); },
    fireTimer() { const [id, entry] = timers.entries().next().value || []; if (!entry) return false; timers.delete(id); entry.fn(); return true; },
    state() { return controls.get("voiceCallCore").dataset.callState; },
    async drain() { await Promise.resolve(); await Promise.resolve(); },
    chat(kind, answer) { w.dispatchEvent({type:"luna:chat",detail:{kind,answer}}); },
    final(rec,text) {
      rec.onresult({resultIndex:0, results:[{isFinal:true, 0:{transcript:text}}]});
    },
  };
}

test("does not start microphone or download anything on page load", () => {
  const h=harness();
  assert.equal(h.recognition.length,0);
  assert.equal(h.sent,0);
  assert.equal(h.state(),undefined); // Initial HUD stays untouched until the user starts.
});

test("start uses on-device pt-BR and ending stops listening", () => {
  const h=harness();
  h.click("startVoiceCall");
  assert.equal(h.state(),"listening");
  assert.equal(h.w.lunaVoiceCallActive,true);
  assert.equal(h.recognition.length,1);
  assert.equal(h.recognition[0].lang,"pt-BR");
  assert.equal(h.recognition[0].processLocally,true);
  assert.equal(h.recognition[0].started,true);
  h.click("endVoiceCall");
  assert.equal(h.recognition[0].aborted,true);
  assert.equal(h.w.lunaVoiceCallActive,false);
  assert.equal(h.state(),"ended");
});

test("silence timer is removed when user resumes talking", () => {
  const h=harness();
  h.click("startVoiceCall");
  const rec=h.recognition[0];
  rec.onspeechend();
  assert.equal(h.state(),"transcribing");
  assert.equal(h.timers.size,1);
  rec.onspeechstart();
  assert.equal(h.state(),"speech");
  assert.equal(h.timers.size,0);
});

test("final STT after speechend must not erase the silence timer", () => {
  const h=harness();
  h.click("startVoiceCall");
  const rec=h.recognition[0];
  rec.onspeechend();
  assert.equal(h.timers.size,1);
  h.final(rec,"Final da frase");
  assert.equal(h.timers.size,1,"Final recognition result is not renewed speech");
  const timer=[...h.timers.values()][0];
  assert.equal(timer.ms,1000);
  timer.fn();
  assert.equal(h.sent,1);
  assert.equal(h.state(),"thinking");
});

test("voice turn submits once, hangup cancels active call-owned request", async () => {
  const h=harness();
  h.click("startVoiceCall");
  const rec=h.recognition[0];
  h.final(rec,"Explique o Brain-SSD");
  rec.onend();
  assert.equal(h.sent,1);
  assert.equal(h.state(),"thinking");
  h.click("endVoiceCall");
  assert.equal(h.cancellation,1);
  assert.equal(h.state(),"ended");
  await h.drain();
  h.chat("done","Resposta tardia");
  assert.equal(h.utterances.length,0,"Late answer must not speak after hangup");
  assert.equal(h.recognition.length,1,"Must not restart microphone after hangup");
});

test("manual interruption during TTS cancels voice and resumes listening", async () => {
  const h=harness();
  h.click("startVoiceCall");
  const rec=h.recognition[0];
  h.final(rec,"Diga olá");
  rec.onend();
  h.sending=false;
  h.chat("done","Olá, tudo bem?");
  assert.equal(h.utterances.length,1);
  assert.equal(h.state(),"responding");
  h.click("interruptVoiceCall");
  await h.drain();
  assert.equal(h.state(),"listening");
  assert.equal(h.recognition.length,2);
  assert.equal(h.cancellation,0);
  assert.ok(h.speechCancel>=1);
});

test("manual interruption during Qwen generation resumes after stopped event", async () => {
  const h=harness();
  h.click("startVoiceCall");
  h.final(h.recognition[0],"Uma pergunta");
  h.recognition[0].onend();
  h.click("interruptVoiceCall");
  assert.equal(h.cancellation,1);
  h.chat("stopped"); // app.js publishes before clearing sending.
  h.sending=false;
  await h.drain();
  assert.equal(h.state(),"listening");
  assert.equal(h.recognition.length,2);
});

test("mute prevents listening after TTS and no automatic microphone permission", async () => {
  const h=harness();
  h.click("startVoiceCall");
  h.click("muteVoiceCall");
  h.chat("done","Resposta da Luna");
  assert.equal(h.state(),"responding");
  h.utterances[0].onend();
  await h.drain();
  assert.equal(h.recognition.length,1);
  assert.equal(h.state(),"muted"); // No misleading responding status once TTS ends.
  h.click("muteVoiceCall");
  assert.equal(h.recognition.length,2);
  assert.equal(h.state(),"listening");
});

test("cannot start a voice call while unrelated typed chat is sending", () => {
  const h=harness();
  h.sending=true;
  h.click("startVoiceCall");
  assert.equal(h.state(),"error");
  assert.equal(h.recognition.length,0);
  assert.equal(h.w.lunaVoiceCallActive,undefined);
});

test("no-speech is a recoverable quiet turn instead of a fatal call error", () => {
  const h = harness();
  h.click("startVoiceCall");
  const initial = h.recognition[0];
  initial.onerror({error:"no-speech"});
  assert.equal(h.state(),"listening");
  assert.equal(h.w.lunaVoiceCallActive,true);
  assert.equal(h.timers.size,1);
  assert.ok(h.controls.get("voiceCallDetail").textContent.includes("Retomando escuta"));
  assert.equal(h.sent,0);
  assert.ok(h.fireTimer());
  assert.equal(h.recognition.length,2);
  assert.equal(h.recognition[1].started,true);
  assert.equal(h.state(),"listening");
  h.click("endVoiceCall");
  assert.equal(h.timers.size,0);
  assert.equal(h.state(),"ended");
});

test("long repeated no-speech offers manual recovery without silently sending", () => {
  const h = harness();
  h.click("startVoiceCall");
  for (let i=0; i<10; i++) {
    const rec = h.recognition.at(-1);
    rec.onerror({error:"no-speech"});
    if (i<9) assert.ok(h.fireTimer());
  }
  assert.equal(h.state(),"error");
  assert.equal(h.sent,0);
  assert.equal(h.timers.size,0);
  assert.equal(h.controls.get("retryVoiceCall").hidden,false);
  h.click("retryVoiceCall");
  assert.equal(h.state(),"listening");
  assert.equal(h.recognition.length,11);
});

test("single no-speech ends may rearm listening with paced retry", () => {
  const h=harness();
  h.click("startVoiceCall");
  h.recognition[0].onend(); // no final transcript and no error
  assert.equal(h.state(),"listening");
  assert.equal(h.timers.size,1);
  h.fireTimer();
  assert.equal(h.recognition.length,2);
});

test("local voice test only runs on explicit click and uses offline Portuguese voice", () => {
  const h = harness();
  assert.equal(h.utterances.length,0);
  h.click("testVoiceCallTts");
  assert.equal(h.utterances.length,1);
  assert.equal(h.utterances[0].lang,"pt-BR");
  assert.equal(h.utterances[0].voice.localService,true);
  h.utterances[0].onstart();
  assert.equal(h.state(),"responding");
  h.utterances[0].onend();
  assert.equal(h.state(),"idle");
  assert.equal(h.recognition.length,0);
});
