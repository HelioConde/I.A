/* QA for separate Luna-generated visual module, never a claim of human visual approval. */
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
(async () => {
  const root=path.resolve(__dirname,'../results/luna_visual_skin');
  fs.mkdirSync(root,{recursive:true});
  const report={tested_model_visual_code:true,passed:false,checks:[],errors:[],
    visual_review:'human_review_required',gameplay_source_unchanged:true};
  let browser;
  try {
    browser=await chromium.launch({headless:true});
    const page=await browser.newPage({viewport:{width:1100,height:850}});
    page.on('pageerror',e=>report.errors.push(e.message));
    page.on('console',m=>{if(m.type()==='error')report.errors.push(m.text());});
    await page.route('**/*',route=>{
      const u=new URL(route.request().url());
      if(['localhost','127.0.0.1'].includes(u.hostname)) return route.continue();
      return route.abort();
    });
    await page.goto('http://127.0.0.1:4819/',{waitUntil:'load',timeout:15000});
    await page.waitForTimeout(700);
    const overlay=page.locator('#luna-skin-overlay');
    report.checks.push({name:'model_visual_module',ok:await page.evaluate(()=>typeof window.LunaSkin?.draw==='function')});
    report.checks.push({name:'visual_overlay_present',ok:await overlay.count()===1});
    report.checks.push({name:'overlay_rendering',ok:await overlay.getAttribute('data-visual-status')==='rendering'});
    const visual=await page.evaluate(()=>{
      const c=document.getElementById('luna-skin-overlay');
      if(!c)return null;
      const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
      const colors=new Set();let opaque=0;
      for(let i=0;i<d.length;i+=160){
        if(d[i+3]>100)opaque++;
        colors.add([d[i],d[i+1],d[i+2],d[i+3]].join(','));
      }
      return {opaque,colors:colors.size};
    });
    report.pixels=visual;
    report.checks.push({name:'nonempty_original_scene',ok:!!visual&&visual.opaque>1000&&visual.colors>5});
    await page.screenshot({path:path.join(root,'menu.png'),fullPage:true});
    await page.locator('#start').click();
    await page.waitForTimeout(500);
    const state=()=>page.evaluate(()=>window.__LUNA_ORIGINAL_QA__?.snapshot?.()??null);
    const a=await state();
    await page.keyboard.down('ArrowRight');await page.waitForTimeout(250);await page.keyboard.up('ArrowRight');
    const b=await state();
    report.checks.push({name:'original_gameplay_movement_intact',ok:!!a&&!!b&&b.player.x>a.player.x});
    await page.keyboard.press('KeyZ');
    await page.waitForTimeout(200);
    report.checks.push({name:'no_browser_errors',ok:report.errors.length===0});
    await page.screenshot({path:path.join(root,'gameplay.png'),fullPage:true});
    report.passed=report.checks.every(c=>c.ok);
  }catch(e){report.errors.push(String(e));}
  finally {
    if(browser)await browser.close();
    fs.writeFileSync(path.join(root,'browser-evidence.json'),JSON.stringify(report,null,2)+'\n');
    process.stdout.write(JSON.stringify(report)+'\n');
  }
  process.exitCode=report.passed?0:1;
})();
