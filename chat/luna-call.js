"use strict";
/* Local browser voice-call controller.  It owns no audio recording or backend
   speech service: Web Speech must advertise processLocally before activation. */
(() => {
  const byId = id => document.getElementById(id);
  const Speech = window.SpeechRecognition || window.webkitSpeechRecognition;
  const state = {active:false, muted:false, recognition:null, finalText:"", interimText:"", silenceTimer:null,
    speaking:false, expectingAnswer:false, utterance:null, turn:0, recognitionFailed:false, emptyRestarts:0};
  const silenceMs = 1000;
  const status = {
    idle:["Pronta para iniciar.","Clique para iniciar; o navegador pedirá o microfone somente então."],
    initializing:["Preparando áudio","Confirmando reconhecimento local pt-BR."],
    listening:["Luna está ouvindo","Fale naturalmente. A fala termina após um breve silêncio."],
    speech:["Você está falando","Capturando a transcrição local parcial."],
    transcribing:["Processando sua fala","Finalizando a transcrição local."],
    thinking:["Luna está pensando","Pergunta enviada ao Qwen local."],
    responding:["Luna está falando","Microfone pausado para evitar eco. Use Interromper resposta para falar antes."],
    interrupted:["Resposta interrompida","A geração e a voz foram canceladas."],
    muted:["Microfone desligado","A ligação permanece aberta; reative quando quiser falar."],
    error:["Erro de áudio","A ligação foi preservada, mas a escuta automática foi pausada."],
    ended:["Ligação encerrada","Microfone, reconhecimento e fala foram desligados."]
  };
  function setState(name, detail) {
    const pair = status[name] || status.error;
    byId("voiceCallCore").dataset.callState = name;
    byId("voiceCallState").textContent = pair[0];
    byId("voiceCallDetail").textContent = detail || pair[1];
    window.dispatchEvent(new CustomEvent("luna:call-state", {detail:{state:name}}));
  }
  function clearSilence() { if (state.silenceTimer) clearTimeout(state.silenceTimer); state.silenceTimer = null; }
  function setTranscript() { byId("voiceCallTranscript").textContent = (state.finalText + " " + state.interimText).trim() || "Ouvindo..."; }
  function supportsLocalRecognition() {
    return Boolean(Speech && window.micStateForCall?.available !== false &&
      ("processLocally" in Speech.prototype) && typeof Speech.available === "function");
  }
  function localVoice() {
    if (!("speechSynthesis" in window) || !("SpeechSynthesisUtterance" in window)) return null;
    const voices = window.speechSynthesis.getVoices();
    return voices.find(v => v.localService && v.lang.toLowerCase() === "pt-br") ||
      voices.find(v => v.localService && v.lang.toLowerCase().startsWith("pt")) || null;
  }
  function cleanForSpeech(text) {
    return String(text || "").replace(/```[\s\S]*?```/g, " código omitido. ")
      .replace(/https?:\/\/\S+/g, " link omitido. ").replace(/[`*_#>[\]{}]/g, " ")
      .replace(/\s+/g, " ").trim().slice(0, 6000);
  }
  function stopRecognition() {
    clearSilence();
    const recognition = state.recognition;
    state.recognition = null;
    if (recognition) try { recognition.abort(); } catch (_) {}
  }
  function stopSpeech() {
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    state.speaking = false; state.utterance = null;
  }
  function buttons() {
    byId("startVoiceCall").disabled = state.active;
    byId("endVoiceCall").disabled = !state.active;
    byId("muteVoiceCall").disabled = !state.active;
    byId("interruptVoiceCall").disabled = !state.active || (!state.speaking && !state.expectingAnswer && !window.appVoiceSending?.());
    byId("muteVoiceCall").textContent = state.muted ? "Ativar microfone" : "Silenciar microfone";
  }
  function resumeListeningAfterChat() {
    // app.js broadcasts luna:chat during its finally block, before it clears
    // app.sending; resume in the next microtask to avoid dropping this turn.
    queueMicrotask(() => {
      if (state.active && !state.muted && !state.speaking) beginListening();
    });
  }
  function beginListening() {
    if (!state.active || state.muted || state.speaking || window.appVoiceSending?.()) return;
    if (!supportsLocalRecognition()) { setState("error", "Reconhecimento local pt-BR não está pronto. Instale/verifique o pacote no controle Falar (local)."); buttons(); return; }
    stopRecognition(); state.finalText = ""; state.interimText = ""; setTranscript();
    const recognition = new Speech(); recognition.lang = "pt-BR"; recognition.processLocally = true;
    recognition.continuous = true; recognition.interimResults = true;
    state.recognition = recognition; state.recognitionFailed = false; setState("listening"); buttons();
    recognition.onspeechstart = () => {
      if (state.recognition !== recognition) return;
      clearSilence(); // User resumed speaking before the silence threshold.
      setState("speech");
    };
    recognition.onspeechend = () => {
      if (state.recognition !== recognition) return;
      clearSilence(); setState("transcribing");
      state.silenceTimer = setTimeout(() => { if (state.recognition === recognition) recognition.stop(); }, silenceMs);
    };
    recognition.onresult = event => {
      if (state.recognition !== recognition) return;
      // Final transcript results may arrive AFTER onspeechend; do not clear
      // the silence timer here or continuous recognition could never finish.
      // Only a new onspeechstart event proves speech has resumed.
      let finalPart = "", interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const part = event.results[i][0]?.transcript || "";
        if (event.results[i].isFinal) finalPart += part + " "; else interim += part + " ";
      }
      if (finalPart) state.finalText = (state.finalText + " " + finalPart).trim();
      state.interimText = interim.trim(); setTranscript();
    };
    recognition.onerror = event => {
      if (state.recognition !== recognition) return;
      state.recognition = null; state.recognitionFailed = true;
      const reason = event.error || "desconhecido";
      if (reason === "aborted" && !state.active) return;
      setState("error", reason === "not-allowed" || reason === "service-not-allowed"
        ? "Microfone bloqueado. Autorize o microfone apenas para a página local da Luna."
        : "Reconhecimento local falhou: " + reason + "."); buttons();
    };
    recognition.onend = () => {
      if (state.recognition !== recognition) return;
      state.recognition = null; clearSilence();
      const text = state.finalText.trim(); state.interimText = ""; setTranscript();
      if (state.recognitionFailed) return;
      if (text) { state.emptyRestarts = 0; void submitTurn(text); }
      else if (state.active && !state.muted) {
        state.emptyRestarts += 1;
        if (state.emptyRestarts > 3) setState("error", "O microfone encerrou repetidamente sem fala. Encerre e reinicie a ligação; verifique a permissão e o pacote pt-BR.");
        else setTimeout(() => { if (state.active && !state.muted && !state.recognition && !state.recognitionFailed) beginListening(); }, 350);
      }
    };
    try { recognition.start(); } catch (_) { state.recognition = null; setState("error", "O navegador não iniciou o microfone local."); buttons(); }
  }
  async function submitTurn(text) {
    if (!state.active || state.muted || state.expectingAnswer || window.appVoiceSending?.()) return;
    state.expectingAnswer = true; state.turn += 1; setState("thinking"); buttons();
    const input = byId("messageInput"); input.value = text; input.dispatchEvent(new Event("input", {bubbles:true}));
    try { await window.sendVoiceCallTranscript(); } catch (_) { setState("error", "A solicitação ao Qwen local não pôde ser iniciada."); }
    finally { state.expectingAnswer = false; buttons(); }
  }
  function speakAnswer(answer) {
    const text = cleanForSpeech(answer); const voice = localVoice();
    if (!state.active || !text) { if (state.active) resumeListeningAfterChat(); return; }
    if (!voice) { setState("error", "Não há voz portuguesa local disponível no navegador."); return; }
    stopSpeech(); state.speaking = true; setState("responding"); buttons();
    const utterance = new SpeechSynthesisUtterance(text); utterance.lang = "pt-BR"; utterance.voice = voice; utterance.rate = 1.0; utterance.volume = 1.0;
    state.utterance = utterance;
    utterance.onend = () => { if (state.utterance !== utterance) return; state.speaking = false; state.utterance = null; buttons(); if (state.active && state.muted) setState("muted"); else resumeListeningAfterChat(); };
    utterance.onerror = () => { if (state.utterance !== utterance) return; state.speaking = false; state.utterance = null; setState("error", "A voz local não conseguiu reproduzir a resposta."); buttons(); };
    try { window.speechSynthesis.speak(utterance); } catch (_) { utterance.onerror(); }
  }
  function interrupt() {
    const pendingVoiceTurn = state.expectingAnswer && Boolean(window.appVoiceSending?.());
    stopSpeech();
    stopRecognition();
    state.expectingAnswer = false;
    setState("interrupted");
    buttons();
    if (pendingVoiceTurn && window.stopVoiceCallGeneration) {
      void window.stopVoiceCallGeneration();
      // The 'stopped' event will restart listening once app.sending is cleared.
    } else if (state.active && !state.muted) {
      resumeListeningAfterChat();
    }
  }
  function endCall() {
    const pendingVoiceTurn = state.expectingAnswer && Boolean(window.appVoiceSending?.());
    state.active = false;
    state.muted = false;
    state.expectingAnswer = false;
    stopRecognition();
    stopSpeech();
    window.lunaVoiceCallActive = false;
    setState("ended");
    buttons();
    // Cancel ONLY generation submitted by this call, not unrelated typed chat.
    if (pendingVoiceTurn && window.stopVoiceCallGeneration) {
      void window.stopVoiceCallGeneration();
    }
  }
  function startCall() {
    if (window.appVoiceSending?.()) {
      setState("error", "Aguarde o término da resposta atual antes de iniciar outra ligação.");
      return;
    }
    if (!supportsLocalRecognition()) { setState("error", "Reconhecimento local pt-BR indisponível. Use Verificar/Instalar pt-BR offline antes de iniciar. Chrome/Edge podem não oferecer esse recurso."); return; }
    if (!localVoice()) { setState("error", "Não há voz portuguesa local instalada neste navegador."); return; }
    state.active = true; state.muted = false; state.emptyRestarts = 0; state.recognitionFailed = false; window.lunaVoiceCallActive = true; setState("initializing"); buttons(); beginListening();
  }
  byId("openVoiceCall").addEventListener("click", () => { byId("voiceCallPanel").hidden = false; });
  byId("closeVoiceCall").addEventListener("click", () => { endCall(); byId("voiceCallPanel").hidden = true; });
  byId("startVoiceCall").addEventListener("click", startCall);
  byId("endVoiceCall").addEventListener("click", endCall);
  byId("muteVoiceCall").addEventListener("click", () => { if (!state.active) return; state.muted = !state.muted; if (state.muted) { stopRecognition(); setState("muted"); } else beginListening(); buttons(); });
  byId("interruptVoiceCall").addEventListener("click", interrupt);
  window.addEventListener("luna:chat", event => { const data = event.detail || {}; if (!state.active) return; if (!state.expectingAnswer) return; if (data.kind === "done") { byId("voiceCallAnswer").textContent = data.answer || "Resposta vazia."; speakAnswer(data.answer); } else if (data.kind === "stopped") {
      state.expectingAnswer = false;
      setState("interrupted");
      buttons();
      resumeListeningAfterChat();
    } else if (data.kind === "failed") { setState("error", "O Qwen local não concluiu a resposta."); buttons(); } });
  window.micStateForCall = window.micStateForCall || {available:false};
  window.appVoiceSending = () => Boolean(window.lunaAppState?.sending);
  window.sendVoiceCallTranscript = () => window.sendVoiceCallMessage();
  window.stopVoiceCallGeneration = () => window.stopVoiceCallMessage();
  buttons();
})();
