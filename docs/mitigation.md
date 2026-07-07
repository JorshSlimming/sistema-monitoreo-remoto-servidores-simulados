# Mitigación del lado cliente

## Visión general

El sistema implementa mitigación real en el lado cliente, pero **se activa cuando el nodo recibe un comando correctivo del servidor**. Desde ese momento el estado interno del cliente cambia y las métricas siguientes muestran la recuperación progresiva.

## Comportamiento

Cuando el cliente se ejecuta en un modo con anomalía (`high-cpu`, `high-ram`, `high-latency`, etc.):

1. **Primera métrica anómala:** el cliente reporta el valor alto para que el servidor detecte la anomalía.
2. **Comando correctivo:** el servidor envía `reduce_cpu`, `reduce_ram`, `fix_latency`, `restart_service` o `normalize_node`.
3. **Mitigación real en el cliente:** al recibir el comando, el cliente muta su `ClientState` y las métricas siguientes se acercan al baseline.
4. **Reporte de mitigación:** cada métrica incluye los campos:
   - `mitigation_active`: `true` mientras la mitigación está en curso, `false` cuando la métrica vuelve a rango normal.
   - `mitigation_type`: cadena descriptiva (ej. `"reduce_cpu"`, `"reduce_ram"`, `"fix_latency"`).
5. **Continuidad:** el cliente sigue enviando métricas periódicamente durante la mitigación.
6. **ACKs enriquecidos:** cuando el cliente responde al comando, el ACK incluye información `before`/`after` del estado interno.

## Cooldown anti-spam del servidor

El servidor (`server/server_state.py`) implementa un cooldown de **12 segundos** (configurable) que:

- Evita emitir comandos duplicados si el mismo nodo ya confirmó la misma acción recientemente.
- Si un comando con estado `confirmed` tiene menos de `cooldown_seconds` de antigüedad, se rechaza el nuevo comando duplicado con una advertencia en logs (`[cooldown] ... was confirmed recently`).
- Los comandos en estado `pending` o con expiración no afectan el cooldown.

Esto previene tormentas de comandos cuando un nodo envía métricas anómalas repetidas.

## Mecánica de mitigación por modo

| Modo | Métrica anómala | Mitigación local | Comando del servidor |
|---|---|---|---|
| `high-cpu` | cpu=95 | Tras `reduce_cpu`, baja gradualmente | `reduce_cpu` |
| `high-ram` | ram=94 | Tras `reduce_ram`, baja gradualmente | `reduce_ram` |
| `high-latency` | latency_ms=350 | Tras `fix_latency`, baja gradualmente | `fix_latency` |
| `service-failure` | service_web="falla" | N/A (mitigación vía servidor) | `restart_service` |
| `failed-event` | event_log con "fallido" | N/A (mitigación vía servidor) | `normalize_node` |

## Visualización en el dashboard

Cuando un nodo tiene mitigación activa, el dashboard muestra:
- Una etiqueta `🛡 Mitigación: <tipo>` en la tarjeta del nodo.
- El badge se actualiza automáticamente con cada ciclo de polling (1s).
- Una vez que la mitigación termina, la etiqueta desaparece.

## Secuencia típica

```
Cliente envía métrica CPU=95 ───→ servidor detecta anomalía
Servidor emite reduce_cpu ─────→ cliente recibe comando
Cliente aplica mitigación real ─→ reduce CPU gradualmente
Cliente confirma con ACK enriquecido
Cliente sigue mitigando ────────→ CPU vuelve a rango normal
Cliente envía métrica con mitigation_active=false
```

## Contrato de mensajes

Los campos `mitigation_active` y `mitigation_type` se incluyen en:

- **Métricas:** enviadas por el cliente en cada mensaje.
- **ACKs:** confirmación de comandos con `before`/`after` y metadatos del comando.

Ver `docs/contract_v1.md` para la especificación completa de campos.
