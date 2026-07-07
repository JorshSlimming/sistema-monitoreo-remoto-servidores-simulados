# Captura de tráfico con Wireshark

## Objetivo

Capturar y analizar el tráfico TCP entre el cliente y el servidor del sistema de monitoreo para verificar:
- Handshake TCP (SYN, SYN-ACK, ACK)
- Transmisión de métricas en JSON
- Envío de comandos del servidor al cliente
- Confirmaciones (ACK) del cliente
- Cierre de conexión (FIN)
- Reconexión automática

## Requisitos

- Wireshark instalado (o tshark para terminal)
- El sistema de monitoreo ejecutándose en `localhost` (127.0.0.1:5000)

## Método 1 — Wireshark (interfaz gráfica)

1. Abrir Wireshark.
2. Seleccionar la interfaz `lo` (loopback) en Linux o `Loopback Pseudo-Interface` en Windows.
3. Aplicar el filtro: `tcp.port == 5000`
4. Iniciar la captura.
5. En otra terminal, ejecutar el cliente:
   ```bash
   python3 -m client.tcp_client --node-id node-01 --mode high-cpu
   ```
6. Dejar correr unos segundos, luego detener la captura.

### Paquetes esperados

| # | Resumen Wireshark | Descripción |
|---|---|---|
| 1 | `[SYN]` | Cliente → Servidor: solicitud de conexión |
| 2 | `[SYN, ACK]` | Servidor → Cliente: aceptación |
| 3 | `[ACK]` | Cliente → Servidor: handshake completo |
| 4 | `PSH, ACK` | Cliente → Servidor: métrica JSON |
| 5 | `[ACK]` | Servidor → Cliente: confirmación TCP |
| 6 | `PSH, ACK` | Servidor → Cliente: comando `reduce_cpu` |
| 7 | `[ACK]` | Cliente → Servidor: confirmación TCP |
| 8 | `PSH, ACK` | Cliente → Servidor: ACK de aplicación |
| 9 | ... | (ciclo continúa) |

### Ver el contenido JSON

1. Seleccionar un paquete `PSH, ACK`.
2. En el panel inferior, expandir `Data` (o `Line-based text data`).
3. El JSON aparece como texto legible.

### Filtros útiles

| Filtro | Qué muestra |
|---|---|
| `tcp.port == 5000` | Todo el tráfico del puerto 5000 |
| `tcp.flags.syn == 1 and tcp.flags.ack == 0` | Solo SYN (inicios de conexión) |
| `tcp.flags.fin == 1` | Cierres de conexión |
| `ip.addr == 127.0.0.1 && tcp.port == 5000` | Tráfico loopback filtrado |
| `tcp.payload contains "metric"` | Paquetes que contienen métricas |
| `tcp.payload contains "command"` | Paquetes que contienen comandos |

## Método 2 — tshark (terminal)

```bash
# Iniciar captura en loopback, filtrando puerto 5000, guardar a archivo
tshark -i lo -f "tcp port 5000" -w captura.pcapng

# En otra terminal, ejecutar el cliente
python3 -m client.tcp_client --node-id node-01 --mode high-cpu

# Volver a la terminal de tshark y detener con Ctrl+C

# Leer el archivo
tshark -r captura.pcapng -Y "tcp.port == 5000"
```

## Método 3 — Captura remota (SSH + tshark)

Si el servidor corre en una máquina virtual o remota:

```bash
ssh usuario@IP_DEL_SERVIDOR "tshark -i any -f 'tcp port 5000' -w -" > captura_remota.pcapng
```

Luego abrir `captura_remota.pcapng` en Wireshark local.

## Evidencia recomendada para la entrega

Para cada escenario, capturar al menos:
1. **Handshake TCP:** los primeros 3 paquetes (SYN, SYN-ACK, ACK).
2. **Intercambio de datos:** una métrica completa y su comando correspondiente.
3. **Reconexión:** la secuencia tras matar y reiniciar el servidor (nuevo SYN).
4. **Cierre:** los paquetes FIN cuando el cliente se desconecta.

Exportar como imagen o PDF desde Wireshark: `File → Export Specified Packets` o `File → Print`.

> **Nota:** Este repositorio no incluye archivos `.pcap` precapturados. Las capturas deben generarse en vivo durante la demostración siguiendo los pasos anteriores.
