const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? "").replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));
const number = (value, digits = 1) => value == null ? "—" : Number(value).toLocaleString("pt-BR", {maximumFractionDigits: digits});
const bytes = (value) => {
  if (value == null) return "—";
  if (value === 0) return "0 B";
  const units = ["B", "KiB", "MiB", "GiB"];
  const index = Math.min(Math.floor(Math.log(Math.abs(value)) / Math.log(1024)), units.length - 1);
  return `${number(value / 1024 ** index, index > 1 ? 2 : 0)} ${units[index]}`;
};
const ms = (value) => value == null ? "—" : `${number(value, value < 10 ? 2 : 0)} ms`;
const statusClass = (value) => String(value || "waiting").toLowerCase();

function renderPipeline(pipeline) {
  const entries = Object.entries(pipeline || {});
  $("pipeline").innerHTML = entries.map(([name, data], index) => {
    const stage = `<div class="stage ${statusClass(data.status)}"><strong>${esc(name)}</strong><span>${esc(data.status)}${data.duration_ms == null ? "" : ` · ${ms(data.duration_ms)}`}</span></div>`;
    return stage + (index < entries.length - 1 ? '<div class="connector" aria-hidden="true"></div>' : "");
  }).join("");
}

function renderBrain(state) {
  const brain = state.brain || {};
  const rate = Number(brain.active_rate || 0);
  $("activeRate").textContent = `${number(rate * 100, rate < .01 ? 3 : 2)}%`;
  $("brainMeter").style.width = `${Math.min(100, rate * 100)}%`;
  $("activeBytes").textContent = bytes(brain.active_bytes);
  $("pageRatio").textContent = `${brain.active_pages || 0} / ${brain.total_pages || 0} pages`;
  $("sleepingRate").textContent = `${number((state.work_avoided?.sleeping_rate || 0) * 100, 2)}%`;
  $("workAvoided").textContent = `${state.work_avoided?.sleeping_pages || 0} páginas`;
  const pages = brain.pages || [];
  $("brainMap").classList.toggle("empty-state", pages.length === 0);
  $("brainMap").innerHTML = pages.length ? pages.map(page => `
    <article class="page-card ${page.state === "INHIBITED" ? "inhibited" : ""}">
      <strong>PAGE ${esc(page.page_id)} · ${esc(page.state)}</strong>
      <span>${esc(page.domain)} / ${esc(page.topic)}</span>
      <p>${esc((page.reasons || []).join(" · ") || "sem justificativa registrada")}</p>
      <small class="technical-only">${esc(JSON.stringify(page.scores || {}))} · ${esc((page.provenance || []).join(", "))}</small>
    </article>`).join("") : "Nenhuma página ativada.";
}

function renderRecords(knowledge) {
  const records = knowledge?.records || [];
  $("recordCount").textContent = `${records.length} records`;
  $("records").classList.toggle("empty-state", records.length === 0);
  $("records").innerHTML = records.length ? records.map(record => `
    <article class="record"><header><span>${esc(record.section)}</span><small>${record.score == null ? "score n/d" : `score ${number(record.score, 3)}`}</small></header>
    <p>${esc(record.excerpt)}</p><small class="technical-only">${esc(record.record_id)} · ${esc(record.source)} · ${esc(record.reason)}</small></article>`).join("") : "Nenhum registro selecionado.";
}

function renderTimeline(events) {
  const latest = (events || []).slice(-12);
  $("timeline").classList.toggle("empty-state", latest.length === 0);
  $("timeline").innerHTML = latest.length ? latest.map(event => `
    <article class="timeline-event ${statusClass(event.status)}"><strong>${esc(event.component)}</strong><span>${esc(event.event_type.replaceAll("_", " "))}</span><span>${event.duration_ms == null ? "" : ms(event.duration_ms)}</span></article>`).join("") : "Os eventos aparecerão aqui.";
}

function renderPhases(phases) {
  $("phases").innerHTML = (phases || []).map(phase => `
    <article class="phase ${statusClass(phase.status)}"><span>PHASE ${esc(phase.phase)} · ${esc(phase.status)}</span><strong>${esc(phase.name)}</strong><p>${esc(phase.proof)}</p><span class="technical-only">${esc(phase.source)}</span></article>`).join("");
}

function render(state) {
  const validation = state.validation || {};
  $("validationBadge").textContent = `VALIDATION: ${validation.track || "NONE"}`;
  $("platformBadge").textContent = `PLATFORM: ${validation.platform || "N/D"}`;
  $("canonicalBadge").textContent = `CANONICAL 4E: ${validation.canonical_phase4e ? "YES" : "NO"}`;
  $("query").textContent = state.query || "Aguardando consulta.";
  $("modePill").textContent = state.mode || "IDLE";
  $("currentMessage").textContent = state.current_message || "";
  const source = state.data_source || "WAITING";
  $("sourceBadge").textContent = source;
  $("sourceBadge").className = `source-badge ${state.demo_data ? "demo" : source.includes("REPLAY") ? "replay" : "waiting"}`;
  renderPipeline(state.pipeline);
  renderBrain(state);
  const core = state.core || {};
  $("coreModel").textContent = core.model || "CPU Core";
  $("coreStatus").textContent = core.status || "IDLE";
  $("coreStatus").className = `status-chip ${statusClass(core.status === "IDLE" ? "success" : core.status)}`;
  $("ttft").textContent = ms(core.ttft_ms);
  $("tokSec").textContent = number(core.tokens_per_second, 2);
  $("latency").textContent = ms(core.total_latency_ms);
  $("tokenDetail").textContent = `input ${number(core.input_tokens, 0)} · output ${number(core.output_tokens, 0)} · ${core.mode || "CPU ONLY"}`;
  $("coreResidency").textContent = `Core Residency: ${core.residency || "NOT_RESIDENT"} · Model loads: ${number(core.model_loads, 0)} · Queries: ${number(core.queries_served, 0)} · Reloads avoided: ${number(core.reloads_avoided, 0)} · Reuse ratio: ${number(core.core_reuse_ratio, 2)}`;
  const context = state.context || {};
  $("contextTokens").textContent = `${number(context.tokens, 0)} / ${number(context.token_budget, 0)}`;
  $("contextMeter").style.width = `${Math.min(100, 100 * (context.tokens || 0) / Math.max(1, context.token_budget || 1))}%`;
  $("recordsUsed").textContent = context.records_used || 0;
  $("recordsDiscarded").textContent = context.records_discarded || 0;
  $("funnelBrain").textContent = bytes((state.brain || {}).active_bytes || 0);
  $("funnelRecords").textContent = `${number(context.records_retained ?? context.records_used, 0)} / ${number(context.records_retrieved || (state.knowledge || {}).retrieved, 0)}`;
  $("funnelEvidence").textContent = bytes(context.evidence_bytes ?? context.bytes ?? 0);
  $("funnelCore").textContent = `${number(context.tokens, 0)} tokens`;
  $("tokensAvoided").textContent = context.tokens_avoided == null ? "—" : number(context.tokens_avoided, 0);
  const factText = context.required_facts_total == null ? "—" : `${number(context.required_facts_found, 0)} / ${number(context.required_facts_total, 0)}`;
  $("contextQuality").textContent = `${factText} · ${context.grounding == null ? "grounding —" : context.grounding ? "grounding PASS" : "grounding FAIL"}`;
  const resources = state.resources || {}, storage = state.storage || {};
  $("pressure").textContent = resources.pressure || "UNKNOWN";
  $("cpu").textContent = resources.cpu_average_percent == null ? "—" : `${number(resources.cpu_average_percent, 1)}%`;
  $("ram").textContent = bytes(resources.ram_bytes);
  $("workingPeak").textContent = bytes(resources.working_set_peak_bytes);
  $("privateBytes").textContent = bytes(resources.private_bytes);
  $("availableRam").textContent = bytes(resources.available_system_ram_bytes);
  $("memoryGrowth").textContent = bytes(resources.memory_growth_bytes);
  $("ssd").textContent = bytes(storage.physical_bytes);
  $("pss").textContent = bytes(resources.pss_bytes);
  $("storageDetail").textContent = `faults ${number(storage.major_faults, 0)} major / ${number(storage.minor_faults, 0)} minor · cache ${storage.cache_state || "UNKNOWN"} · logical ${bytes(storage.logical_bytes)}`;
  renderRecords(state.knowledge);
  const bottleneck = state.bottleneck || {};
  $("bottleneckShare").textContent = bottleneck.share_percent == null ? "—" : `${number(bottleneck.share_percent, 1)}%`;
  $("bottleneckMeter").style.width = `${Math.min(100, Number(bottleneck.share_percent || 0))}%`;
  $("bottleneck").textContent = bottleneck.duration_ms == null ? bottleneck.label || "Aguardando dados." : `${bottleneck.label}: ${ms(bottleneck.duration_ms)} do tempo instrumentado.`;
  $("worked").textContent = (state.components?.worked || []).join(" · ") || "—";
  $("sleeping").textContent = (state.components?.sleeping || []).join(" · ") || "—";
  renderTimeline(state.timeline);
  renderPhases(state.phases);
  const stream = state.event_stream || {};
  $("eventStats").textContent = `seq ${stream.latest_sequence || 0} · dropped ${stream.dropped_events || 0}`;
  $("answer").textContent = state.answer || "Aguardando resposta.";
  $("quality").textContent = state.quality?.status || "UNKNOWN";
  const privacy = state.privacy || {};
  const flags = Object.entries(privacy).filter(([, hidden]) => hidden).map(([name]) => name.replace("_hidden", ""));
  $("privacy").textContent = flags.length ? `privacy: ${flags.join(", ")} oculto(s)` : "privacy: conteúdo visível";
}

let refreshPending = false;
async function refresh() {
  if (refreshPending) return;
  refreshPending = true;
  try {
    const response = await fetch("/api/state", {cache: "no-store"});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    render(await response.json());
  } catch (error) {
    $("streamStatus").textContent = "offline";
    $("streamStatus").classList.remove("online");
  } finally { refreshPending = false; }
}

const stream = new EventSource("/api/events");
stream.addEventListener("open", () => { $("streamStatus").innerHTML = "<i></i> conectado"; $("streamStatus").classList.add("online"); });
stream.addEventListener("brain-event", refresh);
stream.addEventListener("error", () => { $("streamStatus").innerHTML = "<i></i> reconectando"; $("streamStatus").classList.remove("online"); });

$("simpleMode").addEventListener("click", () => { document.body.classList.remove("technical"); $("simpleMode").classList.add("active"); $("technicalMode").classList.remove("active"); });
$("technicalMode").addEventListener("click", () => { document.body.classList.add("technical"); $("technicalMode").classList.add("active"); $("simpleMode").classList.remove("active"); });
$("motionToggle").addEventListener("click", () => { const off = document.body.classList.toggle("motion-off"); $("motionToggle").textContent = `Animação: ${off ? "OFF" : "ON"}`; $("motionToggle").setAttribute("aria-pressed", String(!off)); });
refresh();
