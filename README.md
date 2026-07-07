# Sistema de Monitoreo Remoto de Servidores Simulados

Proyecto final de Redes de Computadores. Simula nodos remotos que envían métricas por TCP a un servidor central, que las valida, persiste y emite comandos correctivos cuando detecta anomalías. Incluye un dashboard web en tiempo real con mitigación del lado cliente.

## Estado actual

Sistema completo con:

| Componente | Estado |
|---|---|
| Servidor TCP multicliente (hilos) | Implementado |
| Cliente persistente con reconexión | Implementado |
| Autenticación PSK con nonce por nodo | Implementado |
| Canal cifrado simétrico post-handshake | Implementado |
| Detección de anomalías y envío de comandos | Implementado |
| Mitigación del lado cliente | Implementado (cooldown anti-spam) |
| Enriquecimiento de ACKs (mitigation, command → state linkage) | Implementado |
| Dashboard web en tiempo real | Implementado (polling `/api/state` cada 1s) |
| Backend `/api/state` como fuente única de verdad | Implementado |
| Persistencia SQLite (métricas, comandos, ACKs) | Implementado |
| Pruebas unitarias y de integración | **63 pruebas — pasan** |
| Captura de tráfico con Wireshark | Documentado |
| Escaneo con Nmap | Documentado |

## Contrato técnico

- **Transporte:** TCP.
- **Puerto por defecto:** `5000` (configurable).
- **Codificación:** UTF-8.
- **Formato de línea:** JSON terminado en `\n` (JSON Lines).
- **Handshake:** `hello` -> `challenge` -> `challenge_response` -> `ready`.
- **Canal seguro:** luego del handshake, los payloads viajan como frames `secure` cifrados y autenticados con clave derivada de la PSK del nodo.
- **Tipos de mensaje de aplicación:** `metric`, `command`, `ack`, `error`.

Ver `docs/contract_v1.md` para el detalle completo de campos, tipos y reglas de validación.

## Arquitectura

```
┌─────────────────┐     TCP/5000      ┌─────────────────────────────────────────┐
│  Client         │ ────────────────> │  Server                                 │
│  node-01        │                   │                                         │
│  client/        │  metric (JSON\n)  │  connection_manager.py                  │
│  tcp_client.py  │ <──────────────── │  client_session.py                      │
└─────────────────┘                   │  tcp_server.py                          │
                                      │  server_state.py (cooldown/anti-spam)   │
┌─────────────────┐                   │  command_dispatcher.py                  │
│  Client         │                   │                                         │
│  node-02        │                   │  ┌──────────────────────┐               │
│  client/        │                   │  │  shared/auth.py      │               │
│  tcp_client.py  │                   │  │  (validación token)  │               │
└─────────────────┘                   │  └──────────────────────┘               │
                                      │                                         │
┌─────────────────┐                   │  ┌──────────────────────┐               │
│  Client         │                   │  │  storage/store.py    │               │
│  node-03        │                   │  │  (SQLite persist.)   │               │
│  client/        │                   │  └──────────────────────┘               │
└─────────────────┘                   │         │                              │
                                      │         v                              │
┌──────────────────────────────────┐  │  ┌──────────────┐                      │
│  Frontend (dashboard_server.py)  │  │  │ monitor.db   │                      │
│  ┌────────────────────────────┐  │  │  │ metrics      │                      │
│  │  /api/state  (SSOT)        │──│──│  │ commands     │                      │
│  │  /api/status               │  │  │  │ acks         │                      │
│  │  /api/scenario             │  │  │  └──────────────┘                      │
│  │  /api/logs                │  │  └─────────────────────────────────────────┘
│  └────────────────────────────┘  │
│  ┌────────────────────────────┐  │
│  │  Dashboard HTML/JS          │──│─ HTTP 8080
│  │  (poll /api/state cada 1s) │  │
│  └────────────────────────────┘  │
└──────────────────────────────────┘
```

## Estructura del repositorio

```
configs/         Configuración del servidor (JSON + variables de entorno)
server/          Servidor TCP, sesiones, estado, despacho de comandos
client/          Cliente TCP persistente con reconexión automática
shared/          Autenticación PSK, canal seguro y validación
storage/         Persistencia SQLite
frontend/        Dashboard web (servidor HTTP + static HTML/JS/CSS)
tests/           Pruebas unitarias y de integración
scripts/         Scripts de ejecución, evidencia y captura
docs/            Guía, contrato técnico, escenarios y documentación de evidencia
```

## Ejecución rápida

### 1. Servidor

```bash
python3 -m server.tcp_server
# o
./scripts/run_server.sh
```

Acepta conexiones en `0.0.0.0:5000` por defecto. Puede cambiarse con variables de entorno:

```bash
SERVER_HOST=127.0.0.1 SERVER_PORT=5001 python3 -m server.tcp_server
```

### 2. Frontend / Dashboard

```bash
python3 frontend/dashboard_server.py
# o
./scripts/run_frontend.sh
```

Sirve el dashboard en `http://localhost:8080` con:
- Panel de nodos activos con métricas en tiempo real
- Gráfico de series temporales (CPU, RAM, latencia)
- Historial de eventos (comandos y ACKs)
- Indicadores de mitigación activa
- Logs del sistema

El frontend **consulta `/api/state` cada 1 segundo** como fuente única de verdad.

### 3. Proyecto completo (servidor + frontend)

```bash
./scripts/run_project.sh
```

Inicia ambos componentes y muestra logs en consola. Usar `Ctrl+C` para detener.

### 3b. Modo presentación fácil

```bash
make present
```

Levanta en un solo comando:
- servidor TCP
- dashboard HTTP
- clientes reales persistentes

Por defecto usa el perfil `trio` (3 nodos). El dashboard también soporta un
escenario `multi-node` desde `/api/scenario` que lanza 7 nodos cubriendo
todas las anomalías más un nodo aleatorio (`chaos`):

| Nodo | Modo | Efecto |
|---|---|---|
| `node-01` | `normal` | Métricas base |
| `node-02` | `high-cpu` | CPU=95 |
| `node-03` | `high-ram` | RAM=94 |
| `node-04` | `high-latency` | latencia=350ms |
| `node-05` | `service-failure` | service_web="falla" |
| `node-06` | `failed-event` | event_log="backup fallido" |
| `node-07` | `chaos` | Cicla por todas las anomalías |

También puedes lanzar perfiles simples:

```bash
PROFILE=cpu make present
PROFILE=ram make present
PROFILE=latency make present
```

### 4. Cliente persistente

```bash
# Modo normal (métricas base cada 5 segundos)
python3 -m client.tcp_client --node-id node-01 --mode normal

# Modo con anomalía (dispara mitigación + comando)
python3 -m client.tcp_client --node-id node-01 --mode high-cpu

# Otro nodo con latencia alta
python3 -m client.tcp_client --node-id node-02 --mode high-latency --interval 3.0

# Wrapper simple
MODE=high-cpu NODE_ID=node-02 INTERVAL=3.0 make client
```

Modos disponibles:

| Modo | Efecto |
|---|---|
| `normal` | Métricas base (CPU=35, RAM=45, latencia=40ms) |
| `high-cpu` | CPU=95 → dispara `reduce_cpu`; la siguiente métrica empieza a bajar |
| `high-ram` | RAM=94 → dispara `reduce_ram`; la siguiente métrica empieza a bajar |
| `high-latency` | latencia=350ms → dispara `fix_latency`; la siguiente métrica empieza a bajar |
| `service-failure` | service_web="falla" → dispara `restart_service` |
| `failed-event` | event_log="backup fallido" → dispara `normalize_node` |
| `chaos` | Cicla por todas las anomalías según el número de secuencia |

El cliente se reconecta automáticamente cada 5 segundos si pierde la conexión. Cuando recibe un comando correctivo, cambia su estado interno y las métricas posteriores muestran recuperación progresiva.

### 5. Pruebas

```bash
python3 -m unittest discover -s tests -v
```

O usando el Makefile:

```bash
make test
```

## Mitigación del lado cliente

Cuando un cliente entra en un modo anómalo (modo `high-cpu`, `high-ram`, etc.):

1. **Reporta la anomalía inicial** para que el servidor la detecte.
2. **Recibe un comando correctivo** (`reduce_cpu`, `reduce_ram`, `fix_latency`, etc.).
3. **Aplica mitigación real en el cliente** y reduce gradualmente la métrica en muestras posteriores.
4. **Reporta el estado de mitigación** en cada métrica (`mitigation_active: true/false`, `mitigation_type`).
5. **Responde al comando** con ACKs enriquecidos que incluyen `before` y `after`.

El servidor implementa un **cooldown anti-spam** (12s por defecto) que evita emitir comandos duplicados si el mismo nodo ya confirmó la misma acción recientemente.

Ver `docs/mitigation.md` para más detalles.

## Dashboard en tiempo real

- El frontend **consulta `/api/state` cada 1 segundo**.
- El endpoint `/api/state` construye un snapshot completo desde SQLite: nodos activos, series temporales, comandos, ACKs y eventos recientes.
- La interfaz actualiza automáticamente: tabla de nodos, gráfico de series, historial de eventos, indicador de mitigación y logs.
- Incluye panel de control de escenarios para ejecutar pruebas desde la UI.

Ver `docs/frontend-realtime.md` para más detalles.

## Autenticación y cifrado

Cada nodo tiene una clave precompartida definida en `shared/auth.py`. La demo deja listas 32 claves, desde `node-01` hasta `node-32`, con el patrón `node-XX-secret`.

| Nodo | PSK |
|---|---|
| `node-01` | `node-01-secret` |
| `node-02` | `node-02-secret` |
| `node-03` | `node-03-secret` |
| `...` | `...` |
| `node-32` | `node-32-secret` |

Al conectarse, el cliente envía su `node_id`, el servidor responde un nonce y el cliente prueba identidad con HMAC. Si la prueba es correcta, ambas partes derivan una clave de sesión y los mensajes `metric`, `command`, `ack` y `error` viajan dentro de frames cifrados. Un nodo desconocido o una prueba inválida produce `AUTH_FAILED`.

## Persistencia

SQLite en `data/monitor.db` (configurable en `configs/server_config.json` o variable `SERVER_CONFIG`).

Tablas:
- `metrics` — métricas recibidas con timestamp y estado de mitigación
- `commands` — comandos emitidos con estado (`pending` / `confirmed` / `timed_out` / `failed`)
- `acks` — confirmaciones de clientes con información de mitigación

## Evidencia para la entrega

Ver:
- `docs/scenarios.md` — escenarios de prueba y resultados esperados
- `docs/mitigation.md` — mitigación del lado cliente
- `docs/demo-flow.md` — flujo de demostración para la presentación
- `docs/frontend-realtime.md` — dashboard en tiempo real
- `docs/evidence/README.md` — índice de artefactos de evidencia
- `docs/evidence/wireshark.md` — cómo capturar tráfico con Wireshark
- `docs/evidence/nmap.md` — cómo verificar el puerto con Nmap
- `docs/report-template.md` — plantilla del informe técnico
- `docs/presentation-template.md` — guión de presentación
- `docs/architecture.md` — diagrama de arquitectura

## Makefile

```bash
make test       # Ejecutar pruebas
make demo       # Iniciar proyecto (servidor + frontend)
make evidence   # Generar artefactos de evidencia
make clean      # Limpiar artefactos y logs
```

Ver `Makefile` para detalles.

## Requisitos

Python 3.11+. Solo biblioteca estándar (sin dependencias externas).
