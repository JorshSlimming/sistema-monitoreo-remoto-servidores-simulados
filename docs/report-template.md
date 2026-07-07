# Informe técnico — Sistema de Monitoreo Remoto de Servidores Simulados

**Curso:** Redes de Computadores  
**Docente:** Diego Arroyo Navarrete  
**Fecha:** _[completar por el grupo]_  
**Integrantes:** _[completar por el grupo]_

## 1. Resumen del proyecto

Este proyecto implementa un sistema de monitoreo remoto seguro para un entorno ciberfísico simulado, completamente ejecutable en software. Uno o más nodos clientes envían métricas de CPU, RAM, latencia y estado de servicio a un servidor central mediante TCP. El servidor valida cada mensaje, persiste la información en SQLite y emite comandos correctivos cuando detecta condiciones anómalas. Además, el sistema incluye un dashboard web local con visualización en tiempo real, registro de eventos, controles de demostración y un flujo reproducible para generar evidencia de pruebas y análisis de red.

## 2. Integrantes y roles

Completar esta tabla con los nombres reales del grupo antes de exportar el PDF.

| Integrante | Rol principal | Aporte principal |
|---|---|---|
| _[Nombre]_ | Arquitectura y documentación | Diseño general, informe, diagrama, protocolo |
| _[Nombre]_ | Nodo o cliente simulado | Cliente TCP, generación de métricas, reconexión |
| _[Nombre]_ | Servidor, procesamiento y visualización | Servidor TCP, reglas de anomalía, dashboard |
| _[Nombre]_ | Persistencia, pruebas y análisis de red | SQLite, escenarios, evidencia Wireshark/Nmap |

## 3. Problema y objetivos

### 3.1 Problema

En un entorno de operación remota es necesario supervisar el estado de nodos o servicios sin acceso físico directo. Para ello se requiere una solución que permita recolectar métricas, detectar anomalías y reaccionar frente a fallas usando comunicación real sobre red, con evidencia técnica reproducible.

### 3.2 Objetivo general

Diseñar e implementar un sistema cliente-servidor que permita monitorear nodos simulados, registrar su actividad, detectar condiciones anómalas y demostrar técnicamente su funcionamiento mediante pruebas y análisis de red.

### 3.3 Objetivos específicos

- Implementar comunicación real sobre TCP entre clientes simulados y un servidor central.
- Validar mensajes y autenticar nodos mediante token por mensaje.
- Persistir métricas, comandos y confirmaciones en una base SQLite.
- Detectar anomalías y emitir comandos correctivos automáticos.
- Visualizar el estado del sistema mediante un dashboard local con gráficos en tiempo real.
- Dejar un flujo reproducible para pruebas, demo y generación de evidencia.

## 4. Arquitectura del sistema

La arquitectura implementada sigue un modelo cliente-servidor centralizado:

- **Clientes simulados**: generan métricas periódicas o escenarios anómalos.
- **Servidor TCP**: recibe, valida, procesa y responde con comandos correctivos.
- **Persistencia SQLite**: almacena métricas, comandos y ACKs.
- **Dashboard HTTP local**: consume la información persistida y la presenta en tiempo real.

Ver `docs/architecture.md` para el diagrama y detalle estructural.

## 5. Tecnologías utilizadas

- Python 3.11+
- `socket`
- `threading`
- `json`
- `sqlite3`
- `http.server`
- Wireshark / tshark
- Nmap

## 6. Diseño del protocolo y flujo de comunicación

### 6.1 Transporte

- **Protocolo:** TCP
- **Puerto por defecto:** `5000`
- **Formato:** JSON Lines (`JSON` + salto de línea)
- **Codificación:** UTF-8

### 6.2 Tipos de mensaje

| Tipo | Dirección | Propósito |
|---|---|---|
| `metric` | Cliente → Servidor | Reporte de métricas y eventos |
| `command` | Servidor → Cliente | Acción correctiva |
| `ack` | Cliente → Servidor | Confirmación de comando |
| `error` | Servidor → Cliente | Notificación de error de validación o autenticación |

### 6.3 Flujo implementado

1. El cliente abre una conexión TCP con el servidor.
2. El cliente envía un mensaje `metric` con `node_id`, `seq`, métricas y `token`.
3. El servidor valida autenticación y formato.
4. Si el mensaje es válido, lo persiste en SQLite.
5. Si se detecta una anomalía, el servidor emite un `command`.
6. El cliente procesa el comando y responde con un `ack`.
7. El servidor persiste tanto el comando como la confirmación.

El detalle de campos y ejemplos se encuentra en `docs/contract_v1.md`.

## 7. Implementación

### 7.1 Servidor TCP

- `server/connection_manager.py`: acepta conexiones concurrentes.
- `server/client_session.py`: procesa mensajes, valida tokens, detecta anomalías y envía comandos.
- `server/server_state.py`: mantiene nodos conectados, comandos pendientes y expiraciones.
- `server/command_dispatcher.py`: genera IDs secuenciales de comandos.
- `server/server_config.py`: carga configuración de host, puerto y base de datos.

### 7.2 Clientes simulados

- `client/tcp_client.py`: cliente persistente con reconexión automática y mitigación simulada de comandos.
- Modos disponibles: `normal`, `high-cpu`, `high-ram`, `high-latency`, `service-failure`, `failed-event`.
- Los clientes pueden ejecutar escenarios de demo mediante scripts.

### 7.3 Visualización local

- `frontend/dashboard_server.py`: servidor HTTP local y API de lectura/operación para la demo.
- `frontend/static/`: interfaz del dashboard con gráficos en tiempo real, stream de comandos/ACKs, cola de logs y controles de escenario.

### 7.4 Persistencia

- `storage/store.py`: persistencia SQLite thread-safe.
- Tablas: `metrics`, `commands`, `acks`.
- Se usa `WAL` para mejorar concurrencia en lectura/escritura.

## 8. Seguridad y confiabilidad incorporadas

El sistema incorpora varias medidas válidas para la rúbrica del curso:

- autenticación básica cliente-servidor mediante token por nodo;
- validación de mensajes y rangos de CPU, RAM y latencia;
- detección de JSON inválido;
- reconexión automática del cliente frente a caída del servidor;
- detección de anomalías por umbrales y eventos fuera de rango;
- persistencia de métricas, comandos y confirmaciones para auditoría.

## 9. Pruebas y validación

### 9.1 Pruebas automatizadas

La suite principal se ejecuta con:

```bash
python3 -m unittest discover -s tests -v
```

Estado actual verificado en este repositorio: **60 pruebas, todas pasan**.

Las pruebas cubren:

- construcción y codificación de métricas;
- reglas de anomalía;
- estados y expiración de comandos del servidor;
- persistencia real de métricas, comandos y ACKs;
- respuesta a condiciones inválidas.

### 9.2 Escenarios funcionales

El proyecto incluye escenarios reproducibles vía `scripts/run_scenario.sh` y `docs/scenarios.md`.

| Escenario | Estado esperado |
|---|---|
| Nodo normal | Persistencia de métricas sin comandos |
| CPU alta | Emisión de `reduce_cpu` |
| RAM alta | Emisión de `reduce_ram` |
| Latencia alta | Emisión de `fix_latency` |
| Servicio en falla | Emisión de `restart_service` |
| Evento fallido | Emisión de `normalize_node` |
| Multi-nodo | Recepción concurrente desde varios clientes |
| Token inválido | Respuesta `AUTH_FAILED` |
| JSON inválido | Respuesta `INVALID_JSON` |
| Caída y reconexión | Reintento automático del cliente |

### 9.3 Demo operable

La demo funcional puede ejecutarse con:

```bash
bash scripts/run_project.sh
```

Esto levanta:

- servidor TCP en `127.0.0.1:5000`;
- dashboard en `http://127.0.0.1:8080`.

Desde el dashboard es posible disparar escenarios, correr pruebas, generar bundle de evidencia y observar métricas, comandos, ACKs y logs en tiempo real.

## 10. Análisis con Wireshark y Nmap

### 10.1 Wireshark / tshark

La guía operativa está en `docs/evidence/wireshark.md` y `scripts/capture_traffic.sh`.

La captura debe mostrar, como mínimo:

- handshake TCP (`SYN`, `SYN-ACK`, `ACK`);
- envío de `metric` desde el cliente;
- envío de `command` desde el servidor;
- respuesta `ack` del cliente.

Filtro base recomendado:

```text
tcp.port == 5000
```

### 10.2 Nmap

La guía operativa está en `docs/evidence/nmap.md`.

Comando base:

```bash
nmap -p 5000 127.0.0.1
```

La evidencia esperada es observar el puerto `5000/tcp open` cuando el servidor está en ejecución.

## 11. Entregables y evidencias del repositorio

Este repositorio ya contiene:

- código fuente completo;
- instrucciones de ejecución (`README.md` y `scripts/`);
- diagrama de arquitectura (`docs/architecture.md`);
- evidencia automatizable de pruebas (`scripts/run_all_tests.sh`);
- flujo para evidencia de red (`docs/evidence/`, `scripts/capture_traffic.sh`);
- dashboard de demo funcional con gráficos en tiempo real.

Antes de la entrega final solo falta completar los datos humanos del grupo, insertar capturas reales obtenidas en su entorno y exportar este informe a PDF.

## 12. Limitaciones del sistema

- autenticación basada en tokens estáticos;
- comunicación sin cifrado de transporte;
- un solo servidor central;
- el análisis Wireshark/tshark puede requerir permisos del sistema operativo;
- la presentación final y defensa oral siguen dependiendo de preparación humana del grupo.

## 13. Conclusiones

El proyecto cumple con los componentes mínimos exigidos por la guía del curso: nodos simulados, comunicación real sobre TCP, servidor central, persistencia, seguridad básica, validación técnica y demostración funcional. La solución es completamente ejecutable en software, reproducible a nivel de código y lo suficientemente simple para ser defendida técnicamente frente a la rúbrica.

Como trabajo futuro, el sistema podría fortalecerse con autenticación más robusta, cifrado de transporte, notificaciones externas y soporte para múltiples servidores o más nodos concurrentes.

## Referencias

- RFC 793 — Transmission Control Protocol
- Documentación oficial de Python: `socket`, `threading`, `sqlite3`, `http.server`
- `Guia_Proyecto_Final_Redes_2026.md`
- `docs/contract_v1.md`
- `docs/architecture.md`

> Exportar este archivo a PDF antes de la entrega final y reemplazar los campos marcados como `_ [completar] _` con los datos reales del grupo.
