# Cambios

## 0.3.0 — distribución firmada de laboratorios

### Añadido

- **Firma de paquetes `.labpack`**: `lab pack --sign <clave privada>` firma el paquete con
  `ssh-keygen -Y sign` (OpenSSH 8.2 o posterior) y deja la firma en `<paquete>.sig`.
  `lab unpack --signer <clave.pub>` exige que la haya firmado una de las claves dadas y la comprueba
  antes de extraer nada. Sin GPG, sin llavero y sin autoridad de certificación: la clave pública del
  profesor —la misma que usa para el SSH— es el único dato que hay que repartir.
- **Descarga de paquetes por URL**: `lab unpack https://…/lab.labpack` se trae el paquete a un
  directorio temporal, verifica y extrae. La firma se busca en `<url>.sig` y la clave pública puede
  ser también una URL, de modo que un bucket estático sirve como repositorio del curso.
- Los errores de un `.labpack` se presentan como problemas del paquete («issues in the labpack») y no
  de la topología.

### Corregido

- **`make box` fallaba en un clon recién hecho**: `images/box/build.sh` estaba versionado sin permiso
  de ejecución, así que en Linux daba `Permission denied`. Ahora los scripts de la caja se versionan
  ejecutables y el `Makefile` los invoca con `bash`, que funciona aunque un clon de Windows pierda el
  permiso.

## 0.2.0 — entornos reproducibles y distribución

### Añadido

- **Paquetes de laboratorio** (lab pack / lab unpack): un .labpack con la topología, los
  ejercicios, los ficheros del escenario y el lab.lock. Al abrirlo se verifica el sha256 de cada
  fichero antes de escribir nada, y se rechazan las rutas que intenten salir del destino.
- **Caché de imágenes** (`tynix.cache`): un directorio —el bucket montado, un pendrive, una carpeta
  compartida— o una URL de solo lectura. Cada entrada lleva su `sha256`; al traer una imagen se
  verifica y, si no coincide, no se importa.
- **`lab push` / `lab pull`**: publicar una imagen en la caché y traerla verificada desde el bucket.
- **Entornos en la topología**: un nodo puede declarar `environment:` (base + paquetes) en vez de una
  imagen concreta. El plan resuelve el entorno a un nombre direccionado por contenido, construye la
  imagen si no está y la publica con su manifiesto. Dos nodos con el mismo entorno comparten imagen.
- **`lab lock`**: clava los entornos de una topología en `lab.lock` y `--check` detecta la deriva.
- **`lab gc`**: borra las imágenes que ningún laboratorio referencia. Solo toca los prefijos del
  proyecto (`lab-` y `lab/`), nunca las imágenes del sistema; sin `--yes` solo enseña lo que
  borraría, y exige saber qué conservar (una topología o `--keep`).
- **`tynix.store`**: la capa de almacén de tynix, con el protocolo mínimo que necesita (`names`,
  `exists`, `delete`) y las operaciones puras de faltantes y basura. Se prueba con un almacén falso,
  sin Incus.
- **`tynix`**, paquete independiente para entornos reproducibles. Toma las ideas de Nix —declarativo,
  direccionado por contenido, verificable— sin usar Nix ni NixOS: la base sigue siendo Debian y los
  nodos son contenedores de Incus.
  - Manifiesto de entorno: imagen base con huella, paquetes con versión y hash, ficheros inyectados y
    comandos de arranque.
  - Direccionamiento por contenido: el nombre de la imagen se deriva del hash del manifiesto, así que
    cambiar una versión produce una imagen distinta y la anterior queda intacta.
  - Lockfile (`tynix.lock`) con detección de deriva: qué entornos se han añadido, eliminado o cambiado
    desde que se clavaron.
  - 15 pruebas propias, sin dependencias de Incus ni del resto del laboratorio.
- **Calidad de código**: `mypy` en modo estricto sobre `src/` (sin errores), `ruff` con reglas de
  seguridad, simplificación y modernización, `ruff format` como formateador, y **cobertura con umbral
  del 75 %** (actual: 81 %). Todo ello en el CI junto a las pruebas.
- `Makefile` con `test`, `lint`, `types`, `cov` y `check`.
- `.editorconfig`, `SECURITY.md` y un índice en `docs/`.

### Corregido

- Tipos opcionales en `dnsmasq` que podían reventar con un nodo sin enlace en una red.
- `lab web` imprimía la dirección del servidor sin normalizar (`bytes` en algunos casos).
- Código muerto e importaciones perezosas innecesarias detectadas por el análisis estático.

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
