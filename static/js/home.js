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

/* --------------------------- MAIN PRICE CHART ----------------------- */

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

/* --------------------------- AI CONTEXT ----------------------------- */

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

    /* HERO */
    renderHero(last, perfSafe, btc || {});
    renderMetrics(perfSafe);
    renderHeatmap(decisionsSafe);
    renderVol(last);
    renderSentiment(dailySafe);

    if (btc && Array.isArray(btc.history))
      renderSparkline(btc.history);

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

/* ==========================================================
   SMARTTRADER ORB + QUANTUM FUSION ENGINE
   ========================================================== */

let orbCanvas, orb;
let time = 0;

/* ORB CONFIG */
const ORB_CONFIG = {
  baseRadius: 180,
  noiseAmp: 22,
  particleCount: 32,
  ringSpeed: 0.0025,
  ringRadius: 260,
};

let quantumNodes = [];

function orbPhysics(dec, trend, adx, power) {
  const color =
    dec === "BUY" ? "#4fffd2" :
    dec === "SELL" ? "#ff5b5b" :
    "#ffe680";

  return {
    color,
    deform: Math.min(Math.abs(power) * 1.9, 2.2),
    pulse: 0.7 + Math.min(adx / 38, 2),
    verticalShift: trend * 35,
  };
}

function drawCoreShape(state) {
  const w = orbCanvas.width;
  const h = orbCanvas.height;

  orb.clearRect(0, 0, w, h);

  const cx = w / 2;
  const cy = h / 2 + state.verticalShift;

  const baseR = ORB_CONFIG.baseRadius;

  orb.beginPath();

  for (let i = 0; i <= 360; i++) {
    const ang = i * Math.PI / 180;
    const noise =
      Math.sin(i * 0.12 + time * state.pulse) *
      state.deform *
      ORB_CONFIG.noiseAmp;

    const r = baseR + noise;

    const x = cx + r * Math.cos(ang);
    const y = cy + r * Math.sin(ang);

    i === 0 ? orb.moveTo(x, y) : orb.lineTo(x, y);
  }

  orb.closePath();

  orb.fillStyle = state.color + "35";
  orb.fill();

  orb.strokeStyle = state.color;
  orb.lineWidth = 2.5;
  orb.stroke();
}

function drawQuantumRings() {
  orb.strokeStyle = "#ffffff22";
  orb.lineWidth = 1;

  const cx = orbCanvas.width / 2;
  const cy = orbCanvas.height / 2;

  for (let i = 0; i < 3; i++) {
    const r = ORB_CONFIG.ringRadius + i * 28;

    orb.beginPath();
    for (let a = 0; a < Math.PI * 2; a += 0.02) {
      const x = cx + Math.cos(a + time * ORB_CONFIG.ringSpeed * (i + 1)) * r;
      const y = cy + Math.sin(a) * (r * 0.32);
      orb.lineTo(x, y);
    }
    orb.stroke();
  }
}

function drawQuantumNodes() {
  const cx = orbCanvas.width / 2;
  const cy = orbCanvas.height / 2;

  quantumNodes.forEach((n) => {
    const pulse = Math.sin(time * 3 + n.seed) * 6;

    orb.beginPath();
    orb.arc(cx + n.x, cy + n.y, n.size + pulse, 0, Math.PI * 2);

    orb.fillStyle = n.color;
    orb.fill();
  });
}

async function fusionLoop() {
  if (!orbCanvas) return;

  const latest = await api("/api/decisions?limit=1");
  const d = latest?.[0];

  if (!d) {
    requestAnimationFrame(fusionLoop);
    return;
  }

  const decision = d.final_decision || d.decision || "HOLD";

  const physics = orbPhysics(
    decision,
    Number(d.trend_raw ?? 0),
    Number(d.confirm_adx ?? d.adx ?? 0),
    Number(d.aggregate_s ?? 0)
  );

  drawCoreShape(physics);
  drawQuantumRings();
  drawQuantumNodes();

  time += 0.013;
  requestAnimationFrame(fusionLoop);
}

async function loadQuantumNodes() {
  const res = await api("/api/decisions?limit=40");

  if (!Array.isArray(res)) return;

  quantumNodes = res.map((d, index) => {
    const angle = Math.random() * Math.PI * 2;

    return {
      x: Math.cos(angle) * (130 + Math.random() * 35),
      y: Math.sin(angle) * (90 + Math.random() * 25),
      size: 6 + Math.random() * 6,
      seed: index,
      color:
        d.final_decision === "BUY"
          ? "#4fffd2"
          : d.final_decision === "SELL"
          ? "#ff5b5b"
          : "#ffe680",
    };
  });
}

/* --------------------------- INIT ---------------------------------- */
document.addEventListener("DOMContentLoaded", async () => {

    /* ----------------------------
       ORB INIT (One-Time Setup)
    ---------------------------- */
    orbCanvas = document.getElementById("marketOrb");

    if (orbCanvas) {
        const resizeOrb = () => {
            orbCanvas.width = window.innerWidth;
            orbCanvas.height = window.innerHeight;
        };

        resizeOrb();
        window.addEventListener("resize", resizeOrb);

        orb = orbCanvas.getContext("2d");

        await loadQuantumNodes();  // preload initial nodes
        requestAnimationFrame(fusionLoop); // start ONE animation loop only
    }

    /* ----------------------------
       DASHBOARD INIT
    ---------------------------- */
    updateDashboard();

    // Refresh UI every 10 sec (safe)
    setInterval(updateDashboard, 10000);

    // Refresh ORB nodes every 10 sec
    setInterval(loadQuantumNodes, 10000);
});
