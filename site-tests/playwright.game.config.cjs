const { defineConfig, devices } = require("@playwright/test");
const url = process.env.LUNA_GAME_URL || "";
if (!/^http:\/\/127\.0\.0\.1:\d+\/?$/.test(url)) {
  throw new Error("Set LUNA_GAME_URL=http://127.0.0.1:PORT to evaluate a running local candidate.");
}
module.exports = defineConfig({
  testDir: "./tests",
  testMatch: "game-benchmark.spec.js",
  timeout: 30000,
  expect: { timeout: 7000 },
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    ...devices["Desktop Chrome"],
    baseURL: url,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
});
