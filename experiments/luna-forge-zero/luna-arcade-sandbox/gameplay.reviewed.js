"use strict";
/*
 * REVISAO HUMANA da primeira tentativa do Qwen2.5-Coder 3B.
 * Esta versao NAO conta como saida autonoma bem-sucedida do modelo.
 * Salve o gameplay.js original do Ollama sem alteracoes para comparacao.
 */
function updateGame(state, input, dt) {
  if (state.status !== "playing" || !Number.isFinite(dt) || dt <= 0) return state;

  const step = Math.min(dt, 1 / 30);
  const p = state.player;
  const clamp = (v, low, high) => Math.max(low, Math.min(high, v));
  const overlaps = (a, b) =>
    a.x < b.x + b.w && a.x + a.w > b.x &&
    a.y < b.y + b.h && a.y + a.h > b.y;

  // Movimento com aceleracao e atrito: velocidade em px/s, dt em segundos.
  const axis = Number(Boolean(input.right)) - Number(Boolean(input.left));
  const targetVx = axis * 265;
  const rate = axis === 0 ? 1900 : 1700;
  p.vx = clamp(p.vx + clamp(targetVx - p.vx, -rate * step, rate * step), -265, 265);

  // Nao pode pular no ar; impulso proporcional a altura das plataformas.
  if (input.jump && p.grounded) {
    p.vy = -655;
    p.grounded = false;
  }

  const oldBottom = p.y + p.h;
  p.x = clamp(p.x + p.vx * step, 0, state.width - p.w);
  p.vy = clamp(p.vy + 1550 * step, -900, 900);
  p.y += p.vy * step;
  p.grounded = false;

  // Sem atravessar o teto. Plataformas sao de mao unica: apenas aterrissagem.
  if (p.y < 0) {
    p.y = 0;
    if (p.vy < 0) p.vy = 0;
  }
  if (p.vy >= 0) {
    let landingY = state.floor;
    for (const platform of state.platforms) {
      const crossesTop = oldBottom <= platform.y + 3 && p.y + p.h >= platform.y;
      const overlapsX = p.x + p.w > platform.x + 3 && p.x < platform.x + platform.w - 3;
      if (crossesTop && overlapsX && platform.y < landingY) {
        landingY = platform.y;
      }
    }
    if (p.y + p.h >= landingY) {
      p.y = landingY - p.h;
      p.vy = 0;
      p.grounded = true;
    }
  }

  p.hurtTime = Math.max(0, (p.hurtTime || 0) - step);

  // Limites locais do inimigo, e nao limites globais do mundo.
  for (const enemy of state.enemies) {
    let direction = enemy.direction >= 0 ? 1 : -1;
    let x = enemy.x + direction * enemy.speed * step;
    if (x >= enemy.right) {
      x = enemy.right;
      direction = -1;
    } else if (x <= enemy.left) {
      x = enemy.left;
      direction = 1;
    }
    enemy.x = x;
    enemy.direction = direction;

    if (p.hurtTime === 0 && overlaps(p, enemy)) {
      p.hp = Math.max(0, p.hp - 1);
      p.hurtTime = 1.1;
      p.vy = -300;
      p.grounded = false;
      const dir = p.x + p.w / 2 < enemy.x + enemy.w / 2 ? -1 : 1;
      p.x = clamp(p.x + dir * 25, 0, state.width - p.w);
    }
  }

  // Estrelas sao pontos; use distancia ao centro do personagem.
  for (const star of state.stars) {
    if (star.taken) continue;
    const dx = p.x + p.w / 2 - star.x;
    const dy = p.y + p.h / 2 - star.y;
    if (Math.hypot(dx, dy) < 38) star.taken = true;
  }

  // Todas as estrelas E portal -> vitoria. Vida zerada -> derrota.
  if (p.hp <= 0) state.status = "lost";
  else if (state.stars.every(star => star.taken) && p.x + p.w >= state.exitX) {
    state.status = "won";
  }
  return state;
}
