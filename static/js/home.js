/* =====================================================================
   SmartTrader – Home Base Dashboard (Final Rewrite)
   Ultra-Stable • No API Spam • No RAM Leak • Fully Home-Compatible
   ===================================================================== */

/* ------------------ GLOBAL CACHE ------------------ */

const cache = {
    perf: null,
    decisions: [],
    daily: [],
    trades: [],
    prices: [],
    btc: null
};

let isUpdating = false;          // ← LOCK: prevents overlapping updates
let lastChartUpdate = 0;         // ← Throttle chart update
let chart = null;


/* ------------------ API WRAPPER ------------------ */

async function api(path) {
    try {
        const r = await fetch(path, { cache: "no-store" });
        if (!r.ok) return null;
        return await r.json();
    } catch (e) {
        console.warn("API error:", path, e);
        return null;
    }
}


/* ------------------ PATCH HELPERS ------------------ */

function setText(id, val) {
    const el = document.getElementById(id);
    if (el && el.textContent !== String(val)) el.textContent = val;
}

function setWidth(id, percent) {
    const el = document.getElementById(id);
    if (el) el.style.width = percent + "%";
}


/* =====================================================
   HERO + METRICS
===================================================== */

function updateHero() {
    const last = cache.decisions.at(-1) || {};
    const perf = cache.perf || {};

    setText("hero-last-decision", last.decision || "–");
    setText("hero-regime", last.regime || "–");
    setText("hero-adx", last.adx ? last.adx.toFixed(1) : "–");
    setText("hero-winrate", perf.winrate ? perf.winrate + "٪" : "–");

    const price =
        cache.btc?.price_tmn ??
        cache.btc?.price ??
        "–";

    setText("hero-btc-price", Number(price).toLocaleString("fa-IR"));
}

function updateMetrics() {
    const p = cache.perf || {};
    setText("metric-total-trades", p.total_trades ?? "0");
    setText("metric-total-wins", p.wins ?? "0");
    setText("metric-total-losses", p.losses ?? "0");
    setText("metric-total-pnl", p.total_pnl ?? "0");
    setText("metric-error-rate", (100 - (p.winrate || 0)).toFixed(1) + "%");
}


/* =====================================================
   HEATMAP
===================================================== */

function updateHeatmap() {
    const box = document.getElementById("heatmap-decisions");
    if (!box) return;

    const list = cache.decisions.slice(-64);
    if (box.children.length === list.length) return;

    box.innerHTML = "";

    list.forEach(d => {
        const div = document.createElement("div");
        div.className = "heat-cell";

        const x = (d.decision || "HOLD").toUpperCase();
        div.style.background =
            x === "BUY" ? "rgba(0,255,120,0.55)" :
            x === "SELL" ? "rgba(255,60,60,0.55)" :
                           "rgba(255,210,0,0.55)";

        box.appendChild(div);
    });
}


/* =====================================================
   PROBABILITY ENGINE
===================================================== */

function updateProbability() {
    const last = cache.decisions.at(-1);
    const win = cache.perf?.winrate ?? 0;

    if (!last) return;

    let buy = 33, sell = 33, hold = 34;

    if (last.decision === "BUY") buy += 15;
    if (last.decision === "SELL") sell += 15;
    if (last.decision === "HOLD") hold += 20;

    buy += (win - 50) * 0.4;
    sell += (50 - win) * 0.4;

    const total = buy + sell + hold;
    const pb = (buy / total) * 100;
    const ps = (sell / total) * 100;
    const ph = (hold / total) * 100;

    setWidth("prob-buy", pb);
    setWidth("prob-sell", ps);
    setWidth("prob-hold", ph);

    setText("prob-buy-label", pb.toFixed(1) + "%");
    setText("prob-sell-label", ps.toFixed(1) + "%");
    setText("prob-hold-label", ph.toFixed(1) + "%");
}


/* =====================================================
   SENTIMENT
===================================================== */

function updateSentiment() {
    const ul = document.getElementById("sentiment-list");
    if (!ul) return;

    const list = cache.daily;
    if (!list.length) return;

    const avg = list.reduce((a, v) => a + (v.day_pnl ?? v.pnl ?? 0), 0) / list.length;
    const greens = list.filter(x => (x.pnl ?? x.day_pnl) > 0).length;
    const reds = list.length - greens;

    const msgs = [
        avg > 0 ? "میانگین سود مثبت است." : "میانگین منفی است.",
        greens >= reds ? "روزهای مثبت بیشتر بوده." : "فشار منفی بیشتر بوده."
    ];

    if (ul.children.length === msgs.length) return;

    ul.innerHTML = "";
    msgs.forEach(m => {
        const li = document.createElement("li");
        li.textContent = m;
        ul.appendChild(li);
    });
}


/* =====================================================
   DECISION FEED
===================================================== */

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
                <span class="decision-pill decision-${d.decision.toLowerCase()}">${d.decision}</span>
                <span class="decision-price">قیمت: ${Number(d.price).toLocaleString("fa-IR")}</span>
            </div>
            <div class="decision-row-meta">
                <span>${new Date(d.timestamp).toLocaleString("fa-IR")}</span>
                <span>رژیم: ${(d.regime || "NEUTRAL").toUpperCase()}</span>
            </div>
        `;
        box.appendChild(row);
    });
}


/* =====================================================
   DAILY PNL
===================================================== */

function updateDailyPNL() {
    const box = document.getElementById("pnl-daily");
    if (!box) return;

    const list = cache.daily;

    if (box.children.length === list.length) return;

    box.innerHTML = "";

    list.forEach(d => {
        const pnl = d.pnl ?? d.day_pnl;
        const sign =
            pnl > 0 ? "pnl-pos" :
            pnl < 0 ? "pnl-neg" :
                      "pnl-flat";

        const row = document.createElement("div");
        row.className = "pnl-row";
        row.innerHTML = `
            <span class="pnl-date">${d.day}</span>
            <span class="pnl-val ${sign}">${Number(pnl).toLocaleString("fa-IR")}</span>
            <span class="pnl-trades">${d.n_trades || 0} ترید</span>
        `;

        box.appendChild(row);
    });
}


/* =====================================================
   TRADES LIST
===================================================== */

function updateRecentTrades() {
    const box = document.getElementById("recent-trades");
    if (!box) return;

    const list = cache.trades;
    if (box.children.length === list.length) return;

    box.innerHTML = "";

    list.forEach(t => {
        const pnl = Number(t.pnl);
        const sign =
            pnl > 0 ? "pnl-pos" :
            pnl < 0 ? "pnl-neg" :
                      "pnl-flat";

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
                <span class="trade-pnl ${sign}">PnL: ${pnl.toLocaleString("fa-IR")}</span>
            </div>
        `;

        box.appendChild(div);
    });
}


/* =====================================================
   CHART ENGINE (Throttle)
===================================================== */

function initChart() {
    const ctx = document.getElementById("priceChart").getContext("2d");

    chart = new Chart(ctx, {
        type: "line",
        data: {
            labels: [],
            datasets: [
                {   // line
                    label: "قیمت",
                    data: [],
                    borderColor: "#60a5fa",
                    backgroundColor: "rgba(37,99,235,0.18)",
                    borderWidth: 2,
                    tension: 0.3,
                    pointRadius: 0,
                    fill: true
                },
                {   // buy
                    type: "scatter",
                    label: "BUY",
                    data: [],
                    pointBackgroundColor: "#16a34a",
                    pointRadius: 6
                },
                {   // sell
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

    const now = Date.now();
    if (now - lastChartUpdate < 4000) return; // throttle
    lastChartUpdate = now;

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
        .map(d => ({ x: d.timestamp, y: values[idx[d.timestamp]] }));

    chart.data.datasets[2].data = dec
        .filter(d => d.decision === "SELL")
        .map(d => ({ x: d.timestamp, y: values[idx[d.timestamp]] }));

    chart.update("none");
}


/* =====================================================
   MAIN UPDATE LOOP (LOCKED)
===================================================== */

async function updateDashboard() {
    if (isUpdating) return;
    isUpdating = true;

    try {
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
        updateSentiment();
        updateDecisionFeed();
        updateDailyPNL();
        updateRecentTrades();
        updateChart();

    } catch (e) {
        console.error("Dashboard update error:", e);
    }

    isUpdating = false;
}


/* =====================================================
   INIT
===================================================== */

document.addEventListener("DOMContentLoaded", () => {
    initChart();
    updateDashboard();
    setInterval(updateDashboard, 12000); // safer interval
});
