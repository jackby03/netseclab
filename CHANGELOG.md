# Cambios

## 0.1.0 — primer PoC

Primera versión completa: el laboratorio se puede describir, generar, levantar y corregir.

### Añadido

- **CLI `lab`** con 16 comandos: `validate`, `render`, `up`, `down`, `status`, `console`, `snapshot`,
  `reset`, `capture`, `check`, `answer`, `web`, `image`, `images`, `toolsets`, `init`.
- **Modelo de topología** en YAML con validación: claves desconocidas con sugerencia, IPs y MACs
  derivadas, detección de solapes, perfiles, políticas y telemetría.
- **Generadores**: bridges y dispositivos de Incus, `nftables`, `dnsmasq` (reservas por MAC y rutas
  por la opción 121), `/etc/hosts`, script de red por nodo con su unidad systemd, telemetría con
  `rsyslog`.
- **Motor de ciclo de vida** idempotente, snapshots y restauración con parada y arranque.
- **Captura por segmento**, con tres modos: puerto espejo, hub y switch.
- **Ejercicios autocorregibles** con siete tipos de aserción: `reachable`, `port-state`,
  `http-status`, `file`, `ids-alerts`, `capture`, `answer`.
- **Consolas por navegador** sin dependencias (PTY + sondeo HTTP), con token opcional y scrollback
  acotado.
- **Imágenes propias**: recetas, `lab image build`, `ls` y `rm`.
- **Caja**: construcción reproducible de la VM de VMware con Debian fijado y checksum verificado.
- **Documentación**: análisis del proyecto original, diseño, formato, catálogo, guía de uso.
- **6 ejercicios** y **4 laboratorios** de ejemplo.
- **131 pruebas**.

### Corregido durante el desarrollo

- `lab reset` no funcionaba con el laboratorio encendido: Incus no restaura instancias en marcha.
- Un ejemplo usaba imágenes que nadie construía.
- El tipo de red `bridged` se comportaba igual que `isolated`.
- El nombre del sistema no se aplicaba dentro del nodo.
- El disco declarado por nodo se aceptaba y se ignoraba.
- La salida de la consola web crecía sin límite.
- `lab down` con un perfil inexistente lanzaba una excepción sin mensaje.
- Las aserciones aceptaban parámetros que luego descartaban.
