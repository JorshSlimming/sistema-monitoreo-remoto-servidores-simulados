# Rol C - Protocolo, validacion y reglas

## Responsable

Por definir segun el grupo.

## Estado

Pendiente.

## Responsabilidad principal

Mantener la logica compartida que define como se validan los mensajes, como se autentican los nodos y como una anomalia se transforma en un comando de mitigacion.

## Archivos sugeridos

```text
shared/protocol.py
shared/message_schema.py
shared/validator.py
shared/auth.py
shared/anomaly_rules.py
shared/command_rules.py
shared/config.py
```

## Funciones esperadas

- Validar JSON correctamente formado.
- Validar campos obligatorios.
- Validar tipos de datos.
- Validar rangos:
  - CPU entre 0 y 100;
  - RAM entre 0 y 100;
  - latencia mayor o igual a 0.
- Validar `node_id` no vacio.
- Validar tipos de mensaje permitidos.
- Validar token estatico por nodo.
- Rechazar mensajes invalidos sin botar el servidor.
- Detectar anomalias:
  - `cpu > 90`;
  - `ram > 90`;
  - `latency_ms > 200`;
  - `service_web == "falla"`;
  - `event_log` contiene `fallido`.
- Elegir comandos:
  - CPU alta -> `reduce_cpu`;
  - RAM alta -> `reduce_ram`;
  - latencia alta -> `fix_latency`;
  - servicio en falla -> `restart_service`;
  - evento fallido -> `normalize_node`.

## Criterio de termino

```text
Mensaje valido -> aceptado
CPU=95 -> cpu_high + reduce_cpu
Latencia=400 -> latency_high + fix_latency
JSON malformado -> rechazado
CPU=150 -> rechazado
Token incorrecto -> rechazado
Servicio web en falla -> restart_service
```

