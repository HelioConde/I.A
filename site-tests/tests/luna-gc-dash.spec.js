const {test,expect}=require("@playwright/test");
const snap=page=>page.evaluate(()=>window.__LUNA_ORIGINAL_QA__?.snapshot?.());
async function play(page){
  const errors=[];page.on("pageerror",e=>errors.push(e.message));
  await page.goto("/");
  await page.locator("#hero").selectOption("melee");
  await page.locator("#start").click();
  await expect.poll(async()=>(await snap(page))?.mode).toBe("game");
  return errors;
}
async function measure(page,code,mode){
  await play(page);
  if(code==="ArrowLeft"){
    await page.keyboard.down("ArrowRight");await page.waitForTimeout(650);await page.keyboard.up("ArrowRight");
    await page.waitForTimeout(90);
  }
  const before=(await snap(page)).player.x;
  if(mode==="walk"){
    await page.keyboard.down(code);await page.waitForTimeout(220);await page.keyboard.up(code);
  }else{
    await page.keyboard.down(code);await page.waitForTimeout(38);await page.keyboard.up(code);
    await page.waitForTimeout(40);
    await page.keyboard.down(code);await page.waitForTimeout(220);await page.keyboard.up(code);
  }
  const after=(await snap(page)).player.x;
  return Math.abs(after-before);
}
test("right double-tap is measurably faster than ordinary movement",async({page})=>{
  const walking=await measure(page,"ArrowRight","walk");
  const dashing=await measure(page,"ArrowRight","dash");
  expect(walking).toBeGreaterThan(20);
  expect(dashing).toBeGreaterThan(walking*1.5);
});
test("left double-tap is measurably faster than ordinary movement",async({page})=>{
  const walking=await measure(page,"ArrowLeft","walk");
  const dashing=await measure(page,"ArrowLeft","dash");
  expect(walking).toBeGreaterThan(20);
  expect(dashing).toBeGreaterThan(walking*1.5);
});
test("a single long held key does not continuously auto-activate dash",async({page})=>{
  const errors=await play(page);
  const before=(await snap(page)).player.x;
  await page.keyboard.down("ArrowRight");
  for(let i=0;i<4;i++){
    await page.dispatchEvent("body","keydown",{key:"ArrowRight",code:"ArrowRight",repeat:true,bubbles:true});
    await page.waitForTimeout(35);
  }
  await page.keyboard.up("ArrowRight");
  const after=(await snap(page)).player.x;
  expect(after-before).toBeGreaterThan(15);
  expect(after-before).toBeLessThan(125);
  expect(errors).toEqual([]);
});
