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

/* --------------------------- Market ORB Hero – CHAOTIC NEURAL ORB --- */

// حالت داخلی اورب
const orbState = {
  canvas: null,
  ctx: null,
  W: 0,
  H: 0,
  CX: 0,
  CY: 0,
  particles: [],   // نودهای اصلی (همه تصمیم‌ها)
  bands: [[], [], []], // نودها تقسیم شده روی 3 باند
  cloud: [],       // ذرات مه‌مانند داخل هسته
  lastDecision: null,
  t0: performance.now(),
  resizeTimer: null,
};

// نویز شبه‌پرلین ساده برای اعوجاج طبیعی
function orbNoise(x) {
  return (
    Math.sin(x * 1.37) * 0.6 +
    Math.sin(x * 2.71 + 1.3) * 0.3 +
    Math.sin(x * 0.73 + 4.2) * 0.1
  );
}

// آماده‌سازی بوم
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

// ساخت نودها از روی لیست تصمیم‌ها
function rebuildOrbFromDecisions(decisions) {
  if (!orbState.canvas || !decisions || !decisions.length) return;

  const N = Math.min(280, decisions.length);
  const size = orbState.W;
  const CX = orbState.CX;
  const CY = orbState.CY;

  /* -------------------------------
     محدوده‌ها و شعاع‌ها
  --------------------------------*/
  const CORE_DEAD_ZONE = size * 0.22;   // مرکز خالی
  const SHELL_MIN = size * 0.32;        // شروع نودها
  const SHELL_MAX = size * 0.65;        // بیشترین فاصله نودها

  orbState.particles = [];
  orbState.bands = [[], [], []];
  orbState.cloud = [];
  orbState.lastDecision = decisions.at(-1);

  /* -------------------------------
     ساخت نودها (Particles)
  --------------------------------*/
  for (let i = 0; i < N; i++) {
    const d = decisions[decisions.length - 1 - i];
    const age = i / N;

    // انتخاب باند بر اساس سن
    const band =
      age < 0.25 ? 0 :
      age < 0.60 ? 1 :
      2;

    // شعاع پایه کاملاً تصادفی ولی محدود در پوسته‌ها
    const baseRadius =
      SHELL_MIN +
      Math.random() * (SHELL_MAX - SHELL_MIN) +
      band * (size * 0.06);

    let r0 = baseRadius;

    // تضمین: هیچ نودی وارد مرکز نشود
    if (r0 < CORE_DEAD_ZONE) {
      r0 = CORE_DEAD_ZONE + Math.random() * (size * 0.08);
    }

    const angle = Math.random() * Math.PI * 2;

    const p = {
      d,
      band,
      baseAngle: angle,
      baseRadius: r0,
      angleDrift: (Math.random() - 0.5) * 0.5,
      radiusJitter: 22 + Math.random() * 40,
      noiseSeed: Math.random() * 500,
      speed: 0.25 + Math.random() * 0.3,
      ageNorm: age
    };

    orbState.particles.push(p);
    orbState.bands[band].push(p);
  }

  /* -------------------------------
     مرتب‌سازی باندها برای اتصال طبیعی
  --------------------------------*/
  orbState.bands.forEach(b => {
    b.sort((a, b) => a.baseAngle - b.baseAngle);
  });

  /* -------------------------------
     پلاسما درونی (Cloud)
  --------------------------------*/
  const cloudN = 150;
  orbState.cloud = [];

  for (let i = 0; i < cloudN; i++) {
    orbState.cloud.push({
      angle: Math.random() * Math.PI * 2,
      radius: CORE_DEAD_ZONE * (0.25 + Math.random() * 0.8),
      phase: Math.random() * Math.PI * 2,
      speed: 0.7 + Math.random() * 1.2,
      size: 1.2 + Math.random() * 1.6
    });
  }
}

// انیمیشن اصلی اورب
function animateOrb(now) {
  if (!orbState.canvas || !orbState.ctx) return;

  const ctx = orbState.ctx;
  const W = orbState.W;
  const H = orbState.H;
  const CX = orbState.CX;
  const CY = orbState.CY;
  const t = (now - orbState.t0) * 0.001;

  ctx.clearRect(0, 0, W, H);

  /* ---------------------- پشت‌زمینه هاله‌ای ---------------------- */
  const outerR = W * 0.5;
  const bgGrad = ctx.createRadialGradient(
    CX,
    CY,
    W * 0.1,
    CX,
    CY,
    outerR
  );
  bgGrad.addColorStop(0, "rgba(10,10,20,0)");
  bgGrad.addColorStop(1, "rgba(3,5,16,0.95)");
  ctx.fillStyle = bgGrad;
  ctx.beginPath();
  ctx.arc(CX, CY, outerR, 0, Math.PI * 2);
  ctx.fill();

  /* --------------------------- هسته --------------------------- */
  const last = orbState.lastDecision;
  const coreColor =
    last?.decision === "BUY"
      ? "rgba(0,255,190,0.95)"
      : last?.decision === "SELL"
      ? "rgba(255,90,120,0.95)"
      : "rgba(255,235,170,0.95)";

  const coreR = W * (0.06 + Math.sin(t * 3) * 0.004);

  // هاله‌ی نرم دور هسته
  const coreGrad = ctx.createRadialGradient(
    CX,
    CY,
    coreR * 0.4,
    CX,
    CY,
    coreR * 2.5
  );
  coreGrad.addColorStop(0, "rgba(255,255,255,0.85)");
  coreGrad.addColorStop(0.3, coreColor);
  coreGrad.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = coreGrad;
  ctx.beginPath();
  ctx.arc(CX, CY, coreR * 2.5, 0, Math.PI * 2);
  ctx.fill();

  // دیسک مرکزی
  ctx.beginPath();
  ctx.fillStyle = coreColor;
  ctx.arc(CX, CY, coreR, 0, Math.PI * 2);
  ctx.fill();

  /* ---------------------- ابر پلاسما (cloud) ---------------------- */
  ctx.fillStyle = "rgba(180,210,255,0.13)";
  orbState.cloud.forEach((c, idx) => {
    const rr =
      c.radius +
      Math.sin(t * c.speed + c.phase) * 3.5;

    const ang =
      c.angle +
      Math.sin(t * 0.4 + idx * 0.37) * 0.4;

    const x = CX + Math.cos(ang) * rr;
    const y = CY + Math.sin(ang) * rr;

    const alpha =
      0.08 +
      0.07 *
        Math.sin(t * 1.3 + c.phase + idx * 0.21);

    ctx.beginPath();
    ctx.fillStyle = `rgba(190,220,255,${alpha})`;
    ctx.arc(x, y, c.size, 0, Math.PI * 2);
    ctx.fill();
  });

  /* ---------------------- موج شوک (Shockwave) ---------------------- */
  const energy = Math.abs(last?.aggregate_s ?? 0);
  if (energy > 0.25) {
    const phase = (t * 1.6) % 1; // ۰..۱
    const r =
      W * 0.18 + phase * (W * 0.35);
    const alpha = 0.6 * (1 - phase);

    ctx.beginPath();
    ctx.lineWidth = 1.8;
    ctx.strokeStyle = `rgba(120,210,255,${alpha})`;
    ctx.arc(CX, CY, r, 0, Math.PI * 2);
    ctx.stroke();
  }

  /* ---------------------- خطوط میدان مغناطیسی ---------------------- */
  ctx.lineWidth = 0.7;
  ctx.strokeStyle = "rgba(80,140,255,0.20)";
  const fieldLines = 14;
  for (let i = 0; i < fieldLines; i++) {
    const baseAng =
      (i / fieldLines) * Math.PI * 2 +
      Math.sin(t * 0.5 + i) * 0.12;

    const bend = Math.sin(t * 0.8 + i * 1.9) * 0.45;

    const r1 = W * 0.11;
    const r2 = W * 0.45;

    const x1 =
      CX + Math.cos(baseAng - bend) * r1;
    const y1 =
      CY + Math.sin(baseAng - bend) * r1;

    const x2 =
      CX + Math.cos(baseAng + bend) * r2;
    const y2 =
      CY + Math.sin(baseAng + bend) * r2;

    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
  }

  /* ---------------------- حلقه‌های مش (Bands) ---------------------- */
  orbState.bands.forEach((bandArr, bandIdx) => {
    if (!bandArr.length) return;

    ctx.beginPath();

    bandArr.forEach((p, idx) => {
      const noiseVal = orbNoise(p.noiseSeed + t * 0.7);
      const r =
        p.baseRadius +
        noiseVal * p.radiusJitter +
        Math.sin(t * 1.1 + p.noiseSeed) * 4;

      const ang =
        p.baseAngle +
        t * p.speed +
        p.angleDrift *
          Math.sin(t * 0.8 + p.noiseSeed);

      const x = CX + Math.cos(ang) * r;
      const y = CY + Math.sin(ang) * r;

      p._x = x; // برای پاس بعدی (نقطه و نود)
      p._y = y;

      if (idx === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });

    ctx.closePath();

    const alpha =
      bandIdx === 0 ? 0.65 : bandIdx === 1 ? 0.45 : 0.30;
    const col =
      bandIdx === 0
        ? `rgba(190,210,255,${alpha})`
        : bandIdx === 1
        ? `rgba(150,190,255,${alpha})`
        : `rgba(110,150,255,${alpha})`;

    ctx.lineWidth = bandIdx === 0 ? 1.2 : 0.9;
    ctx.strokeStyle = col;
    ctx.stroke();
  });

  /* ---------------------- نودهای نورانی (تصمیم‌ها) ---------------------- */
  orbState.particles.forEach((p, idx) => {
    const d = p.d || {};
    const dec = (d.decision || "").toUpperCase();
    const intensity = Math.abs(d.aggregate_s ?? 0.12);

    const age = p.ageNorm; // نزدیک صفر = جدیدتر
    const baseSize = 2.3 + (1 - age) * 2.7;
    const size = baseSize + intensity * 2.3;

    let col;
    if (dec === "BUY")
      col = `rgba(0,255,190,${0.45 + intensity * 0.8})`;
    else if (dec === "SELL")
      col = `rgba(255,110,140,${0.45 + intensity * 0.8})`;
    else
      col = `rgba(255,230,170,${0.35 + intensity * 0.8})`;

    // آخرین تصمیم → هایلایت بیشتر
    let glowExtra = 0;
    if (
      orbState.lastDecision &&
      d.timestamp === orbState.lastDecision.timestamp
    ) {
      glowExtra = 0.4;
    }

    // گلو (هاله) کوچک
    const glowR = size * 2.7;
    const gx = p._x;
    const gy = p._y;

    const gGrad = ctx.createRadialGradient(
      gx,
      gy,
      0,
      gx,
      gy,
      glowR
    );
    gGrad.addColorStop(
      0,
      col.replace("rgba", "rgba").replace(/\)\s*$/, "")
    );
    gGrad.addColorStop(
      1,
      `rgba(0,0,0,0)`
    );
    ctx.fillStyle = gGrad;
    ctx.beginPath();
    ctx.arc(gx, gy, glowR, 0, Math.PI * 2);
    ctx.fill();

    // خود نود
    ctx.beginPath();
    ctx.fillStyle = col;
    ctx.arc(gx, gy, size, 0, Math.PI * 2);
    ctx.fill();

    // فلاش خیلی کوتاه برای سیگنال‌های قوی
    if (intensity > 0.35 && Math.random() < 0.04) {
      ctx.beginPath();
      ctx.fillStyle = col;
      ctx.arc(gx, gy, size * 1.7, 0, Math.PI * 2);
      ctx.fill();
    }
  });

  requestAnimationFrame(animateOrb);
}

// آپدیت دیتا هر چند ثانیه یک بار
async function refreshOrbData() {
  const data = await api("/api/decisions?limit=280");
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
