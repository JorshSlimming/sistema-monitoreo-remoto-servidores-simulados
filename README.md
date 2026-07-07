# Sistema de Monitoreo Remoto de Servidores Simulados

Proyecto final de Redes de Computadores. Simula nodos remotos que envían métricas por TCP a un servidor central, que las valida, persiste y emite comandos correctivos cuando detecta anomalías.

## Estado actual

Sistema completo con:

| Componente | Estado |
|---|---|
| Servidor TCP multicliente (hilos) | Implementado |
| Cliente persistente con reconexión | Implementado |
| Autenticación por token estático | Implementado |
| Detección de anomalías y envío de comandos | Implementado |
| Persistencia SQLite (métricas, comandos, ACKs) | Implementado |
| Pruebas unitarias y de integración | 23 pruebas — pasan |
| Captura de tráfico con Wireshark | Documentado |
| Escaneo con Nmap | Documentado |

## Contrato técnico

- **Transporte:** TCP.
- **Puerto por defecto:** `5000` (configurable).
- **Codificación:** UTF-8.
- **Formato:** JSON terminado en `\n` (JSON Lines).
- **Tipos de mensaje:** `metric`, `command`, `ack`, `error`.

Ver `docs/contract_v1.md` para el detalle completo de campos, tipos y reglas de validación.

## Arquitectura

```
┌─────────────────┐     TCP/5000      ┌──────────────────────────────┐
│  Client         │ ────────────────> │  Server                      │
│  node-01        │                   │                              │
│  client/        │  metric (JSON\n)  │  connection_manager.py       │
│  tcp_client.py  │ <──────────────── │  client_session.py           │
└─────────────────┘                   │  tcp_server.py               │
                                      │                              │
┌─────────────────┐                   │  ┌──────────────────────┐    │
│  Client         │                   │  │  shared/auth.py      │    │
│  node-02        │                   │  │  (validación token)  │    │
│  client/        │                   │  └──────────────────────┘    │
│  tcp_client.py  │                   │                              │
└─────────────────┘                   │  ┌──────────────────────┐    │
                                      │  │  storage/store.py    │    │
┌─────────────────┐                   │  │  (SQLite persist.)   │    │
│  Client         │                   │  └──────────────────────┘    │
│  node-03        │                   │         │                    │
│  client/        │                   │         v                    │
│  tcp_client.py  │                   │  ┌──────────────┐           │
└─────────────────┘                   │  │ monitor.db   │           │
                                      │  │ metrics      │           │
                                      │  │ commands     │           │
                                      │  │ acks         │           │
                                      │  └──────────────┘           │
                                      └──────────────────────────────┘
```

## Estructura del repositorio

```
configs/        Configuración del servidor (JSON + variables de entorno)
server/         Servidor TCP, sesiones, estado, despacho de comandos
client/         Cliente TCP persistente con reconexión automática
shared/         Autenticación y token validation
storage/        Persistencia SQLite
tests/          Pruebas unitarias y de integración
scripts/        Scripts de ejecución
docs/           Guía, contrato técnico, roles, plantillas y evidencia
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

### 2. Cliente persistente

```bash
# Modo normal (métricas base cada 5 segundos)
python3 -m client.tcp_client --node-id node-01 --mode normal

# Modo con anomalía
python3 -m client.tcp_client --node-id node-01 --mode high-cpu

# Otro nodo con latencia alta
python3 -m client.tcp_client --node-id node-02 --mode high-latency --interval 3.0
```

Modos disponibles:

| Modo | Efecto |
|---|---|
| `normal` | Métricas base (CPU=35, RAM=45, latencia=40ms) |
| `high-cpu` | CPU=95 → dispara `reduce_cpu`; luego el cliente vuelve a CPU normal |
| `high-ram` | RAM=94 → dispara comando `reduce_ram` |
| `high-latency` | latencia=350ms → dispara comando `fix_latency` |
| `service-failure` | service_web="falla" → dispara `restart_service` |
| `failed-event` | event_log="backup fallido" → dispara `normalize_node` |

El cliente se reconecta automáticamente cada 5 segundos si pierde la conexión.

### 3. Pruebas

```bash
python3 -m unittest discover -s tests -v
```

## Autenticación

Tokens estáticos definidos en `shared/auth.py`:

| Nodo | Token |
|---|---|
| `node-01` | `node-01-secret` |
| `node-02` | `node-02-secret` |
| `node-03` | `node-03-secret` |

El servidor rechaza métricas o ACKs con token inválido (error `AUTH_FAILED`).

## Persistencia

SQLite en `data/monitor.db` (configurable en `configs/server_config.json` o variable `SERVER_CONFIG`).

Tablas:
- `metrics` — métricas recibidas con timestamp
- `commands` — comandos emitidos con estado (pending / timed_out / confirmed / failed)
- `acks` — confirmaciones de clientes

## Evidencia para la entrega

Ver:
- `docs/scenarios.md` — escenarios de prueba y resultados esperados
- `docs/evidence/wireshark.md` — cómo capturar tráfico con Wireshark
- `docs/evidence/nmap.md` — cómo verificar el puerto con Nmap
- `docs/report-template.md` — plantilla del informe técnico
- `docs/presentation-template.md` — guión de presentación
- `docs/architecture.md` — diagrama de arquitectura

## Requisitos

Python 3.11+. Solo biblioteca estándar (sin dependencias externas).
