# Rol B - Cliente o nodo simulado

## Responsable

Por definir segun el grupo.

## Estado

Pendiente.

## Responsabilidad principal

Implementar el programa que simula un servidor monitoreado. El nodo debe generar metricas, provocar fallos controlados, enviar reportes al servidor, recibir comandos de mitigacion y reconectarse si la conexion cae.

## Archivos sugeridos

```text
client/node_simulator.py
client/metrics_generator.py
client/state_manager.py
client/command_handler.py
client/reconnect_manager.py
client/client_config.json
```

## Funciones esperadas

- Generar metricas periodicas:
  - `node_id`
  - `seq`
  - `cpu`
  - `ram`
  - `latency_ms`
  - `service_web`
  - `event_log`
  - `token`
- Soportar modos de simulacion:
  - normal;
  - CPU alta;
  - RAM alta;
  - latencia alta;
  - servicio web en falla;
  - evento fallido.
- Conectarse por TCP al servidor.
- Enviar mensajes JSON terminados en `\n`.
- Recibir comandos sin detener el envio de metricas.
- Aplicar mitigaciones:
  - `reduce_cpu`;
  - `reduce_ram`;
  - `fix_latency`;
  - `restart_service`;
  - `normalize_node`.
- Enviar `ack` cuando aplica un comando.
- Reintentar conexion cada 5 segundos si el servidor cae.
- Mantener un registro local simple de comandos recibidos.

## Criterio de termino

```text
Nodo inicia normal
-> se activa CPU alta
-> reporta CPU=95
-> recibe reduce_cpu
-> baja la CPU simulada
-> envia ACK
-> reporta CPU dentro de rango
```

Tambien debe demostrar reconexion:

```text
Servidor se apaga
-> cliente detecta desconexion
-> reintenta cada 5 segundos
-> servidor vuelve
-> cliente se reconecta
```

