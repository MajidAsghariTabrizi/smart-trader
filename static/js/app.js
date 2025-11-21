/* =============================
   📌 Helper functions
   ============================= */

async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) {
    console.error("API error:", url, res.status);
    return [];
  }
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
  } catch (e) {
    console.warn("Failed to parse reasons_json", e);
  }

  const joined = Array.isArray(reasons) ? reasons.join(" | ") : (reasons || "");

  const parts = [];

  parts.push(
    `ربات در آخرین کندل قیمت حدود <b>${Number(price).toLocaleString(
      "fa-IR"
    )}</b> تومان را ثبت کرده و به جمع‌بندی <b>${decisionFa(
      dec.decision
    )}</b> رسیده است.`
  );
  parts.push(
    `بازار در وضعیت <b>${regimeFa(dec.regime)}</b> تشخیص داده شده است.`
  );

  if (joined.includes("Trend gated"))
    parts.push(
      "قدرت روند (ADX) پایین بوده و کانال روند به صورت خودکار کم‌اثر شده است تا از سیگنال‌های فیک جلوگیری شود."
    );

  if (joined.includes("MTF reject"))
    parts.push(
      "تایم‌فریم تأییدی با حرکت اصلی هم‌سو نبود، به همین دلیل شدت سیگنال کاهش یافته است."
    );

  if (joined.includes("MTF agree"))
    parts.push(
      "تایم‌فریم تأییدی نیز همین جهت را تأیید کرده و سیگنال از چند بعد تقویت شده است."
    );

  return parts.join(" ");
}

/* =============================
   📌 Stats (winrate)
   ============================= */

function buildStats(decisions, prices) {
  const index = {};
  prices.forEach((p, i) => {
    index[p.timestamp] = i;
  });

  let total = 0,
    buys = 0,
    sells = 0,
    wins = 0;

  decisions.forEach((d) => {
    const dec = (d.decision || "").toUpperCase();
    if (dec !== "BUY" && dec !== "SELL") return;

    const i = index[d.timestamp];
    if (i == null || i >= prices.length - 1) return;

    total++;
    if (dec === "BUY") buys++;
    else sells++;

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

  const winrate = ((wins / total) * 100).toFixed(1) + "%";
  return { total, buys, sells, wins, winrate };
}

/* =============================
   📌 Render Decisions List
   ============================= */

let globalDecisions = [];

function renderDecisionList(filter = "all") {
  const container = document.getElementById("decisions");
  if (!container) return;

  container.innerHTML = "";

  const list = globalDecisions
    .slice()
    .reverse()
    .filter((d) => {
      const dec = (d.decision || "").toUpperCase();
      if (filter === "buy") return dec === "BUY";
      if (filter === "sell") return dec === "SELL";
      if (filter === "hold") return dec === "HOLD";
      return true;
    });

  list.forEach((d) => {
    const div = document.createElement("div");
    div.className = "decision-item " + cls(d.decision);

    div.innerHTML = `
      <div class="decision-label">${decisionFa(d.decision)}</div>
      <div class="decision-price">قیمت: ${Number(d.price).toLocaleString(
        "fa-IR"
      )} تومان</div>
      <div class="decision-time">${formatFaDate(d.timestamp)}</div>
    `;

    container.appendChild(div);
  });
}

/* =============================
   📌 Main Render (Chart + Stats)
   ============================= */

async function render() {
  try {
    const prices = await getJSON("/api/prices?limit=300");
    globalDecisions = await getJSON("/api/decisions?limit=80");

    const labels = prices.map((p) => p.timestamp);
    const data = prices.map((p) => p.price);

    const index = {};
    labels.forEach((t, i) => {
      index[t] = i;
    });

    const buyPoints = [];
    const sellPoints = [];
    const breakoutPoints = [];
    const meanrevPoints = [];

    globalDecisions.forEach((d) => {
      const i = index[d.timestamp];
      if (i == null) return;

      const point = { x: labels[i], y: data[i] };
      const dec = (d.decision || "").toUpperCase();

      if (dec === "BUY") buyPoints.push(point);
      if (dec === "SELL") sellPoints.push(point);

      // تحلیل reasons برای breakout / meanrev
      let reasons = [];
      try {
        if (d.reasons_json) reasons = JSON.parse(d.reasons_json);
      } catch (e) {}
      const joined = Array.isArray(reasons)
        ? reasons.join(" ").toLowerCase()
        : (reasons || "").toString().toLowerCase();

      if (joined.includes("breakout")) breakoutPoints.push(point);
      if (joined.includes("meanrev")) meanrevPoints.push(point);
    });

    /* ----- Chart ----- */
    const canvas = document.getElementById("priceChart");
    if (canvas && prices.length) {
      const ctx = canvas.getContext("2d");

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
              pointBorderColor: "#ffffff",
              pointRadius: 6,
              pointStyle: "triangle"
            },
            {
              type: "scatter",
              label: "فروش",
              data: sellPoints,
              pointBackgroundColor: "#dc2626",
              pointBorderColor: "#ffffff",
              pointRadius: 6,
              pointStyle: "triangle"
            },
            // Breakout – استایل B: دایره با بردر
            {
              type: "scatter",
              label: "Breakout",
              data: breakoutPoints,
              pointStyle: "circle",
              pointRadius: 7,
              pointHoverRadius: 9,
              pointBackgroundColor: "rgba(59,130,246,0.9)",
              pointBorderColor: "#e5f2ff",
              pointBorderWidth: 2
            },
            // Mean Reversion – استایل B: دایره با بردر
            {
              type: "scatter",
              label: "Mean Reversion",
              data: meanrevPoints,
              pointStyle: "circle",
              pointRadius: 7,
              pointHoverRadius: 9,
              pointBackgroundColor: "rgba(239,68,68,0.9)",
              pointBorderColor: "#fee2e2",
              pointBorderWidth: 2
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
                  "قیمت: " +
                  Number(ctx.parsed.y).toLocaleString("fa-IR") +
                  " تومان"
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
    }

    /* ----- Last Summary ----- */
    const summaryEl = document.getElementById("lastSummaryText");
    const last = globalDecisions[globalDecisions.length - 1];

    if (!last || !summaryEl) {
      if (summaryEl) summaryEl.textContent = "هنوز تصمیمی ثبت نشده است.";
      return;
    }

    summaryEl.innerHTML = `
      <span class="${decisionTagClass(last.decision)}">${decisionFa(
      last.decision
    )}</span>
      ${buildPersianSummary(last)}
    `;

    /* ⭐ Signal Strength Meter */
    const strengthEl = document.getElementById("signalStrengthFill");
    if (strengthEl && typeof last.aggregate !== "undefined") {
      const s = Number(last.aggregate); // -1 تا +1
      const pct = Math.max(0, Math.min(100, ((s + 1) / 2) * 100));
      strengthEl.style.width = pct + "%";
    }

    /* ⭐ Regime Component */
    const regimeBox = document.getElementById("regimeLabel");
    if (regimeBox) {
      const regime = (last.regime || "NEUTRAL").toUpperCase();

      regimeBox.classList.remove("regime-low", "regime-neutral", "regime-high");

      if (regime === "LOW") {
        regimeBox.textContent = "کم‌نوسان (LOW)";
        regimeBox.classList.add("regime-low");
      } else if (regime === "HIGH") {
        regimeBox.textContent = "پرنوسان (HIGH)";
        regimeBox.classList.add("regime-high");
      } else {
        regimeBox.textContent = "متعادل (NEUTRAL)";
        regimeBox.classList.add("regime-neutral");
      }
    }

    /* ⭐ ADX Component */
    const adxValueEl = document.getElementById("adxValue");
    if (adxValueEl) {
      const adx = Number(last.adx || 0);

      adxValueEl.textContent = adx.toFixed(1);

      adxValueEl.classList.remove("adx-weak", "adx-medium", "adx-strong");

      if (adx < 20) adxValueEl.classList.add("adx-weak");
      else if (adx < 30) adxValueEl.classList.add("adx-medium");
      else adxValueEl.classList.add("adx-strong");
    }

    /* ----- Stats Bar ----- */
    const stats = buildStats(globalDecisions, prices);
    const statsBar = document.getElementById("statsBar");
    if (statsBar) {
      statsBar.innerHTML = `
        <div class="stat-pill">سیگنال کل: ${stats.total}</div>
        <div class="stat-pill">خرید: ${stats.buys}</div>
        <div class="stat-pill">فروش: ${stats.sells}</div>
        <div class="stat-pill">وین‌ریت: ${stats.winrate}</div>
      `;
    }

    /* ----- Decision List + Filter ----- */
    renderDecisionList();
    const filterSelect = document.getElementById("filterSelect");
    if (filterSelect) {
      filterSelect.addEventListener("change", (e) =>
        renderDecisionList(e.target.value)
      );
    }
  } catch (err) {
    console.error("Render error:", err);
  }
}

/* اجرای اصلی بعد از آماده شدن DOM */
document.addEventListener("DOMContentLoaded", render);

/* =====================================================
   🌗 THEME ENGINE (Light / Dark Pro)
   ===================================================== */

const themeBtn = document.getElementById("toggleThemeBtn");

function setTheme(mode) {
  document.body.classList.remove("theme-light", "theme-dark-pro");
  document.body.classList.add(mode);
  localStorage.setItem("theme", mode);

  const icon = document.querySelector(".theme-toggle .icon");
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

// initial theme
setTheme(localStorage.getItem("theme") || "theme-dark-pro");
