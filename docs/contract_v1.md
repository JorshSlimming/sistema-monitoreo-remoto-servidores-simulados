# Contrato Tecnico v1

Este documento define el contrato que deben respetar cliente, servidor, validacion
y persistencia.

## Decisiones base

| Elemento | Decision |
|---|---|
| Lenguaje | Python 3.11+ |
| Transporte | TCP |
| Puerto por defecto | 5000 |
| Host servidor | 0.0.0.0 |
| Codificacion | UTF-8 |
| Formato de linea | JSON Lines, un objeto JSON terminado en `\n` |
| Seguridad de sesion | PSK por nodo + desafio con nonce + frames cifrados |
| Mensajes de aplicacion | `metric`, `command`, `ack`, `error` |
| Reconexion cliente | Cada 5 segundos |
| Persistencia | SQLite, tablas `metrics`, `commands`, `acks` |
| Polling frontend | Cada 1 segundo a `/api/state` |
| Cooldown anti-spam | 12s para comandos duplicados |
| Mitigacion cliente | Local, gradual por tipo de anomalia |

## Autenticacion PSK y canal seguro

Cada nodo tiene una clave precompartida definida en `shared/auth.py`. La demo
incluye 32 PSK listas, desde `node-01` hasta `node-32`, con el patron
`node-XX-secret`. Al abrir la conexion TCP, el cliente no envia metricas
inmediatamente: primero realiza un handshake de autenticacion.

Flujo de handshake:

```text
Cliente -> Servidor: {"type":"hello","node_id":"node-01"}
Servidor -> Cliente: {"type":"challenge","node_id":"node-01","nonce":"..."}
Cliente -> Servidor: {"type":"challenge_response","client_nonce":"...","proof":"..."}
Servidor -> Cliente: {"type":"ready","node_id":"node-01"}
```

Si el nodo no existe o la prueba HMAC no coincide, el servidor responde
`AUTH_FAILED` y cierra la sesion. Si la autenticacion es valida, ambas partes
derivan una clave de sesion desde la PSK, el nonce del servidor y el nonce del
cliente. Desde ese punto, los mensajes de aplicacion viajan dentro de frames:

```json
{
  "type": "secure",
  "seq": 0,
  "nonce": "...",
  "ciphertext": "...",
  "tag": "..."
}
```

El payload cifrado contiene el mensaje real (`metric`, `command`, `ack` o
`error`). La implementacion usa biblioteca estandar de Python: HMAC-SHA256 para
autenticacion/integridad y una secuencia derivada de HMAC para cifrado simetrico
de demo. Para produccion se recomienda reemplazarlo por TLS o una AEAD auditada.

## Mensaje `metric`

Ejemplo de payload despues de descifrar el frame seguro:

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
| `node_id` | string | Debe coincidir con el nodo autenticado en el canal |
| `seq` | integer | Mayor o igual a 0 |
| `cpu` | number | Entre 0 y 100 |
| `ram` | number | Entre 0 y 100 |
| `latency_ms` | number | Mayor o igual a 0 |
| `service_web` | string | `ok` o `falla` |
| `event_log` | string | Texto descriptivo |
| `token` | string | Token/PSK valido para compatibilidad interna |
| `mitigation_active` | bool | Opcional; true si hay mitigacion activa |
| `mitigation_type` | string | Opcional; ej. `reduce_cpu` |

## Mensaje `command`

```json
{
  "type": "command",
  "command_id": 1,
  "action": "reduce_cpu",
  "reason": "cpu above 90"
}
```

Estados persistidos del comando:

- `pending`: emitido, esperando confirmacion.
- `confirmed`: ACK `applied` recibido.
- `failed`: ACK `failed` recibido.
- `timed_out`: no se recibio ACK dentro del plazo.

Acciones validas:

- `reduce_cpu`
- `reduce_ram`
- `fix_latency`
- `restart_service`
- `normalize_node`

## Mensaje `ack`

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

## Mensaje `error`

```json
{
  "type": "error",
  "code": "INVALID_MESSAGE",
  "message": "cpu must be between 0 and 100"
}
```

Codigos principales:

- `INVALID_JSON`
- `INVALID_MESSAGE`
- `HANDSHAKE_REQUIRED`
- `AUTH_FAILED`
- `SERVER_ERROR`

## Reglas de anomalia

| Condicion | Comando |
|---|---|
| `cpu > 90` | `reduce_cpu` |
| `ram > 90` | `reduce_ram` |
| `latency_ms > 200` | `fix_latency` |
| `service_web == "falla"` | `restart_service` |
| `event_log` contiene `fallido` | `normalize_node` |

## Flujo esperado

```text
Cliente -> hello
Servidor -> challenge
Cliente -> challenge_response
Servidor -> ready
Cliente -> secure(metric)
Servidor -> secure(command), si hay anomalia
Cliente -> secure(ack)
Cliente -> secure(metric recuperada)
```

## Endpoint de estado (`/api/state`)

El dashboard expone `/api/state` como fuente unica de verdad, consultado cada 1s.
Responde con un snapshot JSON que incluye:

- Estado del servidor TCP.
- Nodos activos con ultima metrica, mitigacion y antiguedad.
- Series temporales de metricas.
- Ultimos comandos y ACKs.
- Eventos combinados ordenados cronologicamente.
- Ultimas lineas de log.

Ver `docs/frontend-realtime.md` para la especificacion completa del payload.
