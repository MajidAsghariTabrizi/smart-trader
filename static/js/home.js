/* =====================================================================
   SmartTrader – Dashboard (Ultra-Optimized Rewrite)
   - No re-render loops
   - Patch updates only
   - Cached API responses
   - Stable chart engine (no rebuild)
   ===================================================================== */

const cache = {
    perf: null,
    decisions: [],
    daily: [],
    trades: [],
    prices: [],
    btc: null
};

async function api(path) {
    try {
        const r = await fetch(path);
        return r.ok ? await r.json() : null;
    } catch {
        return null;
    }
}

/* ----------------------------------------------------------
   PATCH UTILS — فقط تغییرات جدید رندر می‌شود
---------------------------------------------------------- */

function patchText(id, value) {
    const el = document.getElementById(id);
    if (!el) return;
    if (el.textContent !== value) el.textContent = value;
}

function patchWidth(id, w) {
    const el = document.getElementById(id);
    if (!el) return;
    const v = w + "%";
    if (el.style.width !== v) el.style.width = v;
}

/* ----------------------------------------------------------
   HERO + METRICS
---------------------------------------------------------- */

function updateHero() {
    const last = cache.decisions.at(-1) || {};
    const perf = cache.perf || {};

    patchText("hero-last-decision", last.decision || "–");
    patchText("hero-regime", last.regime || "–");
    patchText("hero-adx", last.adx ? last.adx.toFixed(1) : "–");
    patchText("hero-winrate", perf.winrate ? perf.winrate + "٪" : "–");

    patchText("hero-btc-price",
        cache.btc?.price_tmn?.toLocaleString("fa-IR") ??
        cache.btc?.price?.toLocaleString("fa-IR") ??
        "–"
    );
}

function updateMetrics() {
    const p = cache.perf || {};
    patchText("metric-total-trades", p.total_trades ?? "0");
    patchText("metric-total-wins", p.wins ?? "0");
    patchText("metric-total-losses", p.losses ?? "0");
    patchText("metric-total-pnl", p.total_pnl ?? "0");
    patchText("metric-error-rate", (100 - (p.winrate || 0)).toFixed(1) + "%");
}

/* ----------------------------------------------------------
   HEATMAP — فقط سلول جدید اضافه می‌شود
---------------------------------------------------------- */

function updateHeatmap() {
    const box = document.getElementById("heatmap-decisions");
    if (!box) return;

    const list = cache.decisions.slice(-64);

    if (box.children.length === list.length) return;

    box.innerHTML = "";
    list.forEach(d => {
        const cell = document.createElement("div");
        cell.className = "heat-cell";

        const dec = (d.decision || "").toUpperCase();
        cell.style.background =
            dec === "BUY" ? "rgba(0,255,120,0.55)" :
            dec === "SELL" ? "rgba(255,60,60,0.55)" :
                             "rgba(255,210,0,0.55)";

        box.appendChild(cell);
    });
}

/* ----------------------------------------------------------
   PROBABILITY ENGINE
---------------------------------------------------------- */

function updateProbability() {
    const last = cache.decisions.at(-1);
    const wr = cache.perf?.winrate ?? 0;

    let buy = 33, sell = 33, hold = 34;

    if (!last) return;

    const d = last.decision;
    if (d === "BUY") buy += 15;
    if (d === "SELL") sell += 15;
    if (d === "HOLD") hold += 20;

    buy += (wr - 50) * 0.4;
    sell += (50 - wr) * 0.4;

    const total = buy + sell + hold;

    const pb = (buy / total) * 100;
    const ps = (sell / total) * 100;
    const ph = (hold / total) * 100;

    patchWidth("prob-buy", pb);
    patchWidth("prob-sell", ps);
    patchWidth("prob-hold", ph);

    patchText("prob-buy-label", pb.toFixed(1) + "%");
    patchText("prob-sell-label", ps.toFixed(1) + "%");
    patchText("prob-hold-label", ph.toFixed(1) + "%");
}

/* ----------------------------------------------------------
   SENTIMENT
---------------------------------------------------------- */

function updateSentiment() {
    const ul = document.getElementById("sentiment-list");
    if (!ul) return;

    const daily = cache.daily;
    if (!daily.length) return;

    const avg =
        daily.reduce((a, v) => a + (v.day_pnl ?? v.pnl ?? 0), 0) / daily.length;

    const greens = daily.filter(x => (x.pnl ?? x.day_pnl) > 0).length;
    const reds = daily.length - greens;

    const out = [
        avg > 0 ? "میانگین سود روزانه مثبت است." : "میانگین منفی است.",
        greens >= reds
            ? "روزهای مثبت بیشتر بوده."
            : "فشار منفی بیشتر بوده."
    ];

    if (ul.children.length === out.length) return;

    ul.innerHTML = "";
    out.forEach(t => {
        const li = document.createElement("li");
        li.textContent = t;
        ul.appendChild(li);
    });
}

/* ----------------------------------------------------------
   DECISIONS FEED — فقط تکراری‌ها اضافه نمی‌شوند
---------------------------------------------------------- */

function updateDecisionFeed() {
    const box = document.getElementById("decision-list");
    if (!box) return;

    const list = cache.decisions.slice(-40);

    if (box.children.length === list.length) return;

    box.innerHTML = "";
    list.slice().reverse().forEach(d => {
        const row = document.createElement("div");
        row.className = "decision-row";

        row.innerHTML = `
            <div class="decision-row-main">
                <span class="decision-pill decision-${d.decision.toLowerCase()}">
                    ${d.decision}
                </span>
                <span class="decision-price">
                    قیمت: ${Number(d.price).toLocaleString("fa-IR")}
                </span>
            </div>
            <div class="decision-row-meta">
                <span>${new Date(d.timestamp).toLocaleString("fa-IR")}</span>
                <span>رژیم: ${(d.regime || "NEUTRAL").toUpperCase()}</span>
            </div>
        `;
        box.appendChild(row);
    });
}

/* ----------------------------------------------------------
   DAILY PNL
---------------------------------------------------------- */

function updateDailyPNL() {
    const box = document.getElementById("pnl-daily");
    if (!box) return;

    const list = cache.daily;

    if (box.children.length === list.length) return;

    box.innerHTML = "";
    list.forEach(d => {
        const pnl = d.pnl ?? d.day_pnl;
        const sign =
            pnl > 0 ? "pnl-pos" : pnl < 0 ? "pnl-neg" : "pnl-flat";

        const row = document.createElement("div");
        row.className = "pnl-row";
        row.innerHTML = `
           <span class="pnl-date">${d.day}</span>
           <span class="pnl-val ${sign}">
             ${Number(pnl).toLocaleString("fa-IR")}
           </span>
           <span class="pnl-trades">${d.n_trades || 0} ترید</span>
        `;
        box.appendChild(row);
    });
}

/* ----------------------------------------------------------
   RECENT TRADES
---------------------------------------------------------- */

function updateRecentTrades() {
    const box = document.getElementById("recent-trades");
    if (!box) return;

    const list = cache.trades;

    if (box.children.length === list.length) return;

    box.innerHTML = "";
    list.forEach(t => {
        const pnl = Number(t.pnl);
        const sign = pnl > 0 ? "pnl-pos" : pnl < 0 ? "pnl-neg" : "pnl-flat";

        const div = document.createElement("div");
        div.className = "trade-row";
        div.innerHTML = `
            <div class="trade-header">
                <span>${t.side}</span>
                <span>${new Date(t.timestamp).toLocaleString("fa-IR")}</span>
            </div>
            <div class="trade-body">
                <span>ورود: ${t.entry_price}</span>
                <span>خروج: ${t.close_price}</span>
                <span>حجم: ${t.qty}</span>
                <span class="trade-pnl ${sign}">
                    PnL: ${pnl.toLocaleString("fa-IR")}
                </span>
            </div>
        `;
        box.appendChild(div);
    });
}

/* ----------------------------------------------------------
   PRICE CHART — never destroy, only update dataset
---------------------------------------------------------- */

let chart;

function initChart() {
    const ctx = document.getElementById("priceChart").getContext("2d");

    chart = new Chart(ctx, {
        type: "line",
        data: {
            labels: [],
            datasets: [
                {
                    label: "قیمت",
                    data: [],
                    borderColor: "#60a5fa",
                    backgroundColor: "rgba(37,99,235,0.18)",
                    borderWidth: 2,
                    pointRadius: 0,
                    tension: 0.3,
                    fill: true
                },
                {
                    type: "scatter",
                    label: "BUY",
                    data: [],
                    pointBackgroundColor: "#16a34a",
                    pointRadius: 6
                },
                {
                    type: "scatter",
                    label: "SELL",
                    data: [],
                    pointBackgroundColor: "#dc2626",
                    pointRadius: 6
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false
        }
    });
}

function updateChart() {
    if (!chart) return;

    const prices = cache.prices;
    const dec = cache.decisions;

    if (!prices.length) return;

    const labels = prices.map(p => p.timestamp);
    const values = prices.map(p => p.price);

    chart.data.labels = labels;
    chart.data.datasets[0].data = values;

    const idx = Object.fromEntries(labels.map((t, i) => [t, i]));

    chart.data.datasets[1].data = dec
        .filter(d => d.decision === "BUY")
        .map(d => ({
            x: d.timestamp,
            y: values[idx[d.timestamp]]
        }));

    chart.data.datasets[2].data = dec
        .filter(d => d.decision === "SELL")
        .map(d => ({
            x: d.timestamp,
            y: values[idx[d.timestamp]]
        }));

    chart.update("none");
}

/* ----------------------------------------------------------
   MAIN DASHBOARD UPDATE
---------------------------------------------------------- */

async function updateDashboard() {
    const [perf, dec, daily, btc, prices, trades] = await Promise.all([
        api("/api/perf/summary"),
        api("/api/decisions?limit=80"),
        api("/api/perf/daily?limit=30"),
        api("/api/btc_price"),
        api("/api/prices?limit=300"),
        api("/api/trades/recent?limit=30")
    ]);

    cache.perf = perf || cache.perf;
    cache.decisions = Array.isArray(dec) ? dec : cache.decisions;
    cache.daily = Array.isArray(daily) ? daily : cache.daily;
    cache.btc = btc || cache.btc;
    cache.prices = Array.isArray(prices) ? prices : cache.prices;
    cache.trades = Array.isArray(trades) ? trades : cache.trades;

    updateHero();
    updateMetrics();
    updateHeatmap();
    updateProbability();
    updateDecisionFeed();
    updateDailyPNL();
    updateRecentTrades();
    updateSentiment();
    updateChart();
}

/* ----------------------------------------------------------
   INIT
---------------------------------------------------------- */

document.addEventListener("DOMContentLoaded", () => {
    initChart();
    updateDashboard();
    setInterval(updateDashboard, 9000);
});
