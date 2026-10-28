/* Luna Arcade S1 — original action-platformer prototype. Plain browser JS, no CDN. */
(() => {
  "use strict";
  const canvas = document.getElementById("game"), ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas 2D unavailable");
  const W = 1200, H = 675, FLOOR = 565, GRAVITY = 1650, MAX_X = 1780;
  const byId = id => document.getElementById(id);
  const CLASSES = {
    melee: { name: "Kael", role: "ESPADACHIM", icon: "⚔", hp: 150, damage: 27, speed: 295, cooldown: .23, tint: "#e6b77c", accent: "#7d91d8" },
    ranged: { name: "Lyra", role: "ARQUEIRA", icon: "➶", hp: 112, damage: 23, speed: 330, cooldown: .28, tint: "#7ce2c2", accent: "#50998e" },
    magic: { name: "Orin", role: "MAGO", icon: "✧", hp: 102, damage: 33, speed: 270, cooldown: .40, tint: "#c9a5ff", accent: "#9273dc" },
  };
  const ROOMS = [
    { label: "01 · CLAREIRA", name: "Clareira dos Ecos", subtitle: "A FLORESTA DESPERTA", enemies: [{x:225,hp:65,training:true},{x:480,hp:72}] },
    { label: "02 · RUÍNAS", name: "Ruínas de Luar", subtitle: "O VENTO MUDA", enemies: [{x:265,hp:85},{x:420,hp:85},{x:650,hp:90}] },
    { label: "03 · SANTUÁRIO", name: "Santuário da Aurora", subtitle: "O ÚLTIMO GUARDIÃO", enemies: [{x:420,hp:290,boss:true}] },
  ];
  const platforms = [{x:335,y:458,w:170,h:15},{x:750,y:415,w:190,h:15},{x:1150,y:465,w:190,h:15}];
  const stars = Array.from({length:72},(_,i)=>({x:(i*89.3+37)%W,y:24+(i*41.7)%360,r:.5+(i%4)*.4}));
  const keys = new Set(), particles = [], projectiles = [], floaters = [];
  const sound = {ctx:null, enabled:false};
  let selected = "melee", s, bannerUntil = 0, ambientTime = 0, last = 0, cam = 0, touchDown = false;
  function freshPlayer(archetype) {
    const c=CLASSES[archetype];
    return {archetype,x:140,y:FLOOR-61,w:36,h:61,vx:0,vy:0,grounded:true,facing:1,hp:c.hp,maxHp:c.hp,mp:100,maxMp:100,invuln:0,attackCooldown:0,attackAnim:0,attackCombo:0,comboTime:0,dashCooldown:0,dashTime:0,walkPhase:0};
  }
  function freshState(mode="menu", room=0, char=selected, score=0) {
    const enemies=ROOMS[room].enemies.map((item,i)=>({id:"r"+room+"-e"+i,x:item.x,y:FLOOR-(item.boss?104:48),w:item.boss?82:39,h:item.boss?104:48,hp:item.hp,maxHp:item.hp,training:!!item.training,boss:!!item.boss,hit:0,attackClock:0,phase:i*2.1,dir:-1,dead:false}));
    return {mode,room,player:freshPlayer(char),enemies,score,cleared:false,time:0,particles:0,deaths:0,enemyKills:0,attackCount:0};
  }
  s=freshState();
  function snapshot() {
    const p=s.player;
    return Object.freeze({
      mode:s.mode,stage:s.room+1,cleared:s.cleared,score:s.score,
      player:Object.freeze({archetype:p.archetype,x:+p.x.toFixed(2),y:+p.y.toFixed(2),vx:+p.vx.toFixed(2),vy:+p.vy.toFixed(2),hp:p.hp,mp:+p.mp.toFixed(2),grounded:p.grounded,maxHp:p.maxHp}),
      enemies:s.enemies.filter(e=>!e.dead).map(e=>({id:e.id,x:+e.x.toFixed(2),y:+e.y.toFixed(2),hp:e.hp,maxHp:e.maxHp,training:e.training,boss:e.boss})),
      attackCount:s.attackCount,enemyKills:s.enemyKills,seconds:+s.time.toFixed(2),
    });
  }
  // Read-only observational hook. No direct state mutation / victory shortcut.
  Object.defineProperty(window,"__LUNA_GAME_QA__",{value:Object.freeze({snapshot}),writable:false,configurable:false});
  const show=(id,visible)=>{byId(id).hidden=!visible};
  function updateUI(){
    show("menu",s.mode==="menu");
    show("hud",["dungeon","pause"].includes(s.mode));
    show("pause-screen",s.mode==="pause");
    show("end-screen",["victory","defeat"].includes(s.mode));
    show("next-room",s.mode==="dungeon"&&s.cleared&&s.room<2);
    show("touch",s.mode==="dungeon"&&(window.innerWidth<821 || matchMedia("(pointer:coarse)").matches));
    if(s.mode!=="menu"){
      const c=CLASSES[s.player.archetype];
      byId("hero-name").textContent=c.name;byId("hero-class").textContent=c.role;byId("avatar").textContent=c.icon;
      byId("hp-fill").style.width=Math.max(0,100*s.player.hp/s.player.maxHp)+"%";
      byId("mp-fill").style.width=Math.max(0,100*s.player.mp/s.player.maxMp)+"%";
      byId("stage-label").textContent=ROOMS[s.room].label;
      byId("enemy-count").textContent="INIMIGOS: "+s.enemies.filter(e=>!e.dead).length;
      byId("score").textContent=String(s.score).padStart(4,"0");
    }
  }
  function announceRoom(){
    byId("banner-small").textContent=ROOMS[s.room].subtitle;
    byId("banner-title").textContent=ROOMS[s.room].name;
    bannerUntil=performance.now()+2250;
    show("stage-banner",true);
  }
  function startGame(){
    s=freshState("dungeon",0,selected);keys.clear();particles.length=0;projectiles.length=0;floaters.length=0;cam=0;
    announceRoom();updateUI();canvas.focus({preventScroll:true});
  }
  function nextRoom(){
    if(s.mode!=="dungeon"||!s.cleared||s.room>=2)return;
    const old=s.player, next=s.room+1, score=s.score;
    s=freshState("dungeon",next,old.archetype,score);
    s.player.hp=Math.min(s.player.maxHp,old.hp+30);
    s.player.mp=Math.min(100,old.mp+35);
    keys.clear();particles.length=0;projectiles.length=0;floaters.length=0;cam=0;announceRoom();updateUI();
    canvas.focus({preventScroll:true});
  }
  function finish(victory){
    s.mode=victory?"victory":"defeat";keys.clear();
    byId("end-badge").textContent=victory?"✦ MISSÃO CUMPRIDA":"✧ FIM DA JORNADA";
    byId("end-title").textContent=victory?"O vale foi salvo":"A luz se apagou";
    byId("end-copy").textContent=victory?"Você restaurou a Aurora. Uma nova história começa aqui.":"O vale ainda precisa de você. Tente uma estratégia diferente.";
    byId("final-score").textContent=String(s.score).padStart(4,"0");
    updateUI();
  }
  function togglePause(){if(s.mode==="dungeon")s.mode="pause";else if(s.mode==="pause")s.mode="dungeon";else return;keys.clear();updateUI()}
  document.querySelectorAll(".class-card").forEach(button=>button.addEventListener("click",()=>{
    selected=button.dataset.class;
    document.querySelectorAll(".class-card").forEach(x=>{x.classList.toggle("active",x===button);x.setAttribute("aria-pressed",String(x===button))});
  }));
  byId("start-game").addEventListener("click",startGame);
  byId("retry-game").addEventListener("click",startGame);
  document.querySelectorAll(".back-menu").forEach(b=>b.addEventListener("click",()=>{s=freshState("menu");updateUI()}));
  byId("next-room").addEventListener("click",nextRoom);
  byId("pause-btn").addEventListener("click",togglePause);
  byId("resume-game").addEventListener("click",togglePause);
  window.addEventListener("keydown",e=>{
    if(["ArrowLeft","ArrowRight","ArrowUp","ArrowDown","Space","KeyZ","KeyX","ShiftLeft","ShiftRight","Escape"].includes(e.code) && (s.mode==="dungeon"||s.mode==="pause")){
      e.preventDefault();
      if(e.code==="Escape"&&!e.repeat){togglePause();return}
      if(s.mode!=="dungeon")return;
      if(!keys.has(e.code)){if(e.code==="Space")jump();if(e.code==="KeyZ")attack();if(e.code==="KeyX")special();if(e.code.startsWith("Shift"))dash()}
      keys.add(e.code);
    }
  },{passive:false});
  window.addEventListener("keyup",e=>keys.delete(e.code));
  window.addEventListener("blur",()=>{if(s.mode==="dungeon")togglePause();keys.clear()});
  document.querySelectorAll("[data-key]").forEach(b=>{
    const code=b.dataset.key;
    const start=e=>{e.preventDefault();touchDown=true;if(s.mode!=="dungeon")return;if(code==="Space")jump();else if(code==="KeyZ")attack();else if(code==="KeyX")special();else keys.add(code)};
    const end=e=>{e.preventDefault();keys.delete(code);touchDown=false};
    b.addEventListener("pointerdown",start);b.addEventListener("pointerup",end);b.addEventListener("pointercancel",end);b.addEventListener("pointerleave",end);
  });
  function jump(){const p=s.player;if(s.mode!=="dungeon"||!p.grounded)return;p.vy=-690;p.grounded=false;p.y-=2;burst(p.x+18,p.y+p.h,"#c7eafa",7,90)}
  function dash(){const p=s.player;if(p.dashCooldown>0)return;p.dashTime=.17;p.dashCooldown=.85;burst(p.x+18,p.y+27,"#b9c5ff",12,160)}
  function emit(x,y,color,amount=8,power=160){
    for(let i=0;i<amount;i++){const a=Math.PI*2*i/amount+Math.random()*.5,v=power*(.35+Math.random()*.65);particles.push({x,y,vx:Math.cos(a)*v,vy:Math.sin(a)*v,life:.45+Math.random()*.3,color,size:2+Math.random()*4})}
  }
  function burst(x,y,color,count=8,power=140){emit(x,y,color,count,power)}
  function popNumber(x,y,value,color="#fff1bb"){floaters.push({x,y,text:String(value),life:.8,color})}
  function hurtEnemy(enemy,damage,impact=1){
    if(enemy.dead)return;
    enemy.hp=Math.max(0,enemy.hp-damage);enemy.hit=.18;enemy.x=Math.min(MAX_X-90,enemy.x+impact*s.player.facing*8);
    emit(enemy.x+enemy.w/2,enemy.y+enemy.h/2,enemy.boss?"#ffd6a6":"#b8f8fb",9,180);
    popNumber(enemy.x+enemy.w/2,enemy.y,damage);
    if(enemy.hp===0){enemy.dead=true;s.score+=enemy.boss?1500:enemy.training?150:250;s.enemyKills++;emit(enemy.x+enemy.w/2,enemy.y+enemy.h/2,"#ffd694",22,210);
      if(s.enemies.every(e=>e.dead)){s.cleared=true;s.score+=350;if(s.room===2){finish(true)}else updateUI()}}
  }
  function attack(){
    const p=s.player;if(s.mode!=="dungeon"||p.attackCooldown>0)return;
    const c=CLASSES[p.archetype];p.attackCooldown=c.cooldown;p.attackAnim=.26;s.attackCount++;
    if(p.comboTime>0)p.attackCombo=(p.attackCombo+1)%3;else p.attackCombo=0;
    p.comboTime=.75;
    if(p.archetype==="melee"){
      const range=105+(p.attackCombo===2?25:0), dmg=c.damage+(p.attackCombo===2?13:0);
      let connected=false;
      for(const e of s.enemies){if(e.dead)continue;
        const dx=(e.x+e.w/2)-(p.x+p.w/2),dy=Math.abs((e.y+e.h/2)-(p.y+p.h/2));
        if(dx*p.facing>=-17&&dx*p.facing<range&&dy<94){hurtEnemy(e,dmg);connected=true}}
      if(!connected)burst(p.x+p.w/2+p.facing*73,p.y+24,"#ffe2a2",5,100);
    }else{
      projectiles.push({x:p.x+(p.facing>0?p.w+8:-8),y:p.y+22,vx:p.facing*(p.archetype==="ranged"?820:680),
        radius:p.archetype==="ranged"?7:12,life:1.6,damage:c.damage,kind:p.archetype,dir:p.facing});
    }
  }
  function special(){
    const p=s.player;if(s.mode!=="dungeon"||p.mp<35)return;
    p.mp-=35;p.attackAnim=.44;
    const range=p.archetype==="melee"?195:p.archetype==="ranged"?270:240;
    emit(p.x+p.w/2,p.y+22,p.archetype==="magic"?"#cbabff":"#f6e6a6",28,245);
    let hit=false;
    for(const e of s.enemies){
      const dx=e.x+e.w/2-(p.x+p.w/2),dy=Math.abs(e.y+e.h/2-p.y-25);
      if(!e.dead && Math.abs(dx)<range && dy<100 && (p.archetype==="magic" || dx*p.facing>=-45)){
        hurtEnemy(e,p.archetype==="magic"?68:p.archetype==="ranged"?55:63,1.5);hit=true;
      }
    }
    if(!hit)popNumber(p.x,p.y-18,"✦","#d6c3ff");
  }
  function collide1D(a,b){return a.x<a.x+a.w && a.x+a.w>b.x && a.x<b.x+b.w}
  function update(dt){
    ambientTime+=dt;
    if(s.mode!=="dungeon")return;
    s.time+=dt;
    const p=s.player,c=CLASSES[p.archetype],oldY=p.y;
    p.invuln=Math.max(0,p.invuln-dt);p.attackCooldown=Math.max(0,p.attackCooldown-dt);p.attackAnim=Math.max(0,p.attackAnim-dt);
    p.comboTime=Math.max(0,p.comboTime-dt);p.dashCooldown=Math.max(0,p.dashCooldown-dt);p.dashTime=Math.max(0,p.dashTime-dt);
    p.mp=Math.min(p.maxMp,p.mp+dt*9.5);
    const dir=(keys.has("ArrowRight")?1:0)-(keys.has("ArrowLeft")?1:0);
    if(dir)p.facing=dir;
    p.vx=dir*c.speed*(p.dashTime>0?2.3:1);p.x=Math.max(20,Math.min(MAX_X-p.w,p.x+p.vx*dt));
    if(dir&&p.grounded)p.walkPhase+=dt*12;
    p.vy+=GRAVITY*dt;p.y+=p.vy*dt;p.grounded=false;
    if(p.y+p.h>=FLOOR){p.y=FLOOR-p.h;p.vy=0;p.grounded=true}
    for(const plat of platforms){
      if(oldY+p.h<=plat.y+3&&p.y+p.h>=plat.y&&p.x+p.w>plat.x&&p.x<plat.x+plat.w&&p.vy>=0){
        p.y=plat.y-p.h;p.vy=0;p.grounded=true;
      }
    }
    for(const e of s.enemies){
      if(e.dead)continue;
      e.phase+=dt;e.hit=Math.max(0,e.hit-dt);e.attackClock-=dt;
      const dx=p.x+18-(e.x+e.w/2),dist=Math.abs(dx);
      if(dist>e.w/2+39){e.x+=Math.sign(dx)*(e.boss?67:54)*dt;e.dir=Math.sign(dx)||1}
      // Enemies remain grounded; only the hero uses platforms.
      if(dist<e.w/2+37&&Math.abs(e.y-p.y)<95&&e.attackClock<=0&&p.invuln<=0){
        e.attackClock=e.boss?1.8:2.2;
        p.hp=Math.max(0,p.hp-(e.boss?19:8));p.invuln=.88;popNumber(p.x+18,p.y-14,e.boss?"-19":"-8","#ff9eac");
        emit(p.x+18,p.y+30,"#fcb4b2",9,130);
        if(p.hp===0){finish(false);return}
      }
    }
    for(let i=projectiles.length-1;i>=0;i--){
      const b=projectiles[i];b.x+=b.vx*dt;b.life-=dt;
      let collided=false;
      for(const e of s.enemies){if(e.dead)continue;
        if(b.x+b.radius>e.x&&b.x-b.radius<e.x+e.w&&b.y+b.radius>e.y&&b.y-b.radius<e.y+e.h){
          hurtEnemy(e,b.damage);collided=true;break}}
      if(collided||b.life<=0)projectiles.splice(i,1);
    }
    for(let i=particles.length-1;i>=0;i--){
      const b=particles[i];b.x+=b.vx*dt;b.y+=b.vy*dt;b.vy+=dt*240;b.life-=dt;
      if(b.life<=0)particles.splice(i,1);
    }
    for(let i=floaters.length-1;i>=0;i--){floaters[i].y-=dt*42;floaters[i].life-=dt;if(floaters[i].life<=0)floaters.splice(i,1)}
    const wanted=Math.max(0,Math.min(650,p.x-320));cam+=(wanted-cam)*Math.min(1,dt*6);
    if(performance.now()>=bannerUntil && !byId("stage-banner").hidden)show("stage-banner",false);
    // Throttle DOM mutations to layout-friendly frequency.
    if(Math.floor(s.time*10)!==Math.floor((s.time-dt)*10))updateUI();
  }
  function rect(x,y,w,h,fill){ctx.fillStyle=fill;ctx.fillRect(x,y,w,h)}
  function circle(x,y,r,fill){ctx.fillStyle=fill;ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fill()}
  function line(x1,y1,x2,y2,color,width=2){ctx.strokeStyle=color;ctx.lineWidth=width;ctx.lineCap="round";ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke()}
  function oval(x,y,rx,ry,fill){ctx.fillStyle=fill;ctx.beginPath();ctx.ellipse(x,y,rx,ry,0,0,Math.PI*2);ctx.fill()}
  function drawTree(x,depth=1){
    const offset=x-cam*.4*depth,scale=depth;
    ctx.save();ctx.translate(offset,FLOOR-35);ctx.scale(scale,scale);
    rect(-7,-200,14,215,"#253b50");line(0,-160,-53,-227,"#354c61",7);line(0,-133,54,-204,"#354c61",7);
    for(const [cx,cy,r] of [[-48,-223,48],[9,-246,58],[62,-209,44],[0,-191,43]]){
      circle(cx,cy,r,"#284b5e");circle(cx-9,cy-13,r*.69,"#365c6b");}
    for(let i=0;i<9;i++)circle(-55+i*13,-230+Math.sin(i*3)*33,2,"#88c4c0");
    ctx.restore();
  }
  function drawBackdrop(){
    const g=ctx.createLinearGradient(0,0,0,H);g.addColorStop(0,s.room===2?"#232140":"#192846");g.addColorStop(.55,s.room===1?"#334a69":"#243e60");g.addColorStop(1,"#182b46");rect(0,0,W,H,g);
    circle(935-cam*.025,135,58,"#e0e6e9");circle(933-cam*.025,133,76,"#c7d9ec17");
    circle(952-cam*.025,117,59,s.room===2?"#232140":"#192846");
    for(const star of stars)circle((star.x-cam*.07+W)%W,star.y,star.r,"#cbdaf5a0");
    ctx.beginPath();ctx.moveTo(0,452);
    for(let x=0;x<=W;x+=14)ctx.lineTo(x,425+Math.sin(x*.01+cam*.0003)*48+Math.cos(x*.023)*23);
    ctx.lineTo(W,675);ctx.lineTo(0,675);ctx.fillStyle="#263c5d";ctx.fill();
    ctx.beginPath();ctx.moveTo(0,490);
    for(let x=0;x<=W;x+=14)ctx.lineTo(x,475+Math.sin(x*.017+cam*.001)*40+Math.cos(x*.041)*14);
    ctx.lineTo(W,675);ctx.lineTo(0,675);ctx.fillStyle="#25495e";ctx.fill();
    for(let x=60;x<W+150;x+=245)drawTree(x-(cam*.15)%245,.6);
    for(let x=130;x<W+200;x+=370)drawTree(x-(cam*.25)%370,.87);
    for(let i=0;i<35;i++){const x=(i*117+17-cam*.12+W*2)%W,y=270+(i*89)%270;circle(x,y,1.8+Math.sin(ambientTime*1.4+i)*.8,"#b6ffde55")}
    // Ground
    rect(0,FLOOR,W,H-FLOOR,"#182f3c");
    rect(0,FLOOR,W,14,"#577d69");
    rect(0,FLOOR,W,4,"#9cb887");
    for(let x=-(cam%62);x<W;x+=62){rect(x,FLOOR+16,51,4,"#234451");rect(x+17,FLOOR+49,32,6,"#284c54");line(x+12,FLOOR-4,x+22,FLOOR-13,"#5f977b",2)}
    for(const plat of platforms){
      const x=plat.x-cam;
      if(x>W||x+plat.w<0)continue;
      rect(x,plat.y,plat.w,plat.h,"#2c4a55");rect(x,plat.y,plat.w,5,"#9eb88b");
      for(let i=0;i<plat.w;i+=36)rect(x+i,plat.y+7,27,3,"#426c71");
    }
    // Decorative crystals in midground
    for(let i=0;i<10;i++){
      const x=(i*217+64-cam*.65+W*6)%W;
      const y=FLOOR-17;
      ctx.fillStyle=i%2?"#7bcbb271":"#9e9ae67d";ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x+8,y-25);ctx.lineTo(x+19,y);ctx.closePath();ctx.fill();
    }
    // Organic vignette.
    const vig=ctx.createRadialGradient(W/2,H/2,250,W/2,H/2,770);vig.addColorStop(0,"#09112400");vig.addColorStop(1,"#0710229b");rect(0,0,W,H,vig);
  }
  function drawHero(p){
    const x=p.x-cam,y=p.y,c=CLASSES[p.archetype],t=s.time;
    ctx.save();ctx.translate(x+p.w/2,y+p.h/2);ctx.scale(p.facing,1);
    if(p.invuln>0 && Math.floor(t*20)%2===0)ctx.globalAlpha=.48;
    // Shadow
    oval(0,p.h/2+2,25,6,"#0008");
    const run=p.grounded&&Math.abs(p.vx)>1?Math.sin(p.walkPhase)*9:0;
    const bounce=p.grounded?Math.abs(run)*-.18:0;
    line(-6,12,-8+run,28,"#182437",8);line(8,12,9-run,28,"#182437",8);
    line(-10+run,29,-2+run,29,"#c7af82",7);line(7-run,29,18-run,29,"#c7af82",7);
    // Cloak
    ctx.fillStyle=c.accent;ctx.beginPath();ctx.moveTo(-11,-14);ctx.lineTo(-23,19+Math.sin(t*5)*3);ctx.lineTo(-6,14);ctx.closePath();ctx.fill();
    rect(-11,-16+bounce,24,34,c.tint);rect(-7,-11+bounce,16,22,"#374263");
    rect(-12,-2+bounce,25,5,"#d7cc9a");
    line(-12,-9+bounce,-19,9+bounce,c.tint,7);line(12,-9+bounce,15,10+bounce,c.tint,7);
    circle(0,-26+bounce,13,"#f7d5b0");
    // Hair
    ctx.fillStyle=p.archetype==="ranged"?"#eee9c8":p.archetype==="magic"?"#dad8ee":"#4c3348";
    ctx.beginPath();ctx.arc(-1,-32+bounce,15,Math.PI,Math.PI*2);ctx.lineTo(14,-29+bounce);ctx.lineTo(-13,-31+bounce);ctx.fill();
    rect(4,-28+bounce,4,2,"#36364a");
    if(p.archetype==="melee"){line(13,-1+bounce,30,-28+bounce,"#fbe0a9",5);line(20,-18+bounce,31,-10+bounce,"#e3dfec",4)}
    if(p.archetype==="ranged"){ctx.strokeStyle="#f9d9a0";ctx.lineWidth=3;ctx.beginPath();ctx.arc(17,-6+bounce,18,-1.3,1.3);ctx.stroke();line(22,-23+bounce,22,11+bounce,"#b0e7cd",2)}
    if(p.archetype==="magic"){circle(18,-2+bounce,8+Math.sin(t*5)*2,"#b68cfa");circle(18,-2+bounce,3,"#f3deff");line(14,-2+bounce,18,29+bounce,"#594d80",4)}
    if(p.attackAnim>0){
      ctx.strokeStyle=p.archetype==="melee"?"#f9e3a3":p.archetype==="ranged"?"#a1f1da":"#cdb0ff";
      ctx.lineWidth=7;ctx.globalAlpha=.75;ctx.beginPath();ctx.arc(16,-3,55,-1.25,.7);ctx.stroke();
    }
    ctx.restore();
  }
  function drawEnemy(e){
    if(e.dead)return;
    const x=e.x-cam,y=e.y,t=s.time;
    if(x<-150||x>W+150)return;
    ctx.save();ctx.translate(x+e.w/2,y+e.h/2);
    if(e.hit>0)ctx.globalAlpha=.45;
    oval(0,e.h/2,30,7,"#080c1c88");
    if(e.boss){
      oval(0,-6,48,47,"#523d76");oval(0,-15,41,30,"#8063a2");
      for(const sign of [-1,1]){ctx.fillStyle="#d0aa9c";ctx.beginPath();ctx.moveTo(sign*26,-29);ctx.lineTo(sign*36,-63);ctx.lineTo(sign*5,-42);ctx.fill()}
      circle(-14,-10,7,"#f3d996");circle(14,-10,7,"#f3d996");circle(-14,-10,3,"#301f46");circle(14,-10,3,"#301f46");
      rect(-25,32,50,6,"#231c34");rect(-25,32,50*e.hp/e.maxHp,6,"#ef8ba5");
    }else{
      oval(0,6,24,24,"#5ca3a3");
      oval(0,-6+Math.sin(t*4+e.phase)*3,23,21,"#7bd1c1");
      circle(-7,-7,4,"#1e4657");circle(8,-7,4,"#1e4657");circle(-6,-8,1.2,"#d7ecff");circle(9,-8,1.2,"#d7ecff");
      for(const sx of [-1,1])circle(sx*16,18,5,"#4f8095");
      rect(-20,-35,40,4,"#142638");rect(-20,-35,40*e.hp/e.maxHp,4,e.training?"#f2d99a":"#eaa5ad");
    }
    ctx.restore();
  }
  function drawProjectiles(){
    for(const b of projectiles){
      const x=b.x-cam;
      if(b.kind==="ranged"){line(x-b.dir*18,b.y,x+b.dir*10,b.y,"#e3c792",4);circle(x+b.dir*11,b.y,4,"#fff0bf")}
      else{circle(x,b.y,15,"#9660e8a1");circle(x,b.y,8,"#e0c8ff");circle(x,b.y,3,"#fff")}
    }
    for(const b of particles)circle(b.x-cam,b.y,b.size*b.life/.75,b.color);
    ctx.save();ctx.font="bold 19px system-ui";ctx.textAlign="center";
    for(const f of floaters){ctx.globalAlpha=Math.min(1,f.life/.35);ctx.fillStyle=f.color;ctx.fillText(f.text,f.x-cam,f.y)}
    ctx.restore();
  }
  function draw(){
    drawBackdrop();
    if(s.mode==="menu"){
      // Decorative hero silhouettes behind menu; the gameplay state remains unstarted.
      ctx.globalAlpha=.55;
      const p=s.player,originalX=p.x,originalY=p.y;
      p.x=175;p.y=FLOOR-p.h;drawHero(p);
      p.x=originalX;p.y=originalY;
      ctx.globalAlpha=1;
    }else{
      for(const e of s.enemies)drawEnemy(e);
      drawHero(s.player);drawProjectiles();
      if(s.cleared&&s.room<2){
        const x=1000-cam,flux=Math.sin(ambientTime*4)*4;
        circle(x,FLOOR-62,46+flux,"#b3a6ff32");circle(x,FLOOR-62,35,"#b4a5f866");
        ctx.strokeStyle="#dfcda8";ctx.lineWidth=5;ctx.beginPath();ctx.ellipse(x,FLOOR-62,32,53,0,0,Math.PI*2);ctx.stroke();
      }
    }
  }
  function frame(now){
    if(!last)last=now;
    let dt=Math.min(.033,(now-last)/1000);last=now;
    if(document.visibilityState==="visible")update(dt);
    draw();
    requestAnimationFrame(frame);
  }
  window.addEventListener("resize",updateUI);
  updateUI();requestAnimationFrame(frame);
})();
