/* =============================
   📌 Helper functions
   ============================= */

async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) {
    console.error("API error:", url, res.status);
    return null;
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
  // بک‌اند timestamp را به ms UNIX می‌فرستد
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
   📌 Decisions List
   ============================= */

let globalDecisions = [];

/** نزدیک‌ترین ایندکس قیمت به timestamp تصمیم را برمی‌گرداند */
function findNearestPriceIndex(ts, labels) {
  if (!labels || !labels.length) return null;

  const target = Number(ts);
  if (!Number.isFinite(target)) return null;

  let bestIdx = 0;
  let bestDiff = Math.abs(Number(labels[0]) - target);

  for (let i = 1; i < labels.length; i++) {
    const diff = Math.abs(Number(labels[i]) - target);
    if (diff < bestDiff) {
      bestDiff = diff;
      bestIdx = i;
    }
  }
  return bestIdx;
}

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
   📌 Daily PnL & Recent Trades
   ============================= */

function renderDailyPnl(daily) {
  const el = document.getElementById("pnlDailyList");
  if (!el) return;

  if (!daily || !daily.length) {
    el.textContent = "هنوز ترید بسته‌شده‌ای برای محاسبه سود روزانه وجود ندارد.";
    return;
  }

  el.innerHTML = "";
  daily.forEach((d) => {
    const pnl = Number(d.pnl || 0);
    const signClass = pnl > 0 ? "pnl-pos" : pnl < 0 ? "pnl-neg" : "pnl-flat";

    const row = document.createElement("div");
    row.className = "pnl-item";

    row.innerHTML = `
      <span class="pnl-date">${d.day}</span>
      <span class="pnl-pnl ${signClass}">${pnl.toLocaleString("fa-IR")}</span>
      <span class="pnl-trades">${d.n_trades} ترید</span>
    `;
    el.appendChild(row);
  });
}

function renderRecentTrades(trades) {
  const el = document.getElementById("tradesList");
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
    row.className = "trade-item";

    row.innerHTML = `
      <div class="trade-header">
        <span class="trade-side">${sideFa}</span>
        <span class="trade-time">${formatFaDate(t.timestamp)}</span>
      </div>
      <div class="trade-body">
        <span>ورود: ${Number(t.entry_price || 0).toLocaleString(
          "fa-IR"
        )}</span>
        <span>خروج: ${Number(t.close_price || 0).toLocaleString(
          "fa-IR"
        )}</span>
        <span>حجم: ${Number(t.qty || 0).toLocaleString("fa-IR")}</span>
        <span class="trade-pnl ${pnlClass}">PnL: ${pnl.toLocaleString(
          "fa-IR"
        )}</span>
      </div>
    `;
    el.appendChild(row);
  });
}

/* =============================
   📌 Main Render (Chart + Stats + Perf)
   ============================= */

async function render() {
  try {
    const [prices, decisions, perfSummaryRaw, dailyPnl, recentTrades] =
      await Promise.all([
        getJSON("/api/prices?limit=300"),
        getJSON("/api/decisions?limit=80"),
        getJSON("/api/perf/summary"),
        getJSON("/api/perf/daily?limit=30"),
        getJSON("/api/trades/recent?limit=50"),
      ]);

    const perfSummary = perfSummaryRaw || {};

    const safePrices = Array.isArray(prices) ? prices : [];
    const safeDecisions = Array.isArray(decisions) ? decisions : [];

    globalDecisions = safeDecisions;

    /* ----- Build price arrays ----- */
    const labels = safePrices.map((p) => p.timestamp);
    const data = safePrices.map((p) => p.price);

    const index = {};
    labels.forEach((t, i) => {
      index[t] = i;
    });

    /* ----- Decision-based points ----- */
    const buyPoints = [];
    const sellPoints = [];
    const breakoutPoints = [];
    const meanrevPoints = [];

    globalDecisions.forEach((d) => {
      // اول تلاش می‌کنیم ایندکس مستقیم پیدا کنیم
      let i = index[d.timestamp];

      // اگر نبود، نزدیک‌ترین کندل قیمت را انتخاب می‌کنیم
      if (i == null) {
        i = findNearestPriceIndex(d.timestamp, labels);
      }
      if (i == null) return;

      const point = { x: labels[i], y: data[i] };
      const dec = (d.decision || "").toUpperCase();

      if (dec === "BUY") buyPoints.push(point);
      if (dec === "SELL") sellPoints.push(point);

      // تحلیل reasons برای breakout / meanrev
      let reasons = [];
      try {
        if (d.reasons_json) reasons = JSON.parse(d.reasons_json);
      } catch (e) {
        // ignore
      }
      const joined = Array.isArray(reasons)
        ? reasons.join(" ").toLowerCase()
        : (reasons || "").toString().toLowerCase();

      if (joined.includes("breakout")) breakoutPoints.push(point);
      if (joined.includes("meanrev")) meanrevPoints.push(point);
    });

    /* ----- Chart ----- */
    const canvas = document.getElementById("priceChart");
    if (canvas && safePrices.length) {
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
              pointRadius: 0,
            },
            {
              type: "scatter",
              label: "خرید",
              data: buyPoints,
              pointBackgroundColor: "#16a34a",
              pointBorderColor: "#ffffff",
              pointRadius: 6,
              pointStyle: "triangle",
            },
            {
              type: "scatter",
              label: "فروش",
              data: sellPoints,
              pointBackgroundColor: "#dc2626",
              pointBorderColor: "#ffffff",
              pointRadius: 6,
              pointStyle: "triangle",
            },
            {
              type: "scatter",
              label: "Breakout",
              data: breakoutPoints,
              pointStyle: "circle",
              pointRadius: 7,
              pointHoverRadius: 9,
              pointBackgroundColor: "rgba(59,130,246,0.9)",
              pointBorderColor: "#e5f2ff",
              pointBorderWidth: 2,
            },
            {
              type: "scatter",
              label: "Mean Reversion",
              data: meanrevPoints,
              pointStyle: "circle",
              pointRadius: 7,
              pointHoverRadius: 9,
              pointBackgroundColor: "rgba(239,68,68,0.9)",
              pointBorderColor: "#fee2e2",
              pointBorderWidth: 2,
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
                font: { family: "IRANSans", size: 11 },
                color: getComputedStyle(document.body).color,
                callback: function (value) {
                  return Number(value).toLocaleString("fa-IR");
                },
              },
            },
          },
        },
      });
    }

    /* ----- Last Summary ----- */
    const summaryEl = document.getElementById("lastSummaryText");
    const last = globalDecisions[globalDecisions.length - 1];

    if (!last || !summaryEl) {
      if (summaryEl) summaryEl.textContent = "هنوز تصمیمی ثبت نشده است.";
    } else {
      summaryEl.innerHTML = `
        <span class="${decisionTagClass(last.decision)}">${decisionFa(
        last.decision
      )}</span>
        ${buildPersianSummary(last)}
      `;
    }

    /* ⭐ Signal Strength Meter (aggregate_s یا aggregate) */
    const strengthEl = document.getElementById("signalStrengthFill");
    if (strengthEl && last) {
      const sRaw =
        last.aggregate_s !== undefined
          ? last.aggregate_s
          : last.aggregate !== undefined
          ? last.aggregate
          : null;

      if (sRaw !== null) {
        const s = Number(sRaw); // فرض -1 تا +1
        const pct = Math.max(0, Math.min(100, ((s + 1) / 2) * 100));
        strengthEl.style.width = pct + "%";
      } else {
        strengthEl.style.width = "0%";
      }
    }

    /* ⭐ Regime Component */
    const regimeBox = document.getElementById("regimeLabel");
    if (regimeBox && last) {
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

    /* ⭐ ADX Component (اگر از API برگردانده شود) */
    const adxValueEl = document.getElementById("adxValue");
    if (adxValueEl && last) {
      const adx = Number(
        last.adx !== undefined ? last.adx : last.confirm_adx || 0
      );
      adxValueEl.textContent = adx.toFixed(1);
      adxValueEl.classList.remove("adx-weak", "adx-medium", "adx-strong");

      if (adx < 20) adxValueEl.classList.add("adx-weak");
      else if (adx < 30) adxValueEl.classList.add("adx-medium");
      else adxValueEl.classList.add("adx-strong");
    }

    /* ----- Stats Bar (real PnL & winrate) ----- */
    const statsBar = document.getElementById("statsBar");
    if (statsBar) {
      const total = perfSummary.total_trades || 0;
      const wins = perfSummary.wins || 0;
      const losses = perfSummary.losses || 0;
      const winrate = Number(perfSummary.winrate || 0).toFixed(1);
      const totalPnl = Number(perfSummary.total_pnl || 0).toLocaleString(
        "fa-IR"
      );

      statsBar.innerHTML = `
        <div class="stat-pill">معاملات بسته‌شده: ${total}</div>
        <div class="stat-pill">برد: ${wins}</div>
        <div class="stat-pill">باخت: ${losses}</div>
        <div class="stat-pill">وین‌ریت واقعی: ${winrate}%</div>
        <div class="stat-pill">PnL کل: ${totalPnl}</div>
      `;
    }

    /* ----- Daily PnL & Trades ----- */
    renderDailyPnl(Array.isArray(dailyPnl) ? dailyPnl : []);
    renderRecentTrades(Array.isArray(recentTrades) ? recentTrades : []);

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
