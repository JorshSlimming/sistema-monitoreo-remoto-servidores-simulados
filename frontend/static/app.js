/* Monitor local · sistema de monitoreo remoto
 * Sala de control demo:
 *   - fuente de verdad: /api/state
 *   - poll cada 1 s, protección contra respuestas obsoletas
 *   - reemplazo completo de estado en cada poll (sin acumulación)
 * Stdlib + DOM. Sin librerías de charting.
 */
(() => {
  "use strict";

  // === Config =============================================================
  const STATE_PATH = "/api/state";
  // POST endpoints.
  const ACTIONS = {
    scenario: { method: "POST", path: "/api/scenario" },
  };

  const POLL_MS = 1000;
  const SPARK_POINTS = 32;
  const CHART_POINTS = 40;
  const MAX_EVENTS = 50;
  const MAX_LOGS = 80;

  // Staleness thresholds (seconds)
  const STALE = { online: 5, stale: 15 };

  // Thresholds (%, ms) → used to color bars, sparklines, and chart series.
  const T = {
    cpu: { warn: 60, error: 80, ymax: 100, unit: "%" },
    ram: { warn: 70, error: 85, ymax: 100, unit: "%" },
    latency_ms: { warn: 100, error: 200, ymax: 400, unit: "ms" },
  };

  // Demo role map for the 7-node multi-node scenario. Each node has a
  // distinct anomaly role that survives real-time updates because the
  // mapping is fixed in the frontend (the backend just spawns the
  // clients; it doesn't tag their anomaly type in /api/state).
  const DEMO_ROLES = {
    "node-01": { label: "operación normal", short: "normal", tone: "ok" },
    "node-02": { label: "cpu alta",         short: "cpu alta", tone: "warn" },
    "node-03": { label: "latencia alta",    short: "latencia alta", tone: "warn" },
    "node-04": { label: "ram alta",         short: "ram alta", tone: "warn" },
    "node-05": { label: "servicio caído",   short: "servicio caído", tone: "error" },
    "node-06": { label: "evento fallido",   short: "evento fallido", tone: "error" },
    "node-07": { label: "caos / aleatorio", short: "caos / aleatorio", tone: "error" },
  };

  // Color tokens per node series (CSS variable names).
  const SERIES = [
    { name: "node-01", color: "var(--info)" },
    { name: "node-02", color: "var(--success)" },
    { name: "node-03", color: "var(--warn)" },
    { name: "node-04", color: "var(--accent)" },
    { name: "node-05", color: "var(--error)" },
    { name: "node-06", color: "var(--idle)" },
    { name: "node-07", color: "var(--text-muted)" },
  ];
  const seriesColor = (id) => {
    let h = 0;
    for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
    const slot = SERIES[h % SERIES.length];
    return slot.color;
  };

  // === State ==============================================================
  const state = {
    nodes: new Map(),       // node_id → node data from backend
    history: new Map(),     // node_id → { cpu:[], ram:[], latency_ms:[], ts:[] }
    events: [],
    logs: [],
    server: {},             // server info from /api/state.server
    scenario: { name: null, startedAt: null, status: "idle" },
    chartMetric: "cpu",
    feedbackTimer: null,
    reqSeq: 0,              // monotonic request sequence → stale-response guard
    hadAnomaly: false,      // causal-chain tracker: was there ever an anomaly?
    recoveryAt: null,       // causal-chain tracker: when the anomaly was last cleared
    autoStartAttempted: false, // guard: only fire the multi-node auto-start once per page session
    autoStartInFlight: false,  // guard: do not stack concurrent auto-start POSTs
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

  const numberOr = (v, fallback) => {
    const n = Number(v);
    return Number.isFinite(n) ? n : fallback;
  };

  const lastOf = (arr) => {
    if (!arr || arr.length === 0) return null;
    return arr[arr.length - 1] ?? null;
  };

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

  // Spanish labels for event types (UI-side only; backend types unchanged).
  const EVENT_LABELS = {
    anomaly: "Anomalía",
    alert: "Anomalía",
    warn: "Aviso",
    warning: "Aviso",
    command: "Comando",
    ack: "ACK",
    error: "Falla",
    fail: "Falla",
    failed: "Falla",
    metric: "Métrica",
    info: "Info",
    event: "Evento",
  };

  // Spanish verb phrases to make each event row read like a sentence.
  const EVENT_VERBS = {
    anomaly: "Detectada",
    alert: "Detectada",
    command: "Servidor envía",
    ack: "Nodo confirma",
    error: "Falla",
    fail: "Falla",
    failed: "Falla",
    metric: "Métrica recibida",
    info: "Info",
  };

  // === Big chart (multi-series) ===========================================
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
      // Backend returns metrics chronological; no reverse needed.
      const values = arr.slice(-CHART_POINTS);
      const labels = ts.slice(-CHART_POINTS);
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
    const yScale = (v) => inner.y0 + (1 - Math.min(v, t.ymax) / t.ymax) * inner.h;
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
      parts.push(`<text class="chart__y-label" x="${inner.x0 - 8}" y="${(y + 3).toFixed(1)}" text-anchor="end">${v.toFixed(0)}</text>`);
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
        const st = toneFor(last, t);
        return `<span class="legend-item" data-state="${st}">
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

  // === Node helpers =======================================================
  function nodeStaleness(node) {
    let s = node.staleness_seconds;
    if (s == null && node.last_seen) {
      s = Math.max(0, Math.floor((Date.now() - new Date(node.last_seen).getTime()) / 1000));
    }
    if (s == null || s > STALE.stale) {
      return { label: "sin señal", pill: "error", seconds: s, hint: "más de 15 s sin métricas" };
    }
    if (s > STALE.online) {
      return { label: "sin actualización reciente", pill: "warn", seconds: s, hint: "5–15 s sin métricas" };
    }
    return { label: "en línea", pill: "ok", seconds: s, hint: "métricas al día" };
  }

  // Short Spanish phrase describing the node's high-level state for the footer.
  function nodeStateSummary(node, isAlert, staleness) {
    if (staleness.pill === "error") return "Sin señal del nodo";
    if (node.service_web && /falla|fail|down/i.test(String(node.service_web))) {
      return "Servicio web caído";
    }
    if (node.anomaly_active) return "Anomalía activa";
    if (node.mitigation_active) return "Mitigación en curso";
    if (isAlert) return "Umbral cruzado";
    return "Operación normal";
  }

  function nodeAlert(node) {
    if (!node) return false;
    const cpu = numberOr(node.cpu, null);
    const ram = numberOr(node.ram, null);
    const lat = numberOr(node.latency_ms, null);
    const svc = (node.service_web || "").toString().toLowerCase();
    return (
      toneFor(cpu, T.cpu) === "error" ||
      toneFor(ram, T.ram) === "error" ||
      toneFor(lat, T.latency_ms) === "error" ||
      svc === "falla" || svc === "fail" || svc === "down"
    );
  }

  // === Node render ========================================================
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

      const staleness = nodeStaleness(node);
      const isAlert = nodeAlert(node);

      const color = seriesColor(id);
      const role = DEMO_ROLES[id] || null;

      // Badges
      const badges = [];
      if (node.anomaly_active) {
        badges.push(`<span class="badge badge--anomaly" title="El servidor detectó una métrica fuera de umbral">anomalía activa</span>`);
      }
      if (node.mitigation_active) {
        const mt = node.mitigation_type || "activa";
        badges.push(`<span class="badge badge--mitigation" title="Acción correctiva en ejecución sobre el nodo">mitigación: ${escapeHtml(mt)}</span>`);
      }
      if (node.last_command) {
        badges.push(`<span class="badge badge--command" title="Último comando enviado por el servidor">comando: ${escapeHtml(node.last_command)}</span>`);
      }

      // Summary lines for the footer
      const stateSummary = nodeStateSummary(node, isAlert, staleness);

      // Pick the most recent "change" to highlight as Último cambio.
      const lastChange = node.last_change || null;
      const lastChangeText = lastChange && lastChange.label
        ? `${escapeHtml(lastChange.label)}${lastChange.at ? ` · ${formatAgo(lastChange.at)}` : ""}`
        : null;

      const roleHtml = role
        ? `<div class="node__role" data-role="${role.tone}" title="Rol del demo multi-nodo"><span class="node__role-dot" aria-hidden="true"></span><span>${escapeHtml(role.label)}</span></div>`
        : "";

      const demoClass = role ? "node--demo" : "";
      const roleAttr = role ? ` data-role="${role.tone}"` : "";

      return `
<article class="node ${isAlert ? "node--alert" : ""} ${staleness.pill === "error" ? "node--stale" : ""} ${demoClass}" data-node="${escapeHtml(id)}"${roleAttr} style="--node-color:${color}">
  <header class="node__head">
    <div class="node__id-block">
      <span class="node__dot" aria-hidden="true"></span>
      <span class="node__id">${escapeHtml(id)}</span>
    </div>
    <div class="node__pills">
      <span class="pill pill--mini pill--ghost" data-state="${svcState}" title="Estado del servicio web del nodo">
        <span class="pill__dot" aria-hidden="true"></span>
        <span class="pill__label">web · ${escapeHtml(svcLabel)}</span>
      </span>
      <span class="pill pill--mini" data-state="${staleness.pill}" title="${escapeHtml(staleness.hint || staleness.label)}">
        <span class="pill__dot" aria-hidden="true"></span>
        <span class="pill__label">${staleness.label}</span>
      </span>
    </div>
  </header>
  ${roleHtml}
  <div class="node__metrics">
    <div class="metric">
      <div class="metric__row">
        <span class="metric__label">CPU</span>
        <span class="metric__value" data-state="${cpuTone}">${cpu == null ? "—" : `${cpu.toFixed(0)}%`}</span>
      </div>
      ${sparkline(h.cpu.slice(-SPARK_POINTS), { width: 120, height: 32, tone: cpuTone })}
    </div>
    <div class="metric">
      <div class="metric__row">
        <span class="metric__label">RAM</span>
        <span class="metric__value" data-state="${ramTone}">${ram == null ? "—" : `${ram.toFixed(0)}%`}</span>
      </div>
      ${sparkline(h.ram.slice(-SPARK_POINTS), { width: 120, height: 32, tone: ramTone })}
    </div>
    <div class="metric">
      <div class="metric__row">
        <span class="metric__label">Latencia</span>
        <span class="metric__value" data-state="${latTone}">${lat == null ? "—" : `${Math.round(lat)} ms`}</span>
      </div>
      ${sparkline(h.latency_ms.slice(-SPARK_POINTS), { width: 120, height: 32, tone: latTone })}
    </div>
  </div>
  ${badges.length > 0 ? `<div class="node__badges">${badges.join("")}</div>` : ""}
  <footer class="node__foot">
    <div class="node__foot-line">
      <span class="node__foot-label">Estado</span>
      <span class="node__foot-value">${escapeHtml(stateSummary)}</span>
    </div>
    <div class="node__foot-line">
      <span class="node__foot-label">Última métrica</span>
      <span class="node__foot-value">${formatAgo(lastTs)}</span>
    </div>
    ${lastChangeText ? `
    <div class="node__foot-line node__foot-line--change">
      <span class="node__foot-label">Último cambio</span>
      <span class="node__foot-value">${lastChangeText}</span>
    </div>` : ""}
  </footer>
</article>`;
    });
    grid.innerHTML = cards.join("");
  }

  // === Events render ======================================================
  function renderEvents() {
    const list = $id("event-list");
    const empty = $id("events-empty");
    const hint = $id("events-hint");
    if (!list) return;

    if (hint) {
      const cmds = state.server.commands_total ?? 0;
      const acks = state.server.acks_total ?? 0;
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
      const type = (e.type || "event").toString().toLowerCase();
      const node = e.node_id || "—";
      const ts = e.timestamp || null;
      const action = e.action || e.command || null;
      const reason = e.reason || null;
      const status = e.status || null;
      const label = EVENT_LABELS[type] || type;
      const verb = EVENT_VERBS[type] || label.toLowerCase();

      // Build a single Spanish sentence for the detail column.
      let detailHtml = "";
      if (action && reason) {
        detailHtml = `${verb} <code>${escapeHtml(action)}</code> <span class="muted">(${escapeHtml(reason)})</span>`;
      } else if (action) {
        detailHtml = `${verb} <code>${escapeHtml(action)}</code>`;
      } else if (status) {
        detailHtml = `${verb} <code>${escapeHtml(status)}</code>`;
      } else if (reason) {
        detailHtml = `${verb} <code>${escapeHtml(reason)}</code>`;
      } else {
        detailHtml = verb;
      }

      return `<li class="event" data-type="${escapeHtml(type)}">
  <span class="event__type event__type--${escapeHtml(type)}">${escapeHtml(label)}</span>
  <span class="event__node">${escapeHtml(node)}</span>
  <span class="event__detail">${detailHtml}</span>
  <span class="event__time">${formatTime(ts)}</span>
</li>`;
    });
    list.innerHTML = items.join("");
  }

  // === Causal chain ("Cómo leer este panel") ==============================
  // Step states: "pending" (never seen) | "active" (just happened, <5s) | "done" (seen).
  const FLOW_STEPS = ["detection", "command", "ack", "recovery"];
  // Map backend event type → which step it advances.
  const FLOW_TRIGGERS = {
    detection: new Set(["anomaly", "alert"]),
    command: new Set(["command"]),
    ack: new Set(["ack"]),
  };

  function latestEventOf(types) {
    if (!Array.isArray(state.events)) return null;
    for (const e of state.events) {
      const t = (e.type || "").toString().toLowerCase();
      if (types.has(t)) return e;
    }
    return null;
  }

  function renderHowto() {
    const list = $id("howto-chain");
    if (!list) return;

    const now = Date.now();
    const FIVE_S = 5_000;
    const stepState = {};
    const stepAt = {};

    // Walk the events list and mark each step with the most recent trigger.
    for (const step of FLOW_STEPS) {
      const triggers = FLOW_TRIGGERS[step];
      if (triggers) {
        const ev = latestEventOf(triggers);
        if (ev && ev.timestamp) {
          const t = new Date(ev.timestamp).getTime();
          if (Number.isFinite(t)) {
            stepAt[step] = t;
            stepState[step] = now - t <= FIVE_S ? "active" : "done";
            continue;
          }
        }
      }
      stepState[step] = "pending";
    }

    // Recovery: any node had anomaly_active previously, and no node has it now.
    // We track previous state to detect the cleared transition.
    if (state.hadAnomaly && !Array.from(state.nodes.values()).some((n) => n.anomaly_active)) {
      stepState.recovery = state.recoveryAt ? "done" : "active";
      if (!state.recoveryAt) state.recoveryAt = now;
      stepAt.recovery = state.recoveryAt;
    } else if (Array.from(state.nodes.values()).some((n) => n.anomaly_active)) {
      state.hadAnomaly = true;
    }

    const stepLabels = {
      pending: "en espera",
      active: "en curso",
      done: "visto",
    };

    for (const step of FLOW_STEPS) {
      const li = list.querySelector(`[data-step="${step}"]`);
      if (!li) continue;
      const stateEl = li.querySelector(".howto__state");
      if (!stateEl) continue;
      const stateName = stepState[step];
      stateEl.dataset.state = stateName;
      li.dataset.state = stateName;
      const labelEl = stateEl.querySelector(".howto__state-label");
      if (labelEl) {
        let lbl = stepLabels[stateName];
        if (stateName === "active" && stepAt[step]) lbl = `en curso · ${formatAgo(new Date(stepAt[step]).toISOString())}`;
        else if (stateName === "done" && stepAt[step]) lbl = `visto · ${formatAgo(new Date(stepAt[step]).toISOString())}`;
        labelEl.textContent = lbl;
      }
    }

    // Top-right summary sentence: "Visto: 1 → 2 → 3" or "Sin actividad".
    const summary = $id("howto-summary");
    if (summary) {
      const seen = FLOW_STEPS.filter((s) => stepState[s] === "done" || stepState[s] === "active");
      if (seen.length === 0) {
        summary.textContent = "Esperando primera anomalía…";
      } else {
        const order = FLOW_STEPS.map((s, i) => {
          const seen_ = stepState[s] === "done" || stepState[s] === "active";
          return seen_ ? String(i + 1) : "·";
        });
        summary.textContent = `Flujo observado: ${order.join(" → ")}`;
      }
    }
  }

  // === Logs render ========================================================
  function renderLogs() {
    const tail = $id("log-tail");
    const empty = $id("logs-empty");
    if (!tail) return;
    if (!Array.isArray(state.logs) || state.logs.length === 0) {
      tail.replaceChildren();
      if (empty) empty.hidden = false;
      return;
    }
    if (empty) empty.hidden = true;
    const lines = state.logs.slice(0, MAX_LOGS).map((l) => {
      const raw = l.line ?? l.message ?? l.msg ?? l.text ?? JSON.stringify(l);
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
  function renderStats() {
    const setKpi = (idVal, idHint, val, hint) => {
      const v = $id(idVal); const h = $id(idHint);
      if (v) v.textContent = val;
      if (h) h.textContent = hint;
    };

    const srv = state.server;
    const hasServer = srv && typeof srv === "object" && Object.keys(srv).length > 0;

    if (!hasServer) {
      setKpi("kpi-metrics", "kpi-metrics-hint", "—", "sin datos");
      setKpi("kpi-commands", "kpi-commands-hint", "—", "sin datos");
      setKpi("kpi-acks", "kpi-acks-hint", "—", "sin datos");
      setKpi("kpi-nodes", "kpi-nodes-hint", "—", "sin datos");
      setKpi("kpi-anomaly", "kpi-anomaly-hint", "—", "sin anomalías activas");
      setKpi("kpi-scenario", "kpi-scenario-hint", "—", "sin escenario activo");
      return;
    }

    setKpi("kpi-metrics", "kpi-metrics-hint", String(srv.metrics_total ?? 0), "totales recibidas");
    setKpi("kpi-commands", "kpi-commands-hint", String(srv.commands_total ?? 0), "emitidos");
    setKpi("kpi-acks", "kpi-acks-hint", String(srv.acks_total ?? 0), "recibidos");

    const nodeCount = Array.isArray(srv.active_nodes) ? srv.active_nodes.length : state.nodes.size;
    setKpi("kpi-nodes", "kpi-nodes-hint", String(nodeCount), "últimos ciclos");

    // Anomaly: any node has anomaly_active
    const anyAnomaly = Array.from(state.nodes.values()).some((n) => n.anomaly_active);
    const anomalyCard = $id("kpi-anomaly-card");
    const anomalyValue = $id("kpi-anomaly");
    if (anyAnomaly) {
      if (anomalyValue) anomalyValue.dataset.tone = "warn";
      if (anomalyCard) anomalyCard.dataset.tone = "warn";
      setKpi("kpi-anomaly", "kpi-anomaly-hint", "activa", "anomalía detectada");
    } else {
      if (anomalyValue) anomalyValue.dataset.tone = "idle";
      if (anomalyCard) anomalyCard.dataset.tone = "idle";
      setKpi("kpi-anomaly", "kpi-anomaly-hint", "—", "sin anomalías activas");
    }

    // Scenario: from local state (the server doesn't echo this in /api/state)
    if (state.scenario.name) {
      const elapsed = state.scenario.startedAt
        ? ` · ${formatDuration(Date.now() - state.scenario.startedAt)}`
        : "";
      setKpi("kpi-scenario", "kpi-scenario-hint", `${state.scenario.name}${elapsed}`, "en ejecución");
    } else {
      setKpi("kpi-scenario", "kpi-scenario-hint", "—", "sin escenario activo");
    }
  }

  // === Mission + clock ====================================================
  function renderMission() {
    const srv = state.server || {};
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
    el.textContent = formatTime((new Date()).toISOString());
  }

  // === /api/state poller ==================================================
  let inFlight = false;

  async function pollState() {
    if (inFlight) return;
    inFlight = true;

    const seq = ++state.reqSeq;
    try {
      let res;
      try {
        res = await fetch(STATE_PATH, { method: "GET", headers: { Accept: "application/json" } });
      } catch {
        setGlobalPill("error", "Sin conexión");
        return;
      }
      if (!res.ok) {
        setGlobalPill("error", `HTTP ${res.status}`);
        return;
      }
      const data = await res.json();

      // Stale response guard: only apply if this response is from the
      // latest issued request.
      if (seq < state.reqSeq) return;

      ingestState(data);
      setGlobalPill("ok", "En línea");
    } catch {
      setGlobalPill("error", "Sin conexión");
    } finally {
      inFlight = false;
    }
  }

  // === State ingestion ====================================================
  function ingestState(data) {
    if (!data || typeof data !== "object") return;

    state.server = data.server || {};

    // Nodes: full snapshot replacement
    state.nodes.clear();
    if (data.nodes && typeof data.nodes === "object") {
      for (const [nid, nd] of Object.entries(data.nodes)) {
        if (nd && typeof nd === "object") {
          state.nodes.set(nid, nd);
        }
      }
    }

    // Series/history: full snapshot replacement
    state.history.clear();
    if (data.series && typeof data.series === "object") {
      for (const [nid, points] of Object.entries(data.series)) {
        if (!Array.isArray(points)) continue;
        const h = { cpu: [], ram: [], latency_ms: [], ts: [] };
        for (const p of points) {
          if (p.cpu != null) h.cpu.push(p.cpu);
          if (p.ram != null) h.ram.push(p.ram);
          if (p.latency_ms != null) h.latency_ms.push(p.latency_ms);
          if (p.received_at) h.ts.push(p.received_at);
        }
        state.history.set(nid, h);
      }
    }

    // Events: full snapshot replacement
    state.events = Array.isArray(data.events) ? data.events : [];

    // Logs: full snapshot replacement
    state.logs = Array.isArray(data.logs) ? data.logs : [];
  }

  // === Render after poll ==================================================
  function renderAll() {
    renderMission();
    renderHowto();
    renderStats();
    renderNodes();
    renderChart();
    renderEvents();
    renderLogs();
    setLastRefreshStamp();
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
      const raw = await fetch(meta.path, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: body == null ? "" : JSON.stringify(body),
      });
      const text = await raw.text();
      let result = {};
      if (text) { try { result = JSON.parse(text); } catch { result = {}; } }
      if (!raw.ok) {
        const msg = (result && (result.error || result.message)) || `HTTP ${raw.status}`;
        throw new Error(msg);
      }
      const ok = result && (result.success !== false);
      const tone = ok ? "success" : "warn";
      const label = result && result.label ? result.label : action;
      const detail = result && result.details && result.details.message
        ? result.details.message
        : (ok ? "Acción completada" : "Acción finalizada con observaciones");
      setFeedback(`${label}: ${detail}`, tone);
      // refresh immediately so the chart shows new data
      pollState();
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

    // Refresh relative timestamps every 1s
    setInterval(() => {
      tickClock();
      renderNodes();
      renderHowto();
    }, 1000);
  }

  // === Auto-start: complete the 7-node demo fleet ==========================
  // Why this exists: the user wants the dashboard to come up populated, not
  // wait for a manual click. Guards:
  //   1. In-memory `state.autoStartAttempted` is set BEFORE the network
  //      call so a second poll loop tick cannot re-fire it.
  //   2. `state.autoStartInFlight` rejects concurrent calls if some other
  //      caller (e.g. a fast double-DOMContentLoaded) re-enters here.
  //   3. `sessionStorage` with a 15 s TTL blocks re-fires across page
  //      reloads during the ~10 s scenario window only — after that the
  //      guard expires so a later refresh can auto-complete a still-
  //      incomplete fleet.
  //   4. We only POST when the fleet is incomplete (< 7 demo nodes), so
  //      we never overwrite an already-running fleet.
  const DEMO_NODE_IDS = ["node-01","node-02","node-03","node-04","node-05","node-06","node-07"];

  function isFleetComplete() {
    return DEMO_NODE_IDS.every((id) => state.nodes.has(id));
  }

  // sessionStorage TTL (ms) — block re-fires across page reloads only
  // during the ~10 s scenario window so a mid-scenario refresh does not
  // start a duplicate set of clients before the first batch finishes.
  const AUTO_START_STORAGE_KEY = "multi-node-auto-started";
  const AUTO_START_TTL_MS = 15000;

  function readAutoStartFlag() {
    try {
      const raw = sessionStorage.getItem(AUTO_START_STORAGE_KEY);
      if (raw === null) return false;
      return Date.now() < parseInt(raw, 10);
    } catch {
      return state.autoStartAttempted;
    }
  }

  function writeAutoStartFlag() {
    try {
      sessionStorage.setItem(
        AUTO_START_STORAGE_KEY,
        String(Date.now() + AUTO_START_TTL_MS),
      );
    } catch {
      // ignored: in-memory flag is enough to prevent repeat fires in
      // this page session.
    }
  }

  async function tryAutoStartDemo() {
    if (state.autoStartAttempted || state.autoStartInFlight) return;
    if (readAutoStartFlag()) {
      // Still inside the TTL window from a previous attempt; skip to
      // avoid starting duplicate clients while the server is busy.
      state.autoStartAttempted = true;
      return;
    }
    // Fire when the fleet is incomplete (fewer than 7 demo nodes).
    if (isFleetComplete()) return;

    // Lock BEFORE awaiting so the next poll tick won't re-fire.
    state.autoStartAttempted = true;
    state.autoStartInFlight = true;
    writeAutoStartFlag();

    setFeedback("Iniciando demo multi-nodo (7 nodos)…", "info");
    setScenarioState("multi-node", Date.now());
    try {
      const raw = await fetch(ACTIONS.scenario.path, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ scenario: "multi-node", node_id: "node-01", interval: 3.0 }),
      });
      if (!raw.ok) throw new Error(`HTTP ${raw.status}`);
      const result = await raw.json().catch(() => ({}));
      if (result && result.success === false) {
        const details = result.details || {};
        throw new Error(details.stderr || details.error || "scenario failed");
      }
      // Refresh immediately so the chart starts showing data.
      await pollState();
      renderAll();
    } catch (err) {
      setFeedback(`Falló auto-inicio: ${err.message || err}`, "error");
    } finally {
      state.autoStartInFlight = false;
      // Scenario typically ends after ~10s on the server side; mark
      // idle after a slightly longer window so the elapsed counter
      // visibly stops before clearing.
      setTimeout(() => {
        if (state.scenario.name === "multi-node") setScenarioState(null);
      }, 11000);
    }
  }

  // === Main loop ==========================================================
  let pollTimer = null;

  async function pollLoop() {
    await pollState();
    renderAll();
    // Try the one-shot auto-start after the first state arrives. The
    // helper short-circuits on every subsequent tick thanks to the
    // state.autoStartAttempted flag, so this stays cheap.
    tryAutoStartDemo();
    pollTimer = setTimeout(pollLoop, POLL_MS);
  }

  // === Boot ===============================================================
  document.addEventListener("DOMContentLoaded", () => {
    bind();
    tickClock();
    pollLoop();
  });
})();
