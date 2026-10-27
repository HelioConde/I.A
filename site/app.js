/**
 * Brain-SSD / Luna — GitHub Pages demonstration.
 * Educational scripted replies ONLY; never presented as model inference.
 * Private data stays in localStorage and is never transmitted by this script.
 */
const STORE_KEY = "brain-ssd-luna-demo-v1";
const MAX_CONVERSATIONS = 150;
const MAX_MESSAGES = 250;
const MAX_IMPORT_BYTES = 2_000_000;
const ANSWER_DELAY = 680;
const $ = (id) => document.getElementById(id);
const refs = {
  sidebar: $("sidebar"), backdrop: $("sidebar-backdrop"), list: $("conversation-list"),
  search: $("search-conversations"), count: $("conversation-count"), messages: $("messages"),
  scroll: $("messages-scroll"), welcome: $("welcome"), title: $("current-title"),
  form: $("composer"), prompt: $("prompt"), send: $("send-button"), stop: $("stop-response"),
  chars: $("char-count"), info: $("info-dialog"), rename: $("rename-dialog"),
  confirm: $("confirm-dialog"), toast: $("toast"), importFile: $("import-file")
};
const state = {conversations: [], activeId: null, pending: null, pendingTimer: null, toastTimer: null, editingId: null, readOnly: false, warningShown: false};
const scriptReplies = [
  {
    test: /mem[oó]ria|contexto|armazenamento|epis[oó]dic/i,
    reply: "No Brain-SSD, a memória persistente é uma área de pesquisa: o sistema organiza registros e tenta recuperar apenas o contexto relevante antes de gerar a resposta. O projeto distingue recuperar dados de treinar os pesos do modelo.\n\nNa versão Windows, algumas dessas etapas podem ser experimentadas com um modelo Qwen local e componentes Python. Nesta página você vê somente uma explicação educativa, sem executar inferência."
  },
  {
    test: /windows|instalar|executar|rodar|baixar|qwen|llama/i,
    reply: "Para experimentar a versão local, acesse o repositório HelioConde/I.A e consulte docs/AUTO_SETUP_WINDOWS.md. O projeto dispõe de scripts de preparação e inicialização para Windows e requer um modelo compatível, um runtime de inferência e recursos locais suficientes.\n\nOs scripts e requisitos podem mudar conforme a versão. Revise o conteúdo antes de executar. Esta demonstração no GitHub Pages não instala nem executa modelos."
  },
  {
    test: /demonstra[çc][aã]o|github pages|limita[çc]|servidor|backend|offline/i,
    reply: "O GitHub Pages hospeda apenas arquivos estáticos, por isso este modo oferece interface, histórico salvo no seu navegador, busca, renomeação e exportação/importação JSON.\n\nNão existe aqui modelo em execução, memória semântica real, busca na web, métricas do computador ou processamento de linguagem por IA. As respostas são exemplos guiados. Se você limpar os dados do navegador, perderá as conversas não exportadas."
  },
  {
    test: /arquitetura|brain.?ssd|funciona|pesquisa|projeto/i,
    reply: "O Brain-SSD é um laboratório experimental de IA local que investiga recuperação seletiva de conhecimento, contexto limitado e eficiência de execução. Seu fluxo conceitual é: pergunta → seleção de contexto → recuperação de informações → inferência local → resposta e avaliação.\n\nO objetivo é pesquisar o consumo de RAM, a latência, o acesso ao armazenamento e a qualidade da recuperação. Isso não comprova que um SSD substitui a RAM nem que o modelo aprende automaticamente com cada conversa."
  },
  {
    test: /privacidade|hist[oó]rico|dados|salvar|exportar|importar/i,
    reply: "Neste modo demonstrativo, as conversas são salvas com LocalStorage no navegador usado por você. Não há banco de dados remoto, conta ou sincronização. Use os botões Importar, Exportar e Limpar na barra lateral para controlar seus dados.\n\nSe o navegador estiver em modo privado ou bloquear o armazenamento, o histórico poderá não persistir. Evite inserir informações confidenciais em dispositivos compartilhados."
  },
  {
    test: /^(oi|ol[aá]|bom dia|boa tarde|boa noite|hey|hello)/i,
    reply: "Olá! Sou a interface demonstrativa da Luna, parte do laboratório Brain-SSD. ✦\n\nPosso mostrar explicações guiadas sobre o projeto, memória, arquitetura, privacidade e instalação no Windows. Este modo não gera respostas com inteligência artificial — você está explorando um protótipo educativo."
  }
];
function replyTo(prompt) {
  return (scriptReplies.find((item) => item.test.test(prompt))?.reply) ||
    "Esta é a demonstração estática da Luna. Não consigo gerar uma resposta inédita para essa pergunta porque nenhum modelo de IA está executando no GitHub Pages.\n\nExperimente perguntar sobre o Brain-SSD, memória, arquitetura, privacidade, limitações ou como executar a versão Windows. Na versão local do projeto, as respostas podem ser produzidas pelo runtime Qwen configurado.";
}
function randomId() {
  if (globalThis.crypto?.randomUUID) return crypto.randomUUID();
  return Date.now().toString(36) + "-" + Math.random().toString(36).slice(2);
}
function toast(message) {
  clearTimeout(state.toastTimer);
  refs.toast.textContent = message;
  refs.toast.hidden = false;
  state.toastTimer = setTimeout(() => {refs.toast.hidden = true;}, 3700);
}
function normalizeMessage(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  if (value.role !== "user" && value.role !== "assistant") return null;
  if (typeof value.content !== "string" || !value.content.trim() || value.content.length > 10000) return null;
  return {id: (typeof value.id === "string" && value.id.length <= 100) ? value.id : randomId(), role:value.role, content:value.content};
}
function normalizeConversation(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  if (!Array.isArray(value.messages) || value.messages.length > MAX_MESSAGES) return null;
  const messages = value.messages.map(normalizeMessage);
  if (messages.some((entry) => !entry)) return null;
  const now = new Date().toISOString();
  const title = typeof value.title === "string" ? value.title.trim().slice(0,80) : "";
  return {
    id: (typeof value.id === "string" && /^[\w-]{4,100}$/.test(value.id)) ? value.id : randomId(),
    title: title || "Conversa sem título",
    createdAt: typeof value.createdAt === "string" && !Number.isNaN(Date.parse(value.createdAt)) ? value.createdAt : now,
    updatedAt: typeof value.updatedAt === "string" && !Number.isNaN(Date.parse(value.updatedAt)) ? value.updatedAt : now,
    messages
  };
}
function parseData(raw) {
  const obj = JSON.parse(raw);
  if (!obj || obj.version !== 1 || !Array.isArray(obj.conversations) || obj.conversations.length > MAX_CONVERSATIONS) {
    throw new Error("Formato JSON incompatível ou limite de conversas excedido.");
  }
  const conversations = obj.conversations.map(normalizeConversation);
  if (conversations.some((x) => !x)) throw new Error("O arquivo contém conversas inválidas.");
  const ids = new Set();
  for (const c of conversations) {
    if (ids.has(c.id)) c.id = randomId();
    ids.add(c.id);
  }
  return {conversations, activeId: typeof obj.activeId === "string" ? obj.activeId : null};
}
function load() {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    if (!raw) {
      state.conversations=[];
      state.activeId=null;
      return;
    }
    if (raw.length > MAX_IMPORT_BYTES) throw new Error("Arquivo local excedeu o limite de segurança.");
    const data = parseData(raw);
    state.conversations = data.conversations;
    state.activeId = data.conversations.some((c) => c.id === data.activeId) ? data.activeId : null;
  } catch (err) {
    state.conversations = [];
    state.activeId = null;
    toast("O histórico salvo não pôde ser lido. Exporte ou limpe o armazenamento pelo navegador para recuperar espaço.");
    console.warn("Histórico local indisponível:", err instanceof Error ? err.message : "erro");
  }
}
function save() {
  if (state.readOnly) return false;
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify({version:1, conversations:state.conversations, activeId:state.activeId}));
    return true;
  } catch (err) {
    if (!state.warningShown) toast("Armazenamento bloqueado ou cheio. Exporte suas conversas: alterações podem não persistir.");
    state.warningShown = true;
    console.warn("Falha de armazenamento local:", err instanceof Error ? err.message : "erro");
    return false;
  }
}
function node(tag, className, textValue) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (textValue != null) element.textContent = textValue;
  return element;
}
function getCurrent() {return state.conversations.find((c) => c.id === state.activeId) || null;}
function updateStats() {
  refs.count.textContent = String(state.conversations.length);
  $("stat-conversations").textContent = String(state.conversations.length);
  $("stat-messages").textContent = String(state.conversations.reduce((sum,c) => sum+c.messages.length,0));
}
function addRow(conversation) {
  const row = node("div","conversation-row" + (conversation.id === state.activeId ? " active" : ""));
  const open = node("button","conversation-open");
  open.type = "button";
  open.setAttribute("aria-label","Abrir conversa: " + conversation.title);
  if (conversation.id === state.activeId) open.setAttribute("aria-current","true");
  const glyph = node("span",null,"▤");
  glyph.setAttribute("aria-hidden","true");
  const name = node("span",null,conversation.title);
  open.append(glyph,name);
  open.addEventListener("click",() => openConversation(conversation.id));
  const rename = node("button","row-action","✎");
  rename.type = "button";rename.title = "Renomear";rename.setAttribute("aria-label","Renomear: " + conversation.title);
  rename.addEventListener("click",() => startRename(conversation.id));
  const remove = node("button","row-action danger","×");
  remove.type = "button";remove.title="Excluir conversa";remove.setAttribute("aria-label","Excluir: " + conversation.title);
  remove.addEventListener("click",()=>confirmAction("Excluir conversa?", "A conversa \"" + conversation.title + "\" será apagada deste navegador.",()=>deleteConversation(conversation.id)));
  row.append(open,rename,remove);
  return row;
}
function renderList() {
  refs.list.replaceChildren();
  const q = refs.search.value.trim().toLocaleLowerCase("pt-BR");
  const matches = [...state.conversations].sort((a,b)=>Date.parse(b.updatedAt)-Date.parse(a.updatedAt))
    .filter((c) => c.title.toLocaleLowerCase("pt-BR").includes(q) || c.messages.some((m)=>m.content.toLocaleLowerCase("pt-BR").includes(q)));
  if (!matches.length) refs.list.append(node("p","empty-history",q?"Nenhuma conversa encontrada.":"Suas conversas aparecerão aqui."));
  else for(const item of matches) refs.list.append(addRow(item));
  updateStats();
}
function messageElement(message) {
  const isUser = message.role === "user";
  const row = node("article","message " + message.role);
  const avatar = node("span","message-avatar",isUser?"◉":"✦");avatar.setAttribute("aria-hidden","true");
  const body = node("div","message-body");
  body.append(node("div","message-name",isUser?"Você":"Luna · Demonstração"),node("div","message-copy",message.content));
  if (!isUser) {
    body.append(node("span","message-note","Resposta guiada · sem IA em execução"));
    const tools = node("div","message-tools");
    const copy = node("button",null,"▢ Copiar resposta");
    copy.type="button";copy.setAttribute("aria-label","Copiar resposta da Luna");
    copy.addEventListener("click",async()=>{
      try{await navigator.clipboard.writeText(message.content);toast("Resposta copiada.");}
      catch{toast("Não foi possível copiar automaticamente.");}
    });
    tools.append(copy);body.append(tools);
  }
  row.append(avatar,body);
  return row;
}
function renderMessages() {
  const conversation=getCurrent();
  refs.messages.replaceChildren();
  const messages = conversation?.messages || [];
  refs.welcome.hidden = messages.length !== 0;
  for(const message of messages) refs.messages.append(messageElement(message));
  refs.title.textContent=conversation?.title || "Nova conversa";
  scrollBottom();
}
function scrollBottom() {requestAnimationFrame(()=>{refs.scroll.scrollTop=refs.scroll.scrollHeight;});}
function syncUi() {renderList();renderMessages();updateSend();}
function newChat() {
  cancelPending(false);
  state.activeId=null;
  refs.prompt.value="";
  save();syncUi();closeSidebar();
  refs.prompt.focus();
}
function openConversation(id) {
  if(!state.conversations.some(c=>c.id===id))return;
  cancelPending(false);state.activeId=id;save();syncUi();closeSidebar();
}
function deleteConversation(id) {
  cancelPending(false);
  state.conversations=state.conversations.filter(c=>c.id!==id);
  if(state.activeId===id) state.activeId=null;
  save();syncUi();toast("Conversa excluída.");
}
function confirmAction(title,description,action) {
  $("confirm-title").textContent=title;
  $("confirm-description").textContent=description;
  refs.confirm.onclose=()=>{if(refs.confirm.returnValue==="confirm")action();};
  refs.confirm.showModal();
}
function startRename(id) {
  const c=state.conversations.find(c=>c.id===id);
  if(!c)return;
  state.editingId=id;
  $("rename-input").value=c.title;
  refs.rename.showModal();
  $("rename-input").focus();
  $("rename-input").select();
}
function renameConversation(event) {
  event.preventDefault();
  const c=state.conversations.find(c=>c.id===state.editingId);
  const title=$("rename-input").value.trim().slice(0,80);
  if(!c||!title)return;
  c.title=title;c.updatedAt=new Date().toISOString();
  refs.rename.close();state.editingId=null;save();syncUi();toast("Conversa renomeada.");
}
function cancelPending(showMessage=true) {
  if (!state.pending) return;
  clearTimeout(state.pendingTimer);
  const pending=state.pending;state.pending=null;state.pendingTimer=null;
  pending.remove();
  refs.stop.hidden=true;
  updateSend();
  if(showMessage) toast("Resposta demonstrativa interrompida.");
}
function updateSend() {
  refs.chars.textContent=refs.prompt.value.length + " / 2000";
  refs.send.disabled = !refs.prompt.value.trim() || Boolean(state.pending);
  refs.prompt.disabled=Boolean(state.pending);
  refs.send.hidden=Boolean(state.pending);
  refs.stop.hidden=!state.pending;
}
function fitTextarea() {
  refs.prompt.style.height="auto";
  refs.prompt.style.height=Math.min(150,refs.prompt.scrollHeight)+"px";
}
function showTyping() {
  const row=node("div","message");
  const avatar=node("span","message-avatar","✦");
  avatar.setAttribute("aria-hidden","true");
  const body=node("div","message-body");
  body.append(node("div","message-name","Luna · Demonstração"));
  const typing=node("div","typing");
  typing.setAttribute("role","status");
  typing.setAttribute("aria-label","Preparando resposta guiada");
  for(let i=0;i<3;i++)typing.append(node("span"));
  body.append(typing);row.append(avatar,body);
  refs.messages.append(row);return row;
}
function sendMessage(textValue=refs.prompt.value) {
  const text=String(textValue).trim().slice(0,2000);
  if(!text||state.pending)return;
  if(!getCurrent()){
    if(state.conversations.length>=MAX_CONVERSATIONS){toast("Limite de conversas atingido. Exporte e limpe conversas antigas.");return;}
    const now=new Date().toISOString();
    const convo={id:randomId(),title:text.slice(0,52),messages:[],createdAt:now,updatedAt:now};
    state.conversations.unshift(convo);state.activeId=convo.id;
  }
  const current=getCurrent();
  if(current.messages.length>MAX_MESSAGES-2){toast("Limite de mensagens desta conversa atingido. Abra outra conversa.");return;}
  current.messages.push({id:randomId(),role:"user",content:text});
  current.updatedAt=new Date().toISOString();
  refs.prompt.value="";fitTextarea();save();syncUi();
  state.pending=showTyping();
  updateSend();scrollBottom();
  const conversationId=current.id;
  state.pendingTimer=setTimeout(()=>{
    if(!state.pending)return;
    cancelPending(false);
    const target=state.conversations.find(c=>c.id===conversationId);
    if(!target)return;
    target.messages.push({id:randomId(),role:"assistant",content:replyTo(text)});
    target.updatedAt=new Date().toISOString();
    save();syncUi();
    refs.prompt.focus();
  },ANSWER_DELAY);
}
function syncSidebarInert() {
  refs.sidebar.inert = window.matchMedia("(max-width:760px)").matches && !refs.sidebar.classList.contains("is-open");
}
function closeSidebar() {
  refs.sidebar.classList.remove("is-open");
  syncSidebarInert();
  refs.backdrop.hidden=true;
  $("open-sidebar").setAttribute("aria-expanded","false");
}
function openSidebar() {
  refs.sidebar.classList.add("is-open");
  syncSidebarInert();refs.backdrop.hidden=false;
  $("open-sidebar").setAttribute("aria-expanded","true");
  $("close-sidebar").focus();
}
function exportData() {
  const data=JSON.stringify({version:1,exportedAt:new Date().toISOString(),conversations:state.conversations,activeId:state.activeId},null,2);
  const blob=new Blob([data],{type:"application/json;charset=utf-8"});
  const url=URL.createObjectURL(blob);
  const link=document.createElement("a");
  link.href=url;link.download="luna-conversas-"+new Date().toISOString().slice(0,10)+".json";
  document.body.append(link);link.click();link.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1500);
  toast("Arquivo de conversas preparado para download.");
}
async function importData(file) {
  if(!file)return;
  if(file.size>MAX_IMPORT_BYTES){toast("Arquivo muito grande (limite de 2 MB).");return;}
  try{
    const data=parseData(await file.text());
    const applyImport=()=>{
      cancelPending(false);
      state.conversations=data.conversations;
      state.activeId=state.conversations.some(c=>c.id===data.activeId)?data.activeId:null;
      save();syncUi();toast(state.conversations.length+" conversa(s) importada(s).");
    };
    if(state.conversations.length) {
      confirmAction("Substituir histórico?", "Esta importação substituirá as conversas já salvas neste navegador. Exporte um backup antes de continuar.",applyImport);
    } else applyImport();
  }catch(err){toast("Importação recusada: "+(err instanceof Error?err.message:"JSON inválido"));}
  finally{refs.importFile.value="";}
}
function clearAll() {
  cancelPending(false);state.conversations=[];state.activeId=null;
  save();syncUi();toast("Conversas locais apagadas.");
}
function wire() {
  $("new-chat").addEventListener("click",newChat);
  $("open-sidebar").addEventListener("click",openSidebar);
  $("close-sidebar").addEventListener("click",()=>{closeSidebar();$("open-sidebar").focus();});
  refs.backdrop.addEventListener("click",closeSidebar);
  refs.search.addEventListener("input",renderList);
  $("open-info").addEventListener("click",()=>refs.info.showModal());
  $("notice-info").addEventListener("click",()=>refs.info.showModal());
  $("import-chat").addEventListener("click",()=>refs.importFile.click());
  $("export-chat").addEventListener("click",exportData);
  refs.importFile.addEventListener("change",event=>importData(event.target.files?.[0]));
  $("clear-chats").addEventListener("click",()=>confirmAction("Limpar conversas?","Todas as conversas deste navegador serão excluídas. Exporte seus dados antes de confirmar.",clearAll));
  refs.form.addEventListener("submit",event=>{event.preventDefault();sendMessage();});
  refs.prompt.addEventListener("input",()=>{fitTextarea();updateSend();});
  refs.prompt.addEventListener("keydown",event=>{
    if(event.key==="Enter" && !event.shiftKey && !event.isComposing){event.preventDefault();sendMessage();}
  });
  refs.stop.addEventListener("click",()=>cancelPending(true));
  document.querySelectorAll("[data-prompt]").forEach(button=>button.addEventListener("click",()=>sendMessage(button.dataset.prompt)));
  $("rename-form").addEventListener("submit",renameConversation);
  $("cancel-rename").addEventListener("click",()=>refs.rename.close());
  $("cancel-rename-x").addEventListener("click",()=>refs.rename.close());
  document.addEventListener("keydown",event=>{
    if(event.key==="Escape"&&refs.sidebar.classList.contains("is-open"))closeSidebar();
    if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==="k"){event.preventDefault();newChat();}
  });
  window.addEventListener("resize",syncSidebarInert);
  window.addEventListener("online",updateNetworkStatus);
  window.addEventListener("offline",updateNetworkStatus);
  window.addEventListener("storage",event=>{
    if(event.key===STORE_KEY&&!state.pending){load();syncUi();toast("Conversas atualizadas de outra aba.");}
  });
}
function updateNetworkStatus() {
  const status=$("network-notice");
  status.hidden=navigator.onLine!==false;
}
function registerOfflineCache() {
  if(!("serviceWorker" in navigator) || !window.isSecureContext) return;
  navigator.serviceWorker.register("./service-worker.js",{scope:"./"}).catch((error)=>{
    console.warn("Cache offline não registrado:",error instanceof Error?error.message:"indisponível");
  });
}
wire();load();syncUi();fitTextarea();syncSidebarInert();updateNetworkStatus();registerOfflineCache();
