const { test, expect } = require("@playwright/test");

// This suite intentionally does NOT run under ordinary Pages QA.
// Run with playwright.game.config.cjs and LUNA_GAME_URL only after a game exists.
test.skip(!process.env.LUNA_GAME_URL, "No candidate supplied; never claim the game passed.");

async function snapshot(page) {
  return page.evaluate(() => {
    const qa = window.__LUNA_GAME_QA__;
    if (!qa || typeof qa.snapshot !== "function") return null;
    return qa.snapshot();
  });
}

async function begin(page, archetype = "melee") {
  await page.goto("/");
  await expect(page.getByTestId("character-" + archetype)).toBeVisible();
  await page.getByTestId("character-" + archetype).click();
  await page.getByTestId("start-game").click();
  await expect.poll(async () => (await snapshot(page))?.mode).toBe("dungeon");
  const state = await snapshot(page);
  expect(state.player).toBeTruthy();
  expect(state.player.archetype).toBe(archetype);
  expect(Number.isFinite(state.player.x)).toBe(true);
  expect(Number.isFinite(state.player.y)).toBe(true);
  return state;
}

test("menu: three real, selectable character archetypes", async ({ page }) => {
  for (const archetype of ["melee", "ranged", "magic"]) {
    await begin(page, archetype);
  }
});

test("movement: right arrow updates real world coordinates", async ({ page }) => {
  const start = await begin(page);
  await page.keyboard.down("ArrowRight");
  await page.waitForTimeout(350);
  await page.keyboard.up("ArrowRight");
  const after = await snapshot(page);
  expect(after.player.x).toBeGreaterThan(start.player.x + 5);
});

test("jump: space applies vertical motion in actual physics state", async ({ page }) => {
  const start = await begin(page);
  await page.keyboard.down("Space");
  await page.waitForTimeout(110);
  const air = await snapshot(page);
  await page.keyboard.up("Space");
  // Screen-space Y decreases on upward movement.
  expect(air.player.y).toBeLessThan(start.player.y - 2);
});

test("combat: Z hits the training enemy and changes real HP", async ({ page }) => {
  const start = await begin(page);
  const enemies = start.enemies;
  expect(Array.isArray(enemies)).toBe(true);
  expect(enemies.length).toBeGreaterThan(0);
  const target = enemies.find(x => x.training === true);
  expect(target).toBeTruthy();
  await page.keyboard.press("KeyZ");
  await page.waitForTimeout(270);
  const after = await snapshot(page);
  const same = after.enemies.find(x => x.id === target.id);
  expect(same == null || same.hp < target.hp).toBe(true);
});

test("pause: Escape stops and resumes simulation", async ({ page }) => {
  await begin(page);
  await page.keyboard.press("Escape");
  await expect.poll(async () => (await snapshot(page))?.mode).toBe("pause");
  await page.keyboard.press("Escape");
  await expect.poll(async () => (await snapshot(page))?.mode).toBe("dungeon");
});

test("UX: render responsive menus without JS errors or page overflow", async ({ page }, testInfo) => {
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  for (const dimensions of [
    {width:390,height:844}, {width:768,height:1024},
    {width:1366,height:768}, {width:1600,height:900}
  ]) {
    await page.setViewportSize(dimensions);
    await page.goto("/");
    await expect(page.getByTestId("start-game")).toBeVisible();
    const overflow = await page.evaluate(() =>
      document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(2);
    await testInfo.attach("menu-" + dimensions.width, {
      body: await page.screenshot({ fullPage: true }), contentType: "image/png",
    });
  }
  expect(errors).toEqual([]);
});


test("real mission: fight creatures, traverse three regions and defeat the boss", async ({page}, testInfo) => {
  test.setTimeout(180000);
  for (const archetype of ["melee","ranged","magic"]) {
  await begin(page, archetype);
  await testInfo.attach("real-gameplay-"+archetype, {body: await page.screenshot(), contentType:"image/png"});
  for (let room=1; room<=3; room++) {
    const started=Date.now();
    let actions=0;
    while (Date.now()-started<28000) {
      const state=await snapshot(page);
      if(state.mode==="victory")break;
      if(state.mode==="defeat")throw new Error("Player was defeated in room "+room+" after "+actions+" actions");
      if(state.cleared)break;
      const living=state.enemies;
      expect(living.length).toBeGreaterThan(0);
      const player=state.player;
      const target=living.slice().sort((a,b)=>Math.abs(a.x-player.x)-Math.abs(b.x-player.x))[0];
      const dx=target.x-player.x;
      // Navigate with real keyboard events; snapshots only observe game state.
      if (dx>100) {
        await page.keyboard.down("ArrowRight");
        await page.waitForTimeout(Math.min(440,Math.max(80,(dx-72)/1.5)));
        await page.keyboard.up("ArrowRight");
      } else if (dx < -10) {
        await page.keyboard.down("ArrowLeft");
        await page.waitForTimeout(Math.min(350,Math.max(65,(-dx+40)/1.7)));
        await page.keyboard.up("ArrowLeft");
      } else {
        await page.keyboard.press("ArrowRight");
      }
      await page.keyboard.press("KeyZ");
      if(actions%2===0)await page.keyboard.press("KeyX");
      await page.waitForTimeout(270);
      actions++;
    }
    const after=await snapshot(page);
    if(room<3){
      expect(after.mode).toBe("dungeon");
      expect(after.cleared).toBe(true);
      await expect(page.getByTestId("next-room")).toBeVisible();
      await page.getByTestId("next-room").click();
      await expect.poll(async ()=>(await snapshot(page))?.stage).toBe(room+1);
    }else{
      expect(after.mode).toBe("victory");
      expect(after.enemies).toHaveLength(0);
      expect(after.score).toBeGreaterThan(0);
      await expect(page.getByText("O vale foi salvo")).toBeVisible();
      await testInfo.attach("real-victory-"+archetype, {body: await page.screenshot(),contentType:"image/png"});
      await page.getByRole("button",{name:/Jogar novamente/}).click();
      await expect.poll(async ()=>(await snapshot(page))?.stage).toBe(1);
      await expect.poll(async ()=>(await snapshot(page))?.mode).toBe("dungeon");
    }
  }
  }
});


test("mobile: actual on-screen controls move and attack", async ({page}, testInfo) => {
  await page.setViewportSize({width:390,height:844});
  const initial=await begin(page,"melee");
  const move=page.getByRole("button",{name:"Mover para direita"});
  await expect(move).toBeVisible();
  await move.dispatchEvent("pointerdown",{pointerId:1,pointerType:"touch"});
  await page.waitForTimeout(280);
  await move.dispatchEvent("pointerup",{pointerId:1,pointerType:"touch"});
  const after=await snapshot(page);
  expect(after.player.x).toBeGreaterThan(initial.player.x+5);
  const attack=page.getByRole("button",{name:"Atacar"});
  await expect(attack).toBeVisible();
  const beforeHit=after.enemies.find(e=>e.training);
  await attack.dispatchEvent("pointerdown",{pointerId:2,pointerType:"touch"});
  await attack.dispatchEvent("pointerup",{pointerId:2,pointerType:"touch"});
  await page.waitForTimeout(130);
  const afterHit=await snapshot(page);
  const target=afterHit.enemies.find(e=>e.training);
  expect(target==null||target.hp<beforeHit.hp).toBe(true);
  await testInfo.attach("touch-gameplay-mobile",{body:await page.screenshot(),contentType:"image/png"});
});


test("player feedback: preview contains selected area, observations and GitHub issue URL", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.getByRole("heading", {name:/Você joga/})).toBeVisible();
  await page.getByTestId("playtest-type").selectOption({label:"Tenho uma sugestão"});
  await page.locator("#playtest-category").selectOption({label:"Movimentação e pulo"});
  await page.locator("#playtest-class").selectOption({label:"Lyra · Arqueira"});
  await page.getByTestId("playtest-problem").fill("O pulo parece lento quando troco de direção.");
  await page.locator("#playtest-good").fill("A seleção das classes é clara.");
  await page.locator("#playtest-expected").fill("Quero conseguir trocar de direção no ar.");
  const report = await page.getByTestId("playtest-report").inputValue();
  expect(report).toContain("ALPHA 0.1.0");
  expect(report).toContain("Tenho uma sugestão");
  expect(report).toContain("Lyra · Arqueira");
  expect(report).toContain("A seleção das classes é clara.");
  expect(report).toContain("O pulo parece lento");
  expect(report).toContain("Quero conseguir trocar");
  expect(report).toContain("Não capturado");
  const issue = page.getByTestId("playtest-github");
  await expect(issue).toHaveAttribute("target","_blank");
  const url = new URL(await issue.getAttribute("href"));
  expect(url.origin + url.pathname).toBe("https://github.com/HelioConde/I.A/issues/new");
  expect(url.searchParams.get("title")).toContain("Tenho uma sugestão");
  expect(url.searchParams.get("body")).toContain("O pulo parece lento");
  await testInfo.attach("player-feedback-desktop", {
    body: await page.screenshot({fullPage:true}), contentType:"image/png",
  });
});

test("player feedback: capture real running engine state, no silent submission", async ({page}) => {
  await begin(page,"magic");
  const live = await snapshot(page);
  expect(live.mode).toBe("dungeon");
  await page.getByTestId("playtest-capture").click();
  await expect(page.locator("#playtest-capture-result")).toContainText("dungeon");
  await expect(page.locator("#playtest-capture-result")).toContainText("magic");
  const report = await page.getByTestId("playtest-report").inputValue();
  expect(report).toContain("Modo: dungeon");
  expect(report).toContain("Classe do motor: magic");
  expect(report).toContain("Região: 1");
  expect(report).toContain("Inimigos restantes:");
  await expect(page.locator("#playtest-status")).toContainText("Nada foi enviado");
});

test("player feedback: mobile layout fits viewport and form remains usable", async ({page},testInfo) => {
  await page.setViewportSize({width:390,height:844});
  await page.goto("/");
  await page.getByTestId("playtest-problem").fill("No celular o botão de ataque ficou difícil.");
  await expect(page.getByTestId("playtest-report")).toHaveValue(/No celular o botão/);
  await expect(page.getByTestId("playtest-copy")).toBeVisible();
  await expect(page.locator("#playtest-download")).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(2);
  await testInfo.attach("player-feedback-mobile", {
    body: await page.screenshot({fullPage:true}), contentType:"image/png",
  });
});


test("outperform baseline: releasing mobile controls has no uncaught ReferenceError", async ({page}) => {
  await page.setViewportSize({width:390,height:844});
  const errors=[];
  page.on("pageerror",error=>errors.push(error.message));
  await begin(page,"melee");
  const move=page.getByRole("button",{name:"Mover para direita"});
  await expect(move).toBeVisible();
  await move.dispatchEvent("pointerdown",{pointerId:37,pointerType:"touch"});
  await page.waitForTimeout(150);
  const running=await snapshot(page);
  await move.dispatchEvent("pointerup",{pointerId:37,pointerType:"touch"});
  await page.waitForTimeout(130);
  const released=await snapshot(page);
  expect(released.player.x).toBeGreaterThan(running.player.x-4);
  expect(errors).toEqual([]);
});
