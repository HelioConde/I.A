const {defineConfig,devices} = require("@playwright/test");
module.exports = defineConfig({
  testDir:"./tests",
  timeout:25_000,
  expect:{timeout:5_000},
  retries:process.env.CI?1:0,
  workers:process.env.CI?2:undefined,
  reporter:process.env.CI?[["list"],["html",{open:"never"}]]:"list",
  use:{
    baseURL:"http://127.0.0.1:4173/site/",
    browserName:"chromium",
    headless:true,
    trace:"retain-on-failure",
    screenshot:"only-on-failure",
    ...devices["Desktop Chrome"]
  },
  webServer:{
    command:"python3 -m http.server 4173 --directory .. --bind 127.0.0.1",
    url:"http://127.0.0.1:4173/site/",
    reuseExistingServer:!process.env.CI,
    timeout:20_000
  }
});
