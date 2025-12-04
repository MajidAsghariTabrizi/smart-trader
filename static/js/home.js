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

function regimeFa(regime) {
  const r = (regime || "").toUpperCase();
  if (r === "HIGH") return "پرنوسان و رونددار (HIGH)";
  if (r === "LOW") return "کم‌نوسان / محافظه‌کار (LOW)";
  return "متعادل (NEUTRAL)";
}

/* ---------------- AI Advisor Logic (rule-based رایگان) ---------------- */

function buildAiAdvice(perf, decisions, dailyPnl) {
  const total = perf?.total_trades || 0;
  const wins = perf?.wins || 0;
  const losses = perf?.losses || 0;
  const winrate = perf?.winrate || 0;
  const totalPnl = perf?.total_pnl || 0;

  const last = Array.isArray(decisions) && decisions.length
    ? decisions[decisions.length - 1]
    : null;

  const recentDays = Array.isArray(dailyPnl)
    ? dailyPnl.slice(-5) // ۵ روز آخر
    : [];

  const sumRecent = recentDays.reduce(
    (acc, d) => acc + Number(d.day_pnl || d.pnl || 0),
    0
  );
  const posDays = recentDays.filter((d) => (d.day_pnl || d.pnl || 0) > 0).length;
  const negDays = recentDays.filter((d) => (d.day_pnl || d.pnl || 0) < 0).length;

  // mood کلی ربات
  let mood = "neutral"; // neutral / confident / defensive

  if (total >= 10 && totalPnl > 0 && winrate >= 55) {
    mood = "confident";
  }
  if (total >= 10 && (totalPnl < 0 || winrate < 50 || sumRecent < 0)) {
    mood = "defensive";
  }

  let title = "در حال جمع‌آوری داده‌ها…";
  let description =
    "به‌محض اینکه تعداد کافی معامله و سیگنال ثبت شود، این بخش یک توصیه عملی برای امروز ارائه می‌دهد.";
  const bullets = [];

  if (!last || total < 5) {
    title = "هنوز زمان مشاهده و یادگیری است 👀";
    description =
      "حجم معاملات و داده‌ها هنوز کم است. بهترین کار در این مرحله، رصد رفتار ربات، بررسی وین‌ریت و آشنایی با منطق آن است.";
    bullets.push("ورود با حجم سنگین در این مرحله پیشنهاد نمی‌شود.");
    bullets.push("روی تحلیل نتایج و رفتار ربات در چند روز آینده تمرکز کن.");
    return { title, description, bullets };
  }

  const lastDec = (last.decision || "").toUpperCase();
  const regime = (last.regime || "NEUTRAL").toUpperCase();

  // توصیه بر اساس تصمیم آخر + مود ربات
  if (lastDec === "BUY") {
    if (mood === "confident") {
      title = "امروز همراه روند خرید حرکت کن ✅";
      description =
        "هم وین‌ریت ربات مناسب است، هم مجموع PnL مثبت است و هم آخرین جمع‌بندی در جهت BUY بوده. امروز اگر می‌خواهی وارد شوی، بهترین سناریو همراهی با جهت خرید ربات و پرهیز از معاملات خلاف جهت است.";
      bullets.push("تریدها را فقط در جهت BUY (لانگ) بررسی کن.");
      bullets.push("حجم هر ترید را در حد ریسک استاندارد (۱٪ یا کمتر) نگه دار.");
      bullets.push("از افزودن پوزیشن خلاف جهت (Short دستی) اجتناب کن.");
    } else if (mood === "defensive") {
      title = "سیگنال خرید هست، اما محتاط باش ⚠️";
      description =
        "آخرین جمع‌بندی در جهت BUY است، اما وین‌ریت یا PnL اخیر نشان می‌دهد ربات در فاز اصلاح یا نوسان بالاست. اگر وارد می‌شوی، حتماً با حجم کوچک و استاپ سخت‌گیرانه حرکت کن.";
      bullets.push("اگر ترید می‌کنی، حجم را نصف یا کمتر از حالت عادی نگه دار.");
      bullets.push("بعد از چند ترید منفی پشت سر هم، برای مدتی فقط مشاهده کن.");
      bullets.push("در صورت برگشت قیمت، سریع از پوزیشن خارج شو (نه امیدواری طولانی).");
    } else {
      title = "سیگنال خرید ملایم – بدون افراط";
      description =
        "جهت فعلی ربات BUY است اما عملکرد کلی نه خیلی درخشان است و نه خیلی ضعیف. می‌توانی وارد شوی، اما با مدیریت ریسک استاندارد و بدون افزایش اهرم یا حجم غیرمعمول.";
      bullets.push("فقط در جهت BUY فکر کن، اما به‌هیچ‌وجه حجم را بیش از حد بزرگ نکن.");
      bullets.push("روی کیفیت نقطه ورود (ورود روی اصلاح‌ها) تمرکز کن.");
    }
  } else if (lastDec === "SELL") {
    if (mood === "confident") {
      title = "تمایل امروز به سمت فروش است ✅";
      description =
        "ربات در بازه اخیر کارنامه‌ی قابل قبولی داشته و آخرین جمع‌بندی روی SELL است. امروز اگر دنبال ترید فعال هستی، سناریوی غالب می‌تواند همراهی با پوزیشن‌های فروش باشد.";
      bullets.push("ستاپ‌های فروش (Short) را بیشتر جدی بگیر.");
      bullets.push("از گرفتن پوزیشن‌های لانگ خلاف جهت بدون دلیل قوی خودداری کن.");
    } else if (mood === "defensive") {
      title = "سیگنال فروش با حالت تدافعی ⚠️";
      description =
        "اگرچه آخرین سیگنال SELL است، اما نتایج چند روز اخیر نشان می‌دهد بازار یا استراتژی در فاز پرفشار بوده. پیشنهاد این است اگر می‌فروشی، حتماً با حجم کوچک و نسبت سود به ضرر منطقی کار کنی.";
      bullets.push("حتی‌الامکان از اورتریدینگ (تعداد ترید زیاد) خودداری کن.");
      bullets.push("فقط ستاپ‌های خیلی تمیز SELL را بگیر، نه هر حرکت کوچکی را.");
    } else {
      title = "سوگیری امروز کاهشی است، اما بدون ریسک‌پذیری اضافه";
      description =
        "در حال حاضر جهت غالب سیگنال‌ها SELL است ولی وضعیت کلی نه آنقدر خوب است که تهاجمی عمل کنی و نه آنقدر بد که کاملاً کنار بکشی. در این فضا، فروش منطقی با مدیریت ریسک محافظه‌کارانه ترجیح دارد.";
      bullets.push("در SELLها حد ضرر را جایی بگذار که در صورت خطا، زیانت قابل‌قبول بماند.");
      bullets.push("از اضافه کردن به پوزیشن‌های زیان‌ده خودداری کن.");
    }
  } else {
    // HOLD
    title = "بهترین کار امروز احتمالاً «تماشا» است 👁‍🗨";
    description =
      "آخرین تصمیم ربات HOLD بوده؛ یعنی شرایط ورود ایده‌آل نبوده است. در چنین روزهایی، بهترین استراتژی برای یک تریدر حرفه‌ای این است که سرمایه‌اش را حفظ کند و فقط بازار را رصد کند.";
    bullets.push("اگر استراتژی‌ات با ربات همسو است، امروز روز کم‌ترید یا بدون ترید است.");
    bullets.push("به‌جای اصرار روی معامله، روی تحلیل گذشته و بهبود پلن تمرکز کن.");
  }

  // چند bullet بر اساس عملکرد اخیر
  if (sumRecent > 0 && posDays >= negDays) {
    bullets.push("سود روزهای اخیر مثبت بوده؛ اما همیشه فرض کن فردا هم ممکن است روز سختی باشد.");
  } else if (sumRecent < 0 && negDays > posDays) {
    bullets.push("روزهای اخیر فشار معاملاتی بالایی داشته؛ بهتر است در مدیریت ریسک سخت‌گیرتر باشی.");
  }

  if (regime === "HIGH") {
    bullets.push("بازار در رژیم پرنوسان است؛ حرکت‌ها تندتر و استاپ‌ها حساس‌تر خواهند بود.");
  } else if (regime === "LOW") {
    bullets.push("بازار کم‌نوسان است؛ بیشتر روی صبر و فیلتر کردن ستاپ‌ها تمرکز کن.");
  }

  return { title, description, bullets };
}

/* ---------------- پر کردن UI هوم + AI ---------------- */

async function loadHome() {
  try {
    // همه چیز را با هم می‌گیریم تا هوم زنده باشد
    const [perf, decisionsRaw, dailyPnlRaw, btc] = await Promise.all([
      getJSON("/api/perf/summary"),
      getJSON("/api/decisions?limit=40"),
      getJSON("/api/perf/daily?limit=10"),
      getJSON("/api/btc_price"),
    ]);

    const perfSafe = perf || {};
    const decisions = Array.isArray(decisionsRaw) ? decisionsRaw : [];
    const dailyPnl = Array.isArray(dailyPnlRaw) ? dailyPnlRaw : [];

    const total = perfSafe.total_trades || 0;
    const wins = perfSafe.wins || 0;
    const losses = perfSafe.losses || 0;
    const winrate = perfSafe.winrate || 0;
    const errorRate = total ? 100 - winrate : 0;
    const totalPnl = perfSafe.total_pnl || 0;

    const last =
      decisions.length > 0 ? decisions[decisions.length - 1] : null;

    /* ---- متریک‌های بالای لندینگ (اگر وجود داشته باشد) ---- */
    const elCorrect = document.getElementById("metric-correct-trades");
    if (elCorrect) elCorrect.textContent = formatNumberFa(wins);

    const elError = document.getElementById("metric-error-rate");
    if (elError) elError.textContent = formatPercent(errorRate);

    const elTotalPnl = document.getElementById("metric-total-pnl");
    if (elTotalPnl) elTotalPnl.textContent = formatNumberFa(totalPnl);

    const elLastDec = document.getElementById("metric-last-decision");
    if (elLastDec && last) elLastDec.textContent = decisionFa(last.decision);

    const capEl = document.getElementById("metric-last-decision-caption");
    if (capEl && last && last.price) {
      capEl.textContent =
        "آخرین تصمیم روی قیمت حدود " +
        Number(last.price).toLocaleString("fa-IR") +
        " تومان گرفته شده است.";
    }

    const riskEl = document.getElementById("metric-risk");
    if (riskEl) {
      const MAX_RISK_PER_TRADE = 0.01; // ۱٪ نمونه
      riskEl.textContent = formatPercent(MAX_RISK_PER_TRADE * 100);
    }

    const btcEl = document.getElementById("metric-btc-price");
    if (btcEl) {
      if (btc && (btc.price_tmn || btc.price)) {
        const val = btc.price_tmn || btc.price;
        btcEl.textContent = formatNumberFa(val);
      } else {
        btcEl.textContent = "در حال اتصال...";
      }
    }

    /* ---- AI Advisor (سکشن جدید) ---- */
    const aiTitleEl = document.getElementById("ai-advice-title");
    const aiBodyEl = document.getElementById("ai-advice-body");
    const aiBulletsEl = document.getElementById("ai-advice-bullets");

    if (aiTitleEl || aiBodyEl || aiBulletsEl) {
      const advice = buildAiAdvice(perfSafe, decisions, dailyPnl);

      if (aiTitleEl) aiTitleEl.textContent = advice.title;
      if (aiBodyEl) aiBodyEl.textContent = advice.description;

      if (aiBulletsEl) {
        aiBulletsEl.innerHTML = "";
        advice.bullets.forEach((b) => {
          const li = document.createElement("li");
          li.textContent = b;
          aiBulletsEl.appendChild(li);
        });
      }
    }

    // کارت وضعیت امروز (سمت راست)
    const ctxRegime = document.getElementById("ai-context-regime");
    const ctxWinrate = document.getElementById("ai-context-winrate");
    const ctxTotalPnl = document.getElementById("ai-context-totalpnl");
    const ctxRecent = document.getElementById("ai-context-recent");
    const ctxLast = document.getElementById("ai-context-lastdecision");

    if (ctxRegime && last) ctxRegime.textContent = regimeFa(last.regime);
    if (ctxWinrate) ctxWinrate.textContent = formatPercent(winrate);
    if (ctxTotalPnl) ctxTotalPnl.textContent = formatNumberFa(totalPnl);

    if (ctxLast && last) ctxLast.textContent = decisionFa(last.decision);

    if (ctxRecent) {
      const sumRecent = dailyPnl.reduce(
        (acc, d) => acc + Number(d.day_pnl || d.pnl || 0),
        0
      );
      if (!dailyPnl.length) {
        ctxRecent.textContent = "هنوز داده کافی برای روزهای اخیر نیست.";
      } else if (sumRecent > 0) {
        ctxRecent.textContent = "چند روز اخیر مجموعاً مثبت بوده است.";
      } else if (sumRecent < 0) {
        ctxRecent.textContent = "چند روز اخیر فشار معاملاتی منفی داشته است.";
      } else {
        ctxRecent.textContent = "خروجی روزهای اخیر تقریباً خنثی بوده است.";
      }
    }
  } catch (e) {
    console.error("Home render error:", e);
  }
}
/* ---------------------------------------------------------
   🔥 بخش ۲: دیتای لایو برای Heatmap / Probability / Volatility / Radar
--------------------------------------------------------- */

function renderHeatmap(decisions) {
  const container = document.getElementById("heatmap-decisions");
  if (!container) return;

  container.innerHTML = "";

  decisions.slice(-60).forEach((d) => {
    const cell = document.createElement("div");
    cell.className = "heat-cell";

    let dec = (d.decision || "").toUpperCase();
    if (dec === "BUY") cell.style.background = "rgba(0,255,120,0.55)";
    else if (dec === "SELL") cell.style.background = "rgba(255,60,60,0.55)";
    else cell.style.background = "rgba(255,210,0,0.55)";

    container.appendChild(cell);
  });
}

/* -------- Probability Engine (Rule-based) -------- */

function computeProbabilities(lastDecision, winrate) {
  const wr = Number(winrate || 0);

  let buy = 33, sell = 33, hold = 34;

  const d = (lastDecision || "").toUpperCase();

  if (d === "BUY") buy += 15;
  if (d === "SELL") sell += 15;
  if (d === "HOLD") hold += 20;

  buy += (wr - 50) * 0.4;
  sell += (50 - wr) * 0.4;

  // normalize
  const total = buy + sell + hold;
  return {
    buy: Math.max(0, (buy / total) * 100),
    sell: Math.max(0, (sell / total) * 100),
    hold: Math.max(0, (hold / total) * 100),
  };
}

function renderProbabilities(prob) {
  const pb = document.getElementById("prob-buy");
  const ps = document.getElementById("prob-sell");
  const ph = document.getElementById("prob-hold");

  const lblB = document.getElementById("prob-buy-label");
  const lblS = document.getElementById("prob-sell-label");
  const lblH = document.getElementById("prob-hold-label");

  if (pb) pb.style.width = prob.buy + "%";
  if (ps) ps.style.width = prob.sell + "%";
  if (ph) ph.style.width = prob.hold + "%";

  if (lblB) lblB.textContent = prob.buy.toFixed(1) + "%";
  if (lblS) lblS.textContent = prob.sell.toFixed(1) + "%";
  if (lblH) lblH.textContent = prob.hold.toFixed(1) + "%";
}

/* ---------------- Volatility Band ---------------- */

function renderVolatility(last) {
  const adx = Number(last?.adx || 0);
  const atr = Number(last?.atr || 0);
  const ptr = document.getElementById("vol-pointer");
  const lbl = document.getElementById("volatility-label");

  if (!ptr || !lbl) return;

  // محاسبه نوسان 0 تا 100
  let vol = Math.min(100, Math.max(0, adx * 1.4 + atr * 0.6));

  ptr.style.left = vol + "%";

  if (vol < 30) lbl.textContent = "بازار آرام و کم‌نوسان است.";
  else if (vol < 60) lbl.textContent = "بازار در محدوده‌ی نوسان متوسط قرار دارد.";
  else lbl.textContent = "بازار بسیار پرنوسان است؛ احتیاط کنید.";
}

/* ---------------- Sentiment Radar ---------------- */

function renderSentiment(daily) {
  const ul = document.getElementById("sentiment-list");
  if (!ul) return;

  ul.innerHTML = "";

  const pnl = daily.map((x) => Number(x.day_pnl || x.pnl || 0));

  const avg = pnl.reduce((a, b) => a + b, 0) / pnl.length;

  const greenDays = pnl.filter((x) => x > 0).length;
  const redDays = pnl.filter((x) => x < 0).length;

  const items = [];

  if (avg > 0) items.push("میانگین سود روزانه مثبت است.");
  else items.push("میانگین سود روزانه منفی است.");

  if (greenDays > redDays)
    items.push("روزهای مثبت بیشتر از روزهای منفی بوده است.");
  else items.push("فشار فروش در روزهای اخیر بیشتر بوده است.");

  if (Math.abs(avg) < 0.1)
    items.push("بازار در روزهای اخیر تقریباً خنثی بوده است.");

  items.forEach((t) => {
    const li = document.createElement("li");
    li.textContent = t;
    ul.appendChild(li);
  });
}

/* ---------------- Hero Sparkline ---------------- */

function renderSparkline(prices) {
  const canvas = document.getElementById("hero-sparkline");
  if (!canvas) return;

  const ctx = canvas.getContext("2d");
  const w = canvas.width, h = canvas.height;

  ctx.clearRect(0, 0, w, h);

  if (!prices || prices.length < 2) return;

  const min = Math.min(...prices);
  const max = Math.max(...prices);

  ctx.beginPath();
  ctx.strokeStyle = "#5da8ff";
  ctx.lineWidth = 2;

  prices.forEach((p, i) => {
    const x = (i / (prices.length - 1)) * w;
    const y = h - ((p - min) / (max - min)) * h;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });

  ctx.stroke();
}

/* ---------------------------------------------------------
   🔥 Loop اصلی آپدیت‌ها
--------------------------------------------------------- */

async function loadLiveModules() {
  const [decisions, perf, daily, btc] = await Promise.all([
    getJSON("/api/decisions?limit=80"),
    getJSON("/api/perf/summary"),
    getJSON("/api/perf/daily?limit=12"),
    getJSON("/api/btc_price"),
  ]);

  const decisionsArr = Array.isArray(decisions) ? decisions : [];
  const dailyArr = Array.isArray(daily) ? daily : [];

  const last = decisionsArr.length ? decisionsArr.at(-1) : null;

  /* Heatmap */
  renderHeatmap(decisionsArr);

  /* Probability */
  const probs = computeProbabilities(last?.decision, perf?.winrate);
  renderProbabilities(probs);

  /* Volatility */
  renderVolatility(last);

  /* Sentiment Radar */
  renderSentiment(dailyArr);

  /* Sparkline */
  if (btc?.history) renderSparkline(btc.history.map((x) => x.price));
}

/* Loop هر 8 ثانیه */
setInterval(loadLiveModules, 8000);


document.addEventListener("DOMContentLoaded", loadHome);
