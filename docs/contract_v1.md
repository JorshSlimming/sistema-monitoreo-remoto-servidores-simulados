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
| Persistencia | SQLite (implementado, 3 tablas) |
| Polling frontend | Cada 1 segundo a `/api/state` |
| Cooldown anti-spam | 12s (servidor, comandos duplicados) |
| Mitigacion cliente | Local, gradual por tipo de anomalia |

## Autenticacion Basica

Cada nodo envia un token estatico definido en `shared/auth.py`. El servidor valida el token
en cada mensaje `metric` y `ack`. Los tokens por defecto son:

| Nodo | Token |
|---|---|
| `node-01` | `node-01-secret` |
| `node-02` | `node-02-secret` |
| `node-03` | `node-03-secret` |

Un token invalido produce respuesta `AUTH_FAILED` sin persistir la metrica.

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
| `mitigation_active` | bool | (opcional) true si hay mitigacion activa tras un comando |
| `mitigation_type` | string | (opcional) tipo de mitigacion, ej. `reduce_cpu` |

## Mensaje Command

```json
{
  "type": "command",
  "command_id": 1,
  "action": "reduce_cpu",
  "reason": "cpu_above_90"
}
```

El servidor persiste cada comando con un estado:

- `pending` — emitido, esperando confirmación
- `confirmed` — ACK recibido del cliente
- `timed_out` — no se recibió ACK dentro del plazo (60s)

Acciones validas:

- `reduce_cpu`
- `reduce_ram`
- `fix_latency`
- `restart_service`
- `normalize_node`

El servidor implementa un **cooldown anti-spam** de 12 segundos: si un comando de la misma
acción para el mismo nodo fue confirmado hace menos de 12s, se rechaza el duplicado.

## Mensaje ACK

```json
{
  "type": "ack",
  "node_id": "node-01",
  "command_id": 1,
  "status": "applied",
  "token": "node-01-secret",
  "mitigation_active": true,
  "mitigation_type": "reduce_cpu"
}
```

Estados validos:

- `applied`
- `failed`

Campos opcionales de mitigacion incluidos cuando el cliente tiene mitigacion activa:

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
Cliente -> metric (con mitigation_active true/false) -> Servidor
Servidor -> command -> Cliente, si hay anomalia (respetando cooldown)
Cliente -> ack (con mitigation_active/type) -> Servidor
Cliente -> metric recuperada -> Servidor
```

## Endpoint de estado (/api/state)

El dashboard expone `/api/state` como fuente única de verdad, consultado cada 1s.
Responde con un snapshot JSON que incluye:

- Estado del servidor (online/offline, puerto)
- Nodos activos con última métrica, mitigación y antigüedad
- Series temporales de métricas
- Últimos comandos y ACKs
- Eventos combinados ordenados cronológicamente
- Últimas líneas de log

Ver `docs/frontend-realtime.md` para la especificación completa del payload.
