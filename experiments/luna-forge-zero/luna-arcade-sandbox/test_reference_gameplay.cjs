"use strict";
// Tests trusted, manually authored reference gameplay. NOT model output.
const fs = require("node:fs"), vm = require("node:vm"), assert = require("node:assert/strict");
const source = fs.readFileSync(__dirname + "/gameplay.js", "utf8");
const ctx = {};
vm.runInNewContext(source + "\n;globalThis.step=updateGame;", ctx, {timeout:1000});
function state() {
  return {
    status:"playing",width:960,height:540,floor:464,exitX:895,
    player:{x:55,y:425,w:29,h:39,vx:0,vy:0,grounded:true,hp:3,hurtTime:0},
    platforms:[{x:256,y:385,w:145,h:14}],
    stars:[{x:165,y:418,taken:false},{x:334,y:349,taken:false},{x:741,y:341,taken:false}],
    enemies:[{x:550,y:434,w:34,h:30,left:520,right:635,direction:1,speed:78}]
  };
}
let s=state(), x=s.player.x;
ctx.step(s,{right:true},1/60);assert.ok(s.player.x>x,"right movement");
s=state();ctx.step(s,{jump:true},1/60);
assert.ok(s.player.vy<0&&s.player.y<425&&!s.player.grounded,"grounded jump");
s=state();s.player.y=347;s.player.x=300;s.player.vy=430;s.player.grounded=false;
for(let i=0;i<20;i++)ctx.step(s,{},1/60);
assert.ok(Math.abs(s.player.y-346)<2&&s.player.grounded,"landing on platform");
s=state();s.enemies[0].x=s.player.x;s.enemies[0].y=s.player.y;
ctx.step(s,{},1/60);const health=s.player.hp;ctx.step(s,{},1/60);
assert.equal(health,2);assert.equal(s.player.hp,2,"invulnerability");
s=state();s.stars.forEach(star=>star.taken=true);s.player.x=886;
ctx.step(s,{},1/60);assert.equal(s.status,"won","stars plus exit");
s=state();s.player.hp=1;s.enemies[0].x=s.player.x;s.enemies[0].y=s.player.y;
ctx.step(s,{},1/60);assert.equal(s.status,"lost","HP zero");
console.log("6 manually authored gameplay tests PASSED. NO model output executed.");
