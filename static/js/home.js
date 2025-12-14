/* =====================================================================
   SmartTrader – Unified Dashboard JS
   Fully Synced with HTML + API Endpoints
   ===================================================================== */

/* --------------------------- Helpers -------------------------------- */

async function api(path) {
  try {
    const res = await fetch(path);
    if (!res.ok) throw new Error("HTTP " + res.status);
    return await res.json();
  } catch (err) {
    console.error("API error:", path, err);
    return null;
  }
}

const fmtNum = (n) =>
  n === null || n === undefined ? "–" : Number(n).toLocaleString("fa-IR");

const fmtPct = (n) =>
  n === null || n === undefined ? "–" : Number(n).toFixed(1) + "٪";

function faDecision(dec) {
  if (!dec) return "نامشخص";
  const d = dec.toUpperCase();
  if (d === "BUY") return "سیگنال خرید";
  if (d === "SELL") return "سیگنال فروش";
  if (d === "HOLD") return "حالت HOLD / بدون ورود";
  return "نامشخص";
}

function formatFaDate(ts) {
  const d = new Date(ts);
  if (isNaN(d.getTime())) return ts;
  return d.toLocaleString("fa-IR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/* --------------------------- Sparkline (Hero) ------------------------ */

function renderSparkline(history) {
  const canvas = document.getElementById("hero-sparkline");
  if (!canvas || !history || history.length < 2) return;

  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;

  ctx.clearRect(0, 0, w, h);

  const prices = history.map((h) => Number(h.price));
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const range = max - min || 1;
  const stepX = w / (prices.length - 1);

  ctx.beginPath();
  ctx.lineWidth = 2;
  ctx.strokeStyle = "#5dd0ff";

  prices.forEach((p, i) => {
    const x = i * stepX;
    const y = h - ((p - min) / range) * h;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });

  ctx.stroke();
}

/* --------------------------- Heatmap -------------------------------- */

function renderHeatmap(decisions) {
  const box = document.getElementById("heatmap-decisions");
  if (!box) return;

  box.innerHTML = "";

  (decisions || [])
    .slice(-64)
    .forEach((d) => {
      const cell = document.createElement("div");
      cell.className = "heat-cell";

      const dec = (d.decision || "").toUpperCase();
      let color = "rgba(255,210,0,0.55)"; // HOLD
      if (dec === "BUY") color = "rgba(0,255,120,0.55)";
      if (dec === "SELL") color = "rgba(255,60,60,0.55)";

      cell.style.background = color;
      box.appendChild(cell);
    });
}

/* ----------------------- Probability Engine -------------------------- */

function computeProb(lastDecision, winrate) {
  const wr = Number(winrate || 0);
  let buy = 33,
    sell = 33,
    hold = 34;

  const d = (lastDecision || "").toUpperCase();
  if (d === "BUY") buy += 15;
  if (d === "SELL") sell += 15;
  if (d === "HOLD") hold += 20;

  buy += (wr - 50) * 0.4;
  sell += (50 - wr) * 0.4;

  const total = buy + sell + hold || 1;

  return {
    buy: Math.max(0, (buy / total) * 100),
    sell: Math.max(0, (sell / total) * 100),
    hold: Math.max(0, (hold / total) * 100),
  };
}

function renderProb(prob) {
  const setWidth = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.style.width = val + "%";
  };
  const setLabel = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val.toFixed(1) + "%";
  };

  setWidth("prob-buy", prob.buy);
  setWidth("prob-sell", prob.sell);
  setWidth("prob-hold", prob.hold);

  setLabel("prob-buy-label", prob.buy);
  setLabel("prob-sell-label", prob.sell);
  setLabel("prob-hold-label", prob.hold);
}

/* --------------------------- Volatility Band ------------------------ */

function renderVol(last) {
  const ptr = document.getElementById("vol-pointer");
  const lbl = document.getElementById("volatility-label");
  if (!ptr || !lbl) return;

  const adx = Number(last?.adx || 0);
  let volScore = Math.min(100, Math.max(0, adx * 1.4));

  ptr.style.left = volScore + "%";

  if (volScore < 30) lbl.textContent = "بازار آرام و کم‌نوسان است.";
  else if (volScore < 60)
    lbl.textContent = "بازار در محدوده‌ی نوسان متوسط قرار دارد.";
  else lbl.textContent = "بازار بسیار پرنوسان است؛ احتیاط کنید.";
}

/* --------------------------- Sentiment Radar ------------------------ */

function renderSentiment(daily) {
  const ul = document.getElementById("sentiment-list");
  if (!ul) return;

  ul.innerHTML = "";
  const list = Array.isArray(daily) ? daily : [];

  const pnlList = list.map((d) => Number(d.day_pnl ?? d.pnl ?? 0));
  if (!pnlList.length) {
    const li = document.createElement("li");
    li.textContent = "داده کافی برای تحلیل مود بازار وجود ندارد.";
    ul.appendChild(li);
    return;
  }

  const avg = pnlList.reduce((a, v) => a + v, 0) / pnlList.length;
  const greens = pnlList.filter((x) => x > 0).length;
  const reds = pnlList.filter((x) => x < 0).length;

  const items = [];
  items.push(avg > 0 ? "میانگین سود روزانه مثبت است." : "میانگین ضرر است.");
  items.push(
    greens >= reds
      ? "روزهای مثبت بیشتر بوده است."
      : "فشار منفی اخیر بیشتر بوده است."
  );

  items.forEach((t) => {
    const li = document.createElement("li");
    li.textContent = t;
    ul.appendChild(li);
  });
}

/* --------------------------- Hero & Metrics ------------------------- */

function renderHero(last, perf, btc) {
  const set = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  };

  set("hero-last-decision", last ? faDecision(last.decision) : "–");
  set("hero-regime", last?.regime || "–");
  set("hero-adx", last?.adx != null ? last.adx.toFixed(1) : "–");
  set("hero-winrate", perf?.winrate != null ? perf.winrate + "٪" : "–");
  set("hero-btc-price", fmtNum(btc?.price_tmn ?? btc?.price));

  const floatBox = document.getElementById("floating-btc");
  if (floatBox) floatBox.classList.add("fx-glow");
}

function renderMetrics(perf) {
  const set = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  };

  set("metric-total-trades", fmtNum(perf.total_trades));
  set("metric-total-wins", fmtNum(perf.wins));
  set("metric-total-losses", fmtNum(perf.losses));
  set("metric-total-pnl", fmtNum(perf.total_pnl));
  set("metric-error-rate", fmtPct(100 - (perf.winrate || 0)));
}

/* --------------------------- Decisions List ------------------------- */

let globalDecisions = [];

function renderDecisionList() {
  const container = document.getElementById("decision-list");
  if (!container) return;

  container.innerHTML = "";

  if (!globalDecisions.length) {
    container.innerHTML = `<div class="decision-empty">هنوز تصمیمی ثبت نشده است.</div>`;
    return;
  }

  globalDecisions
    .slice()
    .reverse()
    .forEach((d) => {
      container.innerHTML += `
        <div class="decision-row">
          <div class="decision-row-main">
            <span class="decision-pill decision-${(d.decision || "hold").toLowerCase()}">
              ${faDecision(d.decision)}
            </span>
            <span class="decision-price">قیمت: ${fmtNum(d.price)}</span>
          </div>
          <div class="decision-row-meta">
            <span>${formatFaDate(d.timestamp)}</span>
            <span>رژیم: ${(d.regime || "NEUTRAL").toUpperCase()}</span>
          </div>
        </div>
      `;
    });
}

/* --------------------------- Daily PnL & Trades --------------------- */

function renderDailyPnl(daily) {
  const el = document.getElementById("pnl-daily");
  if (!el) return;

  if (!daily || !daily.length) {
    el.textContent = "هنوز ترید بسته‌شده‌ای وجود ندارد.";
    return;
  }

  el.innerHTML = "";
  daily.forEach((d) => {
    const pnl = Number(d.pnl ?? d.day_pnl ?? 0);
    const sign =
      pnl > 0 ? "pnl-pos" : pnl < 0 ? "pnl-neg" : "pnl-flat";

    el.innerHTML += `
      <div class="pnl-row">
        <span class="pnl-date">${d.day}</span>
        <span class="pnl-val ${sign}">${pnl.toLocaleString("fa-IR")}</span>
        <span class="pnl-trades">${d.n_trades || 0} ترید</span>
      </div>
    `;
  });
}

function renderRecentTrades(list) {
  const el = document.getElementById("recent-trades");
  if (!el) return;

  if (!list || !list.length) {
    el.textContent = "ترید بسته‌شده‌ای وجود ندارد.";
    return;
  }

  el.innerHTML = "";
  list.forEach((t) => {
    const pnl = Number(t.pnl || 0);
    const sign = pnl > 0 ? "pnl-pos" : pnl < 0 ? "pnl-neg" : "pnl-flat";

    el.innerHTML += `
      <div class="trade-row">
        <div class="trade-header">
          <span>${(t.side || "").toUpperCase()}</span>
          <span>${formatFaDate(t.timestamp)}</span>
        </div>
        <div class="trade-body">
          <span>ورود: ${fmtNum(t.entry_price)}</span>
          <span>خروج: ${fmtNum(t.close_price)}</span>
          <span>حجم: ${fmtNum(t.qty)}</span>
          <span class="trade-pnl ${sign}">PnL: ${fmtNum(pnl)}</span>
        </div>
      </div>
    `;
  });
}

/* --------------------------- Main Price Chart ----------------------- */

let priceChartInstance = null;

function buildPriceDecisionChart(prices, decisions) {
  const canvas = document.getElementById("priceChart");
  if (!canvas) return;

  if (!prices || !prices.length) return;

  const labels = prices.map((p) => p.timestamp);
  const data = prices.map((p) => p.price);

  const indexByTs = {};
  labels.forEach((t, i) => (indexByTs[t] = i));

  const buyPoints = [];
  const sellPoints = [];

  decisions.forEach((d) => {
    const i = indexByTs[d.timestamp];
    if (i == null) return;
    const point = { x: labels[i], y: data[i] };
    if (d.decision === "BUY") buyPoints.push(point);
    if (d.decision === "SELL") sellPoints.push(point);
  });

  const ctx = canvas.getContext("2d");

  if (priceChartInstance) priceChartInstance.destroy();

  priceChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "قیمت",
          data,
          borderColor: "#60a5fa",
          backgroundColor: "rgba(37,99,235,0.18)",
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.35,
          fill: true,
        },
        {
          type: "scatter",
          label: "BUY",
          data: buyPoints,
          pointBackgroundColor: "#16a34a",
          pointBorderColor: "#ffffff",
          pointRadius: 6,
          pointStyle: "triangle",
        },
        {
          type: "scatter",
          label: "SELL",
          data: sellPoints,
          pointBackgroundColor: "#dc2626",
          pointBorderColor: "#ffffff",
          pointRadius: 6,
          pointStyle: "triangle",
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: (items) => formatFaDate(items[0].label),
            label: (ctx) =>
              "قیمت: " + Number(ctx.parsed.y).toLocaleString("fa-IR"),
          },
        },
      },
      scales: {
        x: { ticks: { display: false } },
        y: {
          ticks: {
            callback: (v) => Number(v).toLocaleString("fa-IR"),
          },
        },
      },
    },
  });
}

/* --------------------------- AI Context / Advice -------------------- */

function buildAiAdvice(perf, decisions, daily) {
  const total = perf?.total_trades || 0;
  const winrate = perf?.winrate || 0;
  const totalPnl = perf?.total_pnl || 0;
  const last = decisions?.[decisions.length - 1];

  if (!last || total < 3) {
    return {
      title: "داده کافی نیست",
      description: "برای توصیه عملی‌تر، باید چند ترید واقعی انجام شده باشد.",
      bullets: ["فعلاً فقط رفتار ربات را مشاهده کن."],
    };
  }

  let title = "تحلیل امروز";
  let description = "";
  const bullets = [];

  if (last.decision === "BUY") {
    title = "سوگیری خرید";
    description = "سیگنال فعلی BUY است؛ فقط ستاپ‌های خرید را بررسی کن.";
    bullets.push("ورود فقط در جهت BUY.");
  } else if (last.decision === "SELL") {
    title = "سوگیری فروش";
    description = "سیگنال SELL فعال است؛ بازار احتمالاً در اصلاح/نزول است.";
    bullets.push("ستاپ‌های SELL مناسب‌تر هستند.");
  } else {
    title = "عدم قطعیت (HOLD)";
    description = "سیگنال قطعی وجود ندارد؛ مدیریت سرمایه مهم‌تر است.";
    bullets.push("از ورودهای اجباری خودداری کن.");
  }

  if (totalPnl < 0) bullets.push("PNL اخیر منفی است؛ حجم معاملات را کم کن.");
  if (winrate > 55)
    bullets.push("وین‌ریت خوب است؛ ستاپ‌های هم‌جهت با ربات ارزشمندترند.");

  return { title, description, bullets };
}

function renderAiAdviceUi(advice) {
  const t = document.getElementById("ai-advice-title");
  const b = document.getElementById("ai-advice-body");
  const ul = document.getElementById("ai-advice-bullets");

  if (t) t.textContent = advice.title;
  if (b) b.textContent = advice.description;

  if (ul) {
    ul.innerHTML = "";
    advice.bullets.forEach((x) => {
      const li = document.createElement("li");
      li.textContent = x;
      ul.appendChild(li);
    });
  }
}

/* --------------------------- UPDATE LOOP ---------------------------- */

async function updateDashboard() {
  try {
    const [perf, decisions, daily, btc, prices] = await Promise.all([
      api("/api/perf/summary"),
      api("/api/decisions?limit=80"),
      api("/api/perf/daily?limit=30"),
      api("/api/btc_price"),
      api("/api/prices?limit=300"),
    ]);

    const perfSafe = perf || {
      total_trades: 0,
      wins: 0,
      losses: 0,
      winrate: 0,
      total_pnl: 0,
    };

    const decisionsSafe = Array.isArray(decisions) ? decisions : [];
    const dailySafe = Array.isArray(daily) ? daily : [];
    const pricesSafe = Array.isArray(prices) ? prices : [];
    const last = decisionsSafe[decisionsSafe.length - 1] || null;

    globalDecisions = decisionsSafe;

    /* HERO / SUMMARY */
    renderHero(last, perfSafe, btc || {});
    renderMetrics(perfSafe);
    renderHeatmap(decisionsSafe);
    renderVol(last);
    renderSentiment(dailySafe);

    if (btc && Array.isArray(btc.history)) renderSparkline(btc.history);

    /* Probability */
    const prob = computeProb(last?.decision, perfSafe.winrate);
    renderProb(prob);

    /* Price / Decision chart */
    buildPriceDecisionChart(pricesSafe, decisionsSafe);

    /* Lists */
    renderDecisionList();
    renderDailyPnl(dailySafe);

    const recent = await api("/api/trades/recent?limit=30");
    renderRecentTrades(Array.isArray(recent) ? recent : []);

    /* AI Advisor */
    const advice = buildAiAdvice(perfSafe, decisionsSafe, dailySafe);
    renderAiAdviceUi(advice);
  } catch (e) {
    console.error("Dashboard update error:", e);
  }
}

/* --------------------------- QuantumFlux BG ------------------------- */

async function loadFluxData() {
  const res = await api("/api/decisions?limit=80");
  if (!Array.isArray(res)) return [];

  return res.map((d) => ({
    t: d.timestamp,
    energy: d.confirm_s ?? 0,
    type: d.final_decision,
    vol: Math.abs(d.confirm_adx || 0),
  }));
}

let fluxLastFrame = 0;

function drawQuantumFlux(data, ts) {
  const canvas = document.getElementById("quantumFlux");
  if (!canvas) return;

  const ctx = canvas.getContext("2d");
  const now = ts ?? performance.now();

  // FPS limit ~30
  if (now - fluxLastFrame < 1000 / 30) {
    requestAnimationFrame((t) => drawQuantumFlux(data, t));
    return;
  }
  fluxLastFrame = now;

  const W = canvas.width;
  const H = canvas.height;
  const CX = W / 2;
  const CY = H / 2;

  ctx.clearRect(0, 0, W, H);

  const avgEnergy = data.reduce((a, b) => a + b.energy, 0) / data.length;
  const avgVol = data.reduce((a, b) => a + b.vol, 0) / data.length;

  let coreColor =
    avgEnergy > 0.15
      ? "rgba(80,255,160,0.7)"
      : avgEnergy < -0.15
      ? "rgba(255,80,80,0.7)"
      : "rgba(255,230,80,0.7)";

  const rings = [
    { r: 80, speed: 0.02 + avgVol * 0.001, width: 2, color: coreColor },
    {
      r: 140,
      speed: 0.015 + avgVol * 0.001,
      width: 1.5,
      color: "rgba(100,180,255,0.4)",
    },
    {
      r: 220,
      speed: 0.01 + avgVol * 0.001,
      width: 1,
      color: "rgba(80,120,255,0.25)",
    },
  ];

  const t = now * 0.002;

  rings.forEach((r) => {
    ctx.beginPath();
    ctx.lineWidth = r.width;
    ctx.strokeStyle = r.color;

    const radius = r.r + Math.sin(t * r.speed) * 12;
    ctx.arc(CX, CY, radius, 0, Math.PI * 2);
    ctx.stroke();
  });

  // particles
  data.slice(0, 40).forEach((d, i) => {
    const angle = t * 0.1 + i * 0.3;
    const radius = 160 + Math.sin(t * 0.02 + i) * 40;

    ctx.beginPath();

    const pc =
      d.energy > 0.2
        ? "rgba(90,255,180,0.8)"
        : d.energy < -0.2
        ? "rgba(255,90,90,0.8)"
        : "rgba(255,230,100,0.8)";

    ctx.fillStyle = pc;
    ctx.arc(CX + Math.cos(angle) * radius, CY + Math.sin(angle) * radius, 4, 0, Math.PI * 2);
    ctx.fill();
  });

  requestAnimationFrame((t2) => drawQuantumFlux(data, t2));
}

(async function initFlux() {
  const canvas = document.getElementById("quantumFlux");
  if (!canvas) return;

  const data = await loadFluxData();
  if (!data.length) return;

  requestAnimationFrame((t) => drawQuantumFlux(data, t));
})();

/* ============================================================
   SmartTrader – CHAOTIC NEURAL ORB (Final Refactored Version)
   Natural Fog-Mesh • Plasma Core • Magnetic Field • Shockwaves
   ============================================================ */

const orbState = {
  canvas: null,
  ctx: null,
  W: 0,
  H: 0,
  CX: 0,
  CY: 0,
  particles: [],
  bands: [[], [], []],
  cloud: [],
  lastDecision: null,
  t0: performance.now(),
  resizeTimer: null,
};

/* --------------------- Utility: Natural Noise ---------------------- */
function noise(x) {
  return (
    Math.sin(x * 1.37) * 0.6 +
    Math.sin(x * 2.71 + 1.3) * 0.3 +
    Math.sin(x * 0.73 + 4.2) * 0.1
  );
}

/* ------------------------ INIT CANVAS ----------------------- */
function initOrbCanvas() {
  const canvas = document.getElementById("marketOrb");
  if (!canvas) return;

  const ctx = canvas.getContext("2d");
  orbState.canvas = canvas;
  orbState.ctx = ctx;

  function resize() {
    const rect = canvas.getBoundingClientRect();
    const size = Math.min(rect.width, rect.height);
    canvas.width = size;
    canvas.height = size;

    orbState.W = size;
    orbState.H = size;
    orbState.CX = size / 2;
    orbState.CY = size / 2;
  }

  resize();
  window.addEventListener("resize", () => {
    clearTimeout(orbState.resizeTimer);
    orbState.resizeTimer = setTimeout(resize, 150);
  });
}

/* -------------------- BUILD ORB FROM DECISIONS -------------------- */
function rebuildOrbFromDecisions(decisions) {
  if (!orbState.canvas || !decisions?.length) return;

  const N = Math.min(260, decisions.length);
  const size = orbState.W;
  const CORE_GAP = size * 0.11;     // فضای خالی طبیعی نزدیک مرکز
  const R_MIN = size * 0.28;
  const R_MAX = size * 0.62;

  orbState.particles = [];
  orbState.bands = [[], [], []];
  orbState.cloud = [];
  orbState.lastDecision = decisions.at(-1);

  /* --- PARTICLES --- */
  for (let i = 0; i < N; i++) {
    const d = decisions[decisions.length - 1 - i];
    const age = i / N;

    const band = age < 0.28 ? 0 : age < 0.65 ? 1 : 2;

    let baseRadius = R_MIN + Math.random() * (R_MAX - R_MIN);

    if (baseRadius < CORE_GAP) baseRadius = CORE_GAP + Math.random() * (size * 0.08);

    const p = {
      d,
      band,
      baseAngle: Math.random() * Math.PI * 2,
      baseRadius,
      angleDrift: (Math.random() - 0.5) * 0.45,
      radiusJitter: 20 + Math.random() * 35,
      noiseSeed: Math.random() * 500,
      speed: 0.25 + Math.random() * 0.28,
      ageNorm: age,
    };

    orbState.particles.push(p);
    orbState.bands[band].push(p);
  }

  /* --- SORT BANDS for Smooth Mesh --- */
  orbState.bands.forEach(b => b.sort((a, b) => a.baseAngle - b.baseAngle));

  /* --- INNER PLASMA CLOUD --- */
  const cloudCount = 140;
  for (let i = 0; i < cloudCount; i++) {
    orbState.cloud.push({
      angle: Math.random() * Math.PI * 2,
      radius: CORE_GAP * (0.3 + Math.random() * 0.9),
      phase: Math.random() * Math.PI * 2,
      speed: 0.5 + Math.random() * 1.1,
      size: 1.2 + Math.random() * 1.5,
    });
  }
}

/* --------------------------- RENDER ORB ----------------------------- */
function animateOrb(now) {
  const ctx = orbState.ctx;
  if (!ctx || !orbState.W) return;

  const W = orbState.W;
  const CX = orbState.CX;
  const CY = orbState.CY;
  const t = (now - orbState.t0) * 0.001;

  const last = orbState.lastDecision;
  const energy = Math.abs(last?.aggregate_s ?? 0);

  /* ---------------- SAFE ORGANIC PULSE ---------------- */
  const pulseRaw = Math.sin(t * 1.6);
  const pulse = 0.015 + Math.min(0.018, energy * 0.035) * pulseRaw;

  /* ---------------- CLEAR ---------------- */
  ctx.clearRect(0, 0, W, W);

  ctx.save();
  ctx.translate(CX, CY);
  ctx.scale(1 + pulse, 1 - pulse * 0.55);
  ctx.translate(-CX, -CY);

  /* ---------------- BACKGROUND HALO (SOFT, NON-BOX) ---------------- */
  const bg = ctx.createRadialGradient(CX, CY, W * 0.15, CX, CY, W * 0.55);
  bg.addColorStop(0, "rgba(12,16,32,0)");
  bg.addColorStop(1, "rgba(6,10,24,0.85)");
  ctx.fillStyle = bg;
  ctx.beginPath();
  ctx.arc(CX, CY, W * 0.55, 0, Math.PI * 2);
  ctx.fill();

  /* ---------------- CORE ---------------- */
  const coreColor =
    last?.decision === "BUY"
      ? "rgba(0,255,190,0.95)"
      : last?.decision === "SELL"
      ? "rgba(255,90,120,0.95)"
      : "rgba(255,235,170,0.92)";

  const corePulse = 0.004 + energy * 0.009;
  const coreR = W * (0.06 + Math.sin(t * 2.1) * corePulse);

  const halo = ctx.createRadialGradient(CX, CY, coreR * 0.4, CX, CY, coreR * 2.4);
  halo.addColorStop(0, "rgba(255,255,255,0.85)");
  halo.addColorStop(0.35, coreColor);
  halo.addColorStop(1, "rgba(0,0,0,0)");

  ctx.fillStyle = halo;
  ctx.beginPath();
  ctx.arc(CX, CY, coreR * 2.4, 0, Math.PI * 2);
  ctx.fill();

  ctx.beginPath();
  ctx.fillStyle = coreColor;
  ctx.arc(CX, CY, coreR, 0, Math.PI * 2);
  ctx.fill();

  /* ---------------- INNER CLOUD ---------------- */
  orbState.cloud.forEach((c, i) => {
    const rr = c.radius + Math.sin(t * c.speed + c.phase) * 2.6;
    const ang = c.angle + Math.sin(t * 0.35 + i * 0.2) * 0.25;

    const x = CX + Math.cos(ang) * rr;
    const y = CY + Math.sin(ang) * rr;

    const a = 0.06 + 0.05 * Math.sin(t * 1.1 + c.phase);

    ctx.beginPath();
    ctx.fillStyle = `rgba(190,210,255,${a})`;
    ctx.arc(x, y, c.size, 0, Math.PI * 2);
    ctx.fill();
  });

  /* ---------------- SHOCKWAVE (RARE, CLEAN) ---------------- */
  if (energy > 0.3) {
    const p = (t * 1.3) % 1;
    const r = W * (0.18 + p * 0.35);
    ctx.beginPath();
    ctx.strokeStyle = `rgba(150,210,255,${0.45 * (1 - p)})`;
    ctx.lineWidth = 1.4;
    ctx.arc(CX, CY, r, 0, Math.PI * 2);
    ctx.stroke();
  }

  /* ---------------- FOG MESH (SUBTLE) ---------------- */
  ctx.globalCompositeOperation = "lighter";

  orbState.bands.forEach((bandArr, idx) => {
    if (!bandArr.length) return;

    ctx.strokeStyle =
      idx === 0
        ? "rgba(180,200,255,0.14)"
        : idx === 1
        ? "rgba(140,180,255,0.10)"
        : "rgba(100,140,255,0.07)";

    ctx.lineWidth = idx === 0 ? 0.7 : 0.5;
    ctx.beginPath();

    let prev = null;
    bandArr.forEach((p, i) => {
      const r =
        p.baseRadius +
        noise(p.noiseSeed + t * 0.6) * (p.radiusJitter * 0.6);

      const ang =
        p.baseAngle +
        t * p.speed +
        p.angleDrift * Math.sin(t * 0.7 + p.noiseSeed);

      const x = CX + Math.cos(ang) * r;
      const y = CY + Math.sin(ang) * r;

      p._x = x;
      p._y = y;

      if (!prev) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);

      prev = { x, y };
    });

    ctx.stroke();
  });

  ctx.globalCompositeOperation = "source-over";

  /* ---------------- NODES (FOCUS ELEMENT) ---------------- */
  orbState.particles.forEach((p) => {
    const d = p.d;
    const dec = (d?.decision || "").toUpperCase();
    const intensity = Math.min(1, Math.abs(d?.aggregate_s ?? 0.1));

    const col =
      dec === "BUY"
        ? `rgba(0,255,190,${0.45 + intensity * 0.5})`
        : dec === "SELL"
        ? `rgba(255,110,140,${0.45 + intensity * 0.5})`
        : `rgba(255,230,170,${0.35 + intensity * 0.5})`;

    const size = 2 + (1 - p.ageNorm) * 2.2 + intensity * 0.8;

    const g = ctx.createRadialGradient(p._x, p._y, 0, p._x, p._y, size * 3);
    g.addColorStop(0, col);
    g.addColorStop(1, "rgba(0,0,0,0)");

    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(p._x, p._y, size * 3, 0, Math.PI * 2);
    ctx.fill();

    ctx.beginPath();
    ctx.fillStyle = col;
    ctx.arc(p._x, p._y, size, 0, Math.PI * 2);
    ctx.fill();
  });

  ctx.restore();
  requestAnimationFrame(animateOrb);
}

/* ---------------- REFRESH DATA ---------------- */
async function refreshOrbData() {
  const data = await api("/api/decisions?limit=260");
  if (Array.isArray(data) && data.length) {
    rebuildOrbFromDecisions(data);
  }
}


/* --------------------------- Bubble Spectrum ------------------------ */

async function renderBubbleSpectrum() {
  const container = document.getElementById("bubble-spectrum");
  if (!container) return;

  container.innerHTML = "";

  const data = await api("/api/decisions?limit=150");
  if (!data) return;

  const W = container.clientWidth;
  const H = container.clientHeight;

  // ---- Gridlines ----
  const gridCount = 6;
  for (let i = 1; i < gridCount; i++) {
    const line = document.createElement("div");
    line.className = "spectrum-grid";
    line.style.left = (i / gridCount) * W + "px";
    container.appendChild(line);
  }

  // ---- Bubbles ----
  data.forEach((d, i) => {
    const bubble = document.createElement("div");
    bubble.classList.add("bubble");

    const type = d.decision?.toUpperCase();
    bubble.classList.add(
      type === "BUY"
        ? "bubble-buy"
        : type === "SELL"
        ? "bubble-sell"
        : "bubble-hold"
    );

    const intensity = Math.abs(d.aggregate_s ?? 0.15);
    const size = 10 + intensity * 35;
    bubble.style.width = size + "px";
    bubble.style.height = size + "px";

    const x = (i / data.length) * (W - size);
    bubble.style.left = x + "px";

    const yNorm = 0.5 - (d.aggregate_s ?? 0) / 2;
    let y = yNorm * (H - size);
    y += Math.random() * 20 - 10;
    bubble.style.top = y + "px";

    container.appendChild(bubble);
  });
}

renderBubbleSpectrum();
setInterval(renderBubbleSpectrum, 60000);

/* --------------------------- THEME / BOOTSTRAP ---------------------- */

document.addEventListener("DOMContentLoaded", async () => {
  // داشبورد اصلی
  updateDashboard();
  setInterval(updateDashboard, 10000);

  // اورب
  initOrbCanvas();
  await refreshOrbData();          // بار اول
  requestAnimationFrame(animateOrb);

  // هر ۲۰ ثانیه دیتاهای جدید برای اورب
  setInterval(refreshOrbData, 20000);
});
