# Presentación final — Sistema de Monitoreo Remoto de Servidores Simulados

**Duración estimada:** 10-15 minutos  
**Formato sugerido:** PDF, PowerPoint o Google Slides  
**Completar antes de exponer:** nombres del grupo, fecha y capturas reales.

---

## Diapositiva 1 — Portada

- **Título:** Sistema de Monitoreo Remoto de Servidores Simulados
- **Curso:** Redes de Computadores
- **Institución:** Universidad de Concepción
- **Docente:** Diego Arroyo Navarrete
- **Integrantes:** _[completar]_
- **Fecha:** _[completar]_

---

## Diapositiva 2 — Problema y objetivo

- **Problema:** supervisar nodos o servicios remotos y detectar anomalías sin acceso físico directo.
- **Objetivo:** construir una solución cliente-servidor con comunicación real sobre TCP, validación técnica y evidencia reproducible.
- **Idea central:** clientes simulados generan métricas; el servidor procesa, registra y responde.

---

## Diapositiva 3 — Arquitectura del sistema

Insertar el diagrama de `docs/architecture.md`.

Explicar brevemente:

- clientes TCP persistentes;
- servidor central multihilo;
- persistencia SQLite;
- dashboard local para demo en tiempo real.

---

## Diapositiva 4 — Protocolo de comunicación

- **Transporte:** TCP
- **Puerto:** 5000
- **Formato:** JSON Lines (`JSON` + `\n`)
- **Autenticación básica:** token por nodo

| Tipo | Dirección | Propósito |
|---|---|---|
| `metric` | Cliente → Servidor | Enviar métricas |
| `command` | Servidor → Cliente | Orden correctiva |
| `ack` | Cliente → Servidor | Confirmar comando |
| `error` | Servidor → Cliente | Informar error |

---

## Diapositiva 5 — Seguridad y confiabilidad

- Validación de token por `node_id`
- Validación de formato y rangos del mensaje
- Rechazo de JSON inválido
- Reconexión automática del cliente
- Persistencia de métricas, comandos y ACKs

Esta sección cubre el criterio de seguridad/confiabilidad exigido por la guía.

---

## Diapositiva 6 — Reglas de anomalía

| Condición | Comando emitido |
|---|---|
| CPU > 90% | `reduce_cpu` |
| RAM > 90% | `reduce_ram` |
| Latencia > 200 ms | `fix_latency` |
| `service_web == "falla"` | `restart_service` |
| `event_log` contiene `fallido` | `normalize_node` |

---

## Diapositiva 7 — Demo funcional

Mostrar el dashboard corriendo con gráficos en tiempo real.

Secuencia sugerida:

1. Iniciar proyecto con `bash scripts/run_project.sh`
2. Abrir `http://127.0.0.1:8080`
3. Ejecutar escenario `CPU alta`
4. Mostrar:
   - aumento de la serie en el gráfico;
   - emisión de `reduce_cpu`;
   - recepción de `ack`;
   - recuperación posterior de la métrica;
   - persistencia en SQLite.

Si hay tiempo, repetir con `Multi-nodo`.

---

## Diapositiva 8 — Evidencia de pruebas

```bash
python3 -m unittest discover -s tests -v
```

- **Resultado actual:** 46 pruebas, todas pasan.
- Cobertura: cliente, servidor, persistencia, reglas de anomalía.
- Insertar captura real de la ejecución.

---

## Diapositiva 9 — Evidencia de red

### Wireshark / tshark

- Handshake TCP (`SYN`, `SYN-ACK`, `ACK`)
- Envío de `metric`
- Envío de `command`
- Respuesta `ack`

### Nmap

- `nmap -p 5000 127.0.0.1`
- Evidencia esperada: `5000/tcp open`

Insertar capturas reales del entorno del grupo.

---

## Diapositiva 10 — Conclusiones

### Logros

- Sistema funcional completo y reproducible en software
- Comunicación real cliente-servidor sobre TCP
- Detección de 5 tipos de anomalía
- Persistencia y visualización en tiempo real

### Limitaciones

- Tokens estáticos
- Sin cifrado de transporte
- Un solo servidor central

### Trabajo futuro

- autenticación más robusta;
- notificaciones externas;
- soporte multi-servidor o más nodos.

---

## Diapositiva 11 — Preguntas

- Repositorio / enlace de entrega
- Espacio para preguntas del jurado

---

> Exportar este contenido al formato final de exposición y reemplazar los campos `_ [completar] _` antes de presentar.
