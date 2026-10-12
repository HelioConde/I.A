"use strict";
/* Local browser voice-call controller.  It owns no audio recording or backend
   speech service: Web Speech must advertise processLocally before activation. */
(() => {
  const byId = id => document.getElementById(id);
  const Speech = window.SpeechRecognition || window.webkitSpeechRecognition;
  const state = {active:false, muted:false, recognition:null, finalText:"", interimText:"", silenceTimer:null,
    speaking:false, expectingAnswer:false, utterance:null, turn:0, recognitionFailed:false, emptyRestarts:0,
    restartTimer:null, testInProgress:false};
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
  function clearRestart() { if (state.restartTimer) clearTimeout(state.restartTimer); state.restartTimer = null; }
  function scheduleListeningRetry() {
    clearRestart();
    if (!state.active || state.muted || state.speaking || state.expectingAnswer) return;
    state.emptyRestarts += 1;
    if (state.emptyRestarts >= 10) {
      setState("error", "O navegador não reconheceu nenhuma fala em várias tentativas. Clique em Testar microfone; depois, Retomar escuta. Confira o microfone selecionado no Windows e o pacote pt-BR offline.");
      buttons();
      return;
    }
    const wait = Math.min(2500, 400 + state.emptyRestarts * 250);
    setState("listening", "Nenhuma fala detectada. Retomando escuta local (" + state.emptyRestarts + "/10)... Fale próximo ao microfone.");
    state.restartTimer = setTimeout(() => {
      state.restartTimer = null;
      if (state.active && !state.muted && !state.recognition && !state.speaking && !state.expectingAnswer) beginListening();
    }, wait);
  }
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
    byId("retryVoiceCall").hidden = !state.active || (state.recognition !== null && !state.recognitionFailed);
    byId("retryVoiceCall").disabled = !state.active || state.speaking || state.testInProgress;
    byId("testVoiceCallMic").disabled = state.testInProgress || state.speaking || state.expectingAnswer;
    byId("testVoiceCallTts").disabled = state.testInProgress || state.expectingAnswer || state.speaking;
  }
  function resumeListeningAfterChat() {
    // app.js broadcasts luna:chat during its finally block, before it clears
    // app.sending; resume in the next microtask to avoid dropping this turn.
    queueMicrotask(() => {
      if (state.active && !state.muted && !state.speaking && !state.recognition) {
        // If the chat still reports sending, its finally block has not
        // released the turn; retry once on the next task instead of stalling.
        if (window.appVoiceSending?.()) {
          clearRestart();
          state.restartTimer = setTimeout(() => {
            state.restartTimer = null;
            if (state.active && !state.muted && !state.speaking) beginListening();
          }, 100);
        } else beginListening();
      }
    });
  }
  function beginListening() {
    if (!state.active || state.muted || state.speaking || window.appVoiceSending?.()) return;
    if (!supportsLocalRecognition()) { setState("error", "Reconhecimento local pt-BR não está pronto. Instale/verifique o pacote no controle Falar (local)."); buttons(); return; }
    clearRestart(); stopRecognition(); state.finalText = ""; state.interimText = ""; setTranscript();
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
      if (finalPart) { state.finalText = (state.finalText + " " + finalPart).trim(); state.emptyRestarts = 0; }
      state.interimText = interim.trim(); setTranscript();
    };
    recognition.onerror = event => {
      if (state.recognition !== recognition) return;
      state.recognition = null; clearSilence();
      const reason = event.error || "desconhecido";
      if (reason === "no-speech") {
        // A quiet room is not a broken microphone. Browser Web Speech often
        // emits no-speech when its internal timeout expires; retry with backoff.
        state.recognitionFailed = false;
        scheduleListeningRetry();
        buttons();
        return;
      }
      if (reason === "aborted" && (!state.active || state.muted)) return;
      state.recognitionFailed = true;
      const descriptions = {
        "not-allowed":"Microfone bloqueado. Autorize o endereço local da Luna nas permissões do Chrome/Edge.",
        "service-not-allowed":"Reconhecimento bloqueado pelo navegador. Verifique as permissões de áudio.",
        "audio-capture":"Nenhum sinal de microfone disponível. Selecione o dispositivo correto no Windows e clique em Testar microfone.",
        "language-not-supported":"O pacote offline pt-BR não está disponível. Verifique/instale o pacote pelo botão Falar (local).",
        "network":"Falha do serviço de reconhecimento do navegador. A Luna não fará fallback para transcrição online.",
      };
      setState("error", descriptions[reason] || ("Reconhecimento local falhou: " + reason + ". Tente Retomar escuta."));
      buttons();
    };
    recognition.onend = () => {
      if (state.recognition !== recognition) return;
      state.recognition = null; clearSilence();
      const text = state.finalText.trim(); state.interimText = ""; setTranscript();
      if (state.recognitionFailed) return;
      if (text) { state.emptyRestarts = 0; void submitTurn(text); }
      else if (state.active && !state.muted) { scheduleListeningRetry(); }
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
    clearRestart(); stopRecognition();
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
    clearRestart(); stopRecognition();
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
  byId("retryVoiceCall").addEventListener("click", () => {
    if (!state.active || state.testInProgress) return;
    clearRestart(); state.emptyRestarts = 0; state.recognitionFailed = false;
    if (state.speaking || state.expectingAnswer) return;
    beginListening();
  });
  byId("testVoiceCallMic").addEventListener("click", async () => {
    if (state.testInProgress || state.speaking || state.expectingAnswer) return;
    if (!navigator.mediaDevices?.getUserMedia) {
      setState("error", "O navegador não disponibiliza o teste local do microfone neste endereço.");
      return;
    }
    state.testInProgress = true;
    const wasListening = state.active && !state.muted;
    clearRestart(); stopRecognition(); buttons();
    let stream = null, audio = null;
    try {
      setState("initializing", "Testando entrada do microfone por 3 segundos. Fale perto do microfone; nenhum áudio será gravado ou enviado.");
      // Microphone permission is requested ONLY by clicking "Testar microfone".
      stream = await navigator.mediaDevices.getUserMedia({audio:true, video:false});
      const AudioContextType = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextType) throw new Error("audio-context-unavailable");
      audio = new AudioContextType();
      const source = audio.createMediaStreamSource(stream);
      const analyser = audio.createAnalyser();
      analyser.fftSize = 1024;
      source.connect(analyser);
      const samples = new Uint8Array(analyser.fftSize);
      let peak = 0;
      const deadline = Date.now() + 3000;
      while (Date.now() < deadline && state.testInProgress) {
        analyser.getByteTimeDomainData(samples);
        let power = 0;
        for (const sample of samples) power += ((sample - 128) / 128) ** 2;
        peak = Math.max(peak, Math.sqrt(power / samples.length));
        await new Promise(resolve => setTimeout(resolve, 70));
      }
      setState(peak > 0.014 ? "listening" : "error",
        peak > 0.014
          ? "O microfone recebeu sinal de áudio. O teste não garante que o reconhecimento de fala pt-BR esteja funcionando."
          : "O microfone abriu, mas não houve sinal de voz suficiente. Verifique a entrada padrão do Windows, nível do microfone e permissões.");
    } catch (error) {
      setState("error", error?.name === "NotAllowedError"
        ? "Permissão do microfone negada pelo navegador. Autorize o endereço local e teste novamente."
        : "Não foi possível testar o microfone: " + (error?.name || "dispositivo indisponível") + ".");
    } finally {
      stream?.getTracks().forEach(track => track.stop());
      if (audio) try { await audio.close(); } catch (_) {}
      state.testInProgress = false; buttons();
      if (wasListening && state.active && !state.muted) {
        setState("interrupted", "Teste concluído. Clique em Retomar escuta para continuar a ligação.");
      }
    }
  });
  byId("testVoiceCallTts").addEventListener("click", () => {
    if (state.testInProgress || state.expectingAnswer || state.speaking) return;
    const voice = localVoice();
    if (!voice) {
      setState("error", "Nenhuma voz portuguesa local está disponível no navegador. Instale uma voz PT-BR no Windows e reinicie o Chrome/Edge.");
      return;
    }
    clearRestart(); stopRecognition(); stopSpeech();
    state.speaking = true; buttons();
    const utterance = new SpeechSynthesisUtterance("Olá! Sou a Luna. Esta é uma verificação da minha voz local.");
    utterance.lang = "pt-BR"; utterance.voice = voice;
    state.utterance = utterance;
    utterance.onstart = () => setState("responding", "Teste de reprodução por voz local. Se não ouvir nada, verifique a saída e o volume do Windows.");
    utterance.onend = () => {
      if (state.utterance !== utterance) return;
      state.utterance = null; state.speaking = false; buttons();
      if (state.active && !state.muted) resumeListeningAfterChat();
      else setState(state.active ? "muted" : "idle", "Teste de voz finalizado.");
    };
    utterance.onerror = () => {
      if (state.utterance !== utterance) return;
      state.utterance = null; state.speaking = false; buttons();
      setState("error", "A voz PT-BR local falhou. Verifique a voz instalada, o volume e a saída de áudio.");
    };
    try { window.speechSynthesis.speak(utterance); } catch (_) { utterance.onerror(); }
  });
  byId("openVoiceCall").addEventListener("click", () => { byId("voiceCallPanel").hidden = false; });
  byId("closeVoiceCall").addEventListener("click", () => { endCall(); byId("voiceCallPanel").hidden = true; });
  byId("startVoiceCall").addEventListener("click", startCall);
  byId("endVoiceCall").addEventListener("click", endCall);
  byId("muteVoiceCall").addEventListener("click", () => { if (!state.active) return; state.muted = !state.muted; if (state.muted) { clearRestart(); stopRecognition(); setState("muted"); } else { state.emptyRestarts = 0; beginListening(); } buttons(); });
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
