# Contrato Tecnico v1

Este documento define el contrato inicial que deben respetar cliente, servidor, validacion y persistencia.

## Decisiones Base

| Elemento | Decision |
|---|---|
| Lenguaje | Python 3.11+ |
| Transporte | TCP |
| Puerto por defecto | 5000 |
| Host servidor | 0.0.0.0 |
| Codificacion | UTF-8 |
| Formato | JSON |
| Separador de mensajes | Salto de linea `\n` |
| Tipos de mensaje | `metric`, `command`, `ack`, `error` |
| Reconexion cliente | Cada 5 segundos |
| Persistencia | Pendiente del Rol D; SQLite recomendado |

## Autenticacion Basica

Cada nodo enviara un token estatico. La validacion del token corresponde al Rol C.

El archivo concreto de tokens queda pendiente para el Rol C.

## Mensaje Metric

```json
{
  "type": "metric",
  "node_id": "node-01",
  "seq": 1,
  "cpu": 45.0,
  "ram": 60.0,
  "latency_ms": 35,
  "service_web": "ok",
  "event_log": "normal",
  "token": "node-01-secret"
}
```

Campos:

| Campo | Tipo | Regla |
|---|---|---|
| `type` | string | Debe ser `metric` |
| `node_id` | string | No vacio |
| `seq` | integer | Mayor o igual a 0 |
| `cpu` | number | Entre 0 y 100 |
| `ram` | number | Entre 0 y 100 |
| `latency_ms` | number | Mayor o igual a 0 |
| `service_web` | string | `ok` o `falla` |
| `event_log` | string | Texto descriptivo |
| `token` | string | Token valido para `node_id` |

## Mensaje Command

```json
{
  "type": "command",
  "command_id": "cmd-000001",
  "action": "reduce_cpu",
  "reason": "cpu_above_90"
}
```

Acciones validas iniciales:

- `reduce_cpu`
- `reduce_ram`
- `fix_latency`
- `restart_service`
- `normalize_node`

## Mensaje ACK

```json
{
  "type": "ack",
  "node_id": "node-01",
  "command_id": "cmd-000001",
  "status": "applied",
  "token": "node-01-secret"
}
```

Estados validos iniciales:

- `applied`
- `failed`

## Mensaje Error

```json
{
  "type": "error",
  "code": "INVALID_MESSAGE",
  "message": "cpu must be between 0 and 100"
}
```

Codigos iniciales:

- `INVALID_JSON`
- `INVALID_MESSAGE`
- `AUTH_FAILED`
- `SERVER_ERROR`

## Reglas de Anomalia

| Condicion | Alerta | Comando |
|---|---|---|
| `cpu > 90` | `cpu_high` | `reduce_cpu` |
| `ram > 90` | `ram_high` | `reduce_ram` |
| `latency_ms > 200` | `latency_high` | `fix_latency` |
| `service_web == "falla"` | `service_failure` | `restart_service` |
| `event_log` contiene `fallido` | `failed_event` | `normalize_node` |

## Flujo Esperado

```text
Cliente -> metric -> Servidor
Servidor -> command -> Cliente, si hay anomalia
Cliente -> ack -> Servidor
Cliente -> metric recuperada -> Servidor
```
