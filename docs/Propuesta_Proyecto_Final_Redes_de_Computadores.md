# Ficha de Propuesta Inicial

## Proyecto Final – Redes de Computadores

## 1. Identificación del grupo

**Grupo:** Ping Infinito  
**Integrantes:** Matias Ignacio Figueroa Vasquez, Máximo Ignacio Beltrán Aranzáez, Benjamín Alonso Henríquez Cid, Jorge Alejandro Slimming Lagos  
**Correos institucionales:** [matfigueroa2023@udec.cl](mailto:matfigueroa2023@udec.cl), [maxbeltran2024@udec.cl](mailto:maxbeltran2024@udec.cl), [bhenriquez2023@udec.cl](mailto:bhenriquez2023@udec.cl), [jslimming2023@udec.cl](mailto:jslimming2023@udec.cl)

## 2. Título tentativo del proyecto

“Sistema de Monitoreo Remoto con Respuesta a Anomalías para Servidores Simulados”

## 3. Variante temática elegida

Monitoreo lógico de servidores simulados, incluyendo la generación intencional de sobrecargas (CPU/RAM) y problemas de latencia, con capacidad de reacción automática para amortiguar las anomalías.

## 4. Problema o necesidad a resolver

En entornos de TI reales, los servidores pueden experimentar sobrecargas, latencias anómalas o fallos en servicios. Un sistema de monitoreo no solo debe detectar estas condiciones, sino también tomar acciones para mitigarlas. Este proyecto simula dicho escenario: los nodos (servidores simulados) generan métricas y también inducen fallos controlados; el servidor central detecta anomalías y envía órdenes de corrección (por ejemplo, reducir carga) para estabilizar el sistema. Todo se ejecuta completamente en software sobre máquinas virtuales.

## 5. Objetivo general del proyecto

Diseñar e implementar un sistema de monitoreo remoto basado en TCP/IP donde servidores simulados envíen periódicamente métricas (CPU, RAM, estado de servicio, latencia, logs) a un servidor central, que valida los datos, detecta anomalías, registra eventos y envía comandos de mitigación (amortiguación) a los nodos afectados.

## 6. Objetivos específicos

1. Implementar un cliente (servidor simulado) configurable que genere métricas en JSON y pueda inducir fallos programados (sobrecarga de CPU/RAM, alta latencia).
2. Desarrollar un servidor TCP que reciba múltiples conexiones, valide formato y rangos de los mensajes, y los guarde en un archivo log.txt.
3. Incorporar detección de anomalías (CPU > 90%, RAM > 90%, latencia > 200 ms, log con "fallido") con alertas en consola.
4. Implementar un mecanismo de reacción: cuando el servidor detecta una anomalía, envía un comando al cliente (ej. "reduce_load" o "fix_latency") para que este reduzca su carga simulada o corrija la latencia.
5. Incluir reconexión automática del cliente ante caída del servidor.
6. Validar la comunicación y el comportamiento con Wireshark, usando dos máquinas virtuales en la misma red.

## 7. Arquitectura preliminar del sistema

- **Nodos simulados (clientes):** Programa Python que genera cada cierto tiempo un JSON con: `nodo_id`, `cpu`, `ram`, `servicio_web` (ok/falla), `latencia_ms`, `evento_log`. Puede entrar en "modo problema" (sobrecarga o latencia alta) de forma aleatoria o mediante una orden interna. Envía los datos por socket TCP. Escucha posibles comandos del servidor y los ejecuta (ej. bajar la carga, normalizar latencia). Si pierde la conexión, reintenta cada 5 segundos.

- **Servidor central:** Escucha en un puerto TCP (ej. 5000). Por cada cliente, recibe el JSON, valida campos y rangos. Si es válido, muestra en consola y lo anexa a log.txt. Si detecta una anomalía (según umbrales definidos), imprime "ALERTA: ..." en consola y además envía un comando de vuelta al cliente (ej. "CMD:reduce_cpu"). El servidor puede atender múltiples clientes usando hilos.

- **Flujo de comunicación:** Cliente → (envío de métricas) → Servidor; Servidor → (comando de mitigación) → Cliente. Comunicación bidireccional sobre la misma conexión TCP.

- **Visualización/registro:** Consola en tiempo real + archivo log.txt.

## 8. Software y herramientas que usarán

**Lenguaje principal:** Python 3  
**Herramientas o bibliotecas previstas:** socket, json, time, threading  
**Entorno de ejecución:** Máquinas virtuales (MV) con Linux o Windows, conectadas en la misma red interna (NAT o red interna).

## 9. Comunicación prevista

TCP

**Protocolo o mecanismo elegido:** Sockets TCP con envío de mensajes JSON terminados en newline. El servidor puede responder con un comando en texto plano.

**Justificación breve:** TCP garantiza entrega y orden de los mensajes, facilita la implementación de reconexión y permite comunicación bidireccional fiable. Es estándar en sistemas de monitoreo reales.

## 10. Seguridad o confiabilidad prevista

- Validación de mensajes
- Detección de datos inválidos / Alertas por condición anómala
- Reconexión o manejo de fallos

**Medida elegida y justificación:**

- **Validación de mensajes:** El servidor verifica que cada JSON contenga los campos esperados y que los valores estén en rangos lógicos (CPU/RAM entre 0 y 100, latencia positiva). Los mensajes inválidos se descartan y se registra un error en log.txt.

- **Detección de anomalías y alertas:** Si el servidor recibe un valor fuera de umbral (CPU > 90%, RAM > 90%, latencia > 200 ms o evento_log que contenga "fallido"), imprime una alerta en consola y envía un comando de mitigación al cliente.

- **Reconexión automática:** El cliente, al detectar cierre del socket, intenta reconectarse periódicamente hasta lograrlo, lo que aumenta la confiabilidad del sistema.

## 11. Validación prevista con herramientas del curso

**Uso previsto de Wireshark:** Capturaremos el tráfico TCP entre cliente y servidor en las MV, filtraremos por el puerto utilizado, y mostraremos que los mensajes JSON viajan en texto plano. Analizaremos la secuencia de paquetes (SYN, ACK, datos, FIN) y verificaremos el comportamiento de reconexión y el envío de comandos.

**Uso previsto de Nmap:** Opcional. Desde una MV, escanearemos el puerto del servidor para verificar que aparece como abierto y que el servicio responde (solo en nuestro entorno autorizado).

## 12. Viabilidad del proyecto

1. **¿El proyecto puede ejecutarse completamente con el PC del grupo?**  
   Sí. Todo es software: dos MV (VirtualBox o VMware) ejecutándose en el mismo PC o en PCs distintos. No se requiere hardware adicional.

2. **¿Qué riesgo técnico principal anticipa el grupo?**  
   El manejo de múltiples clientes concurrentes (hilos) y la correcta implementación de la comunicación bidireccional (cliente escuchando comandos mientras también envía datos).

3. **¿Cómo planean reducir ese riesgo?**  
   Implementaremos primero una versión mínima: un solo cliente, sin reconexión, solo envío. Luego añadiremos la recepción de comandos, después la reconexión, y finalmente el soporte para múltiples clientes con hilos. Realizaremos pruebas en localhost antes de pasar a las MV.

## 13. Roles preliminares del grupo

| Rol | Responsable |
|---|---|
| Arquitectura y documentación | Benjamín |
| Cliente o nodo simulado | Jorge |
| Servidor y procesamiento (incluye comandos de mitigación) | Matias |
| Pruebas y análisis de red (Wireshark, Nmap, validación) | Máximo |

## 14. Observaciones del docente o ayudante

## 15. Criterios de revisión de esta propuesta
