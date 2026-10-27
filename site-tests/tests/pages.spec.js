const {test,expect} = require("@playwright/test");
const fs = require("node:fs");
const path = require("node:path");
const screenshots = path.resolve(__dirname,"../test-results/screenshots");
function recordBrowserErrors(page) {
  const errors = [];
  page.on("pageerror",err=>errors.push(err.message));
  page.on("console",msg=>{if(msg.type()==="error")errors.push(msg.text());});
  return errors;
}
test.beforeEach(async ({page})=>{
  await page.goto("./");
  await page.evaluate(()=>localStorage.clear());
  await page.reload();
});
const viewports=[
  {width:320,height:568},
  {width:390,height:844},
  {width:768,height:1024},
  {width:1366,height:768},
  {width:1600,height:900}
];
for(const size of viewports) {
  test(`responsive screenshot ${size.width}x${size.height}, no JS errors or horizontal overflow`,async({page})=>{
    const errors=recordBrowserErrors(page);
    await page.setViewportSize(size);
    await page.reload();
    await expect(page.getByText("Demonstração",{exact:true}).first()).toBeVisible();
    await expect(page.locator("#welcome-title")).toBeVisible();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
    fs.mkdirSync(screenshots,{recursive:true});
    await page.screenshot({path:path.join(screenshots,`luna-${size.width}x${size.height}.png`),fullPage:true,animations:"disabled"});
    expect(errors).toEqual([]);
  });
}
test("guided response makes zero API requests and identifies its source",async({page})=>{
  const errors=recordBrowserErrors(page);
  const api=[];
  page.on("request",req=>{if(new URL(req.url()).pathname.startsWith("/api/"))api.push(req.url());});
  await page.getByRole("button",{name:/Conheça o Brain-SSD/}).click();
  await expect(page.locator(".message.assistant")).toBeVisible();
  await expect(page.getByText("Resposta guiada · sem IA em execução")).toBeVisible();
  expect(api).toEqual([]);
  expect(errors).toEqual([]);
});
test("creates a conversation, persists reload, searches and renames",async({page})=>{
  await page.locator("#prompt").fill("Como funciona o Brain-SSD?");
  await page.locator("#send-button").click();
  await expect(page.locator(".message.assistant")).toBeVisible();
  await page.reload();
  await expect(page.locator(".message.user")).toHaveCount(1);
  await expect(page.locator(".message.assistant")).toHaveCount(1);
  await page.getByRole("button",{name:/Renomear:/}).click();
  await page.locator("#rename-input").fill("Meu estudo de IA");
  await page.getByRole("button",{name:"Salvar nome"}).click();
  await expect(page.locator("#current-title")).toHaveText("Meu estudo de IA");
  await page.locator("#search-conversations").fill("Meu estudo");
  await expect(page.locator(".conversation-row")).toHaveCount(1);
  await page.locator("#search-conversations").fill("sem resultados aqui");
  await expect(page.getByText("Nenhuma conversa encontrada.")).toBeVisible();
});
test("exports and imports versioned JSON data",async({page})=>{
  await page.locator("#prompt").fill("Olá Luna");
  await page.locator("#send-button").click();
  await expect(page.locator(".message.assistant")).toBeVisible();
  const event=page.waitForEvent("download");
  await page.locator("#export-chat").click();
  const download=await event;
  expect(download.suggestedFilename()).toMatch(/^luna-conversas-\d{4}-\d{2}-\d{2}\.json$/);
  const exported=JSON.parse(fs.readFileSync(await download.path(),"utf8"));
  expect(exported.version).toBe(1);
  expect(exported.conversations).toHaveLength(1);
  await page.locator("#import-file").setInputFiles({
    name:"conversas.json",mimeType:"application/json",buffer:Buffer.from(JSON.stringify(exported))
  });
  await expect(page.getByRole("heading",{name:"Substituir histórico?"})).toBeVisible();
  await page.locator('#confirm-dialog button[value="confirm"]').click();
  await expect(page.getByText("1 conversa(s) importada(s).")).toBeVisible();
  await expect(page.locator(".message.assistant")).toHaveCount(1);
});
test("interrupts scripted reply without leaving an assistant message",async({page})=>{
  await page.locator("#prompt").fill("Quais as limitações?");
  await page.locator("#send-button").click();
  await expect(page.locator("#stop-response")).toBeVisible();
  await page.locator("#stop-response").click();
  await page.waitForTimeout(850);
  await expect(page.locator(".message.assistant")).toHaveCount(0);
  await expect(page.locator(".message.user")).toHaveCount(1);
  await expect(page.locator("#prompt")).toBeEnabled();
});
test("deletes a conversation only after confirmation",async({page})=>{
  await page.locator("#prompt").fill("Como executar no Windows?");
  await page.locator("#send-button").click();
  await expect(page.locator(".message.assistant")).toBeVisible();
  await page.getByRole("button",{name:/Excluir:/}).click();
  await expect(page.locator("#confirm-dialog")).toBeVisible();
  await page.locator('#confirm-dialog button[value="cancel"]').click();
  await expect(page.locator(".conversation-row")).toHaveCount(1);
  await page.getByRole("button",{name:/Excluir:/}).click();
  await page.locator('#confirm-dialog button[value="confirm"]').click();
  await expect(page.locator(".conversation-row")).toHaveCount(0);
});
test("keyboard shortcut, modal semantics and reduced motion",async({page})=>{
  await page.emulateMedia({reducedMotion:"reduce"});
  await page.locator("#prompt").fill("Olá");
  await page.keyboard.press("Control+k");
  await expect(page.locator("#prompt")).toHaveValue("");
  const duration=await page.locator(".prompt-card").first().evaluate(el=>getComputedStyle(el).transitionDuration);
  expect(parseFloat(duration)).toBeLessThan(0.001);
  await page.locator("#open-info").click();
  await expect(page.locator("#info-dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.locator("#info-dialog")).toBeHidden();
});
test("mobile navigation is actionable and dismissible",async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.reload();
  await page.locator("#open-sidebar").click();
  await expect(page.locator("#sidebar")).toHaveClass(/is-open/);
  await expect(page.locator("#open-sidebar")).toHaveAttribute("aria-expanded","true");
  await page.locator("#close-sidebar").click();
  await expect(page.locator("#sidebar")).not.toHaveClass(/is-open/);
});
test("invalid import and malicious message text are safely handled",async({page})=>{
  await page.locator("#import-file").setInputFiles({name:"invalid.json",mimeType:"application/json",buffer:Buffer.from('{"unexpected":true}')});
  await expect(page.getByText(/Importação recusada/)).toBeVisible();
  const malicious="<img src=x onerror=alert(1)>";
  await page.locator("#prompt").fill(malicious);
  await page.locator("#send-button").click();
  await expect(page.locator(".message.user .message-copy")).toHaveText(malicious);
  await expect(page.locator(".message.user img")).toHaveCount(0);
});

test("welcome, send and stop honor hidden attribute",async({page})=>{
  await expect(page.locator("#welcome")).toBeVisible();
  await expect(page.locator("#stop-response")).toBeHidden();
  await page.locator("#prompt").fill("Olá");
  await page.locator("#send-button").click();
  await expect(page.locator("#welcome")).toBeHidden();
  await expect(page.locator("#send-button")).toBeHidden();
  await expect(page.locator("#stop-response")).toBeVisible();
  await expect(page.locator(".message.assistant")).toBeVisible();
  await expect(page.locator("#stop-response")).toBeHidden();
  await expect(page.locator("#send-button")).toBeVisible();
});
test("import replacement cancellation preserves existing conversation",async({page})=>{
  await page.locator("#prompt").fill("Luna existente");
  await page.locator("#send-button").click();
  await expect(page.locator(".message.assistant")).toBeVisible();
  const foreign={version:1,activeId:null,conversations:[{
    id:"imported-1234",title:"Importada",messages:[],createdAt:new Date().toISOString(),updatedAt:new Date().toISOString()
  }]};
  await page.locator("#import-file").setInputFiles({
    name:"import.json",mimeType:"application/json",buffer:Buffer.from(JSON.stringify(foreign))
  });
  await expect(page.locator("#confirm-dialog")).toBeVisible();
  await page.locator('#confirm-dialog button[value="cancel"]').click();
  await expect(page.locator(".conversation-row")).toHaveCount(1);
  await expect(page.locator("#current-title")).toContainText("Luna existente");
});
test("offline shell remains available after service worker installation",async({page,context})=>{
  await page.evaluate(()=>navigator.serviceWorker.ready);
  await page.reload();
  await context.setOffline(true);
  try{
    await page.reload();
    await expect(page.locator("#network-notice")).toBeVisible();
    await expect(page.locator("#welcome-title")).toBeVisible();
    await page.locator("#prompt").fill("offline");
    await page.locator("#send-button").click();
    await expect(page.locator(".message.assistant")).toBeVisible();
  } finally {
    await context.setOffline(false);
  }
});
test("clearing data in another tab clears the current history",async({page,context})=>{
  await page.locator("#prompt").fill("Teste duas abas");
  await page.locator("#send-button").click();
  await expect(page.locator(".message.assistant")).toBeVisible();
  const second=await context.newPage();
  await second.goto("./");
  await second.evaluate(()=>localStorage.clear());
  await expect(page.locator(".conversation-row")).toHaveCount(0);
  await second.close();
});
