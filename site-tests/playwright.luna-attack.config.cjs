const {defineConfig,devices}=require("@playwright/test");
const url=process.env.LUNA_ORIGINAL_URL||"";
if(!/^http:\/\/127\.0\.0\.1:\d+\/?$/.test(url))throw new Error("Only isolated localhost Luna game is permitted.");
module.exports=defineConfig({
 testDir:"./tests",testMatch:"luna-attack-single-hit.spec.js",
 timeout:65000,retries:0,reporter:[["list"],["html",{open:"never"}]],
 use:{...devices["Desktop Chrome"],baseURL:url,screenshot:"only-on-failure",trace:"retain-on-failure"}
});
