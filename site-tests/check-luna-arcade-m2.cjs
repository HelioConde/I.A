/* Tests real Qwen-authored combat in Chromium; this is evaluator code, not gameplay. */
const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
(async()=>{
 const dest=path.resolve(__dirname,'../results/luna_arcade_m2/m2-evidence.json');
 fs.mkdirSync(path.dirname(dest),{recursive:true});
 const report={benchmark:'Luna Arcade M2 - actual keyboard combat',passed:false,checks:[],errors:[],visual_review:'human_review_required'};
 let browser;
 try{
  browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:960,height:640}});
  page.on('pageerror',error=>report.errors.push(error.message));
  await page.route('**/*',route=>{
   const u=new URL(route.request().url());
   if(['127.0.0.1','localhost'].includes(u.hostname))return route.continue();
   return route.abort();
  });
  await page.goto('http://127.0.0.1:4817/',{waitUntil:'load',timeout:15000});
  if(await page.locator('#start').count())await page.locator('#start').click();
  await page.waitForTimeout(500);
  const qa=()=>page.evaluate(()=>window.__LUNA_GAMEDEV_QA__?.snapshot?.()??null);
  const initial=await qa();
  report.checks.push({name:'combat_telemetry',ok:!!initial?.player&&Array.isArray(initial?.enemies)&&initial.enemies.length>0});
  report.checks.push({name:'initial_facing',ok:[1,-1].includes(initial?.player?.facing)});
  report.checks.push({name:'combo_field',ok:Number.isInteger(initial?.player?.combo)});
  const enemyHp=initial?.enemies?.[0]?.hp;
  const observed=[];
  for(let i=0;i<3;i++){
   await page.keyboard.down('KeyZ');await page.waitForTimeout(100);await page.keyboard.up('KeyZ');
   const snap=await qa();
   observed.push({combo:snap?.player?.combo,hp:snap?.enemies?.[0]?.hp??null});
   await page.waitForTimeout(115);
  }
  report.combo_trace=observed;
  const after=await qa();
  const finalHp=after?.enemies?.[0]?.hp??(after?.enemies?.length===0?0:null);
  report.checks.push({name:'attacks_damage_nearby_enemy',ok:Number.isFinite(enemyHp)&&Number.isFinite(finalHp)&&finalHp<enemyHp});
  await page.keyboard.down('ArrowLeft');await page.waitForTimeout(150);await page.keyboard.up('ArrowLeft');
  const left=await qa();
  report.checks.push({name:'faces_left',ok:left?.player?.facing===-1});
  await page.keyboard.press('KeyX');await page.waitForTimeout(120);
  report.checks.push({name:'special_key_no_runtime_error',ok:report.errors.length===0});
  await page.screenshot({path:path.join(path.dirname(dest),'combat.png')});
  report.passed=report.checks.every(check=>check.ok);
 }catch(e){report.errors.push(String(e));}
 finally{
  if(browser)await browser.close();
  fs.writeFileSync(dest,JSON.stringify(report,null,2)+'\n');
  process.stdout.write(JSON.stringify(report)+'\n');
 }
 process.exitCode=report.passed?0:1;
})();
