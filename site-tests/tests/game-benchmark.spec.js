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
