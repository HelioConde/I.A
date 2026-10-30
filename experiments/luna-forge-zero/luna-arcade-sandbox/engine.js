"use strict";
(() => {
  const canvas = document.getElementById("game");
  const ctx = canvas.getContext("2d");
  const hudStars = document.getElementById("hud-stars");
  const hudHealth = document.getElementById("hud-health");
  const status = document.getElementById("game-status");
  const W = canvas.width, H = canvas.height, FLOOR = 464;
  const createState = () => ({
    width: W, height: H, floor: FLOOR, exitX: 895, status: "playing",
    player: {x: 55, y: FLOOR - 39, w: 29, h: 39, vx: 0, vy: 0, grounded: true, hp: 3, hurtTime: 0},
    platforms: [{x: 256, y: 385, w: 145, h: 14}, {x: 454, y: 327, w: 147, h: 14}, {x: 684, y: 378, w: 140, h: 14}],
    stars: [{x: 167, y: 418, taken: false}, {x: 334, y: 349, taken: false}, {x: 741, y: 341, taken: false}],
    enemies: [{x: 550, y: FLOOR - 30, w: 34, h: 30, left: 520, right: 635, direction: 1, speed: 78}]
  });
  let state = createState(), jumpQueued = false, last = 0, accumulator = 0;
  const down = {left: false, right: false};
  function reset() { state = createState(); jumpQueued = false; accumulator = 0; last = 0; }
  document.getElementById("restart").addEventListener("click", reset);
  const keyMap = {ArrowLeft: "left", KeyA: "left", ArrowRight: "right", KeyD: "right", Space: "jump", ArrowUp: "jump", KeyW: "jump"};
  window.addEventListener("keydown", e => {
    const control = keyMap[e.code];
    if (!control) return;
    e.preventDefault();
    if (control === "jump" && !e.repeat) jumpQueued = true;
    else if (control !== "jump") down[control] = true;
  });
  window.addEventListener("keyup", e => {
    const control = keyMap[e.code];
    if (control && control !== "jump") down[control] = false;
  });
  window.addEventListener("blur", () => { down.left = false; down.right = false; jumpQueued = false; });
  document.querySelectorAll("[data-input]").forEach(button => {
    const direction = button.dataset.input;
    const pressed = e => {
      e.preventDefault();
      if (direction === "jump") jumpQueued = true;
      else down[direction] = true;
      if (e.pointerId != null) button.setPointerCapture(e.pointerId);
    };
    const released = e => { if (direction !== "jump") down[direction] = false; };
    button.addEventListener("pointerdown", pressed);
    button.addEventListener("pointerup", released);
    button.addEventListener("pointercancel", released);
    button.addEventListener("lostpointercapture", released);
  });
  function fillRound(x, y, w, h, radius, color) {
    ctx.fillStyle = color; ctx.beginPath(); ctx.roundRect(x, y, w, h, radius); ctx.fill();
  }
  function draw(ts) {
    const t = ts / 1000;
    const sky = ctx.createLinearGradient(0, 0, 0, H);
    sky.addColorStop(0, "#14203c"); sky.addColorStop(.65, "#254462"); sky.addColorStop(1, "#2f5868");
    ctx.fillStyle = sky; ctx.fillRect(0, 0, W, H);
    for (let i = 0; i < 28; i++) {
      const x = (i * 167 + 33) % W, y = (i * 59 + 21) % 240;
      ctx.globalAlpha = .38 + .2 * Math.sin(t * 1.8 + i);
      ctx.fillStyle = "#eaf7ff"; ctx.beginPath(); ctx.arc(x, y, i % 5 === 0 ? 2 : 1, 0, Math.PI * 2); ctx.fill();
    }
    ctx.globalAlpha = 1;
    ctx.fillStyle = "#a3e5db"; ctx.beginPath(); ctx.arc(816, 94, 38, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "#bbddd9";
    for (let i = 0; i < 5; i++) {
      const x = i * 234 - 36;
      ctx.beginPath();ctx.moveTo(x, FLOOR);ctx.lineTo(x + 128, 245 + i % 3 * 28);ctx.lineTo(x + 260, FLOOR);ctx.fill();
    }
    fillRound(0, FLOOR, W, H - FLOOR, 0, "#183f42");
    ctx.fillStyle = "#7ae4ad"; ctx.fillRect(0, FLOOR, W, 9);
    for (let i = 0; i < W; i += 28) fillRound(i + 7, FLOOR + 26 + (i % 3) * 7, 6, 4, 2, "#306965");
    for (const p of state.platforms) {
      fillRound(p.x, p.y + 7, p.w, 16, 6, "#183e4b");
      fillRound(p.x, p.y, p.w, 11, 5, "#73deb0");
      ctx.fillStyle = "#b4f3c8"; ctx.fillRect(p.x + 10, p.y + 2, p.w - 20, 2);
    }
    // Exit portal appears energized when all stars are collected.
    const unlocked = state.stars.every(s => s.taken);
    ctx.strokeStyle = unlocked ? "#b4ffca" : "#91a3c6";
    ctx.lineWidth = 9; ctx.beginPath();ctx.ellipse(910, FLOOR - 57, 26, 52, 0, 0, Math.PI * 2);ctx.stroke();
    fillRound(892, FLOOR - 105, 36, 95, 18, unlocked ? "#5ccfa066" : "#445171aa");
    for (const star of state.stars) {
      if (star.taken) continue;
      const b = Math.sin(t * 3 + star.x) * 4;
      ctx.save();ctx.translate(star.x, star.y + b);ctx.rotate(t * .8);ctx.fillStyle = "#ffd989";
      ctx.beginPath();for (let k = 0; k < 10; k++) {
        const r = k % 2 === 0 ? 17 : 8, a = -Math.PI / 2 + k * Math.PI / 5;
        if (k === 0) ctx.moveTo(Math.cos(a) * r, Math.sin(a) * r);
        else ctx.lineTo(Math.cos(a) * r, Math.sin(a) * r);
      }ctx.closePath();ctx.fill();ctx.restore();
    }
    for (const e of state.enemies) {
      fillRound(e.x, e.y + 5, e.w, e.h - 5, [14,14,7,7], "#e7a5d5");
      fillRound(e.x + 4, e.y + 1, e.w - 8, 17, 9, "#f2c1e5");
      ctx.fillStyle="#412c4d";ctx.fillRect(e.x + 10,e.y + 15,4,5);ctx.fillRect(e.x + 23,e.y + 15,4,5);
    }
    const p = state.player;
    if (p.hurtTime <= 0 || Math.floor(t * 12) % 2 === 0) {
      ctx.fillStyle="#102e36";ctx.beginPath();ctx.ellipse(p.x+p.w/2, p.y+p.h+4, 20, 5, 0, 0, Math.PI*2);ctx.fill();
      fillRound(p.x, p.y + 5, p.w, p.h - 5, [14,14,9,9], "#8cf4bd");
      fillRound(p.x + 4, p.y, p.w - 8, 18, 12, "#c4ffe0");
      ctx.fillStyle="#183b46";ctx.fillRect(p.x+8,p.y+19,4,5);ctx.fillRect(p.x+20,p.y+19,4,5);
      ctx.fillStyle="#6bd8aa";ctx.fillRect(p.x+12,p.y+29,7,2);
    }
    if (state.status !== "playing") {
      ctx.fillStyle="#071322bb";ctx.fillRect(0,0,W,H);
      ctx.textAlign="center";ctx.fillStyle="#d4ffe6";ctx.font="900 54px system-ui";
      ctx.fillText(state.status==="won" ? "MISSÃO COMPLETA!" : "TENTE NOVAMENTE",W/2,H/2-6);
      ctx.fillStyle="#ecf6f5";ctx.font="23px system-ui";
      ctx.fillText(state.status==="won" ? "Você encontrou todas as estrelas!" : "Os slimes ganharam esta rodada.",W/2,H/2+42);
      ctx.textAlign="start";
    }
    hudStars.textContent = "✦ ESTRELAS " + state.stars.filter(s => s.taken).length + "/" + state.stars.length;
    hudHealth.textContent = "❤ ".repeat(Math.max(0, p.hp)).trim() || "SEM VIDAS";
    status.textContent = state.status === "won" ? "Vitória! Clique em reiniciar para jogar novamente." :
      state.status === "lost" ? "Fim de jogo. Clique em reiniciar para tentar de novo." :
      state.stars.every(s => s.taken) ? "Todas as estrelas! Vá até o portal à direita." :
      "Colete as estrelas e alcance o portal!";
  }
  function frame(ts) {
    if (!last) last = ts;
    accumulator += Math.min((ts - last) / 1000, .05);
    last = ts;
    let steps = 0;
    while (accumulator >= 1 / 60 && steps < 4) {
      if (typeof updateGame !== "function") {
        status.textContent = "Implementação updateGame ausente. Volte à versão de referência.";
        break;
      }
      try { const next = updateGame(state, {left: down.left, right: down.right, jump: jumpQueued}, 1 / 60); if (next) state = next; }
      catch (_) { status.textContent = "Erro no código de gameplay. Reinicie ou restaure a referência."; break; }
      jumpQueued = false;
      accumulator -= 1 / 60;
      steps++;
    }
    draw(ts);
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
})();
