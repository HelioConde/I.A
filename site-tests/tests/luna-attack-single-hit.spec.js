const {test,expect}=require("@playwright/test");
test("single KeyZ press inflicts exactly one 10 HP hit on first enemy",async({page},info)=>{
  test.setTimeout(60000);
  const errors=[];page.on("pageerror",e=>errors.push(e.message));
  await page.goto("/");
  await page.locator("#hero").selectOption("melee");
  await page.locator("#start").click();
  const snap=()=>page.evaluate(()=>window.__LUNA_ORIGINAL_QA__.snapshot());
  await expect.poll(async()=>(await snap()).enemies.length).toBeGreaterThan(0);
  for(let i=0;i<60;i++){
    const state=await snap();
    if(state.enemies.length===0)throw new Error("Enemy disappeared before the attack");
    const d=state.enemies[0].x-state.player.x;
    if(d>60){
      await page.keyboard.down("ArrowRight");
      await page.waitForTimeout(55);
      await page.keyboard.up("ArrowRight");
    }else break;
  }
  const before=await snap();
  const enemy=before.enemies[0];
  expect(Math.abs(enemy.x-before.player.x)).toBeLessThan(95);
  expect(enemy.hp).toBe(50);
  await page.keyboard.press("KeyZ");
  await page.waitForTimeout(230);
  const after=await snap();
  const newHP=after.enemies.length?after.enemies[0].hp:0;
  expect(enemy.hp-newHP,"One KeyZ may inflict only one hit, not continuous frame damage").toBe(10);
  expect(after.wave).toBe(1);
  expect(errors).toEqual([]);
  await info.attach("one-hit-model-candidate",{body:await page.screenshot(),contentType:"image/png"});
});
