"use strict";
const $ = id => document.getElementById(id);
const app = { ready:false, sending:false, messages:[] };
const composer = $("messageInput");
const log = $("messages");

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
    const response = await fetch("/api/chat", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({message:question, history})
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Não foi possível gerar a resposta.");
    pending.querySelector(".message-content").textContent = payload.answer;
    app.messages.push({role:"assistant", content:payload.answer});
    updateMetrics(payload);
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
  log.replaceChildren();
  const welcome = document.createElement("div");
  welcome.className = "welcome";
  welcome.id = "welcome";
  welcome.innerHTML = '<div class="hero-symbol" aria-hidden="true">✺</div><h1>Nova conversa</h1><p>Envie uma pergunta para conversar com a IA local.</p>';
  log.appendChild(welcome);
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
setInterval(refreshStatus, 3000);
