player = { x: 80, y: 392, w: 28, h: 28, hp: 3, vy: 0, onGround: true };
enemies = [];
mode = 'ready';
const enemies0 = [{ x: 410, y: 392, w: 28, h: 28, hp: 3, vx: 0.5, alive: true }];
function spawnEnemies() { enemies = enemies0.slice(); }
window.__LUNA_GAMEDEV_QA__ = { snapshot: () => ({ player: { x: player.x, y: player.y, hp: player.hp }, enemies: enemies.map(e => ({ x: e.x, hp: e.hp })), mode: mode }) };

const canvas = document.getElementById('game');
const ctx = canvas.getContext('2d');
const keys = {};
const GRAVITY = 0.8;
const GROUND = 420;
const COOLDOWN = 120;
let attackTime = 0;
let lastAttack = 0;

document.addEventListener('keydown', (e) => {
  const k = e.code;
  keys[k] = true;
  if (k === 'ArrowLeft' || k === 'ArrowRight' || k === 'ArrowUp' || k === ' ') e.preventDefault();
  if (k === 'Space') {
    if (player.onGround) { player.vy = -13; player.onGround = false; }
  }
  if (k === 'KeyZ') {
    const now = performance.now();
    if (now - lastAttack >= COOLDOWN) {
      lastAttack = now;
      attackTime = now;
      let hit = false;
      for (const e of enemies) {
        if (!e.alive) continue;
        const dx = e.x + e.w / 2 - player.x - player.w / 2;
        const dy = e.y + e.h / 2 - player.y - player.h / 2;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist <= 75) {
          e.hp -= 1;
          if (e.hp <= 0) { e.alive = false; }
          hit = true;
        }
      }
      if (hit) mode = 'attack';
    }
  }
});
document.addEventListener('keyup', (e) => { keys[e.key] = false; });

spawnEnemies();

function update() {
  player.onGround = false;
  if (keys['ArrowLeft']) player.x -= 4;
  if (keys['ArrowRight']) player.x += 4;
  player.x = Math.max(0, Math.min(player.x, 772));
  player.vy += GRAVITY;
  player.y += player.vy;
  if (player.y + player.h >= GROUND) {
    player.y = GROUND - player.h;
    player.vy = 0;
    player.onGround = true;
  }

  const now = performance.now();
  let attacking = false;
  if (now - attackTime < COOLDOWN) attacking = true;
  if (!attacking && now - lastAttack >= COOLDOWN) mode = 'idle';

  for (const e of enemies) {
    if (!e.alive) continue;
    e.x += e.vx;
    if (e.x < 0 || e.x > 772) e.vx = -e.vx;
    if (mode === 'attack') {
      const dx = e.x + e.w / 2 - player.x - player.w / 2;
      const dy = e.y + e.h / 2 - player.y - player.h / 2;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist <= 75) {
        e.hp -= 1;
        if (e.hp <= 0) { e.alive = false; }
      }
    }
  }

  let aliveCount = 0;
  for (const e of enemies) { if (e.alive) aliveCount++; }
  if (aliveCount === 0) mode = 'win';
}

function drawBackground() {
  ctx.fillStyle = '#1a1a2e';
  ctx.fillRect(0, 0, 800, 480);
  ctx.fillStyle = '#16213e';
  for (let i = 0; i < 800; i += 60) {
    ctx.beginPath();
    ctx.arc(i, 120, 25, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.fillStyle = '#0f3460';
  ctx.fillRect(0, 200, 800, 20);
}

function drawPlayer() {
  ctx.fillStyle = '#00d2ff';
  ctx.fillRect(player.x, player.y, player.w, player.h);
  ctx.fillStyle = '#e0f7ff';
  ctx.fillRect(player.x + 4, player.y + 4, 6, 6);
  ctx.fillRect(player.x + 18, player.y + 4, 6, 6);
}

function drawEnemies() {
  for (const e of enemies) {
    if (!e.alive) continue;
    ctx.fillStyle = '#ff4757';
    ctx.fillRect(e.x, e.y, e.w, e.h);
    ctx.fillStyle = '#fff';
    ctx.fillRect(e.x + 4, e.y + 4, 6, 6);
    ctx.fillRect(e.x + 18, e.y + 4, 6, 6);
    ctx.fillStyle = '#c0392b';
    ctx.fillRect(e.x, e.y + e.h - 4, e.w, 3);
  }
}

function drawGround() {
  ctx.fillStyle = '#5f0f0f';
  ctx.fillRect(0, GROUND, 800, 60);
  ctx.fillStyle = '#8b4513';
  for (let i = 0; i < 800; i += 40) {
    ctx.fillRect(i, GROUND, 20, 8);
  }
}

function drawHUD() {
  ctx.fillStyle = '#ffffff';
  ctx.font = '16px Arial';
  ctx.fillText('HP: ' + player.hp, 10, 20);
  ctx.fillText('Inimigos: ' + enemies.filter(e => e.alive).length, 10, 40);
  ctx.fillText('Modo: ' + mode, 10, 60);
}

function render() {
  drawBackground();
  drawGround();
  drawPlayer();
  drawEnemies();
  drawHUD();
}

function loop() {
  update();
  render();
  requestAnimationFrame(loop);
}
loop();
