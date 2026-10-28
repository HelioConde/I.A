-- This test executes ONLY our own original Lua gameplay module.
-- Never run a game client, extracted Lua or externally sourced scripts.
local folder = (arg[0] or ""):match("^(.*)[/\\][^/\\]+$") or "."
local game = dofile(folder .. "/original_lua_gameplay.lua")
local count = 0
local function near(a,b,tolerance)
    assert(math.abs(a-b) < (tolerance or 0.00001), tostring(a).." != "..tostring(b))
    count = count + 1
end
local function eq(a,b)
    assert(a==b,tostring(a).." != "..tostring(b))
    count = count + 1
end

-- Horizontal movement and facing changes
local a = {x=0, vx=0, facing=1}
game.move_horizontal(a,1,0.1)
near(a.vx,120); near(a.x,12); eq(a.facing,1)
game.move_horizontal(a,-1,0.5)
near(a.vx,-260); eq(a.facing,-1)
local ok = pcall(function() game.move_horizontal(a,1,-1) end)
eq(ok,false)

-- Grounded jump and landing
local p={y=0,vy=0,grounded=true}
game.jump_and_fall(p,true,0.02,0)
eq(p.grounded,false)
eq(p.vy<0,true)
local first=p.vy
game.jump_and_fall(p,true,0.02,0)
eq(p.vy>first,true) -- Cannot double jump
for i=1,200 do
    game.jump_and_fall(p,false,0.02,0)
end
eq(p.grounded,true); near(p.y,0); near(p.vy,0)

-- Three-hit chain and cooldown
local c={chain=0,ready_at=0,window_end=-1}
eq(game.combo_step(c,true,0),1)
eq(game.combo_step(c,true,0.1),0)
eq(game.combo_step(c,true,0.2),2)
eq(game.combo_step(c,true,0.4),3)
eq(game.combo_step(c,true,2),1)

-- Hit invulnerability, HP clamping, knockback
local t={hp=12,vx=0,vy=0,invulnerable_until=-1}
eq(game.apply_damage(t,5,-1,0),true)
eq(t.hp,7); eq(t.vx,-280)
eq(game.apply_damage(t,5,1,0.2),false); eq(t.hp,7)
eq(game.apply_damage(t,50,1,1),true); eq(t.hp,0)
eq(game.apply_damage(t,1,1,2),false)

-- Rectangle hitboxes: touching edges do not overlap
local hit={x=0,y=0,w=10,h=10}
eq(game.hitbox_intersects(hit,{x=9,y=9,w=10,h=10}),true)
eq(game.hitbox_intersects(hit,{x=10,y=0,w=10,h=10}),false)
eq(game.hitbox_intersects(hit,{x=4,y=10,w=10,h=10}),false)

-- Patrol returns before leaving platform
local e={x=100,direction=1}
game.patrol(e,0,100,0.1)
eq(e.direction,-1); near(e.x,93.5)
e.x=0; e.direction=-1
game.patrol(e,0,100,0.1)
eq(e.direction,1); near(e.x,6.5)

print("LUNA_ORIGINAL_LUA_BEHAVIOR_PASS checks="..count)
