/* =============================
   📌 Helper functions
   ============================= */

async function getJSON(url) {
  const res = await fetch(url);
  return res.json();
}

function cls(decision) {
  if (!decision) return "decision-hold";
  const d = decision.toLowerCase();
  if (d.includes("buy")) return "decision-buy";
  if (d.includes("sell")) return "decision-sell";
  return "decision-hold";
}

function decisionFa(dec) {
  const d = (dec || "").toUpperCase();
  if (d === "BUY") return "سیگنال خرید";
  if (d === "SELL") return "سیگنال فروش";
  return "وضعیت HOLD";
}

function regimeFa(r) {
  r = (r || "").toUpperCase();
  if (r === "LOW") return "رژیم کم‌نوسان / محتاط";
  if (r === "HIGH") return "رژیم پرنوسان و رونددار";
  return "رژیم متعادل";
}

function decisionTagClass(dec) {
  const d = (dec || "").toUpperCase();
  if (d === "BUY") return "summary-tag buy";
  if (d === "SELL") return "summary-tag sell";
  return "summary-tag hold";
}

function formatFaDate(ts) {
  const d = new Date(ts);
  if (isNaN(d.getTime())) return ts;
  return d.toLocaleString("fa-IR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}


/* =============================
   📌 Persian AI Commentary
   ============================= */

function buildPersianSummary(dec) {
  if (!dec) return "هنوز تحلیلی در دیتابیس ثبت نشده.";

  const price = dec.price;
  let reasons = [];

  try {
    if (dec.reasons_json) reasons = JSON.parse(dec.reasons_json);
  } catch (e) {}

  const joined = Array.isArray(reasons) ? reasons.join(" | ") : reasons;

  const parts = [];

  parts.push(`ربات در آخرین کندل قیمت حدود <b>${Number(price).toLocaleString("fa-IR")}</b> تومان را ثبت کرده و به جمع‌بندی <b>${decisionFa(dec.decision)}</b> رسیده است.`);
  parts.push(`بازار در وضعیت <b>${regimeFa(dec.regime)}</b> تشخیص داده شده است.`);

  if (joined.includes("Trend gated"))
    parts.push("قدرت روند (ADX) پایین بوده و کانال روند غیرفعال شده است.");

  if (joined.includes("MTF reject"))
    parts.push("تایم‌فریم تأییدی با حرکت اصلی هم‌سو نبود، شدت سیگنال کاهش یافته است.");

  if (joined.includes("MTF agree"))
    parts.push("تایم‌فریم تأییدی نیز همین جهت را تأیید کرده است.");

  return parts.join(" ");
}


/* =============================
   📌 Stats (winrate)
   ============================= */

function buildStats(decisions, prices) {
  const index = {};
  prices.forEach((p, i) => index[p.timestamp] = i);

  let total = 0, buys = 0, sells = 0, wins = 0;

  decisions.forEach(d => {
    const dec = (d.decision || "").toUpperCase();
    if (dec !== "BUY" && dec !== "SELL") return;

    const i = index[d.timestamp];
    if (i == null || i >= prices.length - 1) return;

    total++;
    if (dec === "BUY") buys++; else sells++;

    const now = prices[i].price;
    const next = prices[i + 1].price;

    if (dec === "BUY" && next > now) wins++;
    if (dec === "SELL" && next < now) wins++;
  });

if (total === 0) {
  return {
    total: 0,
    buys: 0,
    sells: 0,
    wins: 0,
    winrate: "بدون سیگنال قابل محاسبه"
  };
}

  return { total, buys, sells, wins, winrate };
}


/* =============================
   📌 Render Decisions List
   ============================= */

let globalDecisions = [];

function renderDecisionList(filter = "all") {
  const container = document.getElementById("decisions");
  container.innerHTML = "";

  const list = globalDecisions
    .slice()
    .reverse()
    .filter(d => {
      const dec = (d.decision || "").toUpperCase();
      if (filter === "buy") return dec === "BUY";
      if (filter === "sell") return dec === "SELL";
      if (filter === "hold") return dec === "HOLD";
      return true;
    });

  list.forEach(d => {
    const div = document.createElement("div");
    div.className = "decision-item " + cls(d.decision);

    div.innerHTML = `
      <div class="decision-label">${decisionFa(d.decision)}</div>
      <div class="decision-price">قیمت: ${Number(d.price).toLocaleString("fa-IR")} تومان</div>
      <div class="decision-time">${formatFaDate(d.timestamp)}</div>
    `;

    container.appendChild(div);
  });
}


/* =============================
   📌 Main Render (Chart + Stats)
   ============================= */

async function render() {
  const prices = await getJSON("/api/prices?limit=300");
  globalDecisions = await getJSON("/api/decisions?limit=80");

  /* ----- Markers ----- */
  const labels = prices.map(p => p.timestamp);
  const data = prices.map(p => p.price);

  const index = {};
  labels.forEach((t, i) => index[t] = i);

  const buyPoints = [];
  const sellPoints = [];

  globalDecisions.forEach(d => {
    const i = index[d.timestamp];
    if (i == null) return;

    const point = { x: labels[i], y: data[i] };

    const dec = (d.decision || "").toUpperCase();
    if (dec === "BUY") buyPoints.push(point);
    if (dec === "SELL") sellPoints.push(point);
  });

  /* ----- Chart ----- */
  const ctx = document.getElementById("priceChart").getContext("2d");

  new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "قیمت",
          data,
          borderColor: "#60a5fa",
          backgroundColor: "rgba(37, 99, 235, 0.18)",
          borderWidth: 2,
          tension: 0.35,
          fill: true,
          pointRadius: 0
        },
        {
          type: "scatter",
          label: "خرید",
          data: buyPoints,
          pointBackgroundColor: "#16a34a",
          pointBorderColor: "#fff",
          pointRadius: 6,
          pointStyle: "triangle"
        },
        {
          type: "scatter",
          label: "فروش",
          data: sellPoints,
          pointBackgroundColor: "#dc2626",
          pointBorderColor: "#fff",
          pointRadius: 6,
          pointStyle: "triangle"
        }
      ]
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
              "قیمت: " + Number(ctx.parsed.y).toLocaleString("fa-IR") + " تومان"
          }
        }
      },
      scales: {
        x: { ticks: { display: false } },
        y: {
         ticks: {
  font: { family: "IRANSans", size: 11 },
  color: getComputedStyle(document.body).color,
  callback: function (value) {
    return Number(value).toLocaleString("fa-IR");
  }
}
        }
      }
    }
  });

  /* ----- Last Summary ----- */
  const last = globalDecisions[globalDecisions.length - 1];
  document.getElementById("lastSummaryText").innerHTML = `
      <span class="${decisionTagClass(last.decision)}">${decisionFa(last.decision)}</span>
      ${buildPersianSummary(last)}
  `;

  /* ----- Stats Bar ----- */
  const stats = buildStats(globalDecisions, prices);
  const statsBar = document.getElementById("statsBar");

statsBar.innerHTML = `
  <div class="stat-pill">سیگنال کل: ${stats.total}</div>
  <div class="stat-pill">خرید: ${stats.buys}</div>
  <div class="stat-pill">فروش: ${stats.sells}</div>
  <div class="stat-pill">وین‌ریت: ${stats.winrate}</div>
`;

  /* ----- Decision List ----- */
  renderDecisionList();

  document.getElementById("filterSelect").addEventListener("change", (e) =>
    renderDecisionList(e.target.value)
  );
}

render();
/* =====================================================
   🌗 THEME ENGINE
   ===================================================== */

const themeBtn = document.getElementById("toggleThemeBtn");

function setTheme(mode) {
  document.body.classList.remove("theme-light", "theme-dark-pro");
  document.body.classList.add(mode);
  localStorage.setItem("theme", mode);

  if (mode === "theme-light") {
    document.querySelector(".theme-toggle .icon").textContent = "🌞";
  } else {
    document.querySelector(".theme-toggle .icon").textContent = "🌙";
  }
}

themeBtn.addEventListener("click", () => {
  const current = localStorage.getItem("theme") || "theme-dark-pro";
  setTheme(current === "theme-dark-pro" ? "theme-light" : "theme-dark-pro");
});

// Load saved theme
setTheme(localStorage.getItem("theme") || "theme-dark-pro");
