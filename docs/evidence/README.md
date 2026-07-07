# Evidencia para la entrega

Este directorio contiene documentación sobre cómo generar y recolectar evidencia del sistema de monitoreo remoto de servidores simulados.

## Artefactos generados automáticamente

Ejecutando `./scripts/generate_demo_artifacts.sh` (o `make evidence`) se generan los siguientes archivos bajo `artifacts/demo/`.

> Importante: ejecútalo **sin** un servidor TCP ya corriendo en `127.0.0.1:5000`. El script levanta sus propios escenarios y falla temprano si el puerto ya está ocupado.

| Archivo | Contenido | Método |
|---|---|---|
| `summary_<timestamp>.json` | Resumen JSON de toda la ejecución: DB stats, Nmap, tshark | Automático |
| `demo_<timestamp>.log` | Log completo de la ejecución de escenarios | Automático |
| `state_snapshot_<timestamp>.json` | Snapshot del endpoint `/api/state` | Automático |
| `metrics_sample.jsonl` | Muestra de métricas (JSON Lines) desde SQLite | Automático |
| `commands_sample.jsonl` | Muestra de comandos (JSON Lines) desde SQLite | Automático |
| `acks_sample.jsonl` | Muestra de ACKs (JSON Lines) desde SQLite | Automático |
| `nmap_output.txt` | Salida del escaneo Nmap del puerto 5000 | Automático (si nmap disponible) |
| `tshark_capture_<timestamp>.pcapng` | Captura de tráfico TCP del puerto 5000 | Automático (si tshark con permisos) |
| `test_output.log` | Resultado de la suite de pruebas | Automático |
| `evidence_index.json` | Índice de todos los artefactos generados | Automático |

## Artefactos manuales

Estos requieren intervención del presentador:

| Artefacto | Dónde está documentado | Qué hacer |
|---|---|---|
| Captura Wireshark gráfica | `docs/evidence/wireshark.md` | Abrir Wireshark, capturar tráfico, exportar screenshot/PDF |
| Escaneo Nmap desde otra máquina | `docs/evidence/nmap.md` | Escanear IP del servidor desde VM o segundo equipo |
| Screenshots del dashboard | `scripts/generate_demo_screenshots.sh` | Ejecutar script (requiere navegador) o capturar manualmente |
| Informe técnico | `docs/report-template.md` | Completar plantilla LaTeX/Markdown |
| Presentación | `docs/presentation-template.md` | Completar guión de presentación |

## Limitaciones conocidas

### tshark / dumpcap

La captura de tráfico con `tshark` en loopback requiere permisos elevados:

```bash
# Error típico sin permisos:
dumpcap: The capture session could not be initiated on interface 'lo' (You don't have permission to capture on that device)

# Soluciones:
# 1. Ejecutar con sudo
sudo tshark -i lo -f "tcp port 5000" -w captura.pcapng

# 2. Agregar usuario al grupo wireshark
sudo usermod -aG wireshark $USER
# (requiere cerrar sesión y volver a entrar)

# 3. Ejecutar el script con sudo
sudo ./scripts/generate_demo_artifacts.sh
```

Si no hay permisos, el script genera una nota explícita en el summary JSON y el archivo `tshark_result_blocked.txt`.

### Nmap

Nmap funciona sin privilegios para escaneo TCP connect (`-sT`) en localhost. Para escaneo SYN (`-sS`) se requieren permisos de superusuario. El script usa `-T4` (TCP connect scan).

Si `nmap` está instalado pero falla por librerías del sistema (por ejemplo `libpcap.so.0.8` ausente), el error queda registrado en `nmap_output.txt` y en `evidence_index.json` como `nmap_status: "error"`.

### Dashboard screenshots

El script `scripts/generate_demo_screenshots.sh` intenta capturar el dashboard automáticamente, pero puede fallar si no hay un navegador en modo headless. Se recomienda capturar manualmente como respaldo.

## Verificación de integridad

Cada ejecución de `make evidence` genera un archivo `evidence_index.json` con la lista completa de artefactos producidos y sus metadatos (tamaño, timestamp, estado).

## Documentación relacionada

- `docs/evidence/wireshark.md` — guía detallada de captura con Wireshark
- `docs/evidence/nmap.md` — guía detallada de escaneo con Nmap
- `docs/demo-flow.md` — flujo de demostración paso a paso
