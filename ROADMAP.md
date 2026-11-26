# Plan de trabajo

Estado: **v0.3.0 publicada**. El código cubre lo que se propuso y la caja está construida y probada.
Lo que queda es contenido docente, el SIEM ligero y la publicación del artefacto.

## Hecho

### v0.1.0 — el laboratorio

- Modelo de topología en YAML con validación y mensajes que dicen dónde está el error.
- Generación de redes, nodos, `nftables`, `dnsmasq`, `/etc/hosts`, red por nodo y telemetría.
- Ciclo de vida idempotente con snapshots y restauración.
- Captura por segmento en tres modos: switch, hub y puerto espejo OVS.
- Ejercicios con hechos del laboratorio y respuestas estrictas con hash, puntuación e informe.
- Consolas en el navegador.
- Caja de VMware reproducible: 1,9 GiB, siete nodos en 2 GB de RAM. Construida y validada en QEMU y
  en VMware.

### v0.2.0 — tynix y distribución

La idea de Nix aplicada a Incus, sin Nix ni NixOS: los nodos siguen siendo Debian y el alumno ve un
Linux normal; la reproducibilidad queda debajo.

- ✅ **Manifiesto y lock**: base, paquetes con versión y hash, ficheros y arranque; hash de contenido;
  `tynix.lock` con detección de deriva.
- ✅ **Store**: protocolo de almacén, direccionamiento por contenido y recolección de basura (`lab gc`).
- ✅ **Caché**: directorio o URL de solo lectura, con `sha256` por entrada; `lab push` y `lab pull`
  verifican antes de importar.
- ✅ **Integración**: un nodo puede declarar `environment:` y `lab up` resuelve, construye y publica
  la imagen; `lab lock` clava los entornos.
- ✅ **Paquetes de laboratorio**: `lab pack` y `lab unpack`, con verificación de cada fichero antes de
  escribir nada y protección contra rutas fuera del destino.

### v0.3.0 — distribución firmada y caja probada

- ✅ **Firma de paquetes**: `lab pack --sign` con OpenSSH (`ssh-keygen -Y sign`) y
  `lab unpack --signer`, que comprueba la firma antes de extraer nada. Sin GPG ni llavero: la clave
  pública del profesor es el único dato que hay que repartir.
- ✅ **Descarga por URL**: `lab unpack https://…/lab.labpack` trae el paquete y su firma, verifica y
  extrae; la clave pública también puede venir de una URL.
- ✅ **Red determinista de los nodos**: direcciones, rutas de segmento y ruta por defecto salen de la
  topología; `lab-net` enmascara `systemd-networkd` y escribe el DNS del laboratorio o el de la red
  NAT. Un nodo reiniciado se comporta igual que uno recién creado.
- ✅ **Salida a Internet por segmento**: `type: nat` con NAT y DNS por la puerta; el escenario lo
  declara y el resto sigue aislado.
- ✅ **Arreglos encontrados al probar la caja en real**: `lab push` encontrando la imagen exportada,
  `lab up` tras `lab down`, espera de arranque, la portada de `lab web` exigiendo token, el toolset
  `sniff` sin `mitmproxy` (no está en Debian 13), el flujo de documentación como YAML válido y los
  scripts de la caja con permiso de ejecución.
- ✅ **Pruebas dentro de la caja**: `tools/probar-caja.sh` arranca el artefacto en QEMU con un overlay
  desechable y ejecuta 31 comprobaciones reales; `tools/pruebas-humanas.md` recoge lo que se revisa a
  mano en VMware.
- ✅ **Documentación de producto**: sitio con `mkdocs-material`, referencia de topología, CLI e
  imágenes, guías de operación y distribución, y el diseño del [SIEM ligero](docs/design/siem.md).

## Lo que queda

### 1. Distribuir la caja

La caja de la 0.3.0 está construida y validada (2,3 GB). Canales decididos:

- **Beta: SourceForge.** No tiene el límite de 2 GB por fichero de GitHub, reparte la descarga entre
  espejos y da estadísticas. Se publica con `tools/publicar-caja.sh`, que verifica el `SHA256SUMS`
  antes de subir y devuelve la URL de descarga.
- **Oficial: Zenodo y espejo de la universidad.** Zenodo da DOI para citar la versión; el espejo
  institucional da la descarga del curso. Se hará cuando la universidad lo confirme.

Mientras tanto, la caja se construye con `make box` y se comprueba con `WORK=build/box
tools/probar-caja.sh`.

Criterio: la beta se descarga desde SourceForge y su `sha256` coincide con el publicado; la oficial
queda pendiente de la universidad.

### 2. Revisar los seis ejercicios con criterio docente

Los ejercicios están validados en estructura y en la caja, pero falta la lectura de profesor:
enunciado, tareas, pistas, comprobaciones y solución de cada uno. Prestar atención al 05
(cortafuegos del servidor) y al 06 (umbral real de Suricata y tiempo de captura).

Criterio: cada ejercicio se entiende sin explicaciones y su solución puntúa completo.

### 3. El SIEM ligero y el laboratorio de SOC

Diseñado en [docs/design/siem.md](docs/design/siem.md): motor de reglas en terminal con SQLite y
PyYAML, casos reproducibles para corregir y probar en el CI, y un nodo `soc` que aprovecha la
telemetría que ya existe. Cinco pasos: núcleo, reglas, replay, integración y ejercicio de triaje.

Criterio: `siem replay` reproduce un caso con sus alertas esperadas en el CI y el ejercicio de triaje
se corrige solo.

### 4. El laboratorio de Samba AD

El escenario de intrusión real con contenedores: controlador de dominio con Samba, SMB anónimo,
credenciales en ficheros y banderas (usuario anónimo, ID de John Doe, contraseña encontrada), más el
informe escrito. La infraestructura está lista: `environment:` para el DC, banderas para corregir y
`labpack` para distribuirlo.

## Más adelante

- **Atajo `--uplink`**: declarar la salida a Internet sin añadir el segmento a mano.
- **Grabación y reproducción de Internet** para prácticas de OSINT sin depender de la red real.
- **Herramientas por nodo** (`tools:`) sin pasar por un toolset completo.
- **Puertos concretos en las políticas** y enlaces punto a punto.
- **Carpeta compartida** con la caja, equivalente al `virtiofs` del original.
- **Plataforma web**: índice de laboratorios publicados, búsqueda y documentación de cada actividad.
  Empieza por un índice en git, no por una aplicación.

## Ideas aparcadas

- **Nodos Windows**: los contenedores de Windows necesitan kernel de Windows; en Linux solo hay VMs
  dentro de contenedores, con licencia y anidamiento. El AD se cubre con Samba.
- **VM externa conectada a un segmento**: técnicamente posible (red `bridged` sobre una segunda
  tarjeta host-only de VMware), pero esa VM queda fuera de la gestión del laboratorio. Si algún día
  se retoma, el gestor sería un script `vmrun` generado desde la propia topología, no un orquestador
  nuevo.
- **Ejecutar el laboratorio directamente en macOS o Windows sin VM**: descartado, Incus necesita
  Linux.
