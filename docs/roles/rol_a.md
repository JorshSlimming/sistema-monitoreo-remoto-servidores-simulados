# Rol A - Servidor TCP y base inicial

## Responsable

Jorge.

## Estado

**Base inicial del Rol A v0.1: completa.**

Ya esta implementado y probado:

- estructura base del repositorio;
- contrato tecnico en `docs/contract_v1.md`;
- configuracion inicial en `configs/`;
- servidor TCP multicliente inicial en `server/`;
- carpetas reservadas para `shared/` y `storage/`;
- cliente falso y servidor falso en `tests/`;
- scripts basicos de ejecucion en `scripts/`;
- README compacto con instrucciones de uso.

Prueba realizada:

```text
fake_client -> metric JSON -> server
server -> recibe, separa por newline, identifica nodo y muestra mensaje
server -> mantiene estado basico de la sesion
```

## Responsabilidad principal

Desarrollar y mantener el servidor TCP central y las decisiones tecnicas comunes necesarias para que los demas roles trabajen sin bloquearse.

## Archivos principales

```text
server/tcp_server.py
server/connection_manager.py
server/client_session.py
server/command_dispatcher.py
server/server_state.py
server/server_config.py
configs/server_config.json
docs/contract_v1.md
README.md
```

## Funciones esperadas

- Levantar un servidor TCP configurable.
- Escuchar por defecto en el puerto `5000`.
- Aceptar multiples clientes simultaneos.
- Leer mensajes JSON terminados en `\n`.
- Dejar lista la integracion para que Rol C agregue validacion y reglas.
- Dejar lista la integracion para que Rol D agregue persistencia.
- Enviar comandos cuando otro modulo entregue la decision.
- Recibir mensajes `ack`.
- Mantener estado basico de nodos conectados.
- Manejar desconexiones sin botar el servidor.

## Pendientes del Rol A

Estos puntos corresponden a la continuacion natural del servidor, no a la base inicial:

- probar varios clientes falsos conectados al mismo tiempo;
- mejorar la visualizacion del estado interno de nodos;
- coordinar integracion con el cliente real del Rol B;
- coordinar integracion con validacion/reglas del Rol C;
- coordinar integracion con persistencia SQLite del Rol D.

## Criterio de termino final

La parte completa del Rol A termina cuando se pueda demostrar:

```text
3 nodos conectados
-> cada nodo envia metricas
-> el servidor identifica cada nodo
-> procesa mensajes simultaneos
-> envia comandos solo al nodo afectado
-> tolera desconexiones
-> sigue funcionando para los demas nodos
```
