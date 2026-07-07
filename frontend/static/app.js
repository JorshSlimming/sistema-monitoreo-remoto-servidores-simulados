/* Monitor local · sistema de monitoreo remoto
 * Vista de solo lectura: estado, métricas, eventos y logs.
 * Polls cada 5 s. Sin frameworks, sin librerías de gráficos.
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
  };
  const POLL_MS = 5000;
  const SPARK_POINTS = 24; // ≈ 2 min a 5 s
  const MAX_HISTORY = 120; // tope duro en cliente
  const MAX_EVENTS = 25;
  const MAX_LOGS = 80;

  // Thresholds (%, ms) → used to color bars and sparklines
  const T = {
    cpu: [60, 80],
    ram: [70, 85],
    latency: [100, 200],
  };

  // === State ==============================================================
  const state = {
    lastRefresh: null,
    // history: node_id -> { cpu: number[], ram: number[], latency_ms: number[], ts: number[] }
    history: new Map(),
    // latest snapshot per node
    nodes: new Map(),
  };

  // === Utils ==============================================================
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

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

  const formatDateTime = (iso) => {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString("es-CO", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  };

  // Time-since helper (Spanish, short)
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

  // Pick the first defined value from a list of candidate field names.
  const pick = (obj, names) => {
    if (!obj || typeof obj !== "object") return undefined;
    for (const n of names) {
      if (obj[n] !== undefined && obj[n] !== null) return obj[n];
    }
    return undefined;
  };

  // Normalize a metric record (different keys → common shape)
  const normalizeMetric = (m) => {
    if (!m || typeof m !== "object") return null;
    const nodeId =
      pick(m, ["node_id", "node", "id", "name"]) || "desconocido";
    return {
      node_id: String(nodeId),
      cpu: numberOr(pick(m, ["cpu", "cpu_pct", "cpu_percent"]), null),
      ram: numberOr(pick(m, ["ram", "mem", "memory", "ram_pct"]), null),
      latency_ms: numberOr(
        pick(m, ["latency_ms", "latency", "lat", "rtt_ms"]),
        null
      ),
      service_web: pick(m, ["service_web", "service", "web"]) ?? null,
      event_log: pick(m, ["event_log", "event", "last_event"]) ?? null,
      timestamp: pick(m, ["timestamp", "ts", "time", "received_at"]) ?? null,
    };
  };

  const numberOr = (v, fallback) => {
    const n = Number(v);
    return Number.isFinite(n) ? n : fallback;
  };

  // === API client =========================================================
  async function fetchJson(url) {
    let res;
    try {
      res = await fetch(url, {
        method: "GET",
        headers: { Accept: "application/json" },
      });
    } catch (err) {
      throw new Error(`Sin conexión con ${url}`);
    }
    const text = await res.text();
    let data = null;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = null;
      }
    }
    if (!res.ok) {
      throw new Error(`HTTP ${res.status} en ${url}`);
    }
    return data || {};
  }

  // === Sparkline ==========================================================
  // Build an inline SVG with a polyline + a soft area fill. No libraries.
  function sparkline(values, { width = 96, height = 28, tone = "info" } = {}) {
    const w = width;
    const h = height;
    const pad = 1.5;
    const xs = values.length;
    if (xs < 2) {
      return `<svg class="spark spark--${tone}" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" aria-hidden="true"></svg>`;
    }
    let min = Infinity;
    let max = -Infinity;
    for (const v of values) {
      if (v == null) continue;
      if (v < min) min = v;
      if (v > max) max = v;
    }
    if (!Number.isFinite(min) || !Number.isFinite(max)) {
      return `<svg class="spark spark--${tone}" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" aria-hidden="true"></svg>`;
    }
    if (min === max) {
      min -= 0.5;
      max += 0.5;
    }
    const dx = (w - pad * 2) / (xs - 1);
    const points = [];
    for (let i = 0; i < xs; i++) {
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

  // === Bar ================================================================
  function toneFor(value, thresholds) {
    if (value == null) return "idle";
    if (value >= thresholds[1]) return "error";
    if (value >= thresholds[0]) return "warn";
    return "success";
  }

  // === History push =======================================================
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

  // === Renders ============================================================
  function renderOverview(status) {
    const setStat = (idVal, idHint, val, hint) => {
      const v = document.getElementById(idVal);
      const h = document.getElementById(idHint);
      if (v) v.textContent = val;
      if (h) h.textContent = hint;
    };

    if (!status || typeof status !== "object") {
      setStat("stat-server", "stat-server-hint", "—", "Sin datos");
      setStat("stat-nodes", "stat-nodes-hint", "—", "Sin datos");
      setStat("stat-metrics", "stat-metrics-hint", "—", "Sin datos");
      setStat("stat-anomaly", "stat-anomaly-hint", "—", "Sin datos");
      return;
    }

    // Server
    const srv = status.server || {};
    if (srv.host || srv.port !== undefined) {
      const host = srv.host || "0.0.0.0";
      const port = srv.port !== undefined ? srv.port : "?";
      setStat("stat-server", "stat-server-hint", `${host}:${port}`, srv.running === false ? "Detenido" : "Activo");
    } else {
      setStat("stat-server", "stat-server-hint", "—", "Sin datos");
    }

    // Nodes
    const nodesActive = pick(status, [
      "nodes_active",
      "active_nodes",
      "clients",
      "connected",
    ]);
    if (nodesActive !== undefined) {
      setStat(
        "stat-nodes",
        "stat-nodes-hint",
        String(nodesActive),
        "vistos en los últimos ciclos"
      );
    } else {
      setStat(
        "stat-nodes",
        "stat-nodes-hint",
        String(state.nodes.size),
        "detectados en esta sesión"
      );
    }

    // Metrics count
    const metricsCount = pick(status, [
      "metrics_total",
      "metrics_received",
      "metrics_count",
      "total_metrics",
    ]);
    if (metricsCount !== undefined) {
      setStat("stat-metrics", "stat-metrics-hint", String(metricsCount), "totales recibidas");
    } else if (status.database && status.database.metrics !== undefined) {
      setStat(
        "stat-metrics",
        "stat-metrics-hint",
        String(status.database.metrics),
        "persistidas"
      );
    } else {
      setStat("stat-metrics", "stat-metrics-hint", "—", "Sin datos");
    }

    // Anomalies
    const lastAnomaly = pick(status, [
      "last_anomaly",
      "last_anomaly_at",
      "anomaly_last",
    ]);
    const anomaliesToday = pick(status, [
      "anomalies_today",
      "anomalies_count",
      "anomalies",
    ]);
    if (lastAnomaly) {
      setStat(
        "stat-anomaly",
        "stat-anomaly-hint",
        formatTime(lastAnomaly),
        anomaliesToday !== undefined ? `${anomaliesToday} en total` : "registrada"
      );
    } else if (anomaliesToday !== undefined) {
      setStat(
        "stat-anomaly",
        "stat-anomaly-hint",
        String(anomaliesToday),
        "eventos detectados"
      );
    } else {
      setStat("stat-anomaly", "stat-anomaly-hint", "—", "Sin datos");
    }
  }

  function renderNodes() {
    const grid = document.getElementById("node-grid");
    const empty = document.getElementById("nodes-empty");
    if (!grid) return;

    const ids = Array.from(state.nodes.keys()).sort();
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
      const spark = (vals) =>
        sparkline(vals.slice(-SPARK_POINTS), { width: 96, height: 28 });

      const cpuTone = toneFor(cpu, T.cpu);
      const ramTone = toneFor(ram, T.ram);
      const latTone = toneFor(lat, T.latency);

      const svc = (node.service_web || "").toString().toLowerCase();
      const svcState = svc === "falla" || svc === "fail" || svc === "down" ? "error" : "success";
      const svcLabel = svc === "falla" || svc === "fail" ? "falla" : svc ? svc : "—";

      const eventLog = node.event_log || "—";
      const fmtPct = (v) => (v == null ? "—" : `${v.toFixed(0)}%`);
      const fmtMs = (v) => (v == null ? "—" : `${Math.round(v)} ms`);

      return `
<article class="node" data-node="${escapeHtml(id)}">
  <header class="node__head">
    <span class="node__id">${escapeHtml(id)}</span>
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
      ${spark(h.cpu)}
    </div>
    <div class="metric">
      <div class="metric__row">
        <span class="metric__label">RAM</span>
        <span class="metric__value" data-state="${ramTone}">${fmtPct(ram)}</span>
      </div>
      ${spark(h.ram)}
    </div>
    <div class="metric">
      <div class="metric__row">
        <span class="metric__label">Latencia</span>
        <span class="metric__value" data-state="${latTone}">${fmtMs(lat)}</span>
      </div>
      ${spark(h.latency_ms)}
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
    const v = arr[arr.length - 1];
    return v == null ? null : v;
  }

  function renderEvents(events) {
    const list = document.getElementById("event-list");
    const empty = document.getElementById("events-empty");
    if (!list) return;
    if (!Array.isArray(events) || events.length === 0) {
      list.replaceChildren();
      if (empty) empty.hidden = false;
      return;
    }
    if (empty) empty.hidden = true;
    const items = events.slice(0, MAX_EVENTS).map((e) => {
      const type = (
        pick(e, ["type", "kind", "event_type"]) || "event"
      ).toString().toLowerCase();
      const node = pick(e, ["node_id", "node", "from"]) || "—";
      const ts = pick(e, ["timestamp", "ts", "time"]) || null;
      const action = pick(e, ["action", "command", "cmd"]);
      const reason = pick(e, ["reason"]);
      const status = pick(e, ["status", "result"]);
      const msg = pick(e, ["message", "detail", "summary", "metric", "what"]);

      let detail = "";
      if (action) detail += `<code>${escapeHtml(action)}</code>`;
      if (reason) detail += detail ? ` <span class="muted">(${escapeHtml(reason)})</span>` : `<span class="muted">${escapeHtml(reason)}</span>`;
      if (!detail && status) detail = `<code>${escapeHtml(status)}</code>`;
      if (!detail && msg) detail = escapeHtml(msg);

      return `<li class="event" data-type="${escapeHtml(type)}">
  <span class="event__type event__type--${escapeHtml(type)}">${escapeHtml(type)}</span>
  <span class="event__node">${escapeHtml(node)}</span>
  <span class="event__detail">${detail || "—"}</span>
  <span class="event__time">${formatTime(ts)}</span>
</li>`;
    });
    list.innerHTML = items.join("");
  }

  function renderLogs(logs) {
    const tail = document.getElementById("log-tail");
    const empty = document.getElementById("logs-empty");
    if (!tail) return;
    if (!Array.isArray(logs) || logs.length === 0) {
      tail.replaceChildren();
      if (empty) empty.hidden = false;
      return;
    }
    if (empty) empty.hidden = true;
    const lines = logs.slice(0, MAX_LOGS).map((l) => {
      const level = (pick(l, ["level"]) || "info").toString().toLowerCase();
      const ts = pick(l, ["timestamp", "ts", "time"]) || null;
      const node = pick(l, ["node_id", "node"]) || "";
      const msg = pick(l, ["message", "msg", "text"]) || JSON.stringify(l);
      const who = node ? `[${escapeHtml(node)}] ` : "";
      return `<span class="log__line" data-level="${escapeHtml(level)}"><span class="log__time">${formatTime(ts)}</span> <span class="log__level">${escapeHtml(level)}</span> ${who}${escapeHtml(msg)}</span>`;
    });
    tail.innerHTML = lines.join("\n");
  }

  // === Pollers ============================================================
  async function pollStatus() {
    try {
      const data = await fetchJson(ENDPOINTS.status.path);
      renderOverview(data);
      setGlobalPill("ok", "En línea");
      return true;
    } catch (err) {
      setGlobalPill("error", "Sin conexión");
      return false;
    }
  }

  async function pollMetrics() {
    try {
      const data = await fetchJson(ENDPOINTS.metrics.path);
      ingestMetrics(data);
    } catch {
      // sin datos nuevos: deja la última vista
    }
    renderNodes();
    return true;
  }

  function ingestMetrics(payload) {
    if (!payload) return;
    // Acepta varias formas:
    //   { metrics: [...] }   { data: [...] }   { items: [...] }   { nodes: { id: {...} } }
    let list = null;
    if (Array.isArray(payload.metrics)) list = payload.metrics;
    else if (Array.isArray(payload.data)) list = payload.data;
    else if (Array.isArray(payload.items)) list = payload.items;
    else if (Array.isArray(payload)) list = payload;
    else if (payload.nodes && typeof payload.nodes === "object") {
      list = Object.values(payload.nodes);
    }

    if (!Array.isArray(list)) return;

    for (const raw of list) {
      const m = normalizeMetric(raw);
      if (!m) continue;
      state.nodes.set(m.node_id, {
        ...state.nodes.get(m.node_id),
        ...m,
      });
      pushHistory(m);
    }
  }

  async function pollEvents() {
    try {
      const data = await fetchJson(ENDPOINTS.events.path);
      const list = pick(data, ["events", "items", "data"]) || [];
      renderEvents(Array.isArray(list) ? list : []);
    } catch {
      // Try /api/logs as fallback for events
      try {
        const data = await fetchJson(ENDPOINTS.logs.path);
        const list = pick(data, ["logs", "items", "data"]) || [];
        renderEvents(Array.isArray(list) ? list : []);
      } catch {
        renderEvents([]);
      }
    }
  }

  async function pollLogs() {
    try {
      const data = await fetchJson(ENDPOINTS.logs.path);
      const list = pick(data, ["logs", "items", "data"]) || [];
      renderLogs(Array.isArray(list) ? list : []);
    } catch {
      renderLogs([]);
    }
  }

  function setGlobalPill(state_, label) {
    const pill = document.getElementById("global-pill");
    if (!pill) return;
    pill.dataset.state = state_;
    const text = pill.querySelector(".pill__label");
    if (text) text.textContent = label;
  }

  function setLastRefreshStamp() {
    const el = document.getElementById("last-refresh");
    if (!el) return;
    if (!state.lastRefresh) {
      el.textContent = "—";
      return;
    }
    el.textContent = `Actualizado ${formatTime(state.lastRefresh.toISOString())}`;
  }

  // === Master poll ========================================================
  let inFlight = false;
  async function pollAll() {
    if (inFlight) return;
    inFlight = true;
    try {
      await Promise.all([pollStatus(), pollMetrics(), pollEvents(), pollLogs()]);
      state.lastRefresh = new Date();
      setLastRefreshStamp();
    } finally {
      inFlight = false;
    }
  }

  // === Bindings ===========================================================
  function bind() {
    const refresh = document.getElementById("refresh");
    if (refresh) {
      refresh.addEventListener("click", () => pollAll());
    }
    // Re-render "hace Xs" stamps once per second without re-fetching
    setInterval(() => {
      // Force re-render of nodes to refresh relative timestamps
      if (state.nodes.size > 0) renderNodes();
    }, 1000);
  }

  // === Boot ===============================================================
  document.addEventListener("DOMContentLoaded", () => {
    bind();
    pollAll();
    setInterval(pollAll, POLL_MS);
  });
})();
