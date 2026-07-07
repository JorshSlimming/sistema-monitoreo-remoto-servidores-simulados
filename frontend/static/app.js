/* Monitor local · sistema de monitoreo remoto
 * Sala de control demo:
 *   - misión arriba, escenarios, chart multi-serie en tiempo real,
 *     paneles por nodo, stream de comandos+acks, logs, controles de demo.
 * Polls cada 5 s. Stdlib + DOM. Sin librerías de charting.
 * Lee el backend de forma defensiva: cualquier campo extra se ignora.
 */
(() => {
  "use strict";

  // === Config =============================================================
  const ENDPOINTS = {
    status: { method: "GET", path: "/api/status" },
    metrics: { method: "GET", path: "/api/metrics" },
    logs: { method: "GET", path: "/api/logs" },
    events: { method: "GET", path: "/api/events" },
    artifacts: { method: "GET", path: "/api/artifacts" },
  };
  // POST endpoints. Body shape mirrors what the server already accepts.
  const ACTIONS = {
    "demo-bundle": { method: "POST", path: "/api/demo-bundle" },
    scenario: { method: "POST", path: "/api/scenario" },
    tests: { method: "POST", path: "/api/tests" },
    nmap: { method: "POST", path: "/api/nmap" },
    "tshark-capture": { method: "POST", path: "/api/tshark-capture" },
    screenshots: { method: "POST", path: "/api/screenshots" },
    reset: { method: "POST", path: "/api/reset" },
  };

  const POLL_MS = 5000;
  const SPARK_POINTS = 32; // ≈ 2 min 40 s a 5 s
  const CHART_POINTS = 40; // ventana del chart grande
  const MAX_HISTORY = 200;
  const MAX_EVENTS = 30;
  const MAX_LOGS = 80;

  // Thresholds (%, ms) → used to color bars, sparklines, and chart series.
  const T = {
    cpu: { warn: 60, error: 80, ymax: 100, unit: "%" },
    ram: { warn: 70, error: 85, ymax: 100, unit: "%" },
    latency_ms: { warn: 100, error: 200, ymax: 400, unit: "ms" },
  };

  // Color tokens per node series (CSS variable names).
  const SERIES = [
    { name: "node-01", color: "var(--info)" },
    { name: "node-02", color: "var(--success)" },
    { name: "node-03", color: "var(--warn)" },
    { name: "node-04", color: "var(--accent)" },
    { name: "node-05", color: "var(--error)" },
    { name: "node-06", color: "var(--idle)" },
  ];
  const seriesColor = (id) => {
    let h = 0;
    for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
    const slot = SERIES[h % SERIES.length];
    return slot.color;
  };

  // === State ==============================================================
  const state = {
    lastRefresh: null,
    history: new Map(), // node_id -> { cpu: [], ram: [], latency_ms: [], ts: [], labels: [] }
    nodes: new Map(),
    events: [],
    events_total: { commands: 0, acks: 0 },
    scenario: { name: null, startedAt: null, status: "idle" },
    chartMetric: "cpu",
    artifactsCount: 0,
    feedbackTimer: null,
  };

  // === Utils ==============================================================
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const $id = (id) => document.getElementById(id);

  const escapeHtml = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[c]));

  const formatTime = (iso) => {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleTimeString("es-CO", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  };

  const formatAgo = (iso) => {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "—";
    const s = Math.max(0, Math.floor((Date.now() - d.getTime()) / 1000));
    if (s < 5) return "ahora";
    if (s < 60) return `hace ${s} s`;
    const m = Math.floor(s / 60);
    if (m < 60) return `hace ${m} min`;
    const h = Math.floor(m / 60);
    return `hace ${h} h`;
  };

  const formatDuration = (ms) => {
    if (ms == null || !Number.isFinite(ms)) return "";
    const s = Math.max(0, Math.floor(ms / 1000));
    const m = Math.floor(s / 60);
    const sec = s % 60;
    if (m === 0) return `0:${String(sec).padStart(2, "0")}`;
    return `${m}:${String(sec).padStart(2, "0")}`;
  };

  const pick = (obj, names) => {
    if (!obj || typeof obj !== "object") return undefined;
    for (const n of names) {
      if (obj[n] !== undefined && obj[n] !== null) return obj[n];
    }
    return undefined;
  };

  const numberOr = (v, fallback) => {
    const n = Number(v);
    return Number.isFinite(n) ? n : fallback;
  };

  const normalizeMetric = (m) => {
    if (!m || typeof m !== "object") return null;
    const nodeId = pick(m, ["node_id", "node", "id", "name"]) || "desconocido";
    return {
      node_id: String(nodeId),
      cpu: numberOr(pick(m, ["cpu", "cpu_pct", "cpu_percent"]), null),
      ram: numberOr(pick(m, ["ram", "mem", "memory", "ram_pct"]), null),
      latency_ms: numberOr(pick(m, ["latency_ms", "latency", "lat", "rtt_ms"]), null),
      service_web: pick(m, ["service_web", "service", "web"]) ?? null,
      event_log: pick(m, ["event_log", "event", "last_event"]) ?? null,
      timestamp: pick(m, ["timestamp", "ts", "time", "received_at"]) ?? null,
    };
  };

  // === API client =========================================================
  async function fetchJson(url) {
    let res;
    try {
      res = await fetch(url, { method: "GET", headers: { Accept: "application/json" } });
    } catch (err) {
      throw new Error(`Sin conexión con ${url}`);
    }
    const text = await res.text();
    let data = null;
    if (text) {
      try { data = JSON.parse(text); } catch { data = null; }
    }
    if (!res.ok) throw new Error(`HTTP ${res.status} en ${url}`);
    return data || {};
  }

  async function postJson(url, body) {
    let res;
    try {
      res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: body == null ? "" : JSON.stringify(body),
      });
    } catch (err) {
      throw new Error(`Sin conexión con ${url}`);
    }
    const text = await res.text();
    let data = null;
    if (text) {
      try { data = JSON.parse(text); } catch { data = null; }
    }
    if (!res.ok) {
      const msg = (data && (data.error || data.message)) || `HTTP ${res.status}`;
      throw new Error(msg);
    }
    return data || {};
  }

  // === Sparkline ==========================================================
  function sparkline(values, { width = 96, height = 28, tone = "info" } = {}) {
    const w = width, h = height, pad = 1.5;
    if (values.length < 2) {
      return `<svg class="spark spark--${tone}" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" aria-hidden="true"></svg>`;
    }
    let min = Infinity, max = -Infinity;
    for (const v of values) {
      if (v == null) continue;
      if (v < min) min = v;
      if (v > max) max = v;
    }
    if (!Number.isFinite(min) || !Number.isFinite(max)) {
      return `<svg class="spark spark--${tone}" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" aria-hidden="true"></svg>`;
    }
    if (min === max) { min -= 0.5; max += 0.5; }
    const dx = (w - pad * 2) / (values.length - 1);
    const points = [];
    for (let i = 0; i < values.length; i++) {
      const v = values[i];
      if (v == null) continue;
      const x = pad + i * dx;
      const y = pad + (1 - (v - min) / (max - min)) * (h - pad * 2);
      points.push(`${x.toFixed(1)},${y.toFixed(1)}`);
    }
    const linePath = `M${points.join(" L")}`;
    const last = points[points.length - 1].split(",");
    const areaPath = `${linePath} L${last[0]},${(h - pad).toFixed(1)} L${pad},${(h - pad).toFixed(1)} Z`;
    return `<svg class="spark spark--${tone}" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" preserveAspectRatio="none" aria-hidden="true"><path class="spark__area" d="${areaPath}"/><path class="spark__line" d="${linePath}"/></svg>`;
  }

  const toneFor = (value, thresholds) => {
    if (value == null) return "idle";
    if (value >= thresholds.error) return "error";
    if (value >= thresholds.warn) return "warn";
    return "success";
  };

  // === Big chart (multi-series) ===========================================
  // viewBox is 1000 × 280. Inset: 56px left (y axis), 14px right, 22px top,
  // 30px bottom (x axis).
  const CHART = { w: 1000, h: 280, padL: 56, padR: 14, padT: 22, padB: 30 };

  function chartInner() {
    return {
      x0: CHART.padL,
      y0: CHART.padT,
      x1: CHART.w - CHART.padR,
      y1: CHART.h - CHART.padB,
      w: CHART.w - CHART.padL - CHART.padR,
      h: CHART.h - CHART.padT - CHART.padB,
    };
  }

  function buildSeries(metric) {
    // metric: "cpu" | "ram" | "latency_ms"
    const out = new Map();
    for (const [id, h] of state.history.entries()) {
      const arr = h[metric] || [];
      const ts = h.ts || [];
      if (arr.length === 0) continue;
      // Backend returns metrics newest-first; flip to oldest→newest
      // so time on the X axis reads left-to-right.
      const values = arr.slice(-CHART_POINTS).slice().reverse();
      const labels = ts.slice(-CHART_POINTS).slice().reverse();
      out.set(id, { id, values, labels });
    }
    return out;
  }

  function renderChart() {
    const svg = $id("chart-svg");
    const empty = $id("chart-empty");
    const legend = $id("chart-legend");
    const meta = $id("chart-meta");
    if (!svg) return;

    const metric = state.chartMetric;
    const t = T[metric];
    const series = buildSeries(metric);

    if (series.size === 0) {
      svg.innerHTML = "";
      if (empty) empty.hidden = false;
      if (legend) legend.innerHTML = "";
      if (meta) meta.textContent = "Sin muestras para esta métrica.";
      return;
    }
    if (empty) empty.hidden = true;

    const inner = chartInner();
    // y axis: 0..ymax, top→bottom
    const yScale = (v) => inner.y0 + (1 - Math.min(v, t.ymax) / t.ymax) * inner.h;
    // x axis: oldest sample on the left
    const xCount = Math.max(...Array.from(series.values(), (s) => s.values.length));
    const xScale = (i, n) => {
      if (n <= 1) return inner.x0 + inner.w / 2;
      return inner.x0 + (i / (n - 1)) * inner.w;
    };

    const parts = [];
    // background grid
    const gridLines = 4;
    for (let i = 0; i <= gridLines; i++) {
      const y = inner.y0 + (i / gridLines) * inner.h;
      parts.push(`<line class="chart__grid" x1="${inner.x0}" y1="${y.toFixed(1)}" x2="${inner.x1}" y2="${y.toFixed(1)}"/>`);
    }

    // y axis labels
    for (let i = 0; i <= gridLines; i++) {
      const v = t.ymax - (i / gridLines) * t.ymax;
      const y = inner.y0 + (i / gridLines) * inner.h;
      parts.push(`<text class="chart__y-label" x="${inner.x0 - 8}" y="${(y + 3).toFixed(1)}" text-anchor="end">${v.toFixed(0)}${t.unit === "ms" ? "" : ""}</text>`);
    }

    // threshold lines
    const warnY = yScale(t.warn);
    const errY = yScale(t.error);
    parts.push(`<line class="chart__threshold chart__threshold--warn" x1="${inner.x0}" y1="${warnY.toFixed(1)}" x2="${inner.x1}" y2="${warnY.toFixed(1)}"/>`);
    parts.push(`<line class="chart__threshold chart__threshold--error" x1="${inner.x0}" y1="${errY.toFixed(1)}" x2="${inner.x1}" y2="${errY.toFixed(1)}"/>`);
    parts.push(`<text class="chart__threshold-label" x="${inner.x1 - 4}" y="${(warnY - 4).toFixed(1)}" text-anchor="end">umbral ${t.warn}${t.unit === "ms" ? " ms" : "%"}</text>`);

    // x axis time labels (4 ticks)
    const xTicks = 4;
    for (let i = 0; i <= xTicks; i++) {
      const x = inner.x0 + (i / xTicks) * inner.w;
      // walk the most recent labels of any series for a reference time
      const refLabels = Array.from(series.values())[0]?.labels || [];
      const refIdx = Math.min(refLabels.length - 1, Math.floor((i / xTicks) * (refLabels.length - 1)));
      const ref = refLabels[Math.max(0, refIdx)] || null;
      const lbl = ref ? formatTime(ref) : "";
      parts.push(`<text class="chart__x-label" x="${x.toFixed(1)}" y="${(CHART.h - 8).toFixed(1)}" text-anchor="middle">${lbl}</text>`);
    }

    // series
    for (const s of series.values()) {
      const color = seriesColor(s.id);
      const n = s.values.length;
      const pts = [];
      let lastX = inner.x0, lastY = inner.y0 + inner.h;
      for (let i = 0; i < n; i++) {
        const v = s.values[i];
        if (v == null) continue;
        const x = xScale(i, n);
        const y = yScale(v);
        pts.push(`${x.toFixed(1)},${y.toFixed(1)}`);
        lastX = x; lastY = y;
      }
      if (pts.length >= 2) {
        const linePath = `M${pts.join(" L")}`;
        const areaPath = `${linePath} L${lastX.toFixed(1)},${(inner.y0 + inner.h).toFixed(1)} L${inner.x0.toFixed(1)},${(inner.y0 + inner.h).toFixed(1)} Z`;
        parts.push(`<path class="chart__area" stroke="${color}" d="${areaPath}"/>`);
        parts.push(`<path class="chart__line" stroke="${color}" d="${linePath}"/>`);
      } else if (pts.length === 1) {
        const [xy] = pts;
        const [x, y] = xy.split(",");
        parts.push(`<circle class="chart__dot" cx="${x}" cy="${y}" r="3" fill="${color}"/>`);
      }
      // live dot at the latest sample
      const last = s.values[s.values.length - 1];
      if (last != null) {
        const x = xScale(n - 1, n);
        const y = yScale(last);
        parts.push(`<circle class="chart__live-dot" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="4.5" fill="${color}"/>`);
        parts.push(`<circle class="chart__live-pulse" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="4.5" fill="${color}"/>`);
      }
    }

    svg.innerHTML = parts.join("");

    // legend
    if (legend) {
      const items = Array.from(series.values()).map((s) => {
        const last = s.values[s.values.length - 1];
        const state = toneFor(last, t);
        return `<span class="legend-item" data-state="${state}">
          <span class="legend-swatch" style="--swatch:${seriesColor(s.id)}"></span>
          <span class="legend-id">${escapeHtml(s.id)}</span>
          <span class="legend-val">${last == null ? "—" : last.toFixed(metric === "latency_ms" ? 0 : 0) + (metric === "latency_ms" ? " ms" : "%")}</span>
        </span>`;
      });
      legend.innerHTML = items.join("");
    }

    if (meta) {
      const total = Array.from(series.values()).reduce((n, s) => n + s.values.length, 0);
      const ts = Array.from(series.values())[0]?.labels || [];
      const oldest = ts[0];
      const newest = ts[ts.length - 1];
      const span = oldest && newest ? ` · ${formatTime(oldest)} → ${formatTime(newest)}` : "";
      meta.textContent = `${series.size} serie${series.size === 1 ? "" : "s"} · ${total} muestra${total === 1 ? "" : "s"}${span}`;
    }
  }

  // === Node render ========================================================
  function pushHistory(metric) {
    const id = metric.node_id;
    if (!state.history.has(id)) {
      state.history.set(id, { cpu: [], ram: [], latency_ms: [], ts: [] });
    }
    const h = state.history.get(id);
    if (metric.cpu != null) h.cpu.push(metric.cpu);
    if (metric.ram != null) h.ram.push(metric.ram);
    if (metric.latency_ms != null) h.latency_ms.push(metric.latency_ms);
    if (metric.timestamp) h.ts.push(metric.timestamp);
    for (const k of ["cpu", "ram", "latency_ms", "ts"]) {
      while (h[k].length > MAX_HISTORY) h[k].shift();
    }
  }

  function renderNodes() {
    const grid = $id("node-grid");
    const empty = $id("nodes-empty");
    const hint = $id("nodes-hint");
    if (!grid) return;

    const ids = Array.from(state.nodes.keys()).sort();
    if (hint) {
      hint.textContent = ids.length === 0
        ? "Esperando datos…"
        : `${ids.length} nodo${ids.length === 1 ? "" : "s"} detectado${ids.length === 1 ? "" : "s"}`;
    }

    if (ids.length === 0) {
      grid.replaceChildren();
      if (empty) empty.hidden = false;
      return;
    }
    if (empty) empty.hidden = true;

    const tNow = Date.now();
    const cards = ids.map((id) => {
      const node = state.nodes.get(id) || {};
      const h = state.history.get(id) || { cpu: [], ram: [], latency_ms: [], ts: [] };
      const cpu = lastOf(h.cpu);
      const ram = lastOf(h.ram);
      const lat = lastOf(h.latency_ms);
      const lastTs = lastOf(h.ts);
      const cpuTone = toneFor(cpu, T.cpu);
      const ramTone = toneFor(ram, T.ram);
      const latTone = toneFor(lat, T.latency_ms);

      const svc = (node.service_web || "").toString().toLowerCase();
      const svcState = svc === "falla" || svc === "fail" || svc === "down" ? "error" : "ok";
      const svcLabel = svc === "falla" || svc === "fail" ? "falla" : svc ? svc : "—";

      const eventLog = node.event_log || "—";
      const fmtPct = (v) => (v == null ? "—" : `${v.toFixed(0)}%`);
      const fmtMs = (v) => (v == null ? "—" : `${Math.round(v)} ms`);

      // staleness
      const last = lastTs ? new Date(lastTs).getTime() : null;
      const staleMs = last ? tNow - last : Infinity;
      const isStale = staleMs > 30_000;
      const alert = (cpuTone === "error" || ramTone === "error" || latTone === "error" || svcState === "error");

      const color = seriesColor(id);
      return `
<article class="node ${alert ? "node--alert" : ""} ${isStale ? "node--stale" : ""}" data-node="${escapeHtml(id)}" style="--node-color:${color}">
  <header class="node__head">
    <div class="node__id-block">
      <span class="node__id">${escapeHtml(id)}</span>
      <span class="node__sub">${formatAgo(lastTs)}${isStale ? " · sin señal" : ""}</span>
    </div>
    <span class="pill pill--ghost" data-state="${svcState}">
      <span class="pill__dot" aria-hidden="true"></span>
      <span class="pill__label">web · ${escapeHtml(svcLabel)}</span>
    </span>
  </header>
  <div class="node__metrics">
    <div class="metric">
      <div class="metric__row">
        <span class="metric__label">CPU</span>
        <span class="metric__value" data-state="${cpuTone}">${fmtPct(cpu)}</span>
      </div>
      ${sparkline(h.cpu.slice(-SPARK_POINTS), { width: 120, height: 32, tone: cpuTone })}
    </div>
    <div class="metric">
      <div class="metric__row">
        <span class="metric__label">RAM</span>
        <span class="metric__value" data-state="${ramTone}">${fmtPct(ram)}</span>
      </div>
      ${sparkline(h.ram.slice(-SPARK_POINTS), { width: 120, height: 32, tone: ramTone })}
    </div>
    <div class="metric">
      <div class="metric__row">
        <span class="metric__label">Latencia</span>
        <span class="metric__value" data-state="${latTone}">${fmtMs(lat)}</span>
      </div>
      ${sparkline(h.latency_ms.slice(-SPARK_POINTS), { width: 120, height: 32, tone: latTone })}
    </div>
  </div>
  <footer class="node__foot">
    <span>Última métrica: <strong>${formatAgo(lastTs)}</strong></span>
    <span>Evento: <code>${escapeHtml(eventLog)}</code></span>
  </footer>
</article>`;
    });
    grid.innerHTML = cards.join("");
  }

  function lastOf(arr) {
    if (!arr || arr.length === 0) return null;
    return arr[arr.length - 1] ?? null;
  }

  // === Events render ======================================================
  function renderEvents() {
    const list = $id("event-list");
    const empty = $id("events-empty");
    const hint = $id("events-hint");
    if (!list) return;

    if (hint) {
      const cmds = state.events_total.commands || 0;
      const acks = state.events_total.acks || 0;
      hint.textContent = cmds + acks > 0
        ? `${cmds} comandos · ${acks} acks`
        : "Sin actividad";
    }

    if (!Array.isArray(state.events) || state.events.length === 0) {
      list.replaceChildren();
      if (empty) empty.hidden = false;
      return;
    }
    if (empty) empty.hidden = true;
    const items = state.events.slice(0, MAX_EVENTS).map((e) => {
      const type = (pick(e, ["type", "kind", "event_type"]) || "event").toString().toLowerCase();
      const node = pick(e, ["node_id", "node", "from"]) || "—";
      const ts = pick(e, ["timestamp", "ts", "time"]) || null;
      const action = pick(e, ["action", "command", "cmd"]);
      const reason = pick(e, ["reason"]);
      const status = pick(e, ["status", "result"]);
      const detail = action
        ? `<code>${escapeHtml(action)}</code>${reason ? ` <span class="muted">(${escapeHtml(reason)})</span>` : ""}`
        : (status ? `<code>${escapeHtml(status)}</code>` : "—");
      return `<li class="event" data-type="${escapeHtml(type)}">
  <span class="event__type event__type--${escapeHtml(type)}">${escapeHtml(type)}</span>
  <span class="event__node">${escapeHtml(node)}</span>
  <span class="event__detail">${detail}</span>
  <span class="event__time">${formatTime(ts)}</span>
</li>`;
    });
    list.innerHTML = items.join("");
  }

  // === Logs render ========================================================
  function renderLogs(logs) {
    const tail = $id("log-tail");
    const empty = $id("logs-empty");
    if (!tail) return;
    if (!Array.isArray(logs) || logs.length === 0) {
      tail.replaceChildren();
      if (empty) empty.hidden = false;
      return;
    }
    if (empty) empty.hidden = true;
    const lines = logs.slice(0, MAX_LOGS).map((l) => {
      const raw = pick(l, ["line", "message", "msg", "text"]) || JSON.stringify(l);
      const text = String(raw);
      let level = "info";
      const m = text.match(/^\s*(\d{2}:\d{2}:\d{2})\s+\[?(\w+)\]?/);
      if (m) level = m[2].toLowerCase();
      else if (/\b(ERROR|FATAL)\b/.test(text)) level = "error";
      else if (/\b(WARN|WARNING)\b/.test(text)) level = "warn";
      const ts = m ? m[1] : "";
      return `<span class="log__line" data-level="${escapeHtml(level)}"><span class="log__time">${escapeHtml(ts)}</span> <span class="log__level">${escapeHtml(level)}</span> ${escapeHtml(text)}</span>`;
    });
    tail.innerHTML = lines.join("\n");
  }

  // === Overview / stats strip =============================================
  function renderStats(status) {
    const setStat = (idVal, idHint, val, hint) => {
      const v = $id(idVal); const h = $id(idHint);
      if (v) v.textContent = val;
      if (h) h.textContent = hint;
    };
    if (!status || typeof status !== "object") {
      setStat("stat-metrics", "stat-metrics-hint", "—", "sin datos");
      setStat("stat-commands", "stat-commands-hint", "—", "sin datos");
      setStat("stat-acks", "stat-acks-hint", "—", "sin datos");
      setStat("stat-nodes", "stat-nodes-hint", "—", "sin datos");
      setStat("stat-anomaly", "stat-anomaly-hint", "—", "sin datos");
      setStat("stat-artifacts", "stat-artifacts-hint", "—", "0");
      return;
    }
    const db = status.db_stats || status.database || {};
    setStat("stat-metrics", "stat-metrics-hint", String(db.metrics ?? 0), "totales recibidas");
    setStat("stat-commands", "stat-commands-hint", String(db.commands ?? 0), "emitidos");
    setStat("stat-acks", "stat-acks-hint", String(db.acks ?? 0), "recibidos");

    const nodesActive = pick(status, ["nodes_active", "active_nodes", "clients", "connected"]);
    setStat("stat-nodes", "stat-nodes-hint",
      nodesActive !== undefined ? String(nodesActive) : String(state.nodes.size),
      nodesActive !== undefined ? "vistos en los últimos ciclos" : "detectados en esta sesión"
    );

    const lastAnomaly = pick(status, ["last_anomaly", "last_anomaly_at", "anomaly_last"]);
    if (lastAnomaly) {
      setStat("stat-anomaly", "stat-anomaly-hint", formatTime(lastAnomaly), "registrada");
    } else {
      const alertNow = Array.from(state.nodes.values()).some((n) => (n.service_web || "").toString().toLowerCase() === "falla");
      if (alertNow) setStat("stat-anomaly", "stat-anomaly-hint", "activa", "servicio en falla");
      else setStat("stat-anomaly", "stat-anomaly-hint", "—", "sin anomalías registradas");
    }

    setStat("stat-artifacts", "stat-artifacts-hint", String(state.artifactsCount), "en artifacts/demo/");
  }

  // === Mission + clock ====================================================
  function renderMission(status) {
    const srv = (status && status.server) || {};
    const host = srv.host || "127.0.0.1";
    const port = srv.port !== undefined ? srv.port : "?";
    $id("mission-server").textContent = `${host}:${port}`;
  }

  function tickClock() {
    const d = new Date();
    const t = d.toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    const el = $id("mission-clock");
    if (el) el.textContent = t;
    // scenario elapsed
    if (state.scenario.name && state.scenario.startedAt) {
      const e = $id("scenario-elapsed");
      if (e) e.textContent = `· ${formatDuration(Date.now() - state.scenario.startedAt)}`;
    }
  }

  // === Status helpers =====================================================
  function setGlobalPill(state_, label) {
    const pill = $id("global-pill");
    if (!pill) return;
    pill.dataset.state = state_;
    const t = pill.querySelector(".pill__label");
    if (t) t.textContent = label;
  }
  function setLastRefreshStamp() {
    const el = $id("last-refresh");
    if (!el) return;
    if (!state.lastRefresh) { el.textContent = "—"; return; }
    el.textContent = formatTime(state.lastRefresh.toISOString());
  }

  // === Pollers ============================================================
  async function pollStatus() {
    try {
      const data = await fetchJson(ENDPOINTS.status.path);
      renderMission(data);
      renderStats(data);
      setGlobalPill("ok", "En línea");
      return true;
    } catch {
      setGlobalPill("error", "Sin conexión");
      return false;
    }
  }

  async function pollMetrics() {
    try {
      const data = await fetchJson(ENDPOINTS.metrics.path);
      ingestMetrics(data);
    } catch { /* sin muestras nuevas */ }
    renderNodes();
    renderChart();
    return true;
  }

  function ingestMetrics(payload) {
    if (!payload) return;
    let list = null;
    if (Array.isArray(payload.metrics)) list = payload.metrics;
    else if (Array.isArray(payload.data)) list = payload.data;
    else if (Array.isArray(payload.items)) list = payload.items;
    else if (Array.isArray(payload)) list = payload;
    else if (payload.nodes && typeof payload.nodes === "object") list = Object.values(payload.nodes);
    if (!Array.isArray(list)) return;
    for (const raw of list) {
      const m = normalizeMetric(raw);
      if (!m) continue;
      state.nodes.set(m.node_id, { ...state.nodes.get(m.node_id), ...m });
      pushHistory(m);
    }
  }

  async function pollEvents() {
    try {
      const data = await fetchJson(ENDPOINTS.events.path);
      const list = pick(data, ["events", "items", "data"]) || [];
      state.events = Array.isArray(list) ? list : [];
      state.events_total = {
        commands: data.commands_total ?? 0,
        acks: data.acks_total ?? 0,
      };
    } catch {
      state.events = [];
      state.events_total = { commands: 0, acks: 0 };
    }
    renderEvents();
  }

  async function pollLogs() {
    try {
      const data = await fetchJson(ENDPOINTS.logs.path);
      const list = pick(data, ["logs", "items", "data"]) || [];
      renderLogs(Array.isArray(list) ? list : []);
    } catch { renderLogs([]); }
  }

  async function pollArtifacts() {
    try {
      const data = await fetchJson(ENDPOINTS.artifacts.path);
      const n = pick(data, ["artifact_count", "count"]) || 0;
      state.artifactsCount = Number.isFinite(Number(n)) ? Number(n) : 0;
      $id("stat-artifacts").textContent = String(state.artifactsCount);
    } catch { /* ignore */ }
  }

  let inFlight = false;
  async function pollAll() {
    if (inFlight) return;
    inFlight = true;
    try {
      await Promise.all([pollStatus(), pollMetrics(), pollEvents(), pollLogs(), pollArtifacts()]);
      state.lastRefresh = new Date();
      setLastRefreshStamp();
    } finally { inFlight = false; }
  }

  // === Demo controls ======================================================
  function setScenarioState(name, startedAt) {
    state.scenario.name = name;
    state.scenario.startedAt = startedAt || null;
    const dot = $id("scenario-dot");
    const label = $id("scenario-status-label");
    const elapsed = $id("scenario-elapsed");
    if (name) {
      dot.dataset.state = "running";
      label.textContent = `Ejecutando: ${name}`;
      elapsed.textContent = startedAt ? `· ${formatDuration(Date.now() - startedAt)}` : "";
    } else {
      dot.dataset.state = "idle";
      label.textContent = "Sin escenario activo";
      elapsed.textContent = "";
    }
  }

  function setFeedback(text, tone = "info") {
    const el = $id("scenario-feedback");
    if (!el) return;
    el.dataset.tone = tone;
    el.textContent = text;
    if (state.feedbackTimer) clearTimeout(state.feedbackTimer);
    if (text) {
      state.feedbackTimer = setTimeout(() => {
        el.textContent = "";
        delete el.dataset.tone;
      }, 8000);
    }
  }

  function setButtonsDisabled(disabled) {
    $$(".scenario button, [data-action]").forEach((b) => {
      b.disabled = disabled;
      b.dataset.busy = disabled ? "true" : "false";
    });
  }

  async function dispatchAction(button) {
    if (!button || button.disabled) return;
    const action = button.dataset.action;
    if (!action) return;
    const meta = ACTIONS[action];
    if (!meta) return;

    setButtonsDisabled(true);
    setFeedback(`Ejecutando: ${action}…`, "info");
    if (action === "scenario") {
      setScenarioState(button.dataset.scenario, Date.now());
    }

    const body = action === "scenario"
      ? { scenario: button.dataset.scenario, node_id: "node-01", interval: 3.0 }
      : null;

    try {
      const result = await postJson(meta.path, body);
      const ok = result && (result.success !== false);
      const tone = ok ? "success" : "warn";
      const label = result && result.label ? result.label : action;
      const detail = result && result.details && result.details.message
        ? result.details.message
        : (ok ? "Acción completada" : "Acción finalizada con observaciones");
      setFeedback(`${label}: ${detail}`, tone);
      // refresh immediately so the chart shows new data
      pollAll();
    } catch (err) {
      setFeedback(`Falló ${action}: ${err.message || err}`, "error");
    } finally {
      setButtonsDisabled(false);
      if (action === "scenario") {
        // scenario typically ends after ~5s in the script; mark as done in 8s
        const name = state.scenario.name;
        setTimeout(() => {
          if (state.scenario.name === name) setScenarioState(null);
        }, 9000);
      }
    }
  }

  // === Bindings ===========================================================
  function bind() {
    const refresh = $id("refresh-btn") || document.querySelector("[data-action='refresh']");
    // (refresh removed from header in this design; manual click is bound via demo controls)

    $$("[data-action]").forEach((b) => {
      b.addEventListener("click", (e) => {
        e.preventDefault();
        dispatchAction(b);
      });
    });

    $$(".seg[data-metric]").forEach((b) => {
      b.addEventListener("click", () => {
        state.chartMetric = b.dataset.metric;
        $$(".seg").forEach((s) => s.setAttribute("aria-selected", s === b ? "true" : "false"));
        $id("chart-frame").dataset.metric = state.chartMetric;
        renderChart();
      });
    });

    // Refresh relative timestamps + scenario elapsed every 1s
    setInterval(() => {
      tickClock();
      if (state.nodes.size > 0) renderNodes();
    }, 1000);
  }

  // === Boot ===============================================================
  document.addEventListener("DOMContentLoaded", () => {
    bind();
    tickClock();
    setInterval(tickClock, 1000);
    pollAll();
    setInterval(pollAll, POLL_MS);
  });
})();
