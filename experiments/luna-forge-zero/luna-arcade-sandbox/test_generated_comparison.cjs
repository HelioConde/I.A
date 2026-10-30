"use strict";
/*
 * Identical gameplay contracts for two versions of Luna Star Trail.
 * Generated JS may ONLY run inside offline, resource-limited Docker.
 * Node vm is not a security boundary. Never execute the original on the host.
 */
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const scene = () => ({
  status: "playing", width: 960, height: 540, floor: 464, exitX: 895,
  player: {x:55,y:425,w:29,h:39,vx:0,vy:0,grounded:true,hp:3,hurtTime:0},
  platforms: [{x:256,y:385,w:145,h:14},{x:454,y:327,w:147,h:14},{x:684,y:378,w:140,h:14}],
  stars: [{x:167,y:418,taken:false},{x:334,y:349,taken:false},{x:741,y:341,taken:false}],
  enemies: [{x:550,y:434,w:34,h:30,left:520,right:635,direction:1,speed:78}],
});
const cases = [
  ["movement_speed_and_friction", step => {
    const s=scene();
    for(let i=0;i<180;i++)step(s,{right:true});
    assert.ok(s.player.x>300&&s.player.x<=931);
    assert.ok(Math.abs(s.player.vx)<=265.01,"horizontal speed cap");
    for(let i=0;i<30;i++)step(s,{});
    assert.ok(Math.abs(s.player.vx)<1,"friction stops movement");
  }],
  ["grounded_jump_and_floor_landing", step => {
    const s=scene();
    step(s,{jump:true});
    assert.ok(s.player.vy < -400 && s.player.vy > -800,"reasonable jump impulse");
    assert.equal(s.player.grounded,false);
    const vy=s.player.vy; step(s,{jump:true});
    assert.ok(s.player.vy>vy,"no midair double jump");
    for(let i=0;i<120;i++)step(s,{});
    assert.equal(s.player.y,425);assert.equal(s.player.vy,0);
    assert.equal(s.player.grounded,true,"grounded restored on floor");
  }],
  ["one_way_platform", step => {
    const s=scene();s.player.x=310;s.player.y=412;s.player.vy=-650;s.player.grounded=false;
    step(s,{});assert.ok(s.player.y<412,"rise through platform underside");
    for(let i=0;i<90;i++)step(s,{});
    assert.equal(s.player.y,346);assert.equal(s.player.grounded,true);
  }],
  ["step_off_platform", step => {
    const s=scene();s.player.x=397;s.player.y=346;s.player.vy=0;s.player.grounded=true;
    for(let i=0;i<8;i++)step(s,{right:true});
    assert.ok(s.player.y>346&&!s.player.grounded,"start falling after leaving platform");
  }],
  ["enemy_local_patrol_limits", step => {
    const s=scene();s.enemies[0].x=635;s.enemies[0].direction=1;
    step(s,{});assert.equal(s.enemies[0].x,635);
    assert.equal(s.enemies[0].direction,-1);
  }],
  ["damage_and_invulnerability", step => {
    const s=scene();s.player.x=553;s.enemies[0].x=553;
    step(s,{});assert.equal(s.player.hp,2);assert.ok(s.player.hurtTime>0);
    s.player.x=553;s.player.y=425;step(s,{});
    assert.equal(s.player.hp,2,"invulnerable against immediate repeated collision");
  }],
  ["stars_require_exit", step => {
    const s=scene();s.stars.forEach(star=>{star.taken=true});
    step(s,{});assert.equal(s.status,"playing","stars alone should not win");
    s.player.x=900;step(s,{});assert.equal(s.status,"won");
  }],
  ["death_priority", step => {
    const s=scene();s.stars.forEach(star=>{star.taken=true});
    s.player.hp=0;s.player.x=886;
    step(s,{});assert.equal(s.status,"lost","zero HP beats stars and portal");
  }],
  ["star_pickup_uses_player_center", step => {
    const s=scene();s.player.x=115;s.player.y=400;
    step(s,{});assert.equal(s.stars[0].taken,true,"pickup around player center");
  }],
];
function runCandidate(filename) {
  const source=fs.readFileSync(path.join(__dirname,filename),"utf8");
  const results=[];
  for(const [id,check] of cases) {
    try {
      const context=vm.createContext({});
      vm.runInContext(source+";globalThis.__step=updateGame;",context,{timeout:300});
      const step=(state,input={},dt=1/60)=>{
        context.__state=state;context.__input=input;context.__dt=dt;
        vm.runInContext("__step(__state,__input,__dt)",context,{timeout:150});
      };
      check(step);
      results.push({id,status:"PASS"});
    } catch(error) {
      results.push({id,status:"FAIL",reason:String(error.message).slice(0,200)});
    }
  }
  return {
    source_file:filename,
    sha256:crypto.createHash("sha256").update(source).digest("hex"),
    passed:results.filter(row=>row.status==="PASS").length,
    total:cases.length,results,
  };
}
const reviewed=runCandidate("gameplay.reviewed.js");
const original=process.env.LUNA_REVIEWED_ONLY==="1" ? null : runCandidate("gameplay.qwen25-original.js");
const report={
  schema:"luna-arcade-generated-vs-reviewed-v1",
  execution_environment:original ? "GitHub Actions offline Docker" : "reviewed-only CI test",
  original:original ? {generated_by:"qwen2.5-coder:3b PRETRAINED Ollama",...original} : null,
  reviewed:{generated_by:"human-reviewed Qwen attempt",...reviewed},
  scratch_minicoder_v3_tested:false,
  model_promoted:false,
  warning:"Reviewed code does NOT count as autonomous model success."
};
process.stdout.write(JSON.stringify(report,null,2)+"\n");
if(reviewed.passed!==cases.length)process.exitCode=1;
