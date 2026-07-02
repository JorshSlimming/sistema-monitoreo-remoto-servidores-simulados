# Rol D - Persistencia, pruebas y analisis de red

## Responsable

Por definir segun el grupo.

## Estado

Pendiente.

## Responsabilidad principal

Convertir el funcionamiento del sistema en evidencia reproducible. Este rol implementa persistencia, prepara pruebas, automatiza escenarios y documenta el comportamiento de red con Wireshark y, si corresponde, Nmap en el entorno autorizado.

## Archivos sugeridos

```text
storage/repository.py
storage/sqlite_store.py
storage/event_logger.py
storage/query_history.py
storage/storage_config.json
tests/test_protocol.py
tests/test_client_server.py
tests/test_reconnection.py
tests/test_multiple_clients.py
tests/test_invalid_messages.py
tests/integration_runner.py
scripts/run_server.ps1
scripts/run_clients.ps1
scripts/reset_environment.ps1
scripts/capture_traffic.ps1
```

## Persistencia esperada

Se recomienda SQLite con campos minimos:

```text
timestamp
node_id
cpu
ram
latency_ms
service_web
event_log
alerta_detectada
comando_enviado
respuesta_del_cliente
```

Consultas utiles:

- ultimo estado de cada nodo;
- historial de alertas;
- historial de comandos enviados;
- confirmaciones de comandos aplicados;
- metricas antes y despues de mitigacion;
- mensajes rechazados por formato o autenticacion.

## Escenarios de prueba

- Un nodo normal.
- Tres nodos conectados simultaneamente.
- Nodo con CPU alta.
- Nodo con RAM alta.
- Nodo con latencia alta.
- Servicio en estado de falla.
- JSON invalido.
- Token incorrecto.
- Caida del servidor.
- Reconexion automatica del cliente.
- Puerto TCP visible desde el entorno autorizado.

## Evidencia de red

Preparar capturas o evidencia de:

- handshake TCP: `SYN`, `SYN-ACK`, `ACK`;
- envio de metricas;
- envio de comandos;
- confirmacion del cliente;
- cierre de conexion;
- reconexion automatica;
- escaneo Nmap solo contra IP o maquina virtual autorizada.

Filtros iniciales de Wireshark:

```text
tcp.port == 5000
ip.addr == IP_DEL_SERVIDOR && tcp.port == 5000
```

## Criterio de termino

```text
Nodo reporta CPU=95
-> se registra la alerta
-> se registra reduce_cpu
-> cliente responde ACK
-> nodo reporta CPU normal
-> SQLite muestra la secuencia completa
-> Wireshark muestra el trafico
```

