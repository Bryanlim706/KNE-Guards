const $ = (id) => document.getElementById(id);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

let sb = null;

async function initSupabase() {
  if (sb) return sb;
  const res = await fetch("/config");
  const cfg = await res.json();
  if (!cfg.supabase_url || !cfg.supabase_anon_key) {
    throw new Error("Supabase not configured on the server.");
  }
  sb = window.supabase.createClient(cfg.supabase_url, cfg.supabase_anon_key);
  window._sb = sb;
  return sb;
}

async function accessToken() {
  const client = await initSupabase();
  const { data } = await client.auth.getSession();
  return data.session ? data.session.access_token : null;
}

const ROUTES = ["dashboard", "products", "runs", "agents", "settings"];

const state = {
  me: { email: null, challengerReady: false },
  collections: { specs: [], runs: [] },
  dashboard: { expression: null, challenge: null, simulation: null, meta: "" },
  agents: null,
  agentsDraft: null,
  personaResults: {},
  personaRunning: {},
  runFilter: "all",
  selectedRunId: null,
  runDetails: new Map(),
};

const AGENTS_DRAFT_KEY = "kne:agents-draft";
const AGENTS_INPUT_IDS = [
  "agentsName",
  "agentsCategory",
  "agentsPrice",
  "agentsSegment",
  "agentsFeatures",
  "agentsSubstitutes",
  "agentsPitch",
];
const VERDICT_LABELS = {
  would_try: "Would try",
  skeptical: "Skeptical",
  pass: "Pass",
  wrong_fit: "Wrong fit",
};
const VERDICT_CHIP = {
  would_try: "sev-low",
  skeptical: "sev-med",
  pass: "sev-high",
  wrong_fit: "sev-high",
};

const TOAST_ICONS = { success: "✓", error: "!", info: "i" };
const TOAST_TITLES = {
  success: "Saved",
  error: "Something went wrong",
  info: "Heads up",
};

let confirmResolver = null;

function setText(id, value) {
  const el = $(id);
  if (el) el.textContent = value;
}

function setHtml(id, value) {
  const el = $(id);
  if (el) el.innerHTML = value;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function pct(value) {
  return `${(Number(value || 0) * 100).toFixed(1)}%`;
}

function currency(value) {
  const amount = Number(value || 0);
  return `$${amount.toFixed(amount % 1 === 0 ? 0 : 2)}`;
}

function formatDate(raw) {
  if (!raw) return "—";
  return new Date(`${raw}Z`).toLocaleString();
}

function clampNumber(value, fallback, min, max) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(min, Math.min(max, parsed));
}

function normalizeLines(value) {
  return String(value || "")
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeCsv(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function toast(message, { type = "success", title, duration = 3200 } = {}) {
  const container = $("toastContainer");
  if (!container) return;

  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.innerHTML = `
    <span class="toast-icon">${TOAST_ICONS[type] || "i"}</span>
    <div class="toast-copy">
      <strong>${escapeHtml(title || TOAST_TITLES[type] || "")}</strong>
      <span>${escapeHtml(message)}</span>
    </div>
    <button class="toast-close" type="button" aria-label="Dismiss">×</button>`;

  const dismiss = () => {
    el.classList.add("leaving");
    window.setTimeout(() => el.remove(), 180);
  };

  let timer = null;
  if (duration > 0) timer = window.setTimeout(dismiss, duration);

  el.querySelector(".toast-close").addEventListener("click", () => {
    if (timer) window.clearTimeout(timer);
    dismiss();
  });

  container.appendChild(el);
}

async function apiFetch(url, options) {
  const token = await accessToken();
  if (!token) {
    window.location.href = "/login";
    throw new Error("unauthenticated");
  }
  const opts = { ...(options || {}) };
  opts.headers = { ...(opts.headers || {}), Authorization: `Bearer ${token}` };
  const res = await fetch(url, opts);
  if (res.status === 401) {
    window.location.href = "/login";
    throw new Error("unauthenticated");
  }
  return res;
}

async function readJson(res) {
  const raw = await res.text();
  if (!raw) return {};

  try {
    return JSON.parse(raw);
  } catch (_) {
    const type = res.headers.get("content-type") || "unknown content type";
    throw new Error(
      `Expected JSON but received ${type} (status ${res.status}).`
    );
  }
}

function collectSpec() {
  return {
    name: $("name").value.trim(),
    category: $("category").value.trim(),
    price_monthly: Number.parseFloat($("price").value || "0"),
    target_segment: $("segment").value.trim(),
    features: normalizeLines($("features").value),
    substitutes: normalizeCsv($("substitutes").value),
  };
}

function collectDraft() {
  return {
    spec: collectSpec(),
    pitch: $("pitch").value.trim(),
    personas: clampNumber($("personas").value, 100, 5, 2000),
    days: clampNumber($("days").value, 30, 1, 120),
    seed: clampNumber($("seed").value, 42, 0, 999999),
  };
}

function validateDraft(spec) {
  if (!spec.name) return "Add a product name first.";
  if (!spec.category) return "Add a category so the brief is anchored.";
  if (!Number.isFinite(spec.price_monthly) || spec.price_monthly < 0) {
    return "Price must be a valid non-negative number.";
  }
  if (!spec.target_segment) return "Describe the student segment you are targeting.";
  if (spec.features.length === 0) return "List at least one feature before running the model.";
  return null;
}

function applySpec(spec) {
  $("name").value = spec.name || "";
  $("category").value = spec.category || "";
  $("price").value = spec.price_monthly ?? "";
  $("segment").value = spec.target_segment || "";
  $("features").value = (spec.features || []).join("\n");
  $("substitutes").value = (spec.substitutes || []).join(", ");
  if ($("pitch")) $("pitch").value = spec.pitch_text || "";
  syncDraftPreview();
}

function buildHypotheses(draft) {
  const { spec, pitch, days, personas } = draft;
  const firstFeature = spec.features[0] || "a clear daily win";
  const leadSubstitute = spec.substitutes[0] || "free alternatives students already trust";
  const priceLine =
    spec.price_monthly > 0
      ? `Students must feel ${currency(spec.price_monthly)}/month is justified within the first week.`
      : "Free access shifts the risk from pricing to whether the habit loop is strong enough.";

  const items = [
    spec.target_segment
      ? `${spec.target_segment} will try ${spec.name || "this product"} if "${firstFeature}" feels immediately useful.`
      : "A clearly defined student segment needs to be convinced in the first session.",
    priceLine,
    `The product needs to beat ${leadSubstitute} on convenience, not just raw capability.`,
    `A ${days}-day run across ${personas} personas will mostly reveal onboarding, retention, and substitution risk.`,
  ];

  if (pitch) {
    items.push("The challenger will test whether the current narrative sounds specific, defensible, and believable.");
  }

  return items.slice(0, 4);
}

function buildBriefSummary(spec) {
  if (!spec.name && !spec.category && !spec.target_segment) {
    return "Give the simulator a product brief and it will summarize the current bet here.";
  }
  const category = spec.category || "student product";
  const segment = spec.target_segment || "students";
  const firstFeature = spec.features[0];
  if (firstFeature) {
    return `${spec.name || "This concept"} is a ${category} bet for ${segment}. The lead promise is "${firstFeature}", with retention depending on whether that value shows up quickly.`;
  }
  return `${spec.name || "This concept"} is a ${category} bet for ${segment}. Add feature detail to make the simulator pressure the right assumptions.`;
}

function renderDraftPreview() {
  const draft = collectDraft();
  const { spec } = draft;

  setText("activeProductName", spec.name || "Untitled concept");
  setText("activeProductSummary", buildBriefSummary(spec));

  const briefCards = [
    { label: "Category", value: spec.category || "Unspecified" },
    { label: "Segment", value: spec.target_segment || "Unspecified" },
    { label: "Monthly price", value: currency(spec.price_monthly || 0) },
    { label: "Feature count", value: String(spec.features.length || 0) },
    { label: "Substitutes", value: String(spec.substitutes.length || 0) },
    { label: "Run profile", value: `${draft.personas} personas / ${draft.days} days` },
  ];

  setHtml(
    "briefCards",
    briefCards
      .map(
        (item) => `
          <article class="brief-card">
            <span>${escapeHtml(item.label)}</span>
            <strong>${escapeHtml(item.value)}</strong>
          </article>`
      )
      .join("")
  );

  const tags = [
    ...spec.features.map((feature) => ({ label: feature, kind: "feature" })),
    ...spec.substitutes.map((substitute) => ({ label: substitute, kind: "substitute" })),
  ];

  setHtml(
    "featureTags",
    tags.length
      ? tags
        .map(
          (tag) =>
            `<span class="tag ${tag.kind === "substitute" ? "substitute" : ""}">${escapeHtml(tag.label)}</span>`
        )
        .join("")
      : `<span class="tag muted">No features or substitutes added yet.</span>`
  );

  setHtml(
    "hypothesisList",
    buildHypotheses(draft)
      .map((item) => `<li>${escapeHtml(item)}</li>`)
      .join("")
  );

  setText("heroPrice", currency(spec.price_monthly || 0));
  renderSignalBoard();
}

function drawRetention(curve) {
  const svg = $("chart");
  svg.innerHTML = "";

  if (!Array.isArray(curve) || curve.length < 2) return;

  const width = 600;
  const height = 220;
  const pad = 30;
  const ns = "http://www.w3.org/2000/svg";
  const x = (index) => pad + (index / (curve.length - 1)) * (width - pad * 2);
  const y = (value) => height - pad - value * (height - pad * 2);

  for (let marker = 0; marker <= 1; marker += 0.25) {
    const line = document.createElementNS(ns, "line");
    line.setAttribute("x1", pad);
    line.setAttribute("x2", width - pad);
    line.setAttribute("y1", y(marker));
    line.setAttribute("y2", y(marker));
    line.setAttribute("stroke", "#d9d2c7");
    line.setAttribute("stroke-dasharray", "4 5");
    svg.appendChild(line);

    const label = document.createElementNS(ns, "text");
    label.setAttribute("x", 2);
    label.setAttribute("y", y(marker) + 4);
    label.setAttribute("fill", "#7d6f62");
    label.setAttribute("font-size", "10");
    label.textContent = `${Math.round(marker * 100)}%`;
    svg.appendChild(label);
  }

  const area = document.createElementNS(ns, "path");
  let areaPath = `M ${x(0)} ${y(0)} `;
  curve.forEach((value, index) => {
    areaPath += `L ${x(index)} ${y(value)} `;
  });
  areaPath += `L ${x(curve.length - 1)} ${y(0)} Z`;
  area.setAttribute("d", areaPath);
  area.setAttribute("fill", "url(#retentionGradient)");

  const defs = document.createElementNS(ns, "defs");
  defs.innerHTML = `
    <linearGradient id="retentionGradient" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#0f766e" stop-opacity="0.45"></stop>
      <stop offset="100%" stop-color="#0f766e" stop-opacity="0.04"></stop>
    </linearGradient>`;
  svg.appendChild(defs);
  svg.appendChild(area);

  const path = document.createElementNS(ns, "path");
  let pathData = `M ${x(0)} ${y(curve[0])}`;
  curve.forEach((value, index) => {
    if (index) pathData += ` L ${x(index)} ${y(value)}`;
  });
  path.setAttribute("d", pathData);
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", "#0f766e");
  path.setAttribute("stroke-width", "3");
  path.setAttribute("stroke-linecap", "round");
  path.setAttribute("stroke-linejoin", "round");
  svg.appendChild(path);

  const axis = document.createElementNS(ns, "text");
  axis.setAttribute("x", width / 2);
  axis.setAttribute("y", height - 6);
  axis.setAttribute("fill", "#7d6f62");
  axis.setAttribute("font-size", "10");
  axis.setAttribute("text-anchor", "middle");
  axis.textContent = `Day 0 to Day ${curve.length - 1}`;
  svg.appendChild(axis);
}

function buildSimulationInsights(report) {
  const breakdown = Object.entries(report.persona_breakdown || {});
  const ranked = breakdown
    .map(([name, counts]) => {
      const total = counts.total || 1;
      return {
        name,
        retainedRate: counts.retained / total,
        churnRate: (counts.abandoned + counts.switched) / total,
      };
    })
    .sort((a, b) => b.retainedRate - a.retainedRate);

  const strongest = ranked[0];
  const weakest = ranked.slice().sort((a, b) => b.churnRate - a.churnRate)[0];

  const dropEntries = Object.entries(report.drop_off_by_day || {}).sort((a, b) => b[1] - a[1]);
  const topDrop = dropEntries[0];

  const topSwitch = Object.entries(report.switched_to || {}).sort((a, b) => b[1] - a[1])[0];

  let viabilityTone = "warn";
  let viabilityLabel = "Mixed";
  if (report.viability_score >= 0.75) {
    viabilityTone = "good";
    viabilityLabel = "Strong";
  } else if (report.viability_score < 0.45) {
    viabilityTone = "bad";
    viabilityLabel = "Fragile";
  }

  return [
    {
      label: "Readiness",
      value: viabilityLabel,
      tone: viabilityTone,
      detail: `Viability score ${report.viability_score.toFixed(2)}`,
    },
    {
      label: "Best fit",
      value: strongest ? strongest.name : "—",
      tone: "good",
      detail: strongest ? `${pct(strongest.retainedRate)} retained` : "No persona signal yet",
    },
    {
      label: "Highest risk",
      value: weakest ? weakest.name : "—",
      tone: "bad",
      detail: weakest ? `${pct(weakest.churnRate)} churned or switched` : "No churn signal yet",
    },
    {
      label: "Primary threat",
      value: topSwitch ? topSwitch[0] : topDrop ? `Day ${topDrop[0]}` : "Stable",
      tone: "warn",
      detail: topSwitch
        ? `${topSwitch[1]} personas switched`
        : topDrop
          ? `${topDrop[1]} first-time drop-offs`
          : "No obvious pressure point",
    },
  ];
}

function renderSignalBoard() {
  const draft = collectDraft();
  const expression = state.dashboard.expression;
  const challenge = state.dashboard.challenge;
  const simulation = state.dashboard.simulation;

  const cards = [
    {
      label: "Draft completeness",
      value: draft.spec.features.length ? "Ready" : "Needs detail",
      detail: `${draft.spec.features.length} features, ${draft.spec.substitutes.length} substitutes`,
      tone: draft.spec.features.length ? "good" : "warn",
    },
    {
      label: "Expression AI",
      value: expression ? (expression.error ? "Blocked" : "Ready") : "Not run",
      detail: expression
        ? expression.error
          ? expression.error
          : "Sharper pitch and deck opener available"
        : "Turn rough notes into a clearer narrative first",
      tone: expression ? (expression.error ? "bad" : "good") : "muted",
    },
    {
      label: "Challenger",
      value: challenge ? (challenge.error ? "Blocked" : "Complete") : "Not run",
      detail: challenge
        ? challenge.error
          ? challenge.error
          : `${(challenge.kill_shots || []).length} kill shots surfaced`
        : "Interrogate the pitch before simulating",
      tone: challenge ? (challenge.error ? "bad" : "good") : "muted",
    },
    {
      label: "Simulation",
      value: simulation ? pct(simulation.adoption_rate) : "Not run",
      detail: simulation
        ? `${pct(simulation.switched_rate)} switched, viability ${simulation.viability_score.toFixed(2)}`
        : "Run synthetic personas to get adoption and retention signal",
      tone: simulation ? "good" : "muted",
    },
  ];

  setHtml(
    "signalGrid",
    cards
      .map(
        (card) => `
          <article class="signal-card tone-${escapeHtml(card.tone)}">
            <span>${escapeHtml(card.label)}</span>
            <strong>${escapeHtml(card.value)}</strong>
            <p>${escapeHtml(card.detail)}</p>
          </article>`
      )
      .join("")
  );

  setText("runMeta", state.dashboard.meta || "");
  setDashboardVisibility();
}

function setDashboardVisibility() {
  const hasOutput = Boolean(state.dashboard.expression || state.dashboard.challenge || state.dashboard.simulation);
  if ($("dashboardEmpty")) $("dashboardEmpty").hidden = hasOutput;
}

function renderSimulation(report, meta = "") {
  state.dashboard.simulation = report;
  state.dashboard.meta = meta;

  $("results").hidden = false;
  $("resultTitle").textContent = `Simulation results for ${report.product_name}`;
  $("kAdoption").textContent = pct(report.adoption_rate);
  $("kAbandoned").textContent = pct(report.abandoned_rate);
  $("kSwitched").textContent = pct(report.switched_rate);
  $("kViability").textContent = report.viability_score.toFixed(2);

  drawRetention(report.retention_curve || []);

  setHtml(
    "simulationInsights",
    buildSimulationInsights(report)
      .map(
        (item) => `
          <article class="insight-card tone-${escapeHtml(item.tone)}">
            <span>${escapeHtml(item.label)}</span>
            <strong>${escapeHtml(item.value)}</strong>
            <p>${escapeHtml(item.detail)}</p>
          </article>`
      )
      .join("")
  );

  const tbody = document.querySelector("#archetypes tbody");
  tbody.innerHTML = "";
  Object.entries(report.persona_breakdown || {})
    .sort(([a], [b]) => a.localeCompare(b))
    .forEach(([archetype, counts]) => {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td class="caps">${escapeHtml(archetype)}</td>
        <td>${counts.retained}</td>
        <td>${counts.abandoned}</td>
        <td>${counts.switched}</td>
        <td>${counts.total}</td>`;
      tbody.appendChild(row);
    });

  const switchedEntries = Object.entries(report.switched_to || {}).sort((a, b) => b[1] - a[1]);
  $("switchedTo").innerHTML = switchedEntries.length
    ? switchedEntries
      .map(([name, count]) => `<li><strong>${escapeHtml(name)}</strong><span>${count} personas</span></li>`)
      .join("")
    : `<li><strong>No switches</strong><span>Personas stayed or abandoned instead.</span></li>`;

  const dropEntries = Object.entries(report.drop_off_by_day || {}).sort((a, b) => Number(a[0]) - Number(b[0]));
  setHtml(
    "dropoffList",
    dropEntries.length
      ? dropEntries
        .map(([day, count]) => `<li><strong>Day ${day}</strong><span>${count} first-time exits</span></li>`)
        .join("")
      : `<li><strong>No sharp drop-off</strong><span>The run did not record any first-time abandon or switch events.</span></li>`
  );

  renderSignalBoard();
}

function renderExpression(data, meta = "") {
  state.dashboard.expression = data;
  state.dashboard.meta = meta;

  const panel = $("expressionPanel");
  if (panel) panel.hidden = false;

  const errorEl = $("expressionError");
  const bodyEl = $("expressionBody");
  if (!errorEl || !bodyEl) {
    renderSignalBoard();
    return;
  }

  if (data.error) {
    errorEl.hidden = false;
    errorEl.textContent = data.error;
    bodyEl.hidden = true;
    renderSignalBoard();
    return;
  }

  errorEl.hidden = true;
  bodyEl.hidden = false;
  setText("eFraming", data.founder_framing || "");
  setText("ePitch", data.elevator_pitch || "");
  setText("eDeckOpening", data.pitch_deck_opening || "");

  const renderSimpleList = (id, items, emptyText) => {
    setHtml(
      id,
      (items || []).length
        ? items.map((item) => `<li><span>${escapeHtml(item)}</span></li>`).join("")
        : `<li class="quiet">${escapeHtml(emptyText)}</li>`
    );
  };

  renderSimpleList("ePains", data.audience_pains, "No audience pains returned.");
  renderSimpleList("eDifferentiators", data.differentiators, "No differentiators returned.");
  renderSimpleList("eStoryBeats", data.story_beats, "No story beats returned.");
  renderSignalBoard();
}

function renderChallenge(data, meta = "") {
  state.dashboard.challenge = data;
  state.dashboard.meta = meta;

  $("challengePanel").hidden = false;
  const errorEl = $("challengeError");
  const bodyEl = $("challengeBody");

  if (data.error) {
    errorEl.hidden = false;
    errorEl.textContent = data.error;
    bodyEl.hidden = true;
    renderSignalBoard();
    return;
  }

  errorEl.hidden = true;
  bodyEl.hidden = false;
  $("cVerdict").textContent = data.verdict || "";

  const renderStack = (target, items, mapper, emptyText) => {
    target.innerHTML = (items || []).length
      ? items.map(mapper).join("")
      : `<li class="quiet">${escapeHtml(emptyText)}</li>`;
  };

  renderStack(
    $("cKillShots"),
    data.kill_shots,
    (item) =>
      `<li><strong>${escapeHtml(item.risk)}</strong><span>${escapeHtml(item.why_it_kills)}</span></li>`,
    "No existential kill shots returned."
  );

  renderStack(
    $("cAssumptions"),
    data.assumption_challenges,
    (item) =>
      `<li><span class="chip sev-${escapeHtml(item.severity)}">${escapeHtml(item.severity)}</span><strong>${escapeHtml(item.claim)}</strong><span>${escapeHtml(item.pushback)}</span></li>`,
    "No explicit assumption challenges returned."
  );

  renderStack(
    $("cFeatures"),
    data.feature_critiques,
    (item) => `<li><strong>${escapeHtml(item.feature)}</strong><span>${escapeHtml(item.critique)}</span></li>`,
    "No feature-level critiques returned."
  );

  renderStack(
    $("cSubstitutes"),
    data.substitute_risks,
    (item) => `<li><strong>${escapeHtml(item.substitute)}</strong><span>${escapeHtml(item.why_it_wins)}</span></li>`,
    "No substitute risks returned."
  );

  const segment = data.segment_coherence || {};
  $("cSegmentAssessment").textContent = segment.assessment || "No segment assessment returned.";
  renderStack(
    $("cSegmentConcerns"),
    segment.concerns || [],
    (item) => `<li><strong>Concern</strong><span>${escapeHtml(item)}</span></li>`,
    "No segment concerns returned."
  );

  const pricing = data.pricing_risks || {};
  $("cPricingAssessment").textContent = pricing.assessment || "No pricing assessment returned.";
  renderStack(
    $("cPricingConcerns"),
    pricing.concerns || [],
    (item) => `<li><strong>Risk</strong><span>${escapeHtml(item)}</span></li>`,
    "No pricing concerns returned."
  );

  $("cSteelman").textContent = data.steelman || "No steelman argument returned.";
  renderSignalBoard();
}

async function runSimulation() {
  const draft = collectDraft();
  const validationError = validateDraft(draft.spec);
  if (validationError) {
    toast(validationError, { type: "error", title: "Incomplete brief" });
    return;
  }

  const button = $("run");
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "Running...";

  try {
    const res = await apiFetch("/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        spec: draft.spec,
        personas: draft.personas,
        days: draft.days,
        seed: draft.seed,
      }),
    });
    const data = await readJson(res);
    if (!res.ok) {
      toast(data.error || res.statusText, { type: "error" });
      return;
    }

    renderSimulation(data, `Latest run: simulation #${data._run_id}`);
    toast(`Simulation #${data._run_id} completed.`, { title: "Run complete" });
    await refreshRuns({ silent: true });
  } catch (error) {
    if (error.message !== "unauthenticated") {
      toast(error.message, { type: "error", title: "Simulation failed" });
    }
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

async function expressIdea() {
  const draft = collectDraft();
  const validationError = validateDraft(draft.spec);
  if (validationError) {
    toast(validationError, { type: "error", title: "Incomplete brief" });
    return;
  }

  const button = $("expressIdea");
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "Writing...";

  try {
    const res = await apiFetch("/express-idea", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        spec: draft.spec,
        pitch_text: draft.pitch || null,
      }),
    });
    const data = await readJson(res);
    if (!res.ok) {
      toast(data.error || res.statusText, { type: "error" });
      return;
    }

    renderExpression(data, "AI expression helper ready");
    toast(
      data.error ? data.error : "Sharper pitch language is ready to reuse.",
      { title: data.error ? "Expression blocked" : "Expression ready", type: data.error ? "info" : "success" }
    );
  } catch (error) {
    if (error.message !== "unauthenticated") {
      toast(error.message, { type: "error", title: "Expression failed" });
    }
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

async function challengePitch() {
  const draft = collectDraft();
  const validationError = validateDraft(draft.spec);
  if (validationError) {
    toast(validationError, { type: "error", title: "Incomplete brief" });
    return;
  }

  const button = $("challenge");
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "Challenging...";

  try {
    const res = await apiFetch("/challenge", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        spec: draft.spec,
        pitch_text: draft.pitch || null,
      }),
    });
    const data = await readJson(res);
    if (!res.ok) {
      toast(data.error || res.statusText, { type: "error" });
      return;
    }

    renderChallenge(data, data._run_id ? `Latest run: challenge #${data._run_id}` : "Challenge completed");
    toast(
      data._run_id ? `Challenge #${data._run_id} completed.` : "Challenge completed.",
      { title: data.error ? "Challenge blocked" : "Challenge finished", type: data.error ? "info" : "success" }
    );
    await refreshRuns({ silent: true });
  } catch (error) {
    if (error.message !== "unauthenticated") {
      toast(error.message, { type: "error", title: "Challenge failed" });
    }
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

function applySuggestedPitch(fieldName) {
  const expression = state.dashboard.expression;
  if (!expression || expression.error) {
    toast("Generate AI wording first.", { type: "info", title: "No suggestion yet" });
    return;
  }

  const value = expression[fieldName];
  if (!value) {
    toast("That suggestion is empty.", { type: "info", title: "Nothing to apply" });
    return;
  }

  $("pitch").value = value;
  syncDraftPreview();
  toast("Inserted the AI suggestion into your draft pitch.", { title: "Pitch updated" });
}

async function loadFixture({ silent = false } = {}) {
  try {
    const res = await fetch("/fixture");
    if (!res.ok) {
      throw new Error(`Example request failed (${res.status}).`);
    }
    const spec = await readJson(res);
    applySpec(spec);
    $("pitch").value =
      "Students need a faster way to turn lecture notes into spaced repetition without building a workflow from scratch.";
    syncDraftPreview();
    if (!silent) toast("Loaded example brief into the composer.", { type: "info", title: "Example ready" });
  } catch (error) {
    toast(error.message, { type: "error", title: "Could not load example" });
  }
}

function openSaveDialog() {
  const draft = collectDraft();
  const validationError = validateDraft(draft.spec);
  if (validationError) {
    toast(validationError, { type: "error", title: "Incomplete brief" });
    return;
  }

  const dialog = $("saveDialog");
  const field = $("saveSpecName");
  if ($("saveDialogError")) $("saveDialogError").hidden = true;
  if (field) field.value = draft.spec.name;

  if (dialog && typeof dialog.showModal === "function") {
    dialog.showModal();
    if (field) {
      field.focus();
      field.select();
    }
    return;
  }

  const fallback = window.prompt("Save this product as:", draft.spec.name);
  if (fallback) saveProduct(fallback);
}

async function saveProduct(name) {
  const draft = collectDraft();
  const spec = { ...draft.spec, pitch_text: draft.pitch || "" };

  try {
    const res = await apiFetch("/specs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, spec }),
    });
    const data = await readJson(res);
    if (!res.ok) {
      throw new Error(data.error || res.statusText);
    }

    closeDialog($("saveDialog"));
    toast(`"${name}" is now in your saved products.`, { title: "Product saved" });
    await refreshSpecs({ silent: true });
  } catch (error) {
    const err = $("saveDialogError");
    const dialog = $("saveDialog");
    if (err && dialog && dialog.open) {
      err.hidden = false;
      err.textContent = error.message;
      return;
    }
    toast(error.message, { type: "error", title: "Save failed" });
  }
}

function closeDialog(dialog) {
  if (!dialog) return;
  if (typeof dialog.close === "function" && dialog.open) dialog.close();
}

function askForConfirmation({ eyebrow = "Confirm", title, message, confirmLabel = "Confirm", danger = false }) {
  const dialog = $("confirmDialog");
  if (!dialog || typeof dialog.showModal !== "function") {
    return Promise.resolve(window.confirm(message));
  }

  $("confirmEyebrow").textContent = eyebrow;
  $("confirmTitle").textContent = title;
  $("confirmMessage").textContent = message;
  $("confirmApprove").textContent = confirmLabel;
  $("confirmApprove").className = danger ? "danger" : "";

  dialog.showModal();
  return new Promise((resolve) => {
    confirmResolver = resolve;
  });
}

function resolveConfirmation(value) {
  closeDialog($("confirmDialog"));
  if (confirmResolver) {
    confirmResolver(value);
    confirmResolver = null;
  }
}

async function refreshSpecs({ silent = false } = {}) {
  try {
    const res = await apiFetch("/specs");
    const data = await readJson(res);
    state.collections.specs = data.specs || [];
    updateGlobalCounts();
    if (getRoute() === "products") renderProducts();
  } catch (error) {
    if (!silent && error.message !== "unauthenticated") {
      toast(error.message, { type: "error", title: "Could not load products" });
    }
  }
}

function renderProducts() {
  const list = $("productsList");
  if (state.collections.specs.length === 0) {
    list.innerHTML = `<div class="empty-state grid-empty"><strong>No saved products yet.</strong>Save a brief from the dashboard and it will show up here.</div>`;
    return;
  }

  list.innerHTML = "";
  state.collections.specs.forEach((item) => {
    const card = document.createElement("article");
    card.className = "card";
    const features = (item.spec.features || []).slice(0, 3);
    card.innerHTML = `
      <div class="card-head">
        <div>
          <p class="card-title">${escapeHtml(item.name)}</p>
          <p class="card-sub">${escapeHtml(item.spec.category || "Unspecified")} · ${currency(item.spec.price_monthly || 0)}/mo</p>
        </div>
        <span class="chip">${formatDate(item.created_at)}</span>
      </div>
      <p class="card-copy">${escapeHtml(item.spec.target_segment || "No target segment")}</p>
      <div class="tag-cloud compact">
        ${features.map((feature) => `<span class="tag">${escapeHtml(feature)}</span>`).join("")}
        ${features.length === 0 ? `<span class="tag muted">No features listed</span>` : ""}
      </div>
      <div class="card-actions">
        <button type="button" data-action="load">Load into dashboard</button>
        <button type="button" class="ghost" data-action="load-agents">Load to Agents</button>
        <button type="button" class="ghost" data-action="delete">Delete</button>
      </div>`;

    card.querySelector('[data-action="load"]').addEventListener("click", () => {
      applySpec(item.spec);
      window.location.hash = "#/dashboard";
      toast(`Loaded "${item.name}" into the dashboard.`, { type: "info", title: "Product loaded" });
    });

    card.querySelector('[data-action="load-agents"]').addEventListener("click", () => {
      applyAgentsSpec(item.spec);
      state.personaResults = {};
      window.location.hash = "#/agents";
      toast(`Loaded "${item.name}" into the Agents page.`, { type: "info", title: "Product loaded" });
    });

    card.querySelector('[data-action="delete"]').addEventListener("click", async () => {
      const approved = await askForConfirmation({
        eyebrow: "Delete",
        title: "Delete saved product?",
        message: `Remove "${item.name}" from your saved products?`,
        confirmLabel: "Delete product",
        danger: true,
      });
      if (!approved) return;
      await apiFetch(`/specs/${item.id}`, { method: "DELETE" });
      toast(`Deleted "${item.name}".`, { type: "info", title: "Product removed" });
      await refreshSpecs({ silent: true });
      renderProducts();
    });

    list.appendChild(card);
  });
}

async function refreshRuns({ silent = false } = {}) {
  try {
    const res = await apiFetch("/runs?limit=100");
    const data = await readJson(res);
    state.collections.runs = data.runs || [];
    updateGlobalCounts();
    if (getRoute() === "runs") renderRuns();
  } catch (error) {
    if (!silent && error.message !== "unauthenticated") {
      toast(error.message, { type: "error", title: "Could not load runs" });
    }
  }
}

function filteredRuns() {
  if (state.runFilter === "all") return state.collections.runs;
  return state.collections.runs.filter((run) => run.kind === state.runFilter);
}

function renderRuns() {
  const wrap = $("runsList");
  const runs = filteredRuns();

  if (runs.length === 0) {
    wrap.innerHTML = `<div class="detail-placeholder">No ${state.runFilter === "all" ? "" : state.runFilter} runs yet.</div>`;
    renderRunDetail(null);
    return;
  }

  wrap.innerHTML = `
    <table class="run-table">
      <thead>
        <tr>
          <th>Created</th>
          <th>Type</th>
          <th>Product</th>
          <th></th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>`;

  const tbody = wrap.querySelector("tbody");
  runs.forEach((run) => {
    const row = document.createElement("tr");
    row.className = run.id === state.selectedRunId ? "selected" : "";
    row.innerHTML = `
      <td>${escapeHtml(formatDate(run.created_at))}</td>
      <td><span class="chip ${run.kind === "challenge" ? "tag-challenge" : "tag-simulation"}">${escapeHtml(run.kind)}</span></td>
      <td>${escapeHtml(run.product_name || "Unnamed product")}</td>
      <td class="cell-actions"><button type="button" class="ghost small" data-action="delete">Delete</button></td>`;

    row.addEventListener("click", (event) => {
      if (event.target.dataset.action === "delete") return;
      loadRunDetail(run.id);
    });

    row.querySelector('[data-action="delete"]').addEventListener("click", async (event) => {
      event.stopPropagation();
      const approved = await askForConfirmation({
        eyebrow: "Delete",
        title: "Delete run?",
        message: `Delete ${run.kind} run for "${run.product_name}"?`,
        confirmLabel: "Delete run",
        danger: true,
      });
      if (!approved) return;
      await apiFetch(`/runs/${run.id}`, { method: "DELETE" });
      if (state.selectedRunId === run.id) {
        state.selectedRunId = null;
        renderRunDetail(null);
      }
      state.runDetails.delete(run.id);
      await refreshRuns({ silent: true });
      renderRuns();
      toast("Run deleted.", { type: "info", title: "Removed" });
    });

    tbody.appendChild(row);
  });

  if (!state.selectedRunId && runs[0]) {
    loadRunDetail(runs[0].id);
  }
}

async function loadRunDetail(id) {
  state.selectedRunId = id;
  renderRuns();

  if (state.runDetails.has(id)) {
    renderRunDetail(state.runDetails.get(id));
    return;
  }

  try {
    const res = await apiFetch(`/runs/${id}`);
    const data = await readJson(res);
    if (!res.ok) throw new Error(data.error || res.statusText);
    state.runDetails.set(id, data);
    renderRunDetail(data);
  } catch (error) {
    renderRunDetail(null, error.message);
  }
}

function renderRunDetail(run, errorMessage = "") {
  const body = $("runDetailBody");
  if (!body) return;
  if (errorMessage) {
    body.innerHTML = `<div class="banner banner-error">${escapeHtml(errorMessage)}</div>`;
    return;
  }
  if (!run) {
    body.innerHTML = `Pick a run to inspect its result summary here.`;
    return;
  }

  if (run.kind === "simulation") {
    const report = run.result || {};
    body.innerHTML = `
      <div class="detail-header">
        <strong>${escapeHtml(run.product_name)}</strong>
        <span class="chip tag-simulation">Simulation</span>
      </div>
      <p class="detail-copy">Created ${escapeHtml(formatDate(run.created_at))}</p>
      <div class="detail-metrics">
        <article><span>Adoption</span><strong>${pct(report.adoption_rate)}</strong></article>
        <article><span>Switched</span><strong>${pct(report.switched_rate)}</strong></article>
        <article><span>Viability</span><strong>${escapeHtml((report.viability_score || 0).toFixed(2))}</strong></article>
      </div>
      <div class="detail-actions">
        <button type="button" id="openSelectedRun">Open on dashboard</button>
      </div>`;
  } else {
    const result = run.result || {};
    body.innerHTML = `
      <div class="detail-header">
        <strong>${escapeHtml(run.product_name)}</strong>
        <span class="chip tag-challenge">Challenge</span>
      </div>
      <p class="detail-copy">Created ${escapeHtml(formatDate(run.created_at))}</p>
      <div class="detail-metrics">
        <article><span>Kill shots</span><strong>${(result.kill_shots || []).length}</strong></article>
        <article><span>Assumptions</span><strong>${(result.assumption_challenges || []).length}</strong></article>
        <article><span>Pricing risks</span><strong>${((result.pricing_risks || {}).concerns || []).length}</strong></article>
      </div>
      <p class="detail-copy">${escapeHtml(result.verdict || result.error || "No verdict recorded.")}</p>
      <div class="detail-actions">
        <button type="button" id="openSelectedRun">Open on dashboard</button>
      </div>`;
  }

  const openButton = $("openSelectedRun");
  if (openButton) openButton.addEventListener("click", () => restoreRun(run));
}

function restoreRun(run) {
  if (run.kind === "simulation") {
    renderSimulation(run.result, `Restored run: simulation #${run.id}`);
  } else {
    renderChallenge(run.result, `Restored run: challenge #${run.id}`);
  }
  window.location.hash = "#/dashboard";
}

function paramBar(label, range) {
  const low = Math.round(range[0] * 100);
  const high = Math.round(range[1] * 100);
  return `
    <div class="param-bar">
      <span>${escapeHtml(label.replace(/_/g, " "))}</span>
      <div class="bar-track" title="${low}% to ${high}%">
        <div class="bar-fill" style="left:${low}%; width:${Math.max(high - low, 4)}%;"></div>
      </div>
    </div>`;
}

async function loadAgents() {
  const personasEl = $("agentsPersonas");
  const aiEl = $("agentsAI");

  if (state.agents) {
    renderAgents();
    return;
  }

  personasEl.innerHTML = `<div class="detail-placeholder">Loading agents...</div>`;
  if (aiEl) aiEl.innerHTML = "";

  try {
    const res = await apiFetch("/agents");
    const data = await readJson(res);
    state.agents = data;
    renderAgents();
  } catch (error) {
    personasEl.innerHTML = `<div class="banner banner-error">${escapeHtml(error.message)}</div>`;
  }
}

function renderAgents() {
  const personasEl = $("agentsPersonas");
  const aiEl = $("agentsAI");
  const data = state.agents || { personas: [], critic: null, expression: null };

  personasEl.innerHTML = "";
  data.personas.forEach((persona) => {
    const card = document.createElement("article");
    card.className = "card agent-card";
    card.dataset.archetype = persona.name;
    const bars = Object.entries(persona.params || {})
      .map(([label, range]) => paramBar(label, range))
      .join("");
    card.innerHTML = `
      <div class="agent-head">
        <span class="agent-icon">${escapeHtml(persona.name[0].toUpperCase())}</span>
        <div>
          <p class="card-title caps">${escapeHtml(persona.name)}</p>
          <p class="card-sub">${escapeHtml(persona.blurb)}</p>
        </div>
      </div>
      <div class="param-bars">${bars}</div>
      <div class="agent-actions">
        <button type="button" class="primary small" data-run-archetype="${escapeHtml(persona.name)}">Run my pitch</button>
        <span class="agent-status" data-status-archetype="${escapeHtml(persona.name)}"></span>
      </div>
      <div class="agent-result" data-result-archetype="${escapeHtml(persona.name)}" hidden></div>`;
    personasEl.appendChild(card);
    renderPersonaResult(persona.name);
  });

  if (!aiEl) return;
  aiEl.innerHTML = "";
  const helpers = [];
  if (data.critic) helpers.push({ ...data.critic, iconClass: "critic", icon: "!" });
  if (data.expression) helpers.push({ ...data.expression, iconClass: "expression", icon: "E" });
  helpers.forEach((helper) => {
    const card = document.createElement("article");
    card.className = "card agent-card critic-card";
    card.innerHTML = `
      <div class="agent-head">
        <span class="agent-icon ${helper.iconClass}">${escapeHtml(helper.icon)}</span>
        <div>
          <p class="card-title">${escapeHtml(helper.name)}</p>
          <p class="card-sub">${escapeHtml(helper.blurb)}</p>
        </div>
      </div>
      <div class="critic-meta">
        <span class="chip">${escapeHtml(helper.model)}</span>
        <span class="chip ${helper.ready ? "sev-low" : "sev-med"}">${helper.ready ? "Ready" : "Needs API key"}</span>
      </div>
      <p class="card-sub" style="margin-top:0.6rem;">Run this helper from the Dashboard.</p>`;
    aiEl.appendChild(card);
  });
}

function collectAgentsSpec() {
  return {
    name: $("agentsName").value.trim(),
    category: $("agentsCategory").value.trim(),
    price_monthly: Number.parseFloat($("agentsPrice").value || "0"),
    target_segment: $("agentsSegment").value.trim(),
    features: normalizeLines($("agentsFeatures").value),
    substitutes: normalizeCsv($("agentsSubstitutes").value),
  };
}

function persistAgentsDraft() {
  const draft = {
    spec: collectAgentsSpec(),
    pitch: $("agentsPitch").value.trim(),
  };
  state.agentsDraft = draft;
  try {
    localStorage.setItem(AGENTS_DRAFT_KEY, JSON.stringify(draft));
  } catch (_) {}
}

function applyAgentsSpec(spec) {
  if (!spec) return;
  $("agentsName").value = spec.name || "";
  $("agentsCategory").value = spec.category || "";
  $("agentsPrice").value = spec.price_monthly ?? "";
  $("agentsSegment").value = spec.target_segment || "";
  $("agentsFeatures").value = (spec.features || []).join("\n");
  $("agentsSubstitutes").value = (spec.substitutes || []).join(", ");
  $("agentsPitch").value = spec.pitch_text || "";
  persistAgentsDraft();
}

function restoreAgentsDraft() {
  let draft = null;
  try {
    const raw = localStorage.getItem(AGENTS_DRAFT_KEY);
    if (raw) draft = JSON.parse(raw);
  } catch (_) {}
  if (!draft) return;
  state.agentsDraft = draft;
  const spec = draft.spec || {};
  $("agentsName").value = spec.name || "";
  $("agentsCategory").value = spec.category || "";
  $("agentsPrice").value = spec.price_monthly ?? "";
  $("agentsSegment").value = spec.target_segment || "";
  $("agentsFeatures").value = (spec.features || []).join("\n");
  $("agentsSubstitutes").value = (spec.substitutes || []).join(", ");
  $("agentsPitch").value = draft.pitch || "";
}

async function runPersona(archetype) {
  if (state.personaRunning[archetype]) return;

  const spec = collectAgentsSpec();
  const invalid = validateDraft(spec);
  if (invalid) {
    state.personaResults[archetype] = { error: invalid };
    renderPersonaResult(archetype);
    return;
  }

  state.personaRunning[archetype] = true;
  const button = document.querySelector(`[data-run-archetype="${archetype}"]`);
  const statusEl = document.querySelector(`[data-status-archetype="${archetype}"]`);
  if (button) button.disabled = true;
  if (statusEl) statusEl.textContent = "Thinking...";

  try {
    const res = await apiFetch("/agents/react", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        archetype,
        spec,
        pitch_text: $("agentsPitch").value.trim() || null,
      }),
    });
    const data = await readJson(res);
    state.personaResults[archetype] = data;
  } catch (error) {
    state.personaResults[archetype] = { error: error.message };
  } finally {
    state.personaRunning[archetype] = false;
    if (button) button.disabled = false;
    if (statusEl) statusEl.textContent = "";
    renderPersonaResult(archetype);
  }
}

function renderPersonaResult(archetype) {
  const card = document.querySelector(`[data-archetype="${archetype}"]`);
  const slot = document.querySelector(`[data-result-archetype="${archetype}"]`);
  if (!slot) return;
  const result = state.personaResults[archetype];

  if (!result) {
    slot.hidden = true;
    slot.innerHTML = "";
    if (card) card.classList.remove("agent-card--persona-active");
    return;
  }

  slot.hidden = false;

  if (result.error) {
    slot.innerHTML = `<div class="banner banner-error">${escapeHtml(result.error)}</div>`;
    if (card) card.classList.remove("agent-card--persona-active");
    return;
  }

  const verdictKey = result.verdict || "skeptical";
  const verdictLabel = VERDICT_LABELS[verdictKey] || verdictKey;
  const verdictChip = VERDICT_CHIP[verdictKey] || "sev-med";
  const hook = result.biggest_hook || {};
  const objection = result.biggest_objection || {};
  const sub = result.likely_substitute || {};
  const fit = Math.max(0, Math.min(1, Number(result.persona_fit_score) || 0));
  const fitPct = Math.round(fit * 100);

  slot.innerHTML = `
    <div class="persona-result">
      <div class="persona-verdict-row">
        <span class="chip ${verdictChip}">${escapeHtml(verdictLabel)}</span>
        <div class="fit-meter">
          <span class="fit-label">Fit</span>
          <div class="bar-track"><div class="bar-fill" style="width:${fitPct}%"></div></div>
          <span class="fit-value">${fitPct}%</span>
        </div>
      </div>
      <p class="persona-quote">"${escapeHtml(result.first_reaction || "")}"</p>
      ${
        hook.feature
          ? `<p class="persona-line"><strong>Hook:</strong> ${escapeHtml(hook.feature)} — ${escapeHtml(hook.why_it_lands || "")}</p>`
          : `<p class="persona-line persona-muted"><strong>Hook:</strong> nothing in the spec catches this archetype.</p>`
      }
      <p class="persona-line">
        <strong>Objection:</strong> ${escapeHtml(objection.issue || "")}
        ${objection.tied_to_param ? `<span class="chip">${escapeHtml(objection.tied_to_param)}</span>` : ""}
      </p>
      ${objection.why ? `<p class="persona-line persona-muted">${escapeHtml(objection.why)}</p>` : ""}
      <p class="persona-line"><strong>What would flip me:</strong> ${escapeHtml(result.what_would_get_me || "")}</p>
      ${
        sub.name
          ? `<p class="persona-line"><strong>Likely substitute:</strong> ${escapeHtml(sub.name)}${sub.why_it_wins ? ` — ${escapeHtml(sub.why_it_wins)}` : ""}</p>`
          : ""
      }
    </div>`;
  if (card) card.classList.add("agent-card--persona-active");
}

function loadSettings() {
  setText("settingsEmail", state.me.email || "—");
  setText("settingsProductsCount", String(state.collections.specs.length));
  setText("settingsRunsCount", String(state.collections.runs.length));
  setText("settingsChallengerStatus", state.me.challengerReady ? "Ready" : "Disabled");
  setText("settingsKeyStatus", state.me.challengerReady ? "Configured" : "Not set");
  setText(
    "settingsProfile",
    `${clampNumber($("personas").value, 100, 5, 2000)} personas / ${clampNumber($("days").value, 30, 1, 120)} days`
  );
}

function updateGlobalCounts() {
  setText("heroSavedProducts", String(state.collections.specs.length));
  setText("heroRuns", String(state.collections.runs.length));
  setText("heroChallenger", state.me.challengerReady ? "Ready" : "Offline");
  loadSettings();
}

function setApiStatus() {
  const el = $("apiStatus");
  if (state.me.challengerReady) {
    el.className = "status-pill ready";
    el.textContent = "Challenger online";
  } else {
    el.className = "status-pill";
    el.textContent = "Challenger offline";
  }
}

async function checkAuth() {
  try {
    const res = await apiFetch("/auth/me");
    const data = await readJson(res);
    const displayName = data.email || "Guest";
    state.me.email = displayName;
    state.me.challengerReady = Boolean(data.challenger_ready);
    setText("userEmail", displayName);
    setText("avatarInitial", displayName.slice(0, 1).toUpperCase());
    setApiStatus();
    updateGlobalCounts();
    return true;
  } catch (error) {
    window.location.href = "/login";
    return false;
  }
}

function openUserMenu() {
  $("userDropdown").hidden = false;
  $("userAvatar").setAttribute("aria-expanded", "true");
}

function closeUserMenu() {
  $("userDropdown").hidden = true;
  $("userAvatar").setAttribute("aria-expanded", "false");
}

function toggleUserMenu(event) {
  event.stopPropagation();
  if ($("userDropdown").hidden) openUserMenu();
  else closeUserMenu();
}

async function logout() {
  try {
    const client = await initSupabase();
    await client.auth.signOut();
  } catch (_) {
    // Intentionally ignore logout transport errors and send the user back to login.
  }
  window.location.href = "/login";
}

function getRoute() {
  const hash = window.location.hash.replace(/^#\/?/, "");
  return ROUTES.includes(hash) ? hash : "dashboard";
}

function setActiveRoute() {
  const route = getRoute();
  $$(".view").forEach((view) => {
    view.hidden = view.dataset.view !== route;
  });
  $$(".nav-tabs a").forEach((link) => {
    link.classList.toggle("active", link.dataset.route === route);
  });
  if (route === "dashboard") setDashboardVisibility();
  if (route === "products") refreshSpecs({ silent: true }).then(() => renderProducts());
  if (route === "runs") refreshRuns({ silent: true }).then(() => renderRuns());
  if (route === "agents") loadAgents();
  if (route === "settings") loadSettings();
}

function syncDraftPreview() {
  renderDraftPreview();
}

function bindFilterChips() {
  $$("#runFilters .filter-chip").forEach((button) => {
    button.addEventListener("click", () => {
      state.runFilter = button.dataset.kind || "all";
      $$("#runFilters .filter-chip").forEach((chip) => {
        chip.classList.toggle("active", chip === button);
      });
      state.selectedRunId = null;
      renderRuns();
    });
  });
}

function bindDialogControls() {
  if (!$("saveDialogForm") || !$("confirmDialog")) return;

  $("saveDialogForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = $("saveSpecName").value.trim();
    if (!name) {
      $("saveDialogError").hidden = false;
      $("saveDialogError").textContent = "Please give this saved product a name.";
      return;
    }
    await saveProduct(name);
  });

  $("saveDialogClose").addEventListener("click", () => closeDialog($("saveDialog")));
  $("saveDialogCancel").addEventListener("click", () => closeDialog($("saveDialog")));

  $("confirmClose").addEventListener("click", () => resolveConfirmation(false));
  $("confirmCancel").addEventListener("click", () => resolveConfirmation(false));
  $("confirmApprove").addEventListener("click", () => resolveConfirmation(true));

  $("confirmDialog").addEventListener("cancel", (event) => {
    event.preventDefault();
    resolveConfirmation(false);
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  $("expressIdea").addEventListener("click", expressIdea);
  $("run").addEventListener("click", runSimulation);
  $("challenge").addEventListener("click", challengePitch);
  $("loadFixture").addEventListener("click", () => loadFixture());
  $("saveSpec").addEventListener("click", openSaveDialog);
  $("logout").addEventListener("click", logout);
  $("settingsLogout").addEventListener("click", logout);
  $("userAvatar").addEventListener("click", toggleUserMenu);
  $("useElevatorPitch").addEventListener("click", () => applySuggestedPitch("elevator_pitch"));
  $("useDeckOpening").addEventListener("click", () => applySuggestedPitch("pitch_deck_opening"));

  bindFilterChips();
  bindDialogControls();

  ["name", "category", "price", "segment", "features", "substitutes", "pitch", "personas", "days", "seed"].forEach((id) => {
    $(id).addEventListener("input", syncDraftPreview);
  });

  restoreAgentsDraft();
  AGENTS_INPUT_IDS.forEach((id) => {
    const el = $(id);
    if (el) el.addEventListener("input", persistAgentsDraft);
  });

  const agentsPersonasEl = $("agentsPersonas");
  if (agentsPersonasEl) {
    agentsPersonasEl.addEventListener("click", (event) => {
      const btn = event.target.closest("[data-run-archetype]");
      if (!btn || btn.disabled) return;
      runPersona(btn.dataset.runArchetype);
    });
  }

  document.addEventListener("click", (event) => {
    if (!$("userMenu").contains(event.target)) closeUserMenu();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeUserMenu();
  });

  window.addEventListener("hashchange", () => {
    closeUserMenu();
    setActiveRoute();
  });

  if (!(await checkAuth())) return;

  await Promise.all([refreshSpecs({ silent: true }), refreshRuns({ silent: true })]);
  if (!$("name").value.trim()) await loadFixture({ silent: true });
  syncDraftPreview();

  if (!window.location.hash) window.location.hash = "#/dashboard";
  setActiveRoute();
});
