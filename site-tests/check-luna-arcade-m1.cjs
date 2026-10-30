/* Playwright smoke probe for real Luna GGUF candidate, not gameplay source. */
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
(async () => {
 const reportPath = process.env.LUNA_M1_REPORT || '../results/luna_arcade_s1/browser-evidence.json';
 const out = path.resolve(__dirname, reportPath);
 fs.mkdirSync(path.dirname(out), { recursive:true });
 const report={benchmark:'Luna Arcade S1 M1',tested_model_code:true,passed:false,checks:[],errors:[]};
 let browser;
 try {
  browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:960,height:640}});
  page.on('pageerror', error=>report.errors.push(error.message));
  await page.route('**/*',route=>{
   const u=new URL(route.request().url());
   if(u.hostname==='127.0.0.1' || u.hostname==='localhost') return route.continue();
   return route.abort();
  });
  await page.goto('http://127.0.0.1:4817/',{waitUntil:'load',timeout:15000});
  if(await page.locator('#start').count()) await page.locator('#start').click();
  await page.waitForTimeout(1200);
  report.checks.push({name:'canvas_visible',ok:await page.locator('canvas#game').isVisible()});
  const qa=()=>page.evaluate(()=>typeof window.__LUNA_GAMEDEV_QA__?.snapshot==='function'?window.__LUNA_GAMEDEV_QA__.snapshot():null);
  const initial=await qa();
  report.checks.push({name:'snapshot_exists',ok:!!initial?.player});
  // Regression: real model once let y exceed 3,000 while the solid floor was at y=440.
  const y0=initial?.player?.y;
  await page.waitForTimeout(650);
  const settled=await qa();
  report.floor_trace={initial_y:y0,after650ms_y:settled?.player?.y};
  report.checks.push({name:'solid_floor_contains_player',ok:!!settled?.player&&Number.isFinite(settled.player.y)&&settled.player.y>=0&&settled.player.y<=440});
  report.checks.push({name:'no_infinite_fall',ok:!!settled?.player&&Number.isFinite(y0)&&Math.abs(settled.player.y-y0)<85});
  await page.keyboard.down('ArrowRight');await page.waitForTimeout(450);await page.keyboard.up('ArrowRight');
  const moved=await qa();
  report.checks.push({name:'move_right',ok:!!(moved?.player&&initial?.player&&moved.player.x>initial.player.x+1)});
  const jumpStart=await qa();
  await page.keyboard.down('ArrowUp');
  await page.waitForTimeout(100);
  const jumped=await qa();
  await page.keyboard.up('ArrowUp');
  report.jump_trace={before:jumpStart?.player,after100ms:jumped?.player};
  report.checks.push({name:'jump_changes_y',ok:!!(jumped?.player&&jumpStart?.player&&jumped.player.y<jumpStart.player.y-1)});
  // Probe down input without pretending that a floor-only snapshot proves one-way platform logic.
  const beforeDown=await qa();
  await page.keyboard.down('ArrowDown'); await page.waitForTimeout(180); await page.keyboard.up('ArrowDown');
  const afterDown=await qa();
  report.checks.push({name:'down_input_does_not_crash',ok:!!beforeDown?.player&&!!afterDown?.player&&report.errors.length===0});
  // Inspect model-authored observable platform state without mutating player or game state.
  const observable=await qa();
  const platformData=Array.isArray(observable?.platforms)?observable.platforms:[];
  const hasOneWay=platformData.some(p=>p?.oneWay===true&&Number.isFinite(p.x)&&Number.isFinite(p.y));
  report.checks.push({name:'one_way_platform_observable',ok:hasOneWay});
  report.platforms_observed=platformData.length;
  report.platform_observations=platformData;
  report.player_after_down=afterDown?.player;
  // Only run a true drop test when model gameplay puts us on a raised one-way platform.
  // Avoid fabricating success by teleporting the character via the test harness.
  let landed=false;
  const platformTargets=platformData.map((p,i)=>({...p,index:i})).filter(p=>p.oneWay&&Number.isFinite(p.x)&&Number.isFinite(p.y)&&Number.isFinite(p.width)).sort((a,b)=>b.y-a.y);
  const trace=[];
  for(const target of platformTargets.slice(0,3)){
    for(let attempt=0;attempt<3&&!landed;attempt++){
      let current=await qa();
      if(!current?.player)break;
      const targetX=target.x+Math.min(target.width/2,30);
      // Navigate horizontally by keyboard, never mutate model-owned player data.
      const direction=targetX>current.player.x+9?'ArrowRight':targetX<current.player.x-9?'ArrowLeft':null;
      if(direction){
        await page.keyboard.down(direction);
        for(let n=0;n<24;n++){
          await page.waitForTimeout(35);
          current=await qa();
          if(!current?.player||Math.abs(targetX-current.player.x)<14)break;
        }
        await page.keyboard.up(direction);
      }
      await page.keyboard.down('ArrowUp');
      await page.waitForTimeout(110);
      await page.keyboard.up('ArrowUp');
      for(let n=0;n<32;n++){
        await page.waitForTimeout(45);
        const state=await qa();
        trace.push({y:state?.player?.y,onPlatform:state?.player?.onPlatform,grounded:state?.player?.grounded});
        if(state?.player?.grounded===true&&state.player.onPlatform===target.index){landed=true;break;}
      }
    }
    if(landed)break;
  }
  report.platform_reach_trace=trace.slice(-30);
  if(landed){
    report.checks.push({name:'one_way_platform_reachable',ok:true});
    const before=await qa();
    await page.keyboard.down('ArrowDown');await page.waitForTimeout(450);await page.keyboard.up('ArrowDown');
    const after=await qa();
    report.checks.push({name:'one_way_drop_real',ok:!!after?.player&&after.player.y>before.player.y+5});
  }else{
    report.checks.push({name:'one_way_platform_reachable',ok:false});
    report.unverified=['one_way_drop_real_no_reachable_platform','three_hit_combo','facing_hitbox','visual_quality'];
  }
  await page.keyboard.press('KeyZ');await page.waitForTimeout(150);
  report.checks.push({name:'no_runtime_errors',ok:report.errors.length===0});
  await page.screenshot({path:path.join(path.dirname(out),'gameplay.png')});
  report.passed=report.checks.every(c=>c.ok);
 } catch(e){report.errors.push(String(e));}
 finally {
  if(browser)await browser.close();
  fs.writeFileSync(out,JSON.stringify(report,null,2)+'\n');
  process.stdout.write(JSON.stringify(report)+'\n');
 }
 // Diagnostic smoke tests do not turn incomplete model code into a successful release.
 process.exitCode=report.passed?0:1;
})();
