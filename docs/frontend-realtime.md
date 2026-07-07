# Dashboard en tiempo real

## Visión general

El frontend es un dashboard web que muestra el estado del sistema de monitoreo en tiempo real. Consiste en un servidor HTTP Python (`frontend/dashboard_server.py`) que sirve archivos estáticos y una API REST, más un cliente JavaScript que actualiza la interfaz cada segundo.

## Componentes

### Backend del dashboard (`frontend/dashboard_server.py`)

Servidor HTTP implementado con `http.server` (biblioteca estándar). Sirve:

| Ruta | Descripción |
|---|---|
| `/` o `/index.html` | Dashboard HTML |
| `/app.js` | Lógica del cliente (JavaScript) |
| `/styles.css` | Estilos CSS |
| `/api/state` | **Fuente única de verdad** — snapshot completo del sistema |
| `/api/status` | Resumen de estado/artefactos del panel |
| `/api/scenario` | Control de escenarios de prueba |
| `/api/logs` | Cola de logs del sistema |

### API `/api/state` — fuente única de verdad

Endpoint principal. Responde con un objeto JSON que contiene:

```json
{
  "updated_at": "2026-07-07T12:00:00Z",
  "server": {
    "running": true,
    "host": "127.0.0.1",
    "port": 5000,
    "metrics_total": 150,
    "commands_total": 5,
    "acks_total": 5,
    "active_nodes": ["node-01", "node-02"]
  },
  "nodes": {
    "node-01": {
      "last_seen": "2026-07-07T12:00:00Z",
      "staleness_seconds": 0.0,
      "cpu": 35.0,
      "ram": 45.0,
      "latency_ms": 40,
      "service_web": "ok",
      "scenario": "normal",
      "anomaly_active": false,
      "mitigation_active": false,
      "mitigation_type": null,
      "last_command": null
    }
  },
  "series": {
    "node-01": [
      { "seq": 1, "cpu": 35.0, "ram": 45.0, "latency_ms": 40, "received_at": "..." }
    ]
  },
  "commands": [ /* últimos 50 comandos */ ],
  "acks": [ /* últimos 50 ACKs */ ],
  "events": [ /* comandos + ACKs mezclados cronológicamente */ ],
  "logs": [ /* últimas 20 líneas de log */ ]
}
```

### Cliente JavaScript (`frontend/static/app.js`)

**Polling:**

- Consulta `/api/state` cada **1000 ms** (`POLL_MS = 1000` en app.js).
- Usa `setTimeout` recursivo para el loop (evita acumulación si una respuesta tarda).
- Control de concurrencia con bandera `inFlight`.
- Guardia de respuestas obsoletas: si una respuesta llega después de una solicitud más reciente, se descarta.

**Ingesta de estado (`ingestState`):**

- Reemplaza completamente el estado anterior (snapshot).
- Actualiza: nodos activos, series temporales, eventos y logs.

**Renderizado:**

- `renderNodes()` — tabla de nodos con indicadores de mitigación.
- `renderChart()` — gráfico de series temporales (CPU/RAM/latencia seleccionable).
- `renderEvents()` — historial de eventos (comandos + ACKs).
- `renderLogs()` — últimas líneas de log del sistema.

**Indicadores visuales:**

- Badge `🛡 Mitigación: <tipo>` cuando `mitigation_active=true`.
- Pill de estado en línea/fuera de línea.
- Reloj de última actualización.

### Panel de control de escenarios

El dashboard incluye botones para disparar escenarios de prueba directamente desde la UI, que se comunican con `/api/scenario` para controlar la ejecución.

## Flujo de datos

```
Cliente TCP ──métrica──> Servidor TCP ──persiste──> SQLite
                                                         │
Dashboard Server <──consulta SQLite──                   │
      │                                                  │
      └── /api/state ──> Frontend JS (cada 1s)          │
                              │                          │
                              └── Render (nodos,         │
                                   gráfico, eventos)     │
```

## Puerto

Por defecto el dashboard se sirve en `http://localhost:8080`. Configurable con la variable de entorno `DASHBOARD_PORT`.

## Inicio

```bash
# Solo frontend
python3 frontend/dashboard_server.py

# Proyecto completo (servidor + frontend)
./scripts/run_project.sh

# Solo frontend con script
./scripts/run_frontend.sh
```
