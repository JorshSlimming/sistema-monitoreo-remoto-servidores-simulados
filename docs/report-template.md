# Informe Técnico — Sistema de Monitoreo Remoto de Servidores Simulados

**Curso:** Redes de Computadores
**Fecha:** _[completar]_

## 1. Portada

- Título del proyecto
- Integrantes
- Curso
- Docente
- Fecha

## 2. Integrantes y roles

| Integrante | Rol principal | Aporte principal |
|---|---|---|
| _[Nombre]_ | _[Rol]_ | _[Aporte]_ |

## 3. Resumen del proyecto

Resumen breve del sistema, su objetivo y el resultado principal.

## 4. Problema y objetivos

### 4.1 Problema

Describir el problema de monitorear servidores remotos, detectar anomalías y emitir comandos correctivos automáticamente.

### 4.2 Objetivo general

_[completar]_

### 4.3 Objetivos específicos

- _[objetivo 1]_
- _[objetivo 2]_
- _[objetivo 3]_

## 5. Arquitectura del sistema

Incluir diagrama de arquitectura (ver `docs/architecture.md`).

Describir:
- Topología: clientes TCP → servidor central → persistencia SQLite.
- Protocolo: JSON sobre TCP, separado por `\n`.
- Puerto: 5000 por defecto.

## 6. Tecnologías utilizadas

- Python 3.11+
- `socket`
- `threading`
- `json`
- `sqlite3`
- Wireshark / tshark
- Nmap

## 7. Diseño del flujo de comunicación o protocolo

Explicar el flujo:
1. Cliente abre conexión TCP.
2. Cliente envía `metric`.
3. Servidor valida token y campos.
4. Servidor persiste la métrica.
5. Si hay anomalía, servidor envía `command`.
6. Cliente responde `ack`.
7. Servidor persiste `command` y `ack`.

Incluir ejemplos JSON de `metric`, `command`, `ack` y `error` desde `docs/contract_v1.md`.

## 8. Implementación

### 8.1 Servidor TCP (`server/`)
- `connection_manager.py`: acepta conexiones concurrentes (un hilo por cliente).
- `client_session.py`: recibe métricas, valida tokens, detecta anomalías, envía comandos.
- `server_state.py`: mantiene estado de nodos conectados, comandos pendientes y timeouts.
- `command_dispatcher.py`: genera IDs secuenciales para comandos.
- `server_config.py`: configuración desde archivo JSON y variables de entorno.

### 8.2 Cliente persistente (`client/`)
- `tcp_client.py`: envía métricas periódicamente, recibe comandos, responde con ACKs.
- Reconexión automática cada 5 segundos.
- Modos de anomalía configurables desde CLI.

### 8.3 Autenticación (`shared/`)
- Tokens estáticos por nodo.
- Validación en cada métrica y ACK.
- Rechazo con error `AUTH_FAILED` si el token no coincide.

### 8.4 Persistencia (`storage/`)
- SQLite con tabla `metrics`, `commands`, `acks`.
- Acceso thread-safe mediante `threading.Lock`.
- WAL mode para mejor concurrencia.

## 9. Seguridad o confiabilidad incorporada

- Validación de tokens por nodo.
- Validación de formato y rangos de mensajes.
- Rechazo de JSON inválido.
- Reconexión automática del cliente.
- Registro persistente de métricas, comandos y ACKs.

## 10. Pruebas y validación

### 10.1 Pruebas unitarias y de integración

```bash
python3 -m unittest discover -s tests -v
```

_Total actual: 18 pruebas — todas pasan._

### 10.2 Escenarios ejecutados

Para cada escenario de `docs/scenarios.md` que se haya probado, incluir:
- Descripción del escenario.
- Comandos ejecutados.
- Resultado observado.

### 10.3 Cobertura de escenarios

| Escenario | Estado |
|---|---|
| Nodo normal | _[Pasa / No probado]_ |
| Anomalía de CPU | _[Pasa / No probado]_ |
| Anomalía de RAM | _[Pasa / No probado]_ |
| Latencia alta | _[Pasa / No probado]_ |
| Servicio en falla | _[Pasa / No probado]_ |
| Evento fallido | _[Pasa / No probado]_ |
| Tres nodos simultáneos | _[Pasa / No probado]_ |
| Token inválido | _[Pasa / No probado]_ |
| JSON mal formado | _[Pasa / No probado]_ |
| Caída y reconexión | _[Pasa / No probado]_ |
| Persistencia SQLite | _[Pasa / No probado]_ |

## 11. Análisis con Wireshark y Nmap

### 11.1 Captura Wireshark

Incluir:
- Handshake TCP (SYN, SYN-ACK, ACK).
- Métrica JSON en tránsito.
- Comando del servidor al cliente.
- Filtros usados.

### 11.2 Verificación Nmap

Incluir:
- Salida del comando `nmap -p 5000 <IP>` mostrando el puerto abierto.
- Fecha y hora del escaneo.

## 12. Limitaciones del sistema

- Tokens estáticos.
- Sin cifrado TLS.
- Un solo servidor central.
- Sin dashboard gráfico.

## 13. Conclusiones

- Resumir logros del proyecto.
- Mencionar limitaciones conocidas.
- Proponer trabajo futuro.

## Referencias

- RFC 793 — Transmission Control Protocol
- Documentación de Python `socket`, `sqlite3`, `threading`
- Guía del proyecto: `Guia_Proyecto_Final_Redes_2026.md`
- Contrato técnico: `docs/contract_v1.md`

> **Nota:** Esta es una plantilla en Markdown. Para la entrega final, convertir a PDF usando Pandoc, Typora o el editor de preferencia.
