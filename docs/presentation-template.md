# Presentación — Sistema de Monitoreo Remoto de Servidores Simulados

**Duración estimada:** 10-15 minutos
**Formato sugerido:** PowerPoint, Google Slides, o PDF con transiciones.

---

## Diapositiva 1 — Portada

- **Título:** Sistema de Monitoreo Remoto de Servidores Simulados
- **Curso:** Redes de Computadores
- **Institución:** _[completar]_
- **Integrantes:** _[nombres]_
- **Fecha:** _[completar]_

---

## Diapositiva 2 — Problema y solución

- **Problema:** Monitorear servidores remotos para detectar anomalías sin intervención humana.
- **Solución:** Sistema cliente-servidor TCP que recolecta métricas, detecta anomalías en tiempo real y emite comandos correctivos automáticos.
- **Conceptos de redes aplicados:** TCP (conexión, handshake, transmisión), sockets, direccionamiento IP, puertos.

---

## Diapositiva 3 — Arquitectura

Diagrama de arquitectura (insertar imagen de `docs/architecture.md`).

Componentes clave:
- Servidor central (TCP, multihilo)
- Clientes persistentes (reconexión automática)
- Autenticación por token
- Persistencia SQLite

---

## Diapositiva 4 — Protocolo de comunicación

- **Transporte:** TCP
- **Puerto:** 5000
- **Formato:** JSON Lines (JSON + `\n`)
- **4 tipos de mensaje:**

| Tipo | Dirección | Propósito |
|---|---|---|
| `metric` | Cliente → Servidor | Enviar métricas |
| `command` | Servidor → Cliente | Orden correctiva |
| `ack` | Cliente → Servidor | Confirmar comando |
| `error` | Servidor → Cliente | Notificar error |

Breve demo visual (opcional): mostrar JSON de ejemplo.

---

## Diapositiva 5 — Reglas de anomalía

| Condición | Comando |
|---|---|
| CPU > 90% | `reduce_cpu` |
| RAM > 90% | `reduce_ram` |
| Latencia > 200ms | `fix_latency` |
| service_web == "falla" | `restart_service` |
| event_log contiene "fallido" | `normalize_node` |

---

## Diapositiva 6 — Demo en vivo

Escenarios a mostrar (elegir 2-3 según tiempo):
1. Nodo normal + nodo con anomalía de CPU.
2. Tres nodos simultáneos.
3. Reconexión automática tras caída del servidor.
4. Verificación SQLite.

> **Nota:** Tener terminales preparadas con comandos copiados para agilizar la demo.

---

## Diapositiva 7 — Evidencia de red

### Captura Wireshark
- Handshake TCP (SYN, SYN-ACK, ACK)
- Métrica JSON viajando por la red
- Comando del servidor al cliente

### Escaneo Nmap
- Puerto 5000 visible como `open`
- Verificación desde máquina virtual o segundo equipo

Insertar capturas de pantalla.

---

## Diapositiva 8 — Pruebas

```bash
python3 -m unittest discover -s tests -v
```

- 18 pruebas unitarias y de integración.
- Cobertura: métricas, encoding, estados del servidor, persistencia real.
- Todas pasan.

Insertar captura de pantalla de la ejecución.

---

## Diapositiva 9 — Conclusiones

### Logros
- Sistema funcional completo con cliente real.
- Detección y corrección automática de 5 tipos de anomalía.
- Persistencia de toda la actividad.
- Reconexión automática del cliente.

### Limitaciones
- Tokens estáticos (mejorable con JWT o base de datos).
- Sin cifrado (mejorable con TLS).
- Un solo servidor (mejorable con balanceo).

### Trabajo futuro
- Dashboard web para visualización en tiempo real.
- Notificaciones por email o Slack.
- Sistema multi-servidor con replicación.

---

## Diapositiva 10 — Preguntas

- Espacio para preguntas del jurado.
- Contacto / enlace al repositorio.

---

> **Nota:** Esta es una plantilla en Markdown. Para la presentación final, convertir a PowerPoint/Google Slides o preparar diapositivas manualmente siguiendo esta estructura.
