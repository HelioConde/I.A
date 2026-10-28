const {defineConfig,devices}=require("@playwright/test");
const url=process.env.LUNA_GAMEDEV_MODEL_URL||"";
if(!/^http:\/\/127\.0\.0\.1:\d+\/?$/.test(url))throw new Error("Isolated local model-generated game required");
module.exports=defineConfig({
 testDir:"./tests",testMatch:"model-gamedev.spec.js",
 timeout:75000,retries:0,reporter:[["list"],["html",{open:"never"}]],
 use:{...devices["Desktop Chrome"],baseURL:url,screenshot:"only-on-failure",trace:"retain-on-failure"}
});
