/* =====================================================================
   SmartTrader – Home Page Logic (FULLY SYNCED WITH web_app.py)
   ===================================================================== */

// --------------------------- Helpers ----------------------------------

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

// --------------------------- Sparkline --------------------------------

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

// --------------------------- Heatmap ----------------------------------

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
      let color = "rgba(255,210,0,0.55)"; // HOLD / default
      if (dec === "BUY") color = "rgba(0,255,120,0.55)";
      if (dec === "SELL") color = "rgba(255,60,60,0.55)";

      cell.style.background = color;
      box.appendChild(cell);
    });
}

// ----------------------- Probability Engine ---------------------------

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

// --------------------------- Volatility -------------------------------

function renderVol(last) {
  const ptr = document.getElementById("vol-pointer");
  const lbl = document.getElementById("volatility-label");
  if (!ptr || !lbl) return;

  const adx = Number(last?.adx || 0);
  const atr = Number(last?.atr || 0);
  let vol = Math.min(100, Math.max(0, adx * 1.4 + atr * 0.6));

  ptr.style.left = vol + "%";

  if (vol < 30) lbl.textContent = "بازار آرام و کم‌نوسان است.";
  else if (vol < 60) lbl.textContent = "بازار در محدوده‌ی نوسان متوسط قرار دارد.";
  else lbl.textContent = "بازار بسیار پرنوسان است؛ احتیاط کنید.";
}

// --------------------------- Sentiment --------------------------------

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

  const avg =
    pnlList.reduce((acc, v) => acc + v, 0) / (pnlList.length || 1);
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

// --------------------------- Hero & Metrics ---------------------------

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
  set("metric-error-rate", fmtPct(100 - (perf.winrate || 0)));
}

// --------------------------- AI Context & Advisor ---------------------

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

function renderAIContext(last, perf, daily) {
  const set = (id, v) => {
    const el = document.getElementById(id);
    if (el) el.textContent = v;
  };

  set("ai-context-regime", last?.regime || "نامشخص");
  set("ai-context-winrate", fmtPct(perf.winrate));
  set("ai-context-totalpnl", fmtNum(perf.total_pnl));
  set(
    "ai-context-lastdecision",
    last ? faDecision(last.decision) : "نامشخص"
  );

  const list = Array.isArray(daily) ? daily : [];
  const sumRecent = list.reduce(
    (acc, d) => acc + Number(d.day_pnl ?? d.pnl ?? 0),
    0
  );

  if (!list.length) {
    set("ai-context-recent", "هنوز داده کافی برای روزهای اخیر وجود ندارد.");
  } else if (sumRecent > 0) {
    set("ai-context-recent", "چند روز اخیر مجموعاً مثبت بوده‌اند.");
  } else if (sumRecent < 0) {
    set("ai-context-recent", "چند روز اخیر فشار منفی بیشتری داشته‌اند.");
  } else {
    set("ai-context-recent", "خروجی روزهای اخیر تقریباً خنثی بوده است.");
  }
}

// --------------------------- UPDATE LOOP ------------------------------

async function updateHome() {
  try {
    const [perf, decisions, daily, btc] = await Promise.all([
      api("/api/perf/summary"),
      api("/api/decisions?limit=80"),
      api("/api/perf/daily?limit=12"),
      api("/api/btc_price"),
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
    const last = decisionsSafe[decisionsSafe.length - 1] || null;

    // Hero + Metrics
    renderHero(last, perfSafe, btc || {});
    renderMetrics(perfSafe);

    // Modules
    renderHeatmap(decisionsSafe);
    renderVol(last);
    renderSentiment(dailySafe);

    if (btc && Array.isArray(btc.history)) {
      renderSparkline(btc.history);
    }

    const advice = buildAiAdvice(perfSafe, decisionsSafe, dailySafe);
    renderAiAdviceUi(advice);
    renderAIContext(last, perfSafe, dailySafe);
  } catch (e) {
    console.error("Home update error:", e);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  updateHome();
  setInterval(updateHome, 6000);
});
