const {test,expect}=require("@playwright/test");
async function snap(page){
  return page.evaluate(()=>window.__LUNA_ORIGINAL_QA__?.snapshot?.()||null);
}
async function begin(page,archetype="melee"){
  await page.goto("/");
  await expect(page.locator("#game")).toBeVisible();
  await page.locator("#hero").selectOption(archetype);
  await page.locator("#start").click();
  await expect.poll(async()=>(await snap(page))?.mode).not.toBe("menu");
  const state=await snap(page);
  expect(state?.player).toBeTruthy();
  expect(Number.isFinite(state.player.x)).toBe(true);
  expect(Number.isFinite(state.player.y)).toBe(true);
  expect(Array.isArray(state.enemies)).toBe(true);
  return state;
}
test("entire game is rendered with three selectable classes",async({page},info)=>{
  const errors=[];page.on("pageerror",e=>errors.push(e.message));
  await page.goto("/");
  await expect(page.locator("#start")).toBeVisible();
  for(const hero of ["melee","ranged","magic"]){
    await expect(page.locator("#hero option[value='"+hero+"']")).toHaveCount(1);
  }
  await info.attach("luna-original-menu",{body:await page.screenshot(),contentType:"image/png"});
  expect(errors).toEqual([]);
});
test("actual keyboard movement, jump, combat, and no console errors",async({page},info)=>{
  const errors=[];page.on("pageerror",e=>errors.push(e.message));
  const first=await begin(page,"melee");
  await page.keyboard.down("ArrowRight");
  await page.waitForTimeout(350);
  await page.keyboard.up("ArrowRight");
  const advanced=await snap(page);
  expect(advanced.player.x).toBeGreaterThan(first.player.x+3);
  const y=advanced.player.y;
  await page.keyboard.press("Space");
  await page.waitForTimeout(100);
  const afterJump=await snap(page);
  expect(afterJump.player.y).toBeLessThan(y-2);
  const beforeAttack=await snap(page);
  for(let i=0;i<5;i++){await page.keyboard.press("KeyZ");await page.waitForTimeout(150)}
  const afterAttack=await snap(page);
  const previousHp=beforeAttack.enemies.map(e=>e.hp).reduce((a,b)=>a+b,0);
  const laterHp=afterAttack.enemies.map(e=>e.hp).reduce((a,b)=>a+b,0);
  expect(afterAttack.wave>beforeAttack.wave || laterHp<previousHp || afterAttack.mode==="victory").toBe(true);
  await info.attach("luna-original-combat",{body:await page.screenshot(),contentType:"image/png"});
  expect(errors).toEqual([]);
});
test("end-to-end: player can defeat three waves, boss, achieve victory and restart",async({page},info)=>{
  test.setTimeout(135000);
  const errors=[];page.on("pageerror",e=>errors.push(e.message));
  await begin(page,"melee");
  let winning=false;
  for(let i=0;i<260;i++){
    const state=await snap(page);
    if(state.mode==="victory"){winning=true;break}
    if(state.mode==="defeat")throw new Error("Qwen-generated game killed the player before victory");
    const p=state.player;
    const target=state.enemies.find(e=>e.hp>0);
    if(target){
      const distance=target.x-p.x;
      if(distance>75){await page.keyboard.down("ArrowRight");await page.waitForTimeout(70);await page.keyboard.up("ArrowRight")}
      else if(distance< -50){await page.keyboard.down("ArrowLeft");await page.waitForTimeout(70);await page.keyboard.up("ArrowLeft")}
      await page.keyboard.press("KeyZ");
    }else{
      await page.keyboard.press("KeyZ");
    }
    await page.waitForTimeout(120);
  }
  expect(winning).toBe(true);
  const state=await snap(page);
  expect(state.wave).toBeGreaterThanOrEqual(3);
  await info.attach("luna-original-victory",{body:await page.screenshot(),contentType:"image/png"});
  await page.locator("#start").click();
  const restarted=await snap(page);
  expect(restarted.mode).not.toBe("victory");
  expect(errors).toEqual([]);
});
test("mobile: interface readable and no sideways overflow",async({page},info)=>{
  await page.setViewportSize({width:390,height:844});
  await page.goto("/");
  await expect(page.locator("#game")).toBeVisible();
  await expect(page.locator("#start")).toBeVisible();
  const x=await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);
  expect(x).toBeLessThanOrEqual(2);
  await info.attach("luna-original-mobile",{body:await page.screenshot({fullPage:true}),contentType:"image/png"});
});
