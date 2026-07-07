# Captura de trafico con Wireshark

## Objetivo

Capturar y analizar el trafico TCP entre cliente y servidor para verificar:

- Handshake TCP (`SYN`, `SYN-ACK`, `ACK`).
- Handshake de autenticacion PSK (`hello`, `challenge`, `challenge_response`, `ready`).
- Uso posterior de frames `secure` cifrados.
- Cierre de conexion y reconexion automatica.
- Rechazo de trafico invalido durante la simulacion de atacante local autorizada.

> Alcance: esta guia cubre una simulacion local autorizada para demo academica.
> No es un pentest real y el canal seguro de aplicacion no reemplaza TLS en un
> despliegue productivo.

## Requisitos

- Wireshark instalado, o tshark para terminal.
- Sistema ejecutandose en `localhost` (`127.0.0.1:5000`).

## Metodo 1 - Wireshark

1. Abrir Wireshark.
2. Seleccionar `lo` en Linux o `Loopback Pseudo-Interface` en Windows.
3. Aplicar el filtro `tcp.port == 5000`.
4. Iniciar captura.
5. En otra terminal, ejecutar:

```bash
python3 -m client.tcp_client --node-id node-01 --mode high-cpu
```

6. Dejar correr unos segundos y detener la captura.

### Variante: simulacion de atacante local

Con la captura activa, tambien puedes ejecutar:

```bash
python3 -m attacker.attack_simulator --attack all --json
```

En este caso deberias observar intentos rechazados por el servidor, por
ejemplo `HANDSHAKE_REQUIRED`, `AUTH_FAILED`, cierre de conexion por frame
manipulado o rechazo de secuencia repetida.

### Paquetes esperados

| # | Resumen | Descripcion |
|---|---|---|
| 1 | `[SYN]` | Cliente a servidor: solicitud de conexion |
| 2 | `[SYN, ACK]` | Servidor a cliente: aceptacion |
| 3 | `[ACK]` | Handshake TCP completo |
| 4 | `PSH, ACK` | Cliente a servidor: `hello` con `node_id` |
| 5 | `PSH, ACK` | Servidor a cliente: `challenge` con nonce |
| 6 | `PSH, ACK` | Cliente a servidor: `challenge_response` |
| 7 | `PSH, ACK` | Servidor a cliente: `ready` |
| 8 | `PSH, ACK` | Cliente a servidor: frame `secure` con `ciphertext` |
| 9 | `PSH, ACK` | Servidor a cliente: frame `secure` con comando cifrado |
| 10 | `PSH, ACK` | Cliente a servidor: frame `secure` con ACK cifrado |

### Ver contenido

Los mensajes del handshake se ven como JSON legible. Despues de `ready`, Wireshark
solo debe mostrar frames `secure` con campos como `seq`, `nonce`, `ciphertext` y
`tag`; el payload real (`metric`, `command`, `ack`) no debe aparecer en claro.

Durante la simulacion de atacante, tampoco deberia verse una metrica valida en
claro aceptada por el servidor: los intentos invalidos deben terminar en error o
en cierre de conexion.

### Filtros utiles

| Filtro | Que muestra |
|---|---|
| `tcp.port == 5000` | Trafico del puerto 5000 |
| `tcp.flags.syn == 1 and tcp.flags.ack == 0` | Inicios de conexion |
| `tcp.flags.fin == 1` | Cierres de conexion |
| `ip.addr == 127.0.0.1 && tcp.port == 5000` | Trafico loopback |
| `tcp.payload contains "challenge"` | Handshake PSK |
| `tcp.payload contains "ciphertext"` | Frames cifrados |

## Metodo 2 - tshark

```bash
tshark -i lo -f "tcp port 5000" -w captura.pcapng
python3 -m client.tcp_client --node-id node-01 --mode high-cpu
tshark -r captura.pcapng -Y "tcp.port == 5000"
```

## Evidencia recomendada

Para la entrega, capturar:

1. Handshake TCP.
2. Handshake PSK completo.
3. Frames `secure` posteriores con `ciphertext`.
4. Reconexion tras detener y reiniciar el servidor.
5. Cierre de conexion cuando el cliente se desconecta.
6. Un ataque rechazado (por ejemplo `plaintext-metric` o `tampered-frame`) con
   el error correspondiente del protocolo.

Este repositorio no incluye archivos `.pcap` precapturados; las capturas deben
generarse en vivo durante la demostracion.
