/* ============================================================
   KNE-Guards — Frontend
   ============================================================ */

const $ = (id) => document.getElementById(id);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

const ROUTES = ["dashboard", "products", "runs", "agents", "settings"];
const ME = { email: null, challenger_ready: false };
let DASHBOARD_HAS_RESULT = false;

/* -------- helpers -------- */

function escapeHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function pct(x) { return (x * 100).toFixed(1) + "%"; }

function setList(el, items, render) {
  el.innerHTML = "";
  items.forEach((item) => {
    const li = document.createElement("li");
    li.innerHTML = render(item);
    el.appendChild(li);
  });
}

/* -------- toast notifications -------- */

const TOAST_ICONS = { success: "✓", error: "!", info: "i" };
const TOAST_TITLES = { success: "Saved", error: "Something went wrong", info: "Heads up" };

function toast(message, { type = "success", title, duration = 3500 } = {}) {
  const container = $("toastContainer");
  if (!container) return;
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  const titleText = title ?? TOAST_TITLES[type] ?? "";
  el.innerHTML = `
    <span class="toast-icon">${TOAST_ICONS[type] || "i"}</span>
    <div class="toast-body">
      <div class="toast-title"></div>
      <div class="toast-msg"></div>
    </div>
    <button class="toast-close" aria-label="Dismiss">×</button>`;
  el.querySelector(".toast-title").textContent = titleText;
  el.querySelector(".toast-msg").textContent = message;

  let timer = null;
  const dismiss = () => {
    if (timer) clearTimeout(timer);
    el.classList.add("leaving");
    setTimeout(() => el.remove(), 200);
  };
  el.querySelector(".toast-close").addEventListener("click", dismiss);
  el.addEventListener("mouseenter", () => { if (timer) { clearTimeout(timer); timer = null; } });
  el.addEventListener("mouseleave", () => { if (duration > 0) timer = setTimeout(dismiss, 1500); });

  container.appendChild(el);
  if (duration > 0) timer = setTimeout(dismiss, duration);
}

async function apiFetch(url, options) {
  const res = await fetch(url, options);
  if (res.status === 401) {
    window.location.href = "/login";
    throw new Error("unauthenticated");
  }
  return res;
}

/* -------- spec form -------- */

function collectSpec() {
  return {
    name: $("name").value.trim(),
    category: $("category").value.trim(),
    price_monthly: parseFloat($("price").value),
    target_segment: $("segment").value.trim(),
    features: $("features").value.split("\n").map(s => s.trim()).filter(Boolean),
    substitutes: $("substitutes").value.split(",").map(s => s.trim()).filter(Boolean),
  };
}

function applySpec(spec) {
  $("name").value = spec.name || "";
  $("category").value = spec.category || "";
  $("price").value = spec.price_monthly ?? "";
  $("segment").value = spec.target_segment || "";
  $("features").value = (spec.features || []).join("\n");
  $("substitutes").value = (spec.substitutes || []).join(", ");
}

function clearForm() {
  applySpec({});
  $("pitch").value = "";
  $("personas").value = 100;
  $("days").value = 30;
  $("seed").value = 42;
  $("results").hidden = true;
  $("challengePanel").hidden = true;
  DASHBOARD_HAS_RESULT = false;
  $("dashboardEmpty").hidden = false;
  $("name").focus();
}

/* -------- retention chart -------- */

function drawRetention(curve) {
  const svg = $("chart");
  svg.innerHTML = "";
  const W = 600, H = 220, PAD = 28;
  const n = curve.length;
  if (n < 2) return;

  const x = (i) => PAD + (i / (n - 1)) * (W - 2 * PAD);
  const y = (v) => H - PAD - v * (H - 2 * PAD);
  const ns = "http://www.w3.org/2000/svg";

  for (let v = 0; v <= 1; v += 0.25) {
    const line = document.createElementNS(ns, "line");
    line.setAttribute("x1", PAD); line.setAttribute("x2", W - PAD);
    line.setAttribute("y1", y(v)); line.setAttribute("y2", y(v));
    line.setAttribute("stroke", "#E9E5F2");
    line.setAttribute("stroke-dasharray", "3 4");
    svg.appendChild(line);

    const label = document.createElementNS(ns, "text");
    label.setAttribute("x", 4); label.setAttribute("y", y(v) + 4);
    label.setAttribute("fill", "#9B95B0"); label.setAttribute("font-size", "10");
    label.textContent = (v * 100) + "%";
    svg.appendChild(label);
  }

  const area = document.createElementNS(ns, "path");
  let d = `M ${x(0)} ${y(0)} `;
  curve.forEach((v, i) => { d += `L ${x(i)} ${y(v)} `; });
  d += `L ${x(n - 1)} ${y(0)} Z`;
  area.setAttribute("d", d);
  area.setAttribute("fill", "#7C3AED");
  area.setAttribute("fill-opacity", "0.12");
  svg.appendChild(area);

  const path = document.createElementNS(ns, "path");
  let pd = `M ${x(0)} ${y(curve[0])}`;
  curve.forEach((v, i) => { if (i) pd += ` L ${x(i)} ${y(v)}`; });
  path.setAttribute("d", pd);
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", "#7C3AED");
  path.setAttribute("stroke-width", "2.5");
  path.setAttribute("stroke-linecap", "round");
  path.setAttribute("stroke-linejoin", "round");
  svg.appendChild(path);

  const xAxis = document.createElementNS(ns, "text");
  xAxis.setAttribute("x", W / 2); xAxis.setAttribute("y", H - 6);
  xAxis.setAttribute("fill", "#9B95B0"); xAxis.setAttribute("font-size", "10");
  xAxis.setAttribute("text-anchor", "middle");
  xAxis.textContent = `Day 0 → Day ${n - 1}`;
  svg.appendChild(xAxis);
}

/* -------- result rendering -------- */

function showDashboardResult() {
  DASHBOARD_HAS_RESULT = true;
  $("dashboardEmpty").hidden = true;
}

function render(report) {
  showDashboardResult();
  $("results").hidden = false;
  $("resultTitle").textContent = `Results — ${report.product_name}`;
  $("kAdoption").textContent = pct(report.adoption_rate);
  $("kAbandoned").textContent = pct(report.abandoned_rate);
  $("kSwitched").textContent = pct(report.switched_rate);
  $("kViability").textContent = report.viability_score.toFixed(2);

  drawRetention(report.retention_curve);

  const tbody = document.querySelector("#archetypes tbody");
  tbody.innerHTML = "";
  Object.entries(report.persona_breakdown).sort().forEach(([arch, c]) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td style="text-transform:capitalize">${arch}</td><td>${c.retained}</td><td>${c.abandoned}</td><td>${c.switched}</td><td>${c.total}</td>`;
    tbody.appendChild(tr);
  });

  const ul = $("switchedTo");
  ul.innerHTML = "";
  const entries = Object.entries(report.switched_to || {}).sort((a, b) => b[1] - a[1]);
  if (entries.length === 0) {
    ul.innerHTML = "<li style='color:var(--muted)'>No personas switched.</li>";
  } else {
    entries.forEach(([sub, n]) => {
      const li = document.createElement("li");
      li.textContent = `${sub}: ${n}`;
      ul.appendChild(li);
    });
  }
}

function renderChallenge(data) {
  showDashboardResult();
  const panel = $("challengePanel");
  const errEl = $("challengeError");
  const body = $("challengeBody");
  panel.hidden = false;

  if (data.error) {
    errEl.hidden = false;
    errEl.textContent = data.error;
    body.hidden = true;
    return;
  }
  errEl.hidden = true;
  body.hidden = false;

  $("cVerdict").textContent = data.verdict || "";

  setList($("cKillShots"), data.kill_shots || [], (k) =>
    `<strong>${escapeHtml(k.risk)}</strong> — ${escapeHtml(k.why_it_kills)}`);
  setList($("cAssumptions"), data.assumption_challenges || [], (a) =>
    `<span class="chip sev-${escapeHtml(a.severity)}">${escapeHtml(a.severity)}</span> ` +
    `<strong>${escapeHtml(a.claim)}</strong><div class="pushback">${escapeHtml(a.pushback)}</div>`);
  setList($("cFeatures"), data.feature_critiques || [], (f) =>
    `<strong>${escapeHtml(f.feature)}</strong> — ${escapeHtml(f.critique)}`);
  setList($("cSubstitutes"), data.substitute_risks || [], (s) =>
    `<strong>${escapeHtml(s.substitute)}</strong> — ${escapeHtml(s.why_it_wins)}`);

  const seg = data.segment_coherence || {};
  $("cSegmentAssessment").textContent = seg.assessment || "";
  setList($("cSegmentConcerns"), seg.concerns || [], (c) => escapeHtml(c));

  const pr = data.pricing_risks || {};
  $("cPricingAssessment").textContent = pr.assessment || "";
  setList($("cPricingConcerns"), pr.concerns || [], (c) => escapeHtml(c));

  $("cSteelman").textContent = data.steelman || "";
}

/* -------- API actions -------- */

async function run() {
  const btn = $("run");
  btn.disabled = true;
  const label = btn.textContent;
  btn.textContent = "Running…";
  try {
    const res = await apiFetch("/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        spec: collectSpec(),
        personas: parseInt($("personas").value, 10),
        days: parseInt($("days").value, 10),
        seed: parseInt($("seed").value, 10),
      }),
    });
    const data = await res.json();
    if (!res.ok) { alert("Error: " + (data.error || res.statusText)); return; }
    render(data);
  } catch (e) {
    if (e.message !== "unauthenticated") alert("Request failed: " + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = label;
  }
}

async function challenge() {
  const btn = $("challenge");
  btn.disabled = true;
  const label = btn.textContent;
  btn.textContent = "Challenging…";
  try {
    const res = await apiFetch("/challenge", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        spec: collectSpec(),
        pitch_text: $("pitch").value.trim() || null,
      }),
    });
    const data = await res.json();
    if (!res.ok) { alert("Error: " + (data.error || res.statusText)); return; }
    renderChallenge(data);
  } catch (e) {
    if (e.message !== "unauthenticated") alert("Request failed: " + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = label;
  }
}

async function loadFixture() {
  const res = await fetch("/fixture");
  applySpec(await res.json());
}

async function saveSpec() {
  const spec = collectSpec();
  if (!spec.name) {
    toast("Give your product a name first.", { type: "error", title: "Missing name" });
    return;
  }
  const name = prompt("Save this product as:", spec.name);
  if (!name) return;
  try {
    const res = await apiFetch("/specs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, spec }),
    });
    const data = await res.json();
    if (!res.ok) {
      toast(data.error || res.statusText, { type: "error" });
      return;
    }
    clearForm();
    toast(`"${name}" is now in your products.`, {
      type: "success",
      title: "Product saved",
    });
  } catch (e) {
    if (e.message !== "unauthenticated") toast(e.message, { type: "error" });
  }
}

/* -------- views: products / runs / agents / settings -------- */

async function loadProducts() {
  const list = $("productsList");
  list.innerHTML = `<div class="empty">Loading…</div>`;
  try {
    const res = await apiFetch("/specs");
    const data = await res.json();
    if (!data.specs || data.specs.length === 0) {
      list.innerHTML = `<div class="empty"><strong>No saved products yet.</strong>Save a spec from the Dashboard to keep it here.</div>`;
      return;
    }
    list.className = "card-grid";
    list.innerHTML = "";
    data.specs.forEach((s) => {
      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML = `
        <div>
          <p class="card-title">${escapeHtml(s.name)}</p>
          <p class="card-sub">${escapeHtml(s.spec.category || "—")} · $${(s.spec.price_monthly ?? 0).toFixed(2)}/mo</p>
        </div>
        <div class="card-body">
          <div style="margin-bottom:0.4rem;"><strong>Segment:</strong> ${escapeHtml(s.spec.target_segment || "—")}</div>
          <div><strong>Features:</strong> ${(s.spec.features || []).length}</div>
        </div>
        <div class="card-footer">
          <button data-act="load">Load into dashboard</button>
          <button class="link" data-act="del" title="Delete">×</button>
        </div>`;
      card.querySelector('[data-act="load"]').addEventListener("click", () => {
        applySpec(s.spec);
        window.location.hash = "#/dashboard";
      });
      card.querySelector('[data-act="del"]').addEventListener("click", async () => {
        if (!confirm(`Delete "${s.name}"?`)) return;
        await apiFetch(`/specs/${s.id}`, { method: "DELETE" });
        loadProducts();
      });
      list.appendChild(card);
    });
  } catch (e) {
    if (e.message !== "unauthenticated") list.innerHTML = `<div class="empty">Error: ${escapeHtml(e.message)}</div>`;
  }
}

async function loadRuns() {
  const wrap = $("runsList");
  wrap.innerHTML = `<div class="empty">Loading…</div>`;
  try {
    const res = await apiFetch("/runs?limit=100");
    const data = await res.json();
    if (!data.runs || data.runs.length === 0) {
      wrap.innerHTML = `<div class="empty"><strong>No runs yet.</strong>Run a simulation or challenge a pitch from the Dashboard.</div>`;
      return;
    }
    wrap.innerHTML = `
      <section class="panel" style="padding:0;overflow:hidden;">
        <table>
          <thead><tr><th>Date</th><th>Type</th><th>Product</th><th></th></tr></thead>
          <tbody></tbody>
        </table>
      </section>`;
    const tbody = wrap.querySelector("tbody");
    data.runs.forEach((r) => {
      const tr = document.createElement("tr");
      tr.style.cursor = "pointer";
      const date = new Date(r.created_at + "Z").toLocaleString();
      const kindLabel = r.kind === "challenge" ? "Challenge" : "Simulation";
      tr.innerHTML = `
        <td>${escapeHtml(date)}</td>
        <td><span class="chip tag-${escapeHtml(r.kind)}">${kindLabel}</span></td>
        <td>${escapeHtml(r.product_name || "—")}</td>
        <td style="text-align:right;"><button class="link" data-act="del" title="Delete">×</button></td>`;
      tr.addEventListener("click", (e) => {
        if (e.target.dataset.act === "del") return;
        restoreRun(r.id);
      });
      tr.querySelector('[data-act="del"]').addEventListener("click", async (e) => {
        e.stopPropagation();
        if (!confirm("Delete this run?")) return;
        await apiFetch(`/runs/${r.id}`, { method: "DELETE" });
        loadRuns();
      });
      tbody.appendChild(tr);
    });
  } catch (e) {
    if (e.message !== "unauthenticated") wrap.innerHTML = `<div class="empty">Error: ${escapeHtml(e.message)}</div>`;
  }
}

async function restoreRun(id) {
  try {
    const res = await apiFetch(`/runs/${id}`);
    const data = await res.json();
    if (!res.ok) { alert("Error: " + (data.error || res.statusText)); return; }
    if (data.kind === "simulation") render(data.result);
    else if (data.kind === "challenge") renderChallenge(data.result);
    window.location.hash = "#/dashboard";
  } catch (e) { if (e.message !== "unauthenticated") alert(e.message); }
}

function paramBar(label, range) {
  const lo = (range[0] * 100).toFixed(0);
  const hi = (range[1] * 100).toFixed(0);
  const left = lo + "%";
  const width = (hi - lo) + "%";
  return `<div class="param-bar">
    <span style="text-transform:capitalize">${escapeHtml(label.replace(/_/g, " "))}</span>
    <div class="bar-track" title="${lo}–${hi}%">
      <div class="bar-fill" style="left:${left};width:${width};"></div>
    </div>
  </div>`;
}

async function loadAgents() {
  const personasEl = $("agentsPersonas");
  const criticEl = $("agentsCritic");
  personasEl.innerHTML = `<div class="empty">Loading…</div>`;
  criticEl.innerHTML = "";
  try {
    const res = await apiFetch("/agents");
    const data = await res.json();
    personasEl.innerHTML = "";
    data.personas.forEach((p) => {
      const card = document.createElement("div");
      card.className = "card agent-card";
      const initial = p.name[0].toUpperCase();
      const bars = Object.entries(p.params).map(([k, v]) => paramBar(k, v)).join("");
      card.innerHTML = `
        <div class="agent-name"><span class="agent-icon">${initial}</span><span>${escapeHtml(p.name)}</span></div>
        <p class="agent-blurb">${escapeHtml(p.blurb)}</p>
        <div class="param-bars">${bars}</div>`;
      personasEl.appendChild(card);
    });

    const c = data.critic;
    const critic = document.createElement("div");
    critic.className = "card agent-card critic";
    const status = c.ready
      ? `<span class="chip sev-low">Ready</span>`
      : `<span class="chip sev-med">Needs API key</span>`;
    critic.innerHTML = `
      <div class="agent-name"><span class="agent-icon">!</span><span>${escapeHtml(c.name)}</span></div>
      <p class="agent-blurb">${escapeHtml(c.blurb)}</p>
      <div style="margin-top:0.5rem;font-size:0.8rem;color:var(--muted);">
        <span class="chip">${escapeHtml(c.model)}</span> ${status}
      </div>`;
    criticEl.appendChild(critic);
  } catch (e) {
    if (e.message !== "unauthenticated") personasEl.innerHTML = `<div class="empty">Error: ${escapeHtml(e.message)}</div>`;
  }
}

function loadSettings() {
  $("settingsEmail").textContent = ME.email || "—";
  $("settingsChallengerStatus").textContent = ME.challenger_ready ? "Ready" : "Disabled";
  $("settingsKeyStatus").textContent = ME.challenger_ready ? "Set in environment" : "Not set";
}

/* -------- auth + nav -------- */

function setApiStatus() {
  const el = $("apiStatus");
  if (ME.challenger_ready) {
    el.className = "api-status ready";
    el.textContent = "Challenger: ready";
  } else {
    el.className = "api-status off";
    el.textContent = "Challenger: off";
  }
}

async function checkAuth() {
  try {
    const res = await fetch("/auth/me");
    if (res.status === 401) { window.location.href = "/login"; return false; }
    const data = await res.json();
    ME.email = data.email;
    ME.challenger_ready = !!data.challenger_ready;
    $("userEmail").textContent = data.email;
    $("avatarInitial").textContent = (data.email || "?")[0];
    setApiStatus();
    return true;
  } catch (e) {
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
function toggleUserMenu(e) {
  e.stopPropagation();
  if ($("userDropdown").hidden) openUserMenu();
  else closeUserMenu();
}

async function logout() {
  try { await fetch("/auth/logout", { method: "POST" }); } catch (e) { /* ignore */ }
  window.location.href = "/login";
}

function getRoute() {
  const hash = window.location.hash.replace(/^#\/?/, "");
  return ROUTES.includes(hash) ? hash : "dashboard";
}

function setActiveRoute() {
  const route = getRoute();
  $$(".view").forEach((v) => { v.hidden = v.dataset.view !== route; });
  $$(".nav-tabs a").forEach((a) => {
    a.classList.toggle("active", a.dataset.route === route);
  });
  if (route === "dashboard" && !DASHBOARD_HAS_RESULT) $("dashboardEmpty").hidden = false;
  if (route === "products") loadProducts();
  if (route === "runs") loadRuns();
  if (route === "agents") loadAgents();
  if (route === "settings") loadSettings();
}

/* -------- bootstrap -------- */

document.addEventListener("DOMContentLoaded", async () => {
  $("run").addEventListener("click", run);
  $("challenge").addEventListener("click", challenge);
  $("loadFixture").addEventListener("click", loadFixture);
  $("saveSpec").addEventListener("click", saveSpec);
  $("logout").addEventListener("click", logout);
  $("settingsLogout").addEventListener("click", logout);
  $("userAvatar").addEventListener("click", toggleUserMenu);
  document.addEventListener("click", (e) => {
    if (!$("userMenu").contains(e.target)) closeUserMenu();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeUserMenu();
  });

  window.addEventListener("hashchange", () => { closeUserMenu(); setActiveRoute(); });

  if (!(await checkAuth())) return;
  if (!window.location.hash) window.location.hash = "#/dashboard";
  loadFixture();
  setActiveRoute();
});
