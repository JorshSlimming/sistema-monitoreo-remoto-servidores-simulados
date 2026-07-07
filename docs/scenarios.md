# Escenarios de prueba

Este documento describe los escenarios verificables del sistema, el procedimiento para ejecutarlos y los resultados esperados.

## Prerrequisitos

```bash
# Todas las terminales desde la raíz del repositorio
cd /home/benja/projects/sistema-monitoreo-remoto-servidores-simulados
```

## Escenario 1 — Nodo normal

Enviar una métrica base y verificar que el servidor la recibe sin emitir comandos.

**Terminal 1 — Servidor:**
```bash
python3 -m server.tcp_server
```

**Terminal 2 — Cliente normal:**
```bash
python3 -m client.tcp_client --node-id node-01 --mode normal
```

**Resultado esperado:**
```
[server] listening on 0.0.0.0:5000
[server] client connected from 127.0.0.1:XXXXX
[metric] node-01: {'type': 'metric', 'node_id': 'node-01', 'seq': 0, ...}
```
El servidor **no** envía comandos porque todas las métricas están en rango normal.

---

## Escenario 2 — Anomalía de CPU

El cliente envía CPU=95 y el servidor responde con `reduce_cpu`.

**Terminal 1:**
```bash
python3 -m server.tcp_server
```

**Terminal 2:**
```bash
python3 -m client.tcp_client --node-id node-01 --mode high-cpu
```

**Resultado esperado:**
```
[server] client connected from 127.0.0.1:XXXXX
[metric] node-01: {'type': 'metric', 'node_id': 'node-01', 'cpu': 95.0, ...}
[command] node-01: {'type': 'command', 'command_id': 1, 'action': 'reduce_cpu', 'reason': 'cpu above 90'}
```
El cliente recibe el comando, aplica la mitigación simulada y responde con un ACK:
```
[client] ack sent for command 1: reduce_cpu
```
En las métricas siguientes, la CPU vuelve al valor normal simulado.

---

## Escenario 3 — Anomalía de RAM

```bash
# Terminal 2
python3 -m client.tcp_client --node-id node-01 --mode high-ram
```

**Resultado esperado:** Comando `reduce_ram` emitido por el servidor.

---

## Escenario 4 — Latencia alta

```bash
python3 -m client.tcp_client --node-id node-01 --mode high-latency
```

**Resultado esperado:** Comando `fix_latency` emitido.

---

## Escenario 5 — Servicio en falla

```bash
python3 -m client.tcp_client --node-id node-01 --mode service-failure
```

**Resultado esperado:** Comando `restart_service` emitido.

---

## Escenario 6 — Evento fallido

```bash
python3 -m client.tcp_client --node-id node-01 --mode failed-event
```

**Resultado esperado:** Comando `normalize_node` emitido.

---

## Escenario 7 — Tres nodos simultáneos

**Terminal 1 — Servidor:**
```bash
python3 -m server.tcp_server
```

**Terminales 2, 3, 4 — Clientes:**
```bash
python3 -m client.tcp_client --node-id node-01 --mode normal --interval 3.0
python3 -m client.tcp_client --node-id node-02 --mode high-cpu --interval 5.0
python3 -m client.tcp_client --node-id node-03 --mode high-latency --interval 4.0
```

**Resultado esperado:** Los tres nodos se conectan y envían métricas. El servidor maneja las
conexiones concurrentemente (un hilo por nodo). Solo `node-02` y `node-03` reciben comandos.
La desconexión de un nodo no afecta a los demás.

---

## Escenario 8 — Token inválido

Enviar una métrica con token incorrecto.

```bash
python3 -m client.tcp_client --node-id node-99 --mode normal
```

O usando herramientas de red directamente:

```bash
echo '{"type":"metric","node_id":"node-01","seq":1,"cpu":50,"ram":50,"latency_ms":30,"service_web":"ok","event_log":"normal","token":"wrong"}' | nc -q1 127.0.0.1 5000
```

**Resultado esperado:** El servidor responde con un error `AUTH_FAILED` y **no** persiste la métrica.

---

## Escenario 9 — JSON mal formado

Enviar datos que no son JSON válido.

```bash
echo "HJDASDJAHADADA" | nc -q1 127.0.0.1 5000
```

**Resultado esperado:** El servidor responde con error `INVALID_JSON`.

---

## Escenario 10 — Caída y reconexión

1. Iniciar servidor y cliente.
2. Verificar que el cliente envía métricas.
3. Matar el servidor (Ctrl+C).
4. El cliente muestra: `connection lost (ConnectionRefusedError); reconnecting in 5s...`
5. Reiniciar el servidor.
6. El cliente se reconecta automáticamente y reanuda el envío de métricas (el contador `seq` continúa).

---

## Escenario 11 — Verificar persistencia SQLite

Ejecutar el servidor, conectar un cliente con anomalía, y revisar la base de datos.

```bash
# Iniciar servidor, luego en otra terminal:
python3 -m client.tcp_client --node-id node-01 --mode high-cpu --interval 2.0
# Esperar unos segundos, luego:
sqlite3 data/monitor.db "SELECT * FROM metrics;"
sqlite3 data/monitor.db "SELECT * FROM commands;"
sqlite3 data/monitor.db "SELECT * FROM acks;"
```

**Resultado esperado:** Las tres tablas contienen filas con los datos de la sesión.

---

## Pruebas automáticas

```bash
python3 -m unittest discover -s tests -v
```

Ejecuta 23 pruebas que cubren:
- Construcción de métricas en todos los modos
- Codificación/decodificación de mensajes
- Estados del servidor (timeout, confirmación)
- Persistencia real con SQLite (métrica, comando, ACK)
