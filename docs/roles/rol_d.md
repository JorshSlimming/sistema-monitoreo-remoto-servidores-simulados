# Rol D - Persistencia, pruebas y analisis de red

## Responsable

Por definir segun el grupo.

## Estado

Implementado. Persistencia SQLite (monitor.db) con 3 tablas, pruebas unitarias y de integración automáticas, scripts de escenario, captura de tráfico con tshark, escaneo Nmap documentado.

## Responsabilidad principal

Convertir el funcionamiento del sistema en evidencia reproducible. Este rol implementa persistencia, prepara pruebas, automatiza escenarios y documenta el comportamiento de red con Wireshark y, si corresponde, Nmap en el entorno autorizado.

## Archivos reales

```text
storage/store.py              Persistencia SQLite (métricas, comandos, ACKs)
tests/test_persistence.py     Integración: servidor real + SQLite
tests/test_tcp_client.py      Unitarias: formato y construcción de métricas
tests/test_server_state.py    Unitarias: estados del servidor
tests/mock_server.py          Servidor TCP mínimo para pruebas aisladas
tests/malformed_json_client.py Prueba de respuesta a JSON inválido
scripts/run_all_tests.sh      Ejecuta `unittest discover`
scripts/run_server.sh         Inicia el servidor TCP
scripts/run_client.sh         Inicia el cliente persistente
scripts/run_scenario.sh       Ejecuta escenarios de prueba completos
scripts/reset_environment.sh  Limpia BD, capturas y __pycache__
scripts/run_project.sh        Levanta servidor + panel frontend
scripts/stop_project.sh       Detiene el proyecto
scripts/capture_traffic.sh    Captura tráfico con tcpdump
scripts/generate_demo_artifacts.sh  Pipeline completo de evidencia
```

## Persistencia implementada

SQLite con tres tablas (ver `storage/store.py`):

**Tabla `metrics`** — cada métrica recibida:

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER | Clave primaria (autoincremental) |
| `node_id` | TEXT | Identificador del nodo |
| `seq` | INTEGER | Secuencia del cliente |
| `cpu` | REAL | Porcentaje de CPU (0-100) |
| `ram` | REAL | Porcentaje de RAM (0-100) |
| `latency_ms` | REAL | Latencia en milisegundos |
| `service_web` | TEXT | Estado del servicio web (`ok`/`falla`) |
| `event_log` | TEXT | Descripción de evento |
| `received_at` | TEXT | Timestamp UTC ISO 8601 |

**Tabla `commands`** — comandos emitidos por el servidor:

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER | Clave primaria |
| `command_id` | INTEGER | ID del comando |
| `action` | TEXT | Acción (`reduce_cpu`, etc.) |
| `reason` | TEXT | Motivo del comando |
| `node_id` | TEXT | Nodo destino |
| `status` | TEXT | `pending`, `timed_out`, `confirmed` o `failed` |
| `issued_at` | TEXT | Timestamp ISO 8601 |

**Tabla `acks`** — confirmaciones de los clientes:

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER | Clave primaria |
| `command_id` | INTEGER | ID del comando confirmado |
| `node_id` | TEXT | Nodo que respondió |
| `status` | TEXT | `applied` o `failed` |
| `received_at` | TEXT | Timestamp ISO 8601 |

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

