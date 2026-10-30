-- Luna Forge: original, generic 2D action-platform Lua lessons.
-- Authored for this project. No Grand Chase client code, asset or archive was used.
-- Each "-- lesson:" block is an independent training example.
local Game = {}

-- lesson: horizontal_motion
function Game.move_horizontal(actor, axis, dt)
    assert(dt >= 0, "dt must be nonnegative")
    axis = math.max(-1, math.min(1, axis))
    local top_speed, acceleration = 260, 1200
    local target = axis * top_speed
    local difference = target - actor.vx
    local step = math.max(-acceleration * dt, math.min(acceleration * dt, difference))
    actor.vx = actor.vx + step
    actor.x = actor.x + actor.vx * dt
    if math.abs(actor.vx) > 0.1 then
        actor.facing = actor.vx > 0 and 1 or -1
    end
    return actor
end
-- end-lesson

-- lesson: grounded_jump
function Game.jump_and_fall(actor, pressed, dt, floor_y)
    assert(dt >= 0, "dt must be nonnegative")
    if pressed and actor.grounded then
        actor.vy = -560
        actor.grounded = false
    end
    if not actor.grounded then
        actor.vy = math.min(960, actor.vy + 1400 * dt)
        actor.y = actor.y + actor.vy * dt
        if actor.y >= floor_y and actor.vy >= 0 then
            actor.y = floor_y
            actor.vy = 0
            actor.grounded = true
        end
    end
    return actor
end
-- end-lesson

-- lesson: three_hit_combo
function Game.combo_step(combo, pressed, now)
    if now > combo.window_end then
        combo.chain = 0
    end
    if not pressed or now < combo.ready_at then
        return 0
    end
    combo.chain = (combo.chain % 3) + 1
    combo.ready_at = now + 0.18
    combo.window_end = now + 0.75
    return combo.chain
end
-- end-lesson

-- lesson: damage_and_invulnerability
function Game.apply_damage(target, amount, direction, now)
    if target.hp <= 0 or now < target.invulnerable_until then
        return false
    end
    if amount <= 0 then
        return false
    end
    target.hp = math.max(0, target.hp - amount)
    target.vx = direction < 0 and -280 or 280
    target.vy = -130
    target.invulnerable_until = now + 0.35
    return true
end
-- end-lesson

-- lesson: rectangle_hitbox
function Game.hitbox_intersects(a, b)
    return a.x < b.x + b.w and a.x + a.w > b.x
        and a.y < b.y + b.h and a.y + a.h > b.y
end
-- end-lesson

-- lesson: enemy_patrol
function Game.patrol(enemy, left, right, dt)
    assert(dt >= 0 and left < right, "invalid patrol bounds")
    if enemy.x >= right then
        enemy.direction = -1
    elseif enemy.x <= left then
        enemy.direction = 1
    end
    enemy.x = math.max(left, math.min(right, enemy.x + enemy.direction * 65 * dt))
    return enemy
end
-- end-lesson

return Game
