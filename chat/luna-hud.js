"use strict";
/* Luna HUD: a presentation layer for verified Brain-SSD events only.
 * No screen capture, microphone activation, web search or file read occurs here.
 * Nothing is persisted by the HUD; existing chat permission gates remain in force.
 */
(() => {
  const element = id => document.getElementById(id);
  const layout = element("lunaLayout");
  const rail = element("lunaRail");
  if (!layout || !rail) return;

  const states = {
    starting: ["Inicializando", "Aguardando resposta do servidor local."],
    ready: ["À disposição", "Modelo local disponível para novos pedidos."],
    thinking: ["Processando", "Aguardando a resposta da solicitação enviada."],
    streaming: ["Respondendo", "Recebendo resposta do servidor local."],
    listening: ["Ouvindo", "Microfone local ativado pelo usuário."],
    verifying: ["Verificando", "Atualizando informações autorizadas."],
    error: ["Desconectada", "O serviço local não está disponível."],
  };
  const hud = { connection:"starting", sending:false, streaming:false, listening:false, lastState:"", permissions:null };
  const activity = element("lunaActivityLog");
  const media = window.matchMedia("(max-width: 900px)");

  function announce(message) {
    if (!message || activity.firstElementChild?.dataset.event === message) return;
    const item = document.createElement("li");
    item.textContent = message;
    item.dataset.event = message;
    activity.prepend(item);
    while (activity.children.length > 5) activity.lastElementChild.remove();
  }
  function state(mode) {
    const [label, description] = states[mode] || states.starting;
    if (hud.lastState === mode) return;
    hud.lastState = mode;
    layout.dataset.lunaMode = mode;
    element("lunaState").textContent = label;
    element("lunaStateDetail").textContent = description;
    const welcome = element("lunaWelcomeState");
    if (welcome) welcome.textContent = label + " · " + description;
  }
  function recalculate() {
    const mode = hud.listening ? "listening" :
      hud.sending ? (hud.streaming ? "streaming" : "thinking") :
      hud.connection === "ready" ? "ready" :
      hud.connection === "error" ? "error" : "starting";
    state(mode);
  }
  function setExpanded(expanded) {
    layout.classList.toggle("rail-collapsed", !expanded);
    element("lunaRailToggle").setAttribute("aria-expanded", String(expanded));
  }
  setExpanded(!media.matches);
  if (typeof media.addEventListener === "function") {
    media.addEventListener("change", event => setExpanded(!event.matches));
  }

  element("lunaRailToggle").addEventListener("click", () => {
    setExpanded(layout.classList.contains("rail-collapsed"));
  });

  function openPanel(id, isHidden) {
    const panel = element(id);
    if (!panel) return;
    if (isHidden(panel)) {
      const opener = element(id === "copilotPanel" ? "openCopilot" : "showDetails");
      if (opener) opener.click();
    }
  }
  element("lunaQuickCopilot").addEventListener("click", () =>
    openPanel("copilotPanel", panel => panel.hidden));
  element("lunaQuickMetrics").addEventListener("click", () =>
    openPanel("detailsPanel", panel => panel.hidden));

  document.querySelectorAll("[data-luna-prompt]").forEach(button => {
    button.addEventListener("click", () => {
      const composer = element("messageInput");
      if (!composer || composer.disabled) return;
      composer.value = button.dataset.lunaPrompt;
      composer.dispatchEvent(new Event("input", {bubbles:true}));
      composer.focus();
      // In particular, no automatic submission or tool action is performed.
    });
  });

  // Project context is limited to explicit paths typed in Copilot's own UI.
  // It does not inspect files or infer which window the user is using.
  function updateProject() {
    const text = element("copilotProjectPath")?.value.trim() ||
                 element("copilotPath")?.value.trim() || "";
    let label = "Nenhum selecionado";
    if (text) {
      const parts = text.replace(/[\\/]+$/, "").split(/[\\/]/).filter(Boolean);
      label = parts[parts.length - 1]?.slice(0, 62) || "Caminho selecionado";
    }
    element("lunaRailProject").textContent = label;
    element("lunaRailProject").title = text
      ? "Pasta/arquivo informado manualmente no Copiloto" : "Nenhum caminho informado";
  }
  ["copilotProjectPath","copilotPath"].forEach(id => {
    element(id)?.addEventListener("input", updateProject);
  });
  updateProject();

  window.addEventListener("luna:connection", event => {
    const data = event.detail || {};
    const previous = hud.connection;
    hud.connection = data.status === "ready" ? "ready" :
      data.status === "error" ? "error" : "starting";
    element("lunaRailModel").textContent = data.model || "Qwen local";
    element("lunaRailProfile").textContent = data.profile || "Não informado";
    element("lunaModelStatus").textContent = hud.connection === "ready"
      ? (data.inference_verified ? "Validado na sessão" : "Aguardando primeira resposta")
      : "Indisponível";
    recalculate();
    if (previous !== hud.connection) {
      announce(hud.connection === "ready" ? "Servidor local disponível" :
        hud.connection === "error" ? "Servidor local indisponível" :
        "Verificando conexão local");
    }
  });

  window.addEventListener("luna:permission", event => {
    const info = event.detail || {};
    hud.permissions = info;
    element("lunaRailFiles").textContent =
      info.files_enabled ? "Autorizados" : "Desativados";
    element("lunaRailScreen").textContent =
      info.screen_enabled ? "Sob demanda" : "Desativada";
    if (info.error) {
      element("lunaRailFiles").textContent = "Indisponível";
      element("lunaRailScreen").textContent = "Indisponível";
    }
  });

  window.addEventListener("luna:chat", event => {
    const kind = event.detail?.kind;
    if (kind === "send") {
      hud.sending = true;
      hud.streaming = false;
      announce("Mensagem enviada · processamento solicitado");
    } else if (kind === "stream") {
      hud.streaming = true;
    } else if (kind === "done") {
      hud.sending = false;
      hud.streaming = false;
      announce("Resposta recebida");
    } else if (kind === "stopped") {
      hud.sending = false;
      hud.streaming = false;
      announce("Resposta interrompida");
    } else if (kind === "failed") {
      hud.sending = false;
      hud.streaming = false;
      announce("Resposta não concluída");
    }
    recalculate();
  });

  window.addEventListener("luna:microphone", event => {
    hud.listening = event.detail?.active === true;
    if (hud.listening) announce("Microfone local ativado manualmente");
    recalculate();
  });

  recalculate();
})();
