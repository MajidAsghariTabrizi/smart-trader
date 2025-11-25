async function getJSON(url) {
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error("HTTP " + res.status);
    return res.json();
  } catch (e) {
    console.error("API error:", url, e);
    return null;
  }
}

function formatPercent(num) {
  if (num === null || num === undefined) return "–";
  return Number(num).toFixed(1) + "٪";
}

function formatNumberFa(num) {
  if (num === null || num === undefined) return "–";
  return Number(num).toLocaleString("fa-IR");
}

function decisionFa(dec) {
  const d = (dec || "").toUpperCase();
  if (d === "BUY") return "سیگنال خرید";
  if (d === "SELL") return "سیگنال فروش";
  if (d === "HOLD") return "حالت HOLD / بدون ورود";
  return "نامشخص";
}

async function loadMetrics() {
  const perf = await getJSON("/api/perf/summary");
  const decisions = await getJSON("/api/decisions?limit=1");

  // ۱) متریک‌های عملکرد از /api/perf/summary
  if (perf) {
    const total = perf.total_trades || 0;
    const wins = perf.wins || 0;
    const losses = perf.losses || 0;
    const winrate = perf.winrate || 0;
    const errorRate = total ? 100 - winrate : 0;
    const totalPnl = perf.total_pnl || 0;

    document.getElementById("metric-correct-trades").textContent =
      formatNumberFa(wins);
    document.getElementById("metric-error-rate").textContent =
      formatPercent(errorRate);
    document.getElementById("metric-total-pnl").textContent =
      formatNumberFa(totalPnl);
  }

  // ۲) آخرین تصمیم ربات از /api/decisions
  if (Array.isArray(decisions) && decisions.length > 0) {
    const last = decisions[decisions.length - 1];
    const decFa = decisionFa(last.decision);
    document.getElementById("metric-last-decision").textContent = decFa;

    const capEl = document.getElementById("metric-last-decision-caption");
    if (capEl && last.price) {
      capEl.textContent =
        "آخرین تصمیم روی قیمت حدود " +
        Number(last.price).toLocaleString("fa-IR") +
        " تومان گرفته شده است.";
    }
  }

  // ۳) ضریب ریسک – فعلاً از config دستی (درصد سرمایه در هر ترید)
  // می‌توانی این مقدار را با cfg.STRATEGY["max_risk_per_trade"] سینک کنی
  const MAX_RISK_PER_TRADE = 0.01; // ۱٪ نمونه
  document.getElementById("metric-risk").textContent =
    formatPercent(MAX_RISK_PER_TRADE * 100);

  // ۴) قیمت لحظه‌ای بیت‌کوین (بهتر است در backend یک /api/btc_price بسازی)
  try {
    const btc = await getJSON("/api/btc_price");
    if (btc && btc.price_tmn) {
      document.getElementById("metric-btc-price").textContent =
        formatNumberFa(btc.price_tmn);
    } else {
      document.getElementById("metric-btc-price").textContent = "در حال اتصال...";
    }
  } catch (e) {
    console.warn("BTC price error", e);
    document.getElementById("metric-btc-price").textContent = "نامشخص";
  }
}

document.addEventListener("DOMContentLoaded", loadMetrics);
