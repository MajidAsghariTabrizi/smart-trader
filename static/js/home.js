/* =====================================================================
   SmartTrader – Unified Dashboard JS
   (Sync with /api/... endpoints on backend)
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
  const atr = Number(last?.atr || 0);
  // scale ساده؛ اگر خواستی می‌تونی تغییر بدهی
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

  const avg = pnlList.reduce((acc, v) => acc + v, 0) / (pnlList.length || 1);
  const greens = pnlList.filter((x) => x > 0).length;
  const reds = pnlList.filter((x) => x < 0).length;

  const items = [];
  items.push(
    avg > 0 ? "میانگین سود روزانه مثبت است." : "میانگین سود روزانه منفی است."
  );
  items.push(
    greens >= reds
      ? "روزهای مثبت بیشتر یا برابر با روزهای منفی بوده است."
      : "فشار منفی در روزهای اخیر بیشتر بوده است."
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
  // اگر تو HTML درصد خطا داری
  set("metric-error-rate", fmtPct(100 - (perf.winrate || 0)));
}

/* --------------------------- Decisions List ------------------------- */

let globalDecisions = [];

function renderDecisionList() {
  const container = document.getElementById("decision-list");
  if (!container) return;

  container.innerHTML = "";

  if (!globalDecisions.length) {
    const empty = document.createElement("div");
    empty.className = "decision-empty";
    empty.textContent = "هنوز تصمیمی ثبت نشده است.";
    container.appendChild(empty);
    return;
  }

  const list = globalDecisions.slice().reverse();

  list.forEach((d) => {
    const item = document.createElement("div");
    item.className = "decision-row";

    item.innerHTML = `
      <div class="decision-row-main">
        <span class="decision-pill decision-${(d.decision || "hold").toLowerCase()}">
          ${faDecision(d.decision)}
        </span>
        <span class="decision-price">
          قیمت: ${fmtNum(d.price)} تومان
        </span>
      </div>
      <div class="decision-row-meta">
        <span>${formatFaDate(d.timestamp)}</span>
        <span>رژیم: ${(d.regime || "NEUTRAL").toUpperCase()}</span>
      </div>
    `;
    container.appendChild(item);
  });
}

/* --------------------------- Daily PnL & Trades --------------------- */

function renderDailyPnl(daily) {
  const el = document.getElementById("pnl-daily");
  if (!el) return;

  if (!daily || !daily.length) {
    el.textContent =
      "هنوز ترید بسته‌شده‌ای برای محاسبه سود و زیان روزانه وجود ندارد.";
    return;
  }

  el.innerHTML = "";
  daily.forEach((d) => {
    const pnl = Number(d.pnl ?? d.day_pnl ?? 0);
    const signClass = pnl > 0 ? "pnl-pos" : pnl < 0 ? "pnl-neg" : "pnl-flat";

    const row = document.createElement("div");
    row.className = "pnl-row";

    row.innerHTML = `
      <span class="pnl-date">${d.day}</span>
      <span class="pnl-val ${signClass}">
        ${pnl.toLocaleString("fa-IR")}
      </span>
      <span class="pnl-trades">${d.n_trades || d.trades || 0} ترید</span>
    `;
    el.appendChild(row);
  });
}

function renderRecentTrades(trades) {
  const el = document.getElementById("recent-trades");
  if (!el) return;

  if (!trades || !trades.length) {
    el.textContent = "هنوز ترید بسته‌شده‌ای ثبت نشده است.";
    return;
  }

  el.innerHTML = "";
  trades.forEach((t) => {
    const pnl = Number(t.pnl || 0);
    const pnlClass = pnl > 0 ? "pnl-pos" : pnl < 0 ? "pnl-neg" : "pnl-flat";
    const sideFa =
      (t.side || "").toUpperCase() === "LONG" ? "خرید (LONG)" : "فروش (SHORT)";

    const row = document.createElement("div");
    row.className = "trade-row";

    row.innerHTML = `
      <div class="trade-header">
        <span class="trade-side">${sideFa}</span>
        <span class="trade-time">${formatFaDate(t.timestamp)}</span>
      </div>
      <div class="trade-body">
        <span>ورود: ${fmtNum(t.entry_price)}</span>
        <span>خروج: ${fmtNum(t.close_price)}</span>
        <span>حجم: ${fmtNum(t.qty)}</span>
        <span class="trade-pnl ${pnlClass}">
          PnL: ${pnl.toLocaleString("fa-IR")}
        </span>
      </div>
    `;
    el.appendChild(row);
  });
}

/* --------------------------- Main Price Chart ----------------------- */

let priceChartInstance = null;

function buildPriceDecisionChart(prices, decisions) {
  const canvas = document.getElementById("priceChart");
  if (!canvas || !prices || !prices.length) return;

  const labels = prices.map((p) => p.timestamp);
  const data = prices.map((p) => p.price);

  const indexByTs = {};
  labels.forEach((t, i) => {
    indexByTs[t] = i;
  });

  const buyPoints = [];
  const sellPoints = [];

  decisions.forEach((d) => {
    const i = indexByTs[d.timestamp];
    if (i == null) return;

    const point = { x: labels[i], y: data[i] };
    const dec = (d.decision || "").toUpperCase();
    if (dec === "BUY") buyPoints.push(point);
    if (dec === "SELL") sellPoints.push(point);
  });

  const ctx = canvas.getContext("2d");
  if (priceChartInstance) {
    priceChartInstance.destroy();
  }

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
          tension: 0.35,
          fill: true,
          pointRadius: 0,
        },
        {
          type: "scatter",
          label: "خرید",
          data: buyPoints,
          pointBackgroundColor: "#16a34a",
          pointBorderColor: "#ffffff",
          pointRadius: 5,
          pointStyle: "triangle",
        },
        {
          type: "scatter",
          label: "فروش",
          data: sellPoints,
          pointBackgroundColor: "#dc2626",
          pointBorderColor: "#ffffff",
          pointRadius: 5,
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
              "قیمت: " +
              Number(ctx.parsed.y).toLocaleString("fa-IR") +
              " تومان",
          },
        },
      },
      scales: {
        x: { ticks: { display: false } },
        y: {
          ticks: {
            callback: function (value) {
              return Number(value).toLocaleString("fa-IR");
            },
          },
        },
      },
    },
  });
}

/* --------------------------- AI Context & Advice -------------------- */

function buildAiAdvice(perf, decisions, daily) {
  const total = perf?.total_trades || 0;
  const winrate = perf?.winrate || 0;
  const totalPnl = perf?.total_pnl || 0;
  const last = decisions?.[decisions.length - 1] || null;

  if (!last || total < 3) {
    return {
      title: "هنوز داده کافی وجود ندارد",
      description:
        "برای ارائه توصیه عملی، باید چند معامله و تصمیم واقعی ثبت شده باشد.",
      bullets: ["فعلاً بهترین کار مشاهده رفتار ربات و جمع‌آوری داده است."],
    };
  }

  const dec = (last.decision || "").toUpperCase();
  const regime = (last.regime || "NEUTRAL").toUpperCase();

  let title = "تحلیل امروز";
  let description = "";
  const bullets = [];

  if (dec === "BUY") {
    title = "سوگیری امروز روی خرید است";
    description =
      "سیگنال غالب فعلی BUY است. اگر قصد ورود داری، فقط در جهت خرید فکر کن و مدیریت ریسک را رعایت کن.";
    bullets.push("ورود فقط در جهت BUY و همراه با روند.");
  } else if (dec === "SELL") {
    title = "سوگیری امروز روی فروش است";
    description =
      "سیگنال غالب SELL است. بازار می‌تواند در فاز اصلاح یا نزول باشد.";
    bullets.push("اگر ترید می‌کنی، ستاپ‌های SELL را جدی‌تر بگیر.");
  } else {
    title = "امروز بیشتر حالت HOLD است";
    description =
      "سیگنال واضحی برای ورود قوی وجود ندارد؛ حفظ سرمایه مهم‌تر از ورود اجباری است.";
    bullets.push("به‌جای اصرار روی معامله، روی تحلیل گذشته تمرکز کن.");
  }

  if (totalPnl < 0) {
    bullets.push("PNL اخیر منفی است؛ حجم ترید را کاهش بده و سخت‌گیرتر استاپ بگذار.");
  }
  if (winrate > 55) {
    bullets.push("وین‌ریت کلی خوب است؛ ستاپ‌های هم‌جهت با ربات ارزش توجه دارند.");
  }

  if (regime === "HIGH") {
    bullets.push("بازار پرنوسان است؛ مراقب جهش‌های سریع قیمت باش.");
  } else if (regime === "LOW") {
    bullets.push("بازار کم‌نوسان است؛ صبر و فیلتر کردن ستاپ‌ها مهم‌تر است.");
  }

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

    // Hero & top metrics
    renderHero(last, perfSafe, btc || {});
    renderMetrics(perfSafe);

    // Modules
    renderHeatmap(decisionsSafe);
    renderVol(last);
    renderSentiment(dailySafe);
    if (btc && Array.isArray(btc.history)) {
      renderSparkline(btc.history);
    }

    // Probability engine (از last decision + winrate)
    const prob = computeProb(last?.decision, perfSafe.winrate);
    renderProb(prob);

    // Main price chart
    buildPriceDecisionChart(pricesSafe, decisionsSafe);

    // Lists
    renderDecisionList();
    renderDailyPnl(dailySafe);
    const recent = await api("/api/trades/recent?limit=30");
    renderRecentTrades(Array.isArray(recent) ? recent : []);

    // AI Advisor
    const advice = buildAiAdvice(perfSafe, decisionsSafe, dailySafe);
    renderAiAdviceUi(advice);
  } catch (e) {
    console.error("Dashboard update error:", e);
  }
}

/* --------------------------- THEME (Optional) ----------------------- */

const themeBtn = document.getElementById("toggleThemeBtn");

function setTheme(mode) {
  document.body.classList.remove("theme-light", "theme-dark-pro");
  document.body.classList.add(mode);
  localStorage.setItem("theme", mode);

  const icon = document.querySelector(".theme-toggle-icon");
  if (icon) icon.textContent = mode === "theme-light" ? "🌞" : "🌙";
}

if (themeBtn) {
  themeBtn.addEventListener("click", () => {
    const current = localStorage.getItem("theme") || "theme-dark-pro";
    const next =
      current === "theme-dark-pro" ? "theme-light" : "theme-dark-pro";
    setTheme(next);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setTheme(localStorage.getItem("theme") || "theme-dark-pro");
  updateDashboard();
  // رفرش هر ۱۰ ثانیه
  setInterval(updateDashboard, 10000);
});
