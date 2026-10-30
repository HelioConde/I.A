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
  await page.keyboard.down('ArrowRight');await page.waitForTimeout(450);await page.keyboard.up('ArrowRight');
  const moved=await qa();
  report.checks.push({name:'move_right',ok:!!(moved?.player&&initial?.player&&moved.player.x>initial.player.x+1)});
  await page.keyboard.press('ArrowUp');await page.waitForTimeout(100);
  const jumped=await qa();
  report.checks.push({name:'jump_changes_y',ok:!!(jumped?.player&&moved?.player&&jumped.player.y<moved.player.y-1)});
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
