function updateGame(state, input, dt) {
  // Gravity
  state.player.vy += 1550 * dt;

  // Horizontal movement
  if (input.left) state.player.vx -= 265 * dt;
  if (input.right) state.player.vx += 265 * dt;

  // Jump
  if (state.player.grounded && input.jump) {
    state.player.vy = -1550;
    state.player.grounded = false;
  }

  // Update player position
  state.player.x += state.player.vx * dt;
  state.player.y += state.player.vy * dt;

  // Clamp player to world boundaries
  state.player.x = Math.max(0, Math.min(state.player.x, state.width - state.player.w));
  state.player.y = Math.max(0, Math.min(state.player.y, state.floor - state.player.h));

  // Check for collisions with platforms
  state.platforms.forEach(platform => {
    if (state.player.y + state.player.h > platform.y && state.player.y + state.player.h < platform.y + platform.h) {
      if (state.player.x + state.player.w > platform.x && state.player.x < platform.x + platform.w) {
        state.player.grounded = true;
        state.player.vy = 0;
        state.player.y = platform.y - state.player.h;
      }
    }
  });

  // Check for collisions with enemies
  state.enemies.forEach(enemy => {
    if (state.player.y + state.player.h > enemy.y && state.player.y + state.player.h < enemy.y + enemy.h) {
      if (state.player.x + state.player.w > enemy.x && state.player.x < enemy.x + enemy.w) {
        if (state.player.hurtTime <= 0) {
          state.player.hurtTime = 0.5;
          state.player.hp -= 1;
        }
      }
    }
  });

  // Collect stars
  state.stars.forEach(star => {
    if (Math.abs(state.player.x - star.x) < 50 && Math.abs(state.player.y - star.y) < 50) {
      star.taken = true;
    }
  });

  // Check if all stars are collected
  if (state.stars.every(star => star.taken)) {
    state.status = 'won';
  }

  // Check if player is out of bounds
  if (state.player.x > state.exitX) {
    state.status = 'lost';
  }

  // Enemy patrol
  state.enemies.forEach(enemy => {
    if (enemy.left && enemy.x < 0) {
      enemy.direction = 1;
    }
    if (enemy.right && enemy.x > state.width - enemy.w) {
      enemy.direction = -1;
    }
    enemy.x += enemy.speed * enemy.direction * dt;
  });

  // Temporary invulnerability
  if (state.player.hurtTime > 0) {
    state.player.hurtTime -= dt;
  }

  return state;
}
