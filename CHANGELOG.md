# Cambios

## 0.1.0 — primer PoC funcional

Primera versión completa y validada en la caja: el laboratorio se describe en YAML, se levanta en una
VM ligera con contenedores, se rompe sin miedo, se restaura en un comando y se corrige solo.

### Añadido

- **CLI `lab`** con 18 comandos: `validate`, `render`, `up`, `down`, `status`, `console`, `snapshot`,
  `reset`, `capture`, `check`, `answer`, `report`, `hash`, `web`, `image`, `images`, `toolsets`,
  `init`.
- **Modelo de topología** en YAML con validación: claves desconocidas con sugerencia, IPs y MACs
  derivadas, detección de solapes, perfiles, políticas y telemetría.
- **Generadores**: bridges y dispositivos de Incus, `nftables`, `dnsmasq` (reservas por MAC y rutas
  por la opción 121), `/etc/hosts`, script de red por nodo con su unidad systemd, telemetría con
  `rsyslog`.
- **Motor de ciclo de vida** idempotente, con snapshots y restauración.
- **Captura por segmento** con tres modos: puerto espejo OVS, hub y switch.
- **Ejercicios** con dos partes: hechos del laboratorio (`reachable`, `port-state`, `http-status`,
  `file`, `ids-alerts`, `capture`) y **respuestas estrictas** —un valor concreto comparado por
  `sha256`, con puntuación y variantes declaradas—, más el **informe escrito** que corrige el
  profesor (`lab report`).
- **Consolas por navegador** sin dependencias (PTY + sondeo HTTP), con token opcional y scrollback
  acotado.
- **Imágenes propias**: recetas, `lab image build`, `ls` y `rm`.
- **Caja**: construcción reproducible de la VM de VMware con Debian fijado y checksum verificado.
  Pool btrfs copy-on-write para que quepan siete nodos en disco; credenciales en los nodos.
- **Documentación**: análisis del proyecto original, diseño, formato, catálogo, guía de uso,
  ejercicios y límites.
- **6 ejercicios** y **4 laboratorios** de ejemplo.
- **175 pruebas**.

### Corregido durante la validación en la caja

Estos fallos solo aparecieron al ejecutar el laboratorio de verdad, no en las pruebas con ejecutor
simulado:

- **La fase de ficheros no se ejecutaba**: ningún nodo recibía su configuración.
- Faltaba `systemctl daemon-reload` antes de activar las unidades recién copiadas.
- `lab launch` sobre una instancia existente devolvía una violación de unicidad, no «already exists»:
  `lab up` dejó de ser idempotente.
- La imagen de nodo no traía `dnsmasq`, y los nodos no tenían credenciales.
- `incus list` devuelve `state.network` como mapa, no como lista: `lab status` reventaba.
- `incus snapshot list -c name` devuelve vacío sin error: `lab reset` no encontraba el snapshot.
- El hub y el puerto espejo necesitan root; el `hub` además fallaba en silencio.
- El driver `dir` de Incus copia la imagen entera por contenedor: siete nodos llenaban el disco.
- Sin `discard` ni `fstrim`, el disco virtual no encogía y el artefacto pesaba 4,5 GB en vez de 1,9.
- El pool btrfs se creaba pero el perfil de los nodos seguía apuntando al pool de directorios.
- `answer` con `contains` solo comprobaba una palabra dentro de un texto: sustituido por respuestas
  estrictas con hash.

### Limitaciones conocidas

- `lab pack` / `lab pull`: diseñado y documentado, sin implementar.
- Salida a Internet declarada (`--uplink`) y grabación/reproducción de Internet.
- Herramientas por nodo (`tools:`) y puertos concretos en las políticas.
- Nodos Windows: requieren virtualización anidada. El controlador de dominio se cubrirá con Samba AD
  en contenedor.
