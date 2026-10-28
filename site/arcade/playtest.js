/* Luna Arcade S1 — player review (entirely client-side, no service or storage). */
(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const form = $("playtest-form");
  if (!form) return;
  const status = $("playtest-status");
  const preview = $("playtest-report");
  const issueLink = $("playtest-github");
  const captureResult = $("playtest-capture-result");
  const issueBase = "https://github.com/HelioConde/I.A/issues/new";
  const allowedModes = new Set(["menu", "dungeon", "pause", "victory", "defeat"]);
  const maxText = 1200;
  let captured = null;
  let capturedAt = null;

  function say(message, error = false) {
    status.textContent = message;
    status.classList.toggle("playtest-error", error);
  }
  function safeField(id) {
    return String($(id).value || "").trim().slice(0, maxText);
  }
  function readSnapshot() {
    const fn = window.__LUNA_GAME_QA__?.snapshot;
    if (typeof fn !== "function") return null;
    try {
      const raw = fn();
      if (!raw || !allowedModes.has(raw.mode) || !Number.isFinite(raw.stage)) return null;
      const p = raw.player || {};
      return {
        mode: raw.mode,
        stage: Math.trunc(raw.stage),
        archetype: String(p.archetype || "desconhecida").slice(0, 20),
        x: Number.isFinite(p.x) ? p.x : null,
        y: Number.isFinite(p.y) ? p.y : null,
        hp: Number.isFinite(p.hp) ? p.hp : null,
        enemyCount: Array.isArray(raw.enemies) ? raw.enemies.length : null,
        score: Number.isFinite(raw.score) ? raw.score : null
      };
    } catch (_) {
      return null;
    }
  }
  function capture() {
    captured = readSnapshot();
    capturedAt = captured ? new Date().toISOString() : null;
    captureResult.textContent = captured
      ? "Capturado: " + captured.mode + " · região " + captured.stage + " · " + captured.archetype + " · HP " + (captured.hp ?? "—")
      : "Estado do motor indisponível. Você pode relatar normalmente.";
    render();
  }
  function report() {
    const type = safeField("playtest-type");
    const category = safeField("playtest-category");
    const character = safeField("playtest-class");
    const region = safeField("playtest-region");
    const device = safeField("playtest-device");
    const good = safeField("playtest-good");
    const problem = safeField("playtest-problem");
    const expected = safeField("playtest-expected");
    const gameVersion = document.querySelector(".version")?.textContent?.trim() || "não informada";
    const stageText = captured
      ? [
          "Modo: " + captured.mode, "Região: " + captured.stage,
          "Classe do motor: " + captured.archetype,
          "Posição: " + (captured.x ?? "—") + ", " + (captured.y ?? "—"),
          "Vida: " + (captured.hp ?? "—"),
          "Inimigos restantes: " + (captured.enemyCount ?? "—"),
          "Pontos: " + (captured.score ?? "—"),
          "Capturado em: " + capturedAt
        ].join("\n")
      : "Não capturado";
    return [
      "# Luna Arcade S1 — avaliação do jogador",
      "",
      "Versão: " + gameVersion,
      "Tipo: " + type,
      "Área: " + category,
      "Classe testada: " + character,
      "Região informada: " + region,
      "Dispositivo: " + device,
      "",
      "## O que funcionou",
      good || "Não informado",
      "",
      "## O que deu errado / pode melhorar",
      problem || "Não informado",
      "",
      "## Comportamento esperado / sugestão",
      expected || "Não informado",
      "",
      "## Diagnóstico do jogo (opcional)",
      stageText,
      "",
      "Observação: avaliação manual, não enviada automaticamente pelo jogo."
    ].join("\n");
  }
  function issueTitle() {
    const category = safeField("playtest-category");
    const type = safeField("playtest-type");
    return "[Luna Arcade S1] " + type + " · " + category;
  }
  function render() {
    const body = report();
    preview.value = body;
    const url = issueBase + "?title=" + encodeURIComponent(issueTitle()) + "&body=" + encodeURIComponent(body);
    // GitHub's prefilled URL is finite. Copying the report is always available.
    issueLink.href = url.length <= 6500 ? url : issueBase;
    issueLink.title = url.length <= 6500 ? "Abrir formulário preenchido no GitHub" : "Relatório longo: copie antes de abrir o GitHub";
    return body;
  }
  for (const el of form.querySelectorAll("select,textarea")) el.addEventListener("input", render);
  $("playtest-capture").addEventListener("click", () => {
    capture();
    say(captured ? "Estado da partida adicionado ao relatório. Nada foi enviado." : "Não foi possível capturar o estado; seu relato ainda funciona.");
  });
  $("playtest-copy").addEventListener("click", async () => {
    const body = render();
    try {
      if (!navigator.clipboard?.writeText) throw new Error("clipboard unavailable");
      await navigator.clipboard.writeText(body);
      say("Relatório copiado! Cole aqui na conversa com o ChatGPT e envie seu print, se tiver.");
    } catch (_) {
      preview.focus();
      preview.select();
      say("Selecione e copie o texto do relatório (Ctrl+C), depois cole no chat.", true);
    }
  });
  $("playtest-download").addEventListener("click", () => {
    const data = new Blob([render() + "\n"], {type: "text/plain;charset=utf-8"});
    const url = URL.createObjectURL(data);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "luna-arcade-s1-avaliacao.txt";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    say("Relatório TXT salvo no seu dispositivo. Você pode anexá-lo no chat.");
  });
  $("playtest-screenshot").addEventListener("click", () => {
    const canvas = $("game");
    if (!canvas?.toBlob) {
      say("Captura da cena indisponível neste navegador.", true);
      return;
    }
    canvas.toBlob(blob => {
      if (!blob) {
        say("Não foi possível capturar a cena.", true);
        return;
      }
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "luna-arcade-s1-cena.png";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      say("Cena PNG salva! Para mostrar os menus, use uma captura de tela do dispositivo.");
    }, "image/png");
  });
  form.addEventListener("submit", event => {
    event.preventDefault();
    render();
    say("Relatório pronto. Copie para o chat ou abra a issue no GitHub; o jogo não envia nada sozinho.");
  });
  render();
})();
