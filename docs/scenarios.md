# Escenarios de prueba

Este documento describe los escenarios verificables del sistema, el procedimiento para ejecutarlos y los resultados esperados.

## Dashboard recomendado

Para todos los escenarios, es útil tener el dashboard abierto:

```bash
# Terminal 1: Proyecto completo
./scripts/run_project.sh
```

El dashboard en `http://localhost:8080` muestra en tiempo real los nodos, mitigaciones,
comandos y ACKs. Alternativamente, se puede ver el estado via API:

```bash
curl -s http://localhost:8080/api/state | python3 -m json.tool
```

---

## Escenario 1 — Nodo normal

Enviar una métrica base y verificar que el servidor la recibe sin emitir comandos.

**Terminal 2 — Cliente normal:**
```bash
python3 -m client.tcp_client --node-id node-01 --mode normal
```

**Resultado esperado:**
- El servidor recibe métricas sin emitir comandos (todo en rango normal).
- El dashboard muestra `node-01` con CPU≈35, RAM≈45, latencia≈40ms.
- No hay badge de mitigación.
- El endpoint `/api/state` muestra `mitigation_active: false`.

---

## Escenario 2 — Anomalía de CPU

El cliente envía CPU=95, el servidor responde con `reduce_cpu` y el nodo cambia su estado interno.

**Terminal 2:**
```bash
python3 -m client.tcp_client --node-id node-02 --mode high-cpu
```

**Resultado esperado:**
1. El dashboard muestra la anomalía de CPU.
2. El servidor emite comando `reduce_cpu` (visible en eventos del dashboard).
3. El cliente confirma con ACK enriquecido.
4. Las métricas siguientes bajan gradualmente y aparece badge `🛡 Mitigación: reduce_cpu`.
5. CPU vuelve gradualmente a rango normal; badge de mitigación desaparece.

---

## Escenario 3 — Anomalía de RAM

```bash
# Terminal 2
python3 -m client.tcp_client --node-id node-03 --mode high-ram
```

**Resultado esperado:** Comando `reduce_ram` emitido por el servidor y recuperación gradual de RAM en métricas posteriores.

---

## Escenario 4 — Latencia alta

```bash
python3 -m client.tcp_client --node-id node-01 --mode high-latency
```

**Resultado esperado:** Comando `fix_latency` emitido y recuperación gradual de latencia en métricas posteriores.

---

## Escenario 5 — Servicio en falla

```bash
python3 -m client.tcp_client --node-id node-01 --mode service-failure
```

**Resultado esperado:** Comando `restart_service` emitido (mitigación por servidor).

---

## Escenario 6 — Evento fallido

```bash
python3 -m client.tcp_client --node-id node-01 --mode failed-event
```

**Resultado esperado:** Comando `normalize_node` emitido (mitigación por servidor).

---

## Escenario 7 — Tres nodos simultáneos

**Terminales 2, 3, 4 — Clientes:**
```bash
python3 -m client.tcp_client --node-id node-01 --mode normal --interval 3.0
python3 -m client.tcp_client --node-id node-02 --mode high-cpu --interval 5.0
python3 -m client.tcp_client --node-id node-03 --mode high-latency --interval 4.0
```

**Resultado esperado:** Los tres nodos aparecen en el dashboard. Solo `node-02` y `node-03`
muestran mitigación activa. El servidor maneja las conexiones concurrentemente.
La desconexión de un nodo no afecta a los demás.

---

## Escenario 8 — Token inválido

Enviar una métrica con token incorrecto.

```bash
python3 -m client.tcp_client --node-id node-99 --mode normal
```

O usando netcat:

```bash
echo '{"type":"metric","node_id":"node-01","seq":1,"cpu":50,"ram":50,"latency_ms":30,"service_web":"ok","event_log":"normal","token":"wrong"}' | nc -q1 127.0.0.1 5000
```

**Resultado esperado:** El servidor responde con error `AUTH_FAILED` y **no** persiste la métrica.

---

## Escenario 9 — JSON mal formado

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
6. El cliente se reconecta automáticamente y reanuda el envío (el contador `seq` continúa).

---

## Escenario 11 — Verificar persistencia SQLite

```bash
# Iniciar servidor, luego en otra terminal:
python3 -m client.tcp_client --node-id node-01 --mode high-cpu --interval 2.0
# Esperar unos segundos, luego:
sqlite3 data/monitor.db "SELECT * FROM metrics;"
sqlite3 data/monitor.db "SELECT * FROM commands;"
sqlite3 data/monitor.db "SELECT * FROM acks;"
```

**Resultado esperado:** Las tres tablas contienen filas. Las métricas incluyen campos
`mitigation_active` y `mitigation_type`. Los comandos tienen estado (`pending`, `confirmed`, `timed_out`).

---

## Pruebas automáticas

```bash
make test
# o
python3 -m unittest discover -s tests -v
```

Ejecuta **45 pruebas** que cubren:
- Construcción de métricas en todos los modos
- Codificación/decodificación de mensajes
- Estados del servidor (timeout, confirmación)
- Cooldown anti-spam (evita comandos duplicados)
- Mitigación progresiva real del cliente tras recibir comando
- Persistencia real con SQLite (métrica, comando, ACK)
- Actualización de estado de comandos al recibir ACK
- Construcción del payload `/api/state`
- Autenticación multi-nodo

## Verificación rápida con API REST

```bash
# Estado básico del dashboard
curl -s http://localhost:8080/api/status

# Estado completo del sistema (JSON)
curl -s http://localhost:8080/api/state | python3 -m json.tool

# Filtrar solo comandos
curl -s http://localhost:8080/api/state | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('Servidor:', d['server']['running'])
print('Nodos activos:', ', '.join(d['server']['active_nodes']))
for c in d.get('commands', []):
    print(f\"  [{c['status']}] {c['node_id']}: {c['action']}\")
"
```
