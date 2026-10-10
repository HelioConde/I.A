"use strict";
const $ = id => document.getElementById(id);
const app = { ready:false, sending:false, messages:[], conversationId:null, conversations:[], requestId:null, abortController:null, streamStarted:false };
const composer = $("messageInput");
const log = $("messages");

async function requestJson(path, options = {}) {
  const response = await fetch(path, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "Falha ao acessar o histórico local.");
  return payload;
}
async function refreshEpisodicMemory() {
  const status = $("episodicStatus");
  const list = $("episodicList");
  try {
    const payload = await requestJson("/api/memories", {cache:"no-store"});
    $("saveMemory").disabled = !payload.enabled;
    status.textContent = payload.enabled
      ? "Notas salvas só neste computador. A IA recupera pistas relacionadas; você pode apagar a qualquer momento."
      : "Desativadas. Reinicie com --episodic-memory para permitir notas explícitas.";
    list.replaceChildren();
    if (!payload.enabled) return;
    for (const memory of payload.memories || []) {
      const row = document.createElement("div");
      row.className = "episodic-item";
      const caption = document.createElement("span");
      caption.textContent = memory.content;
      caption.title = memory.content;
      const del = document.createElement("button");
      del.type = "button";
      del.textContent = "×";
      del.title = "Apagar esta lembrança";
      del.setAttribute("aria-label", "Apagar lembrança: " + memory.content.slice(0,60));
      del.addEventListener("click", async () => {
        if (!window.confirm("Apagar esta nota da memória episódica local?")) return;
        try {
          await requestJson("/api/memories/" + encodeURIComponent(memory.id), {
            method:"DELETE", headers:{"Origin":window.location.origin}
          });
          await refreshEpisodicMemory();
        } catch (error) {
          window.alert("Erro ao apagar memória: " + error.message);
        }
      });
      row.append(caption,del);
      list.appendChild(row);
    }
  } catch (_) {
    status.textContent = "Memória episódica indisponível.";
    $("saveMemory").disabled = true;
  }
}
async function saveEpisodicMemory() {
  if (app.sending) return;
  const note = window.prompt(
    "Guardar uma lembrança local (máximo 500 caracteres)? Só salve informações que você quer que a IA recupere em outras conversas. Não inclua senhas nem dados confidenciais."
  );
  if (note === null || !note.trim()) return;
  try {
    await requestJson("/api/memories", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({content:note.trim()})
    });
    await refreshEpisodicMemory();
  } catch (error) {
    window.alert("Não foi possível guardar a lembrança: " + error.message);
  }
}

function renderConversations() {
  const container = $("conversationList");
  container.replaceChildren();
  if (!app.conversations.length) {
    const empty = document.createElement("p");
    empty.className = "history-empty";
    empty.textContent = "As suas conversas aparecerão aqui.";
    container.appendChild(empty);
    return;
  }
  for (const conversation of app.conversations) {
    const row = document.createElement("div");
    row.className = "conversation-row" + (conversation.id === app.conversationId ? " active" : "");
    const open = document.createElement("button");
    open.className = "conversation-open";
    open.type = "button";
    open.textContent = conversation.title || "Nova conversa";
    open.title = conversation.title || "Nova conversa";
    open.addEventListener("click", () => openConversation(conversation.id));
    const remove = document.createElement("button");
    remove.className = "conversation-delete";
    remove.type = "button";
    remove.textContent = "×";
    remove.title = "Excluir esta conversa";
    remove.setAttribute("aria-label", "Excluir conversa: " + (conversation.title || "Nova conversa"));
    remove.addEventListener("click", () => deleteConversation(conversation.id));
    row.append(open, remove);
    container.appendChild(row);
  }
}
async function refreshConversations() {
  try {
    const result = await requestJson("/api/conversations", {cache:"no-store"});
    app.conversations = Array.isArray(result.conversations) ? result.conversations : [];
    renderConversations();
  } catch (_) {
    $("conversationList").textContent = "Não foi possível ler o histórico local.";
  }
}
async function openConversation(identifier) {
  if (app.sending) return;
  try {
    const result = await requestJson("/api/conversations/" + encodeURIComponent(identifier), {cache:"no-store"});
    app.conversationId = identifier;
    app.messages = result.messages || [];
    log.replaceChildren();
    if (!app.messages.length) showWelcome();
    for (const message of app.messages) addMessage(message.role, message.content);
    renderConversations();
    closeMenu();
    composer.focus();
  } catch (error) {
    window.alert("Não foi possível abrir a conversa: " + error.message);
  }
}
async function deleteConversation(identifier) {
  if (app.sending) return;
  if (!window.confirm("Excluir esta conversa do histórico local?")) return;
  try {
    await requestJson("/api/conversations/" + encodeURIComponent(identifier),
      {method:"DELETE", headers:{"Origin":window.location.origin}});
    if (app.conversationId === identifier) resetChat();
    await refreshConversations();
  } catch (error) {
    window.alert("Não foi possível excluir a conversa: " + error.message);
  }
}
function showWelcome() {
  const welcome = document.createElement("div");
  welcome.className = "welcome";
  welcome.id = "welcome";
  welcome.innerHTML = '<div class="hero-symbol" aria-hidden="true">✺</div><h1>Nova conversa</h1><p>Envie uma pergunta para conversar com a IA local.</p>';
  log.appendChild(welcome);
}

function setConnection(state, detail = "", verified = false) {
  app.ready = state === "ready";
  const banner = $("connectionBanner");
  banner.className = "connection-banner " + (state === "ready" ? "ready" : state === "error" ? "error" : "");
  $("connectionText").textContent = state === "ready" ? (verified ? "IA local validada nesta sessão" : "Modelo encontrado — faça sua primeira pergunta") :
    state === "error" ? (detail || "Não foi possível carregar o modelo local.") :
    "Preparando o modelo local...";
  $("sidebarStatus").textContent = state === "ready" ? "Modelo pronto" : state === "error" ? "Requer configuração" : "Iniciando...";
  $("sidebarDot").className = "status-dot " + (state === "ready" ? "ready" : state === "error" ? "error" : "");
  updateSend();
}
async function refreshStatus() {
  try {
    const res = await fetch("/api/status", {cache:"no-store"});
    if (!res.ok) throw new Error("servidor indisponível");
    const data = await res.json();
    setConnection(data.status, data.error, Boolean(data.inference_verified));
    $("modeInfo").textContent = data.profile ? ("Perfil: " + data.profile) : "Perfil: —";
    $("knowledgeInfo").textContent = data.knowledge_note || "Conhecimento SSD: verificando";
  } catch (_) {
    setConnection("error", "Servidor local desconectado. Abra o iniciador do Brain-SSD.");
  }
}
function updateSend() {
  $("sendButton").disabled = !app.ready || app.sending || !composer.value.trim();
  $("sendButton").hidden = app.sending;
  $("stopButton").hidden = !app.sending;
}
function fitComposer() {
  composer.style.height = "auto";
  composer.style.height = Math.min(composer.scrollHeight, 160) + "px";
  updateSend();
}
function addMessage(role, content, extraClass = "") {
  const row = document.createElement("div");
  row.className = "message " + role + (extraClass ? " " + extraClass : "");
  if (role !== "user") {
    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = "✺";
    avatar.setAttribute("aria-hidden", "true");
    row.appendChild(avatar);
  }
  const body = document.createElement("div");
  body.className = "message-body";
  if (role !== "user") {
    const label = document.createElement("p");
    label.className = "message-label";
    label.textContent = extraClass === "error" ? "Problema na execução" : "Brain-SSD";
    body.appendChild(label);
  }
  const text = document.createElement("div");
  text.className = "message-content";
  text.textContent = content;
  body.appendChild(text);
  if (role === "assistant" && !extraClass) {
    const copy = document.createElement("button");
    copy.className = "copy-message";
    copy.type = "button";
    copy.textContent = "Copiar resposta";
    copy.addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(text.textContent || ""); copy.textContent = "Copiado!"; }
      catch (_) { copy.textContent = "Cópia indisponível"; }
    });
    body.appendChild(copy);
  }
  row.appendChild(body);
  $("welcome")?.remove();
  log.appendChild(row);
  scrollBottom();
  return row;
}
function scrollBottom() {
  const area = document.querySelector(".conversation");
  area.scrollTop = area.scrollHeight;
}
function addThinking() {
  const row = addMessage("assistant", "");
  row.querySelector(".message-content").innerHTML = '<span class="pending-dots" aria-label="Gerando resposta"><i></i><i></i><i></i></span>';
  return row;
}
function humanTime(value) { return Number.isFinite(value) ? (value / 1000).toFixed(1) + " s" : "—"; }
function humanMemory(value) { return Number.isFinite(value) ? (value / (1024 * 1024)).toFixed(0) + " MiB" : "—"; }
function updateMetrics(data) {
  const m = data.metrics || {};
  $("detailLatency").textContent = humanTime(m.latency_ms);
  $("detailFirstToken").textContent = humanTime(m.ttft_ms);
  $("detailSpeed").textContent = Number.isFinite(m.tokens_per_second) ? m.tokens_per_second.toFixed(1) + " tokens/s" : "—";
  $("detailRam").textContent = humanMemory(m.working_set_bytes_max);
  $("detailPages").textContent = Number.isFinite(data.active_pages) ? String(data.active_pages) : "—";
  $("detailSources").textContent = Number.isFinite(data.sources_from_ssd) ? String(data.sources_from_ssd) : "—";
  $("detailEpisodes").textContent = Number.isFinite(data.episodic_memories_used) ? String(data.episodic_memories_used) : "—";
  const shadow = data.cognitive_shadow;
  $("detailAttention").textContent = shadow ? shadow.attention_selected_candidates + " candidatos / " + shadow.attention_candidate_bytes + " B" : "desativado";
  $("detailWorking").textContent = shadow ? shadow.working_memory_bytes + " B · " + shadow.working_topics.length + " tópicos" : "desativado";
}
async function send() {
  const question = composer.value.trim();
  if (!app.ready || app.sending || !question) return;
  app.sending = true;
  app.streamStarted = false;
  app.requestId = null;
  app.abortController = new AbortController();
  composer.value = "";
  fitComposer();
  addMessage("user", question);
  app.messages.push({role:"user", content:question});
  const pending = addThinking();
  updateSend();
  let completed = false;
  let interrupted = false;
  try {
    if (!app.conversationId) {
      const created = await requestJson("/api/conversations", {
        method:"POST", headers:{"Content-Type":"application/json"}, body:"{}"
      });
      app.conversationId = created.conversation.id;
    }
    if (app.abortController.signal.aborted) throw new DOMException("Interrompido", "AbortError");
    app.requestId = crypto.randomUUID();
    const response = await fetch("/api/chat/stream", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      signal:app.abortController.signal,
      body:JSON.stringify({
        message:question, conversation_id:app.conversationId,
        request_id:app.requestId
      })
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.error || "Falha ao iniciar a geração local.");
    }
    if (!response.body) throw new Error("O navegador não suporta o canal de resposta.");
    const stream = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let partial = "";
    const output = pending.querySelector(".message-content");
    output.textContent = "";
    const applyEvent = (packet) => {
      const lines = packet.split(/\r?\n/);
      const event = lines.find(line => line.startsWith("event:"))?.slice(6).trim();
      const data = lines.filter(line => line.startsWith("data:")).map(line => line.slice(5)).join("\n");
      if (!event || !data) return;
      const payload = JSON.parse(data);
      if (event === "started") app.streamStarted = true;
      if (event === "delta") {
        partial += payload.text || "";
        output.textContent = partial;
        scrollBottom();
      } else if (event === "done") {
        output.textContent = payload.answer;
        app.messages.push({role:"assistant", content:payload.answer});
        updateMetrics(payload);
        completed = true;
      } else if (event === "cancelled") {
        interrupted = true;
        output.textContent = "Resposta interrompida. A geração foi encerrada.";
        pending.classList.add("interrupted");
      } else if (event === "error") {
        throw new Error(payload.error || "Erro na geração de resposta.");
      }
    };
    try {
      while (true) {
        const {value, done} = await stream.read();
        if (done) break;
        buffer += decoder.decode(value, {stream:true});
        while (true) {
          const match = /\r?\n\r?\n/.exec(buffer);
          if (!match) break;
          const packet = buffer.slice(0, match.index);
          buffer = buffer.slice(match.index + match[0].length);
          applyEvent(packet);
        }
        if (completed || interrupted) break;
      }
    } finally {
      await stream.cancel().catch(() => {});
    }
    if (!completed && !interrupted) throw new Error("A conexão foi interrompida antes do fim da resposta.");
    if (completed) await refreshConversations();
  } catch (error) {
    if (error.name === "AbortError") {
      interrupted = true;
      pending.querySelector(".message-content").textContent = "Resposta interrompida.";
      pending.classList.add("interrupted");
    } else {
      pending.remove();
      addMessage("assistant", "Não consegui responder: " + error.message, "error");
    }
  } finally {
    app.sending = false;
    app.requestId = null;
    app.streamStarted = false;
    app.abortController = null;
    updateSend();
    scrollBottom();
    composer.focus();
  }
}
async function stopGeneration() {
  if (!app.sending || !app.abortController) return;
  if (!app.streamStarted || !app.requestId) {
    app.abortController.abort();
    return;
  }
  $("stopButton").disabled = true;
  try {
    const result = await requestJson("/api/chat/cancel", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({request_id:app.requestId})
    });
    if (!result.cancelled) app.abortController.abort();
  } catch (_) {
    app.abortController.abort();
  } finally {
    $("stopButton").disabled = false;
  }
}
function resetChat() {
  if (app.sending) return;
  app.messages = [];
  app.conversationId = null;
  log.replaceChildren();
  showWelcome();
  renderConversations();
  composer.value = "";
  fitComposer();
  closeMenu();
  composer.focus();
}
function closeMenu() {
  $("sidebar").classList.remove("open");
  $("backdrop").hidden = true;
}
$("chatForm").addEventListener("submit", event => { event.preventDefault(); send(); });
composer.addEventListener("input", fitComposer);
composer.addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault(); send();
  }
});
document.querySelectorAll("[data-prompt]").forEach(button => button.addEventListener("click", () => {
  composer.value = button.dataset.prompt;
  fitComposer();
  composer.focus();
}));
$("newChat").addEventListener("click", resetChat);
document.addEventListener("keydown", event => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
    event.preventDefault(); resetChat();
  }
  if (event.key === "Escape") { closeMenu(); $("detailsPanel").hidden = true; $("showDetails").setAttribute("aria-expanded","false"); }
});
$("openMenu").addEventListener("click", () => { $("sidebar").classList.add("open"); $("backdrop").hidden = false; });
$("closeMenu").addEventListener("click", closeMenu);
$("backdrop").addEventListener("click", closeMenu);
$("showDetails").addEventListener("click", () => {
  const visible = $("detailsPanel").hidden;
  $("detailsPanel").hidden = !visible;
  $("showDetails").setAttribute("aria-expanded", String(visible));
});
$("closeDetails").addEventListener("click", () => {
  $("detailsPanel").hidden = true;
  $("showDetails").setAttribute("aria-expanded","false");
});
$("stopButton").addEventListener("click", stopGeneration);
$("saveMemory").addEventListener("click", saveEpisodicMemory);
fitComposer();
refreshStatus();
refreshConversations();
refreshEpisodicMemory();
setInterval(refreshStatus, 3000);
