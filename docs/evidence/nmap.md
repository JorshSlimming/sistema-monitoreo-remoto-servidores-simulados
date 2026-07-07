# Verificación del puerto con Nmap

## Objetivo

Verificar que el puerto TCP del servidor de monitoreo está abierto y aceptando conexiones, usando Nmap desde el entorno autorizado (máquina virtual o segundo equipo en la misma red).

## Requisitos

- Nmap instalado en el equipo que realiza el escaneo.
- El servidor de monitoreo ejecutándose y accesible desde la red.
- **Permiso explícito** del administrador de la red o del laboratorio antes de escanear.

## Escaneo básico

Con el servidor corriendo, desde otra máquina:

```bash
nmap -p 5000 <IP_DEL_SERVIDOR>
```

### Resultado esperado

```
Starting Nmap 7.xx ( https://nmap.org )
Nmap scan report for <IP_DEL_SERVIDOR>
PORT     STATE SERVICE
5000/tcp open  unknown
Nmap done: 1 IP address (1 host up) scanned in 0.xx seconds
```

## Escaneo detallado

```bash
nmap -sV -p 5000 <IP_DEL_SERVIDOR>
```

Agrega detección de versión del servicio. El resultado mostrará algo como:

```
5000/tcp open  unknown  Python <version>
```

(No se detecta un protocolo conocido porque es un servicio personalizado, no HTTP/SSH/etc.)

## Escaneo de un rango de nodos

```bash
nmap -p 5000 192.168.1.100-120
```

## Verificación de servicio con netcat (alternativa a Nmap)

```bash
nc -zv <IP_DEL_SERVIDOR> 5000
```

## Verificación desde el servidor (localhost)

```bash
nmap -p 5000 127.0.0.1
```

## Consideraciones de seguridad

- El escaneo Nmap debe realizarse **únicamente** contra equipos autorizados (máquina virtual propia o servidor del laboratorio).
- No escanear equipos de otros grupos sin permiso.
- El servidor por defecto escucha en `0.0.0.0`, por lo que responde en todas las interfaces de red.
- Si se desea limitar el acceso, configurar `SERVER_HOST=127.0.0.1` para escuchar solo en loopback.

## Evidencia recomendada para la entrega

Capturar la salida de terminal del comando `nmap` mostrando:
1. La IP del servidor.
2. El puerto `5000` como `open`.
3. El servicio (si se usó `-sV`).
4. La hora/fecha del escaneo.

```bash
# Ejemplo de captura para el informe
nmap -p 5000 <IP> | tee evidencia_nmap.txt
```

> **Nota:** Este repositorio no incluye archivos de salida de Nmap precapturados. La evidencia debe generarse en vivo durante la demostración.
