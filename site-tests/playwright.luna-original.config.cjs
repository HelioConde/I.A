const {defineConfig,devices}=require("@playwright/test");
const url=process.env.LUNA_ORIGINAL_URL || "";
if(!/^http:\/\/127\.0\.0\.1:\d+\/?$/.test(url))throw new Error("LUNA_ORIGINAL_URL must point to an isolated localhost server.");
module.exports=defineConfig({
  testDir:"./tests",
  testMatch:"luna-original.spec.js",
  timeout:90000,
  expect:{timeout:8500},
  retries:0,
  reporter:[["list"],["html",{open:"never"}]],
  use:{...devices["Desktop Chrome"],baseURL:url,
       screenshot:"only-on-failure",trace:"retain-on-failure"}
});
