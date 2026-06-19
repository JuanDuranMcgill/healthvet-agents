/*
 * Questionnaire UI logic  fetches the form definition from the backend,
 * renders ranking / sliders / deal-breakers / risk-appetite, validates, and
 * submits to /api/submit_questionnaire which builds + saves a HospitalProfile.
 */
let FORM = null;

function slugify(s) {
  return (s || "hospital").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "hospital";
}

async function load() {
  FORM = await fetch("/api/questionnaire").then((r) => r.json());
  renderRanks();
  renderSliders();
  renderDealBreakers();
  renderAppetite();
}

function renderRanks() {
  const host = document.getElementById("ranks");
  const n = FORM.categories.length;
  host.innerHTML = FORM.categories
    .map((c, i) => {
      const opts = Array.from({ length: n }, (_, k) =>
        `<option value="${k + 1}" ${k === i ? "selected" : ""}>${k + 1}</option>`
      ).join("");
      return `<div class="rank-row">
        <span class="label">${c.label}</span>
        <select data-cat="${c.id}">${opts}</select>
      </div>`;
    })
    .join("");
  host.querySelectorAll("select").forEach((s) => s.addEventListener("change", validateRanks));
  validateRanks();
}

function validateRanks() {
  const vals = [...document.querySelectorAll("#ranks select")].map((s) => s.value);
  const dup = vals.length !== new Set(vals).size;
  document.getElementById("rank-warn").textContent = dup
    ? "Each rank must be unique  you have duplicate ranks."
    : "";
  return !dup;
}

function renderSliders() {
  document.getElementById("sliders").innerHTML = FORM.sliders
    .map(
      (s) => `<div class="slider-row">
      <span class="label">${s.label}</span>
      <input type="range" min="1" max="5" value="3" data-cat="${s.category}"
             oninput="this.nextElementSibling.textContent=this.value">
      <span class="slider-val">3</span>
    </div>`
    )
    .join("");
}

function renderDealBreakers() {
  document.getElementById("dealbreakers").innerHTML = FORM.deal_breakers
    .map(
      (d) => `<label class="choice">
      <input type="checkbox" value="${d.factor}">
      <span>${d.question || d.factor}</span>
    </label>`
    )
    .join("");
}

function renderAppetite() {
  const opts = FORM.risk_appetite.options;
  document.getElementById("appetite").innerHTML = opts
    .map(
      (o, i) => `<label class="choice">
      <input type="radio" name="appetite" value="${o.id}" ${i === 1 ? "checked" : ""}>
      <span>${o.label}</span>
    </label>`
    )
    .join("");
}

function collect() {
  const ranks = {};
  document.querySelectorAll("#ranks select").forEach((s) => (ranks[s.dataset.cat] = parseInt(s.value)));
  const sliders = {};
  document.querySelectorAll("#sliders input[type=range]").forEach((s) => (sliders[s.dataset.cat] = parseInt(s.value)));
  const deal_breakers = [...document.querySelectorAll("#dealbreakers input:checked")].map((c) => c.value);
  const risk_appetite = document.querySelector('input[name="appetite"]:checked').value;
  const gap_mode = document.querySelector('input[name="gapmode"]:checked').value;
  const hospital = document.getElementById("hospital").value.trim() || "Unnamed Hospital";
  return { slug: slugify(hospital), hospital, ranks, sliders, deal_breakers, risk_appetite, gap_mode };
}

function renderResult(profile) {
  const el = document.getElementById("result");
  el.style.display = "block";
  const cats = Object.entries(profile.categories).sort((a, b) => b[1].weight - a[1].weight);
  const max = cats[0][1].weight || 1;
  const rows = cats
    .map(
      ([k, c]) => `<div class="wrow"><span>${k.replace(/_/g, " ")}</span><span>${(c.weight * 100).toFixed(1)}%</span></div>
      <div class="bar"><span style="width:${(c.weight / max) * 100}%"></span></div>`
    )
    .join("");
  el.innerHTML = `<h2><i class="fa-solid fa-circle-check" style="color:var(--good)"></i> Profile saved: ${profile.hospital} (v${profile.version})</h2>
    <p style="color:var(--muted);font-size:13px">This is now the active scoring model. Run a vendor assessment and results will be ranked against it.</p>
    ${rows}
    <p style="font-size:13px;margin-top:14px">Deal-breakers: ${(profile.deal_breakers || []).map((d) => d.factor).join(", ") || "none"}  
       Thresholds: approve ≥ ${profile.thresholds.approve}, escalate ≥ ${profile.thresholds.escalate}</p>
    <div class="actions"><a class="btn primary" href="index.html">Go to dashboard</a></div>`;
  el.scrollIntoView({ behavior: "smooth" });
}

document.getElementById("submit").addEventListener("click", async () => {
  if (!validateRanks()) {
    document.getElementById("rank-warn").scrollIntoView({ behavior: "smooth" });
    return;
  }
  const btn = document.getElementById("submit");
  btn.disabled = true;
  btn.textContent = "Building…";
  try {
    const res = await fetch("/api/submit_questionnaire", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(collect()),
    }).then((r) => r.json());
    if (res.status === "success") renderResult(res.profile);
    else alert("Error: " + (res.message || "could not build profile"));
  } catch (e) {
    alert("Request failed: " + e);
  } finally {
    btn.disabled = false;
    btn.textContent = "Build scoring profile";
  }
});

load();
