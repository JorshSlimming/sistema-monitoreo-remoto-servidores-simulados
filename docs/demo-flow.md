# Flujo de demostración

Este documento describe el flujo paso a paso para la demostración del sistema en la presentación final del curso de Redes de Computadores.

## Prerrequisitos

- Python 3.11+
- Acceso a terminal (4 ventanas recomendadas)
- Navegador web para el dashboard

## Estructura de la demostración

La demo completa toma aproximadamente **10-12 minutos** y cubre:

| Paso | Duración | Qué se demuestra |
|---|---|---|
| 1. Inicio del sistema | 1 min | Servidor + frontend |
| 2. Nodo normal | 1 min | Métrica base sin anomalías |
| 3. Anomalía de CPU | 2 min | Detección, mitigación y comando |
| 4. Anomalía de RAM | 1 min | Segundo tipo de anomalía |
| 5. Múltiples nodos | 2 min | Concurrencia |
| 6. Reconexión | 1 min | Tolerancia a fallos |
| 7. Dashboard | 2 min | Exploración de la interfaz |
| 8. Evidencia | 1 min | Generación de artefactos |

---

## Paso 1: Inicio del sistema

**Terminal 1:**

```bash
make present
```

Esto inicia:
- Servidor TCP en `127.0.0.1:5000`
- Dashboard HTTP en `http://localhost:8080`
- Clientes reales persistentes para la demo

Perfil por defecto de `make present`:
- `node-01` normal
- `node-02` high-cpu
- `node-03` high-latency

**Verificar:**
- Log muestra `[tcp-server] listening on 0.0.0.0:5000`
- Log muestra `[panel] Dashboard on http://0.0.0.0:8080`
- Navegador en `http://localhost:8080` muestra el dashboard

```bash
# Verificar conectividad
curl -s http://localhost:8080/api/state | python3 -m json.tool | head -20
```

---

## Paso 2: Nodo normal

**Alternativa manual (si quieres controlar cada nodo por separado):**

```bash
MODE=normal NODE_ID=node-01 INTERVAL=3.0 make client
```

**Qué observar:**
- El cliente envía métricas base cada 5 segundos.
- El servidor no emite comandos (todas las métricas en rango normal).
- El dashboard muestra `node-01` con CPU≈35, RAM≈45, latencia≈40ms.
- No hay badge de mitigación.

---

## Paso 3: Anomalía de CPU

**Escenario CPU manual:**

```bash
MODE=high-cpu NODE_ID=node-02 INTERVAL=3.0 make client
```

**Qué observar:**
1. El dashboard muestra `node-02` con CPU≈95 (valor anómalo).
2. Aparece badge `🛡 Mitigación: reduce_cpu`.
3. El servidor emite comando `reduce_cpu` (visible en logs y en la tabla de eventos).
4. El cliente confirma con ACK (visible en eventos).
5. Gradualmente, la CPU de node-02 baja hasta valores normales.
6. El badge de mitigación desaparece cuando la métrica se normaliza.

**Verificar:**

```bash
# Comandos emitidos
curl -s http://localhost:8080/api/state | python3 -c "
import json,sys
d = json.load(sys.stdin)
for c in d.get('commands', []):
    print(f\"  [{c['status']}] node={c['node_id']} action={c['action']} cmd_id={c['command_id']}\")
"
```

---

## Paso 4: Anomalía de RAM

En la misma terminal 3 (o terminal 4):

```bash
MODE=high-ram NODE_ID=node-03 INTERVAL=3.0 make client
```

**Qué observar:**
- Anomalía de RAM (≈94).
- Mitigación local `reduce_ram`.
- Comando `reduce_ram` del servidor.
- Recuperación gradual.

---

## Paso 5: Múltiples nodos simultáneos

Ejecutar en terminales separadas:

```bash
# Terminal 2: nodo normal
python3 -m client.tcp_client --node-id node-01 --mode normal --interval 3.0

# Terminal 3: anomalía CPU
python3 -m client.tcp_client --node-id node-02 --mode high-cpu --interval 5.0

# Terminal 4: anomalía latencia
python3 -m client.tcp_client --node-id node-03 --mode high-latency --interval 4.0
```

**Qué observar:**
- Los tres nodos aparecen en el dashboard.
- Cada nodo tiene sus propias métricas y estado de mitigación.
- node-02 muestra badge `reduce_cpu`, node-03 muestra `fix_latency`.
- node-01 permanece sin mitigación.
- El servidor maneja las tres conexiones concurrentemente.
- La desconexión de un nodo no afecta a los demás.

---

## Paso 6: Reconexión

1. Con node-01 corriendo, matar el servidor (`Ctrl+C` en terminal 1).
2. Observar en terminal 2: `connection lost ... reconnecting in 5s...`
3. Reiniciar el servidor (`./scripts/run_project.sh`).
4. El cliente se reconecta automáticamente y continúa enviando métricas.
5. El contador `seq` continúa desde donde quedó.

---

## Paso 7: Exploración del dashboard

- **Solapa de nodos:** cada nodo con métricas en vivo.
- **Gráfico:** series temporales de CPU, RAM o latencia.
- **Eventos:** historial de comandos y ACKs.
- **Logs:** registros del sistema.
- **Filtro de métrica:** alternar entre CPU, RAM y latencia en el gráfico.

---

## Paso 8: Generación de evidencia

```bash
# Generar artefactos completos
./scripts/generate_demo_artifacts.sh

# O usando el Makefile
make evidence
```

Los artefactos se guardan en `artifacts/demo/`.

Ver `docs/evidence/README.md` para la descripción de cada archivo generado.

---

## Paso opcional 9: Simulación de ataques (defensa en profundidad)

Si el tiempo lo permite, ejecutar el simulador de ataques para demostrar
que el protocolo resiste intentos de bypass:

```bash
make attack
```

Esto ejecuta 7 ataques controlados y muestra cuáles fueron detectados
correctamente. También se puede generar evidencia de ataque:

```bash
make attack-evidence
```

Los resultados quedan en `artifacts/demo/attack_results_<timestamp>.json`.

Ver `docs/attack-simulation.md` para más detalles.

---

## Resumen de verificación

| Aspecto | Comando de verificación |
|---|---|
| Servidor activo | `curl -s http://localhost:8080/api/status` |
| Estado completo | `curl -s http://localhost:8080/api/state \| python3 -m json.tool` |
| Pruebas unitarias | `make test` |
| DB persistencia | `sqlite3 data/monitor.db ".tables"` |
| Nmap | `nmap -p 5000 127.0.0.1` |
