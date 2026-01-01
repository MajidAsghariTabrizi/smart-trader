/* =====================================================================
   SmartTrader – Quantum Neural ORB (Standalone for Landing Page)
   ===================================================================== */

const orbState = {
  canvas: null,
  ctx: null,
  W: 0,
  H: 0,
  CX: 0,
  CY: 0,
  particles: [],
  bands: [[], [], []],
  cloud: [],
  lastDecision: null,
  t0: performance.now(),
  resizeTimer: null,
};

function noise(x) {
  return (
    Math.sin(x * 1.37) * 0.6 +
    Math.sin(x * 2.71 + 1.3) * 0.3 +
    Math.sin(x * 0.73 + 4.2) * 0.1
  );
}

function initOrbCanvas() {
  const canvas = document.getElementById("marketOrb");
  if (!canvas) return;

  const ctx = canvas.getContext("2d");
  orbState.canvas = canvas;
  orbState.ctx = ctx;

  function resize() {
    const rect = canvas.getBoundingClientRect();
    const size = Math.min(rect.width, rect.height);
    canvas.width = size;
    canvas.height = size;

    orbState.W = size;
    orbState.H = size;
    orbState.CX = size / 2;
    orbState.CY = size / 2;
  }

  resize();
  window.addEventListener("resize", () => {
    clearTimeout(orbState.resizeTimer);
    orbState.resizeTimer = setTimeout(resize, 150);
  });
}

async function loadOrbData() {
  try {
    const res = await fetch("/api/decisions?limit=260");
    const decisions = await res.json();
    if (Array.isArray(decisions) && decisions.length > 0) {
      rebuildOrbFromDecisions(decisions);
    } else {
      // Fallback: create demo particles
      createDemoOrb();
    }
  } catch (err) {
    console.error("ORB data load error:", err);
    createDemoOrb();
  }
}

function createDemoOrb() {
  const size = orbState.W || 600;
  const CORE_GAP = size * 0.11;
  const R_MIN = size * 0.28;
  const R_MAX = size * 0.62;

  orbState.particles = [];
  orbState.bands = [[], [], []];
  orbState.cloud = [];
  orbState.lastDecision = { aggregate_s: 0.3 };

  for (let i = 0; i < 100; i++) {
    const age = i / 100;
    const band = age < 0.28 ? 0 : age < 0.65 ? 1 : 2;
    let baseRadius = R_MIN + Math.random() * (R_MAX - R_MIN);
    if (baseRadius < CORE_GAP) baseRadius = CORE_GAP + Math.random() * (size * 0.08);

    const p = {
      d: { decision: i % 3 === 0 ? "BUY" : i % 3 === 1 ? "SELL" : "HOLD" },
      band,
      baseAngle: Math.random() * Math.PI * 2,
      baseRadius,
      angleDrift: (Math.random() - 0.5) * 0.45,
      radiusJitter: 20 + Math.random() * 35,
      noiseSeed: Math.random() * 500,
      speed: 0.25 + Math.random() * 0.28,
      ageNorm: age,
    };

    orbState.particles.push(p);
    orbState.bands[band].push(p);
  }

  orbState.bands.forEach(b => b.sort((a, b) => a.baseAngle - b.baseAngle));

  const cloudCount = 140;
  for (let i = 0; i < cloudCount; i++) {
    orbState.cloud.push({
      angle: Math.random() * Math.PI * 2,
      radius: CORE_GAP * (0.3 + Math.random() * 0.9),
      phase: Math.random() * Math.PI * 2,
      speed: 0.5 + Math.random() * 1.1,
      size: 1.2 + Math.random() * 1.5,
    });
  }
}

function rebuildOrbFromDecisions(decisions) {
  if (!orbState.canvas || !decisions?.length) return;

  const N = Math.min(260, decisions.length);
  const size = orbState.W;
  const CORE_GAP = size * 0.11;
  const R_MIN = size * 0.28;
  const R_MAX = size * 0.62;

  orbState.particles = [];
  orbState.bands = [[], [], []];
  orbState.cloud = [];
  orbState.lastDecision = decisions.at(-1);

  for (let i = 0; i < N; i++) {
    const d = decisions[decisions.length - 1 - i];
    const age = i / N;
    const band = age < 0.28 ? 0 : age < 0.65 ? 1 : 2;

    let baseRadius = R_MIN + Math.random() * (R_MAX - R_MIN);
    if (baseRadius < CORE_GAP) baseRadius = CORE_GAP + Math.random() * (size * 0.08);

    const p = {
      d,
      band,
      baseAngle: Math.random() * Math.PI * 2,
      baseRadius,
      angleDrift: (Math.random() - 0.5) * 0.45,
      radiusJitter: 20 + Math.random() * 35,
      noiseSeed: Math.random() * 500,
      speed: 0.25 + Math.random() * 0.28,
      ageNorm: age,
    };

    orbState.particles.push(p);
    orbState.bands[band].push(p);
  }

  orbState.bands.forEach(b => b.sort((a, b) => a.baseAngle - b.baseAngle));

  const cloudCount = 140;
  for (let i = 0; i < cloudCount; i++) {
    orbState.cloud.push({
      angle: Math.random() * Math.PI * 2,
      radius: CORE_GAP * (0.3 + Math.random() * 0.9),
      phase: Math.random() * Math.PI * 2,
      speed: 0.5 + Math.random() * 1.1,
      size: 1.2 + Math.random() * 1.5,
    });
  }
}

function animateOrb(now) {
  const ctx = orbState.ctx;
  if (!ctx || !orbState.W) {
    requestAnimationFrame(animateOrb);
    return;
  }

  const W = orbState.W;
  const CX = orbState.CX;
  const CY = orbState.CY;
  const t = (now - orbState.t0) * 0.001;

  const last = orbState.lastDecision;
  const energyRaw = Math.abs(last?.aggregate_s ?? 0);
  const energy = Math.min(1, energyRaw * 1.6);

  ctx.clearRect(0, 0, W, W);

  // Inner plasma cloud
  orbState.cloud.forEach(c => {
    const angle = c.angle + t * c.speed * 0.3;
    const radius = c.radius + Math.sin(t * 0.5 + c.phase) * (W * 0.02);
    const x = CX + Math.cos(angle) * radius;
    const y = CY + Math.sin(angle) * radius;

    const alpha = 0.15 + Math.sin(t * 2 + c.phase) * 0.1;
    ctx.fillStyle = `rgba(96, 165, 250, ${alpha})`;
    ctx.beginPath();
    ctx.arc(x, y, c.size, 0, Math.PI * 2);
    ctx.fill();
  });

  // Particle bands with mesh
  orbState.bands.forEach((band, bi) => {
    if (band.length < 2) return;

    band.forEach((p, i) => {
      const n = noise(t * p.speed + p.noiseSeed);
      const angle = p.baseAngle + t * p.speed + p.angleDrift * n;
      const radius = p.baseRadius + Math.sin(t * 0.8 + p.noiseSeed) * p.radiusJitter * 0.3;

      const x = CX + Math.cos(angle) * radius;
      const y = CY + Math.sin(angle) * radius;

      p.x = x;
      p.y = y;
    });

    // Draw mesh
    ctx.strokeStyle = `rgba(96, 165, 250, ${0.15 - bi * 0.03})`;
    ctx.lineWidth = 1;
    ctx.beginPath();

    for (let i = 0; i < band.length; i++) {
      const p1 = band[i];
      const p2 = band[(i + 1) % band.length];
      const dist = Math.sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2);
      if (dist < W * 0.15) {
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
      }
    }
    ctx.stroke();

    // Draw particles
    band.forEach(p => {
      const decision = p.d?.decision || "HOLD";
      const color = decision === "BUY" ? "rgba(34, 197, 94, 0.8)" :
                    decision === "SELL" ? "rgba(239, 68, 68, 0.8)" :
                    "rgba(148, 163, 178, 0.6)";

      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(p.x, p.y, 2 + energy * 2, 0, Math.PI * 2);
      ctx.fill();
    });
  });

  // Energy core
  const coreRadius = W * 0.08 + energy * W * 0.05;
  const gradient = ctx.createRadialGradient(CX, CY, 0, CX, CY, coreRadius);
  gradient.addColorStop(0, `rgba(96, 165, 250, ${0.6 + energy * 0.3})`);
  gradient.addColorStop(1, "rgba(96, 165, 250, 0)");
  ctx.fillStyle = gradient;
  ctx.beginPath();
  ctx.arc(CX, CY, coreRadius, 0, Math.PI * 2);
  ctx.fill();

  requestAnimationFrame(animateOrb);
}

// Initialize on DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    initOrbCanvas();
    loadOrbData().then(() => {
      orbState.t0 = performance.now();
      requestAnimationFrame(animateOrb);
    });
  });
} else {
  initOrbCanvas();
  loadOrbData().then(() => {
    orbState.t0 = performance.now();
    requestAnimationFrame(animateOrb);
  });
}

