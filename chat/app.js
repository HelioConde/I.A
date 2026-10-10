"use strict";
const $ = id => document.getElementById(id);
const app = { ready:false, sending:false, messages:[], conversationId:null, conversations:[] };
const composer = $("messageInput");
const log = $("messages");

async function requestJson(path, options = {}) {
  const response = await fetch(path, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "Falha ao acessar o histórico local.");
  return payload;
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
  $("detailSpeed").textContent = Number.isFinite(m.tokens_per_second) ? m.tokens_per_second.toFixed(1) + " tokens/s" : "—";
  $("detailRam").textContent = humanMemory(m.working_set_bytes_max);
  $("detailPages").textContent = Number.isFinite(data.active_pages) ? String(data.active_pages) : "—";
  $("detailSources").textContent = Number.isFinite(data.sources_from_ssd) ? String(data.sources_from_ssd) : "—";
}
async function send() {
  const question = composer.value.trim();
  if (!app.ready || app.sending || !question) return;
  const history = app.messages.slice(-8);
  app.sending = true;
  composer.value = "";
  fitComposer();
  addMessage("user", question);
  app.messages.push({role:"user", content:question});
  const pending = addThinking();
  updateSend();
  try {
    if (!app.conversationId) {
      const created = await requestJson("/api/conversations", {
        method:"POST", headers:{"Content-Type":"application/json"},
        body:"{}"
      });
      app.conversationId = created.conversation.id;
    }
    const response = await fetch("/api/chat", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({message:question, conversation_id:app.conversationId})
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Não foi possível gerar a resposta.");
    pending.querySelector(".message-content").textContent = payload.answer;
    app.messages.push({role:"assistant", content:payload.answer});
    updateMetrics(payload);
    await refreshConversations();
  } catch (error) {
    pending.remove();
    addMessage("assistant", "Não consegui responder: " + error.message, "error");
  } finally {
    app.sending = false;
    updateSend();
    scrollBottom();
    composer.focus();
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
fitComposer();
refreshStatus();
refreshConversations();
setInterval(refreshStatus, 3000);
