/* =====================================================================
   SmartTrader – Home Base Dashboard (Stable Auto Loop)
   - No overlapping requests
   - No RAM leak
   - Compatible with home.html structure
   ===================================================================== */
/* Anti-duplicate boot */
if (window.__HOME_JS_RUNNING__) {
    console.warn("Home.js already running – duplicate prevented.");
    throw new Error("Duplicate Home.js instance prevented."); 
}
window.__HOME_JS_RUNNING__ = true;

/* بقیه فایل از اینجا ادامه پیدا می‌کند… */
/* ------------------ GLOBAL CACHE ------------------ */

const cache = {
    perf: null,
    decisions: [],
    daily: [],
    trades: [],
    prices: [],
    btc: null,
};

let isUpdating = false;      // قفل برای جلوگیری از اجرای موازی
let lastChartUpdate = 0;     // throttle برای آپدیت چارت
let chart = null;

const REFRESH_MS = 9000;     // فاصله‌ی دفعات رفرش
const FETCH_TIMEOUT_MS = 7000;

/* ------------------ HELPERS ------------------ */

function formatNum(n, def = "0") {
    if (n === null || n === undefined) return def;
    const x = Number(n);
    if (!isFinite(x)) return def;
    return x.toLocaleString("fa-IR");
}

function setText(id, val) {
    const el = document.getElementById(id);
    if (!el) return;
    const s = String(val);
    if (el.textContent !== s) el.textContent = s;
}

function setWidth(id, percent) {
    const el = document.getElementById(id);
    if (!el) return;
    el.style.width = percent + "%";
}

/* ------------------ API WRAPPER (with timeout) ------------------ */

async function api(path) {
    const controller = new AbortController();
    const t = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);

    try {
        const res = await fetch(path, {
            cache: "no-store",
            signal: controller.signal,
        });
        if (!res.ok) {
            console.warn("API non-200:", path, res.status);
            return null;
        }
        return await res.json();
    } catch (e) {
        if (e.name === "AbortError") {
            console.warn("API timeout:", path);
        } else {
            console.warn("API error:", path, e);
        }
        return null;
    } finally {
        clearTimeout(t);
    }
}

/* =====================================================
   HERO + METRICS
===================================================== */

function updateHero() {
    const last = cache.decisions[cache.decisions.length - 1] || {};
    const perf = cache.perf || {};

    setText("hero-last-decision", last.decision || "–");
    setText("hero-regime", last.regime || "–");
    setText(
        "hero-adx",
        last.adx !== undefined && last.adx !== null
            ? Number(last.adx).toFixed(1)
            : "–"
    );
    setText(
        "hero-winrate",
        perf.winrate !== undefined && perf.winrate !== null
            ? `${perf.winrate}٪`
            : "–"
    );

    const rawPrice =
        cache.btc && cache.btc.price_tmn != null
            ? cache.btc.price_tmn
            : cache.btc && cache.btc.price != null
            ? cache.btc.price
            : null;

    const priceText = rawPrice == null ? "–" : formatNum(rawPrice, "–");
    setText("hero-btc-price", priceText);
}

function updateMetrics() {
    const p = cache.perf || {};
    setText("metric-total-trades", formatNum(p.total_trades));
    setText("metric-total-wins", formatNum(p.wins));
    setText("metric-total-losses", formatNum(p.losses));
    setText("metric-total-pnl", formatNum(p.total_pnl, "0"));
    const winrate = Number(p.winrate || 0);
    setText("metric-error-rate", (100 - winrate).toFixed(1) + "%");
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

    list.forEach((d) => {
        const div = document.createElement("div");
        div.className = "heat-cell";

        const x = (d.decision || "HOLD").toUpperCase();
        div.style.background =
            x === "BUY"
                ? "rgba(0,255,120,0.55)"
                : x === "SELL"
                ? "rgba(255,60,60,0.55)"
                : "rgba(255,210,0,0.55)";

        box.appendChild(div);
    });
}

/* =====================================================
   PROBABILITY ENGINE
===================================================== */

function updateProbability() {
    const last = cache.decisions[cache.decisions.length - 1];
    const win = Number(cache.perf?.winrate || 0);

    if (!last) return;

    let buy = 33,
        sell = 33,
        hold = 34;

    if (last.decision === "BUY") buy += 15;
    if (last.decision === "SELL") sell += 15;
    if (last.decision === "HOLD") hold += 20;

    buy += (win - 50) * 0.4;
    sell += (50 - win) * 0.4;

    const total = buy + sell + hold || 1;
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
    if (!Array.isArray(list) || !list.length) return;

    const avg =
        list.reduce((a, v) => a + Number(v.day_pnl ?? v.pnl ?? 0), 0) /
        list.length;
    const greens = list.filter((x) => (x.pnl ?? x.day_pnl) > 0).length;
    const reds = list.length - greens;

    const msgs = [
        avg > 0 ? "میانگین سود مثبت است." : "میانگین منفی است.",
        greens >= reds ? "روزهای مثبت بیشتر بوده." : "فشار منفی بیشتر بوده.",
    ];

    if (ul.children.length === msgs.length) return;

    ul.innerHTML = "";
    msgs.forEach((m) => {
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

    list
        .slice()
        .reverse()
        .forEach((d) => {
            const row = document.createElement("div");
            row.className = "decision-row";
            row.innerHTML = `
                <div class="decision-row-main">
                    <span class="decision-pill decision-${(d.decision || "hold").toLowerCase()}">
                        ${d.decision || "HOLD"}
                    </span>
                    <span class="decision-price">
                        قیمت: ${formatNum(d.price, "–")}
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

/* =====================================================
   DAILY PNL
===================================================== */

function updateDailyPNL() {
    const box = document.getElementById("pnl-daily");
    if (!box) return;

    const list = cache.daily;
    if (!Array.isArray(list)) return;
    if (box.children.length === list.length) return;

    box.innerHTML = "";

    list.forEach((d) => {
        const pnl = Number(d.pnl ?? d.day_pnl ?? 0);
        const sign =
            pnl > 0 ? "pnl-pos" : pnl < 0 ? "pnl-neg" : "pnl-flat";

        const row = document.createElement("div");
        row.className = "pnl-row";
        row.innerHTML = `
            <span class="pnl-date">${d.day}</span>
            <span class="pnl-val ${sign}">${formatNum(pnl, "0")}</span>
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
    if (!Array.isArray(list)) return;
    if (box.children.length === list.length) return;

    box.innerHTML = "";

    list.forEach((t) => {
        const pnl = Number(t.pnl ?? 0);
        const sign =
            pnl > 0 ? "pnl-pos" : pnl < 0 ? "pnl-neg" : "pnl-flat";

        const div = document.createElement("div");
        div.className = "trade-row";
        div.innerHTML = `
            <div class="trade-header">
                <span>${(t.side || "").toUpperCase()}</span>
                <span>${new Date(t.timestamp).toLocaleString("fa-IR")}</span>
            </div>
            <div class="trade-body">
                <span>ورود: ${formatNum(t.entry_price, "–")}</span>
                <span>خروج: ${formatNum(t.close_price, "–")}</span>
                <span>حجم: ${formatNum(t.qty, "–")}</span>
                <span class="trade-pnl ${sign}">
                    PnL: ${formatNum(pnl, "0")}
                </span>
            </div>
        `;
        box.appendChild(div);
    });
}

/* =====================================================
   CHART ENGINE (Throttle)
===================================================== */

function initChart() {
    const canvas = document.getElementById("priceChart");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

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
                    tension: 0.3,
                    pointRadius: 0,
                    fill: true,
                },
                {
                    type: "scatter",
                    label: "BUY",
                    data: [],
                    pointBackgroundColor: "#16a34a",
                    pointRadius: 6,
                },
                {
                    type: "scatter",
                    label: "SELL",
                    data: [],
                    pointBackgroundColor: "#dc2626",
                    pointRadius: 6,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
        },
    });
}

function updateChart() {
    if (!chart) return;

    const now = Date.now();
    if (now - lastChartUpdate < 4000) return; // throttle هر ۴ ثانیه
    lastChartUpdate = now;

    const prices = cache.prices;
    const dec = cache.decisions;

    if (!Array.isArray(prices) || prices.length < 5) return;

    const labels = prices.map((p) => p.timestamp);
    const values = prices.map((p) => Number(p.price));

    // اگر دیتای خراب (NaN) داشته باشیم، رها کن
    if (!values.every((v) => isFinite(v))) return;

    chart.data.labels = labels;
    chart.data.datasets[0].data = values;

    const idx = {};
    labels.forEach((t, i) => (idx[t] = i));

    chart.data.datasets[1].data = dec
        .filter((d) => d.decision === "BUY" && idx[d.timestamp] != null)
        .map((d) => ({
            x: d.timestamp,
            y: values[idx[d.timestamp]],
        }));

    chart.data.datasets[2].data = dec
        .filter((d) => d.decision === "SELL" && idx[d.timestamp] != null)
        .map((d) => ({
            x: d.timestamp,
            y: values[idx[d.timestamp]],
        }));

    chart.update("none");
}

/* =====================================================
   MAIN UPDATE LOOP (CHAINED, NO INTERVAL OVERLAP)
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
            api("/api/trades/recent?limit=30"),
        ]);

        if (perf) cache.perf = perf;
        if (Array.isArray(dec)) cache.decisions = dec;
        if (Array.isArray(daily)) cache.daily = daily;
        if (btc) cache.btc = btc;
        if (Array.isArray(prices)) cache.prices = prices;
        if (Array.isArray(trades)) cache.trades = trades;

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
    } finally {
        isUpdating = false;
    }
}

/* ------------------ AUTO LOOP (بدون setInterval) ------------------ */

async function autoLoop() {
    await updateDashboard();
    setTimeout(autoLoop, REFRESH_MS);
}

/* =====================================================
   INIT
===================================================== */

document.addEventListener("DOMContentLoaded", () => {
    initChart();
    autoLoop();
});
