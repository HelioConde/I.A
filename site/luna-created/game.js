const canvas = document.getElementById('game'), ctx = canvas.getContext('2d');
const startBtn = document.getElementById('start');
const heroSelect = document.getElementById('hero');
const status = document.getElementById('status');

let mode = 'menu';
let player = { x: 100, y: 400, vx: 0, vy: 0, hp: 100 };
let enemies = [];
let wave = 0;
let isJumping = false;
let isAttacking = false;
let isInvulnerable = false;
let lastAttackTime = 0;
let lastEnemySpawn = 0;
let lastBossSpawn = 0;
let lastJumpTime = 0;
let gravity = 0.5;
let jumpPower = -10;
let attackRange = 100;
let attackSpeed = 5;
let attackCooldown = 100;
let attackDuration = 50;
let attackInterval = 10;
let attackTimer = 0;
let attackTarget = null;

startBtn.addEventListener('click', () => {
  mode = 'game';
  player = { x: 100, y: 400, vx: 0, vy: 0, hp: 100 };
  enemies = [];
  wave = 0;
  isJumping = false;
  isAttacking = false;
  isInvulnerable = false;
  lastAttackTime = 0;
  lastEnemySpawn = 0;
  lastBossSpawn = 0;
  lastJumpTime = 0;
  document.getElementById('status').textContent = '';
  document.getElementById('start').textContent = 'Restart';
  document.getElementById('hero').value = 'melee';
  gameLoop();
});

document.addEventListener('keydown', (e) => {
  if (e.code === 'Space' || e.code === 'ArrowLeft' || e.code === 'ArrowRight' || e.code === 'KeyZ') {
    e.preventDefault();
  }
  if (e.key === 'ArrowRight') {
    player.vx = 5;
  } else if (e.key === 'ArrowLeft') {
    player.vx = -5;
  } else if (e.code === 'Space') {
    if (player.vy === 0) {
      player.vy = jumpPower;
      isJumping = true;
    }
  } else if (e.code === 'KeyZ') {
    if (lastAttackTime + attackCooldown <= Date.now() && !isAttacking) {
      lastAttackTime = Date.now();
      isAttacking = true;
      attackTimer = attackDuration;
      attackTarget = enemies.find(e => e.hp > 0) || null;
    }
  }
});

document.addEventListener('keyup', (e) => {
  if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
    player.vx = 0;
  }
});

function gameLoop() {
  const now = Date.now();
  const delta = Math.min(1000 / 60, now - lastBossSpawn);
  lastBossSpawn = now;

  if (mode === 'menu') {
    ctx.fillStyle = 'black';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = 'white';
    ctx.font = '48px Arial';
    ctx.textAlign = 'center';
    ctx.fillText('Press Start to Begin', canvas.width / 2, canvas.height / 2);
    return;
  }

  if (mode === 'game') {
    ctx.fillStyle = 'black';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Player
    ctx.fillStyle = 'blue';
    ctx.fillRect(player.x, player.y, 20, 20);

    // Enemies
    for (let i = 0; i < enemies.length; i++) {
      const enemy = enemies[i];
      ctx.fillStyle = 'red';
      ctx.fillRect(enemy.x, enemy.y, 20, 20);
    }

    // Boss
    if (wave === 2) {
      ctx.fillStyle = 'green';
      ctx.fillRect(400, 300, 60, 60);
    }

    // Ground
    ctx.fillStyle = 'gray';
    ctx.fillRect(0, 440, canvas.width, 10);

    // Gravity
    player.vy += gravity;
    player.y += player.vy;

    // Collision with ground
    if (player.y + 20 >= 440) {
      player.y = 440 - 20;
      player.vy = 0;
      isJumping = false;
    }

    // Movement
    player.x += player.vx;
    player.x = Math.max(0, Math.min(canvas.width - 20, player.x));

// Attack
    if (isAttacking) {
      if (attackTimer > 0) {
        attackTimer--;
      } else {
        isAttacking = false;
      }

      if (attackTarget) {
        const dx = attackTarget.x - player.x;
        const dy = attackTarget.y - player.y;
        const distance = Math.sqrt(dx * dx + dy * dy);

        if (distance < attackRange) {
          attackTarget.hp -= 10;
          if (attackTarget.hp <= 0) {
            enemies.splice(enemies.indexOf(attackTarget), 1);
          }
        }
      }
    }
    // Enemy movement
    for (let i = 0; i < enemies.length; i++) {
      const enemy = enemies[i];
      enemy.x += 1;
      if (enemy.x > canvas.width) {
        enemies.splice(i, 1);
      }
    }

    // Check for enemy collision
    for (let i = 0; i < enemies.length; i++) {
      const enemy = enemies[i];
      if (Math.abs(player.x - enemy.x) < 20 && Math.abs(player.y - enemy.y) < 20) {
        if (!isInvulnerable) {
          player.hp--;
          isInvulnerable = true;
          setTimeout(() => {
            isInvulnerable = false;
          }, 200);
        }
      }
    }

// Check for victory
    if (enemies.length === 0 && wave < 3) {
      wave++;
      if (wave === 1) {
        enemies.push({ x: 400, y: 420, hp: 50, boss: false });
      } else if (wave === 2) {
        enemies.push({ x: 400, y: 420, hp: 100, boss: false });
      } else if (wave === 3) {
        enemies.push({ x: 400, y: 420, hp: 150, boss: true });
      }
    }
    // Check for defeat
    if (player.hp <= 0) {
      mode = 'defeat';
      status.textContent = 'DEFEAT';
      return;
    }

// Check for victory
    if (wave === 3 && enemies.length === 0) {
      mode = 'victory';
      status.textContent = 'VITÓRIA';
      return;
    }
    // Update status
    status.textContent = `Wave: ${wave} | HP: ${player.hp}`;

    requestAnimationFrame(gameLoop);
  }
}

window.__LUNA_ORIGINAL_QA__ = {
  snapshot: () => ({
    mode,
    player: { x: player.x, y: player.y, hp: player.hp },
    wave,
    enemies: enemies.map(e => ({ x: e.x, hp: e.hp, boss: e.boss }))
  })
};
