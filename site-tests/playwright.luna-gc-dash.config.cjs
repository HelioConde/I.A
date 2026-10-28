const {defineConfig,devices}=require("@playwright/test");
const url=process.env.LUNA_GC_DASH_URL||"";
if(!/^http:\/\/127\.0\.0\.1:\d+\/?$/.test(url))throw new Error("Luna dash must run on isolated loopback");
module.exports=defineConfig({
 testDir:"./tests",testMatch:"luna-gc-dash.spec.js",retries:0,timeout:65000,
 reporter:[["list"],["html",{open:"never"}]],
 use:{...devices["Desktop Chrome"],baseURL:url,trace:"retain-on-failure",screenshot:"only-on-failure"}
});
