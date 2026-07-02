# Sistema de Monitoreo Remoto de Servidores Simulados

Proyecto final de Redes de Computadores. El sistema simula nodos remotos que envian metricas por TCP a un servidor central. La base actual corresponde al Rol A: servidor, sesiones, configuracion y contrato tecnico inicial.

## Rol A - Base inicial v0.1

Esta version deja lista la base tecnica para que el resto del grupo pueda avanzar:

- servidor TCP multicliente en `server/`;
- carpetas reservadas para `shared/` y `storage/`, que desarrollan los roles C y D;
- cliente falso y servidor falso en `tests/`;
- configuracion en `configs/`;
- contrato tecnico formal en `docs/contract_v1.md`;
- responsabilidades separadas en `docs/roles/`.

## Contrato Rapido

- Transporte: TCP.
- Puerto por defecto: `5000`.
- Codificacion: UTF-8.
- Formato: JSON terminado en `\n`.
- Tipos de mensaje: `metric`, `command`, `ack`, `error`.

## Ejecucion

Levantar servidor:

```powershell
python -m server.tcp_server
```

Enviar una metrica de prueba desde otra terminal:

```powershell
python tests/fake_client.py --node-id node-01 --mode high-cpu
```

Modos disponibles:

```text
normal
high-cpu
high-ram
high-latency
service-failure
failed-event
```

En esta etapa el servidor solo muestra los mensajes por consola. La validacion, las reglas de anomalia y la persistencia quedan para los roles C y D.

## Estructura

```text
configs/   configuracion del servidor
server/    servidor TCP, sesiones y despacho basico de comandos
shared/    reservado para protocolo, validacion, autenticacion y reglas
storage/   reservado para persistencia y registro historico
tests/     herramientas falsas para probar sin depender de otros modulos
scripts/   comandos de ejecucion
docs/      guia, propuesta, contrato tecnico y roles
```
