const {test,expect}=require("@playwright/test");
const state=async page=>page.evaluate(()=>window.__LUNA_GAMEDEV_QA__?.snapshot?.()||null);
async function launch(page){
 await page.goto("/");
 await expect(page.locator("#game")).toBeVisible();
 await expect.poll(async()=>(await state(page))?.player?.x).toBeGreaterThanOrEqual(0);
}
test("Qwen or Ornith authored Canvas runs with live enemy and no exceptions",async({page},info)=>{
 const errors=[];page.on("pageerror",error=>errors.push(error.message));
 await launch(page);
 const data=await state(page);
 expect(data.enemies.some(e=>e.hp>0)).toBe(true);
 await info.attach("initial",{body:await page.screenshot(),contentType:"image/png"});
 expect(errors).toEqual([]);
});
test("actual keyboard movement and grounded jump",async({page})=>{
 const errors=[];page.on("pageerror",error=>errors.push(error.message));
 await launch(page);
 await page.waitForTimeout(350);
 const a=await state(page);
 await page.keyboard.down("ArrowRight");await page.waitForTimeout(220);await page.keyboard.up("ArrowRight");
 const b=await state(page);
 expect(b.player.x).toBeGreaterThan(a.player.x+4);
 await page.keyboard.press("Space");await page.waitForTimeout(100);
 const c=await state(page);
 expect(c.player.y).toBeLessThan(b.player.y-3);
 expect(errors).toEqual([]);
});
test("KeyZ causes real enemy HP loss from actual player proximity",async({page},info)=>{
 const errors=[];page.on("pageerror",error=>errors.push(error.message));
 await launch(page);
 let damaged=false;
 for(let i=0;i<120;i++){
   const before=await state(page);
   const target=before.enemies.find(e=>e.hp>0);
   if(!target){damaged=true;break}
   const hp=target.hp;
   const diff=target.x-before.player.x;
   if(diff>50){await page.keyboard.down("ArrowRight");await page.waitForTimeout(60);await page.keyboard.up("ArrowRight")}
   else if(diff< -50){await page.keyboard.down("ArrowLeft");await page.waitForTimeout(60);await page.keyboard.up("ArrowLeft")}
   await page.keyboard.press("KeyZ");
   await page.waitForTimeout(150);
   const after=await state(page);
   if(after.enemies.length<before.enemies.length||after.enemies.some(e=>e.hp<hp)){damaged=true;break}
 }
 expect(damaged).toBe(true);
 await info.attach("combat",{body:await page.screenshot(),contentType:"image/png"});
 expect(errors).toEqual([]);
});
test("mobile canvas does not overflow viewport",async({page})=>{
 await page.setViewportSize({width:390,height:844});
 await launch(page);
 const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);
 expect(overflow).toBeLessThanOrEqual(3);
});
