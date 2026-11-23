# Plan de trabajo

Estado: **v0.2.0 publicada**. El código está completo para lo que se propuso; lo que queda es
empaquetado, contenido y publicación.

## Hecho

### v0.1.0 — el laboratorio

- Modelo de topología en YAML con validación y mensajes que dicen dónde está el error.
- Generación de redes, nodos, `nftables`, `dnsmasq`, `/etc/hosts`, red por nodo y telemetría.
- Ciclo de vida idempotente con snapshots y restauración.
- Captura por segmento en tres modos: switch, hub y puerto espejo OVS.
- Ejercicios con hechos del laboratorio y respuestas estrictas con hash, puntuación e informe.
- Consolas en el navegador.
- Caja de VMware reproducible: 1,9 GiB, siete nodos en 2 GB de RAM. **Construida y validada en QEMU
  y en VMware.**

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

## Lo que queda

### 1. Reconstruir el artefacto con la 0.2.0

La caja publicada lleva el CLI de la 0.1.0. El código nuevo está en el repositorio, pero el artefacto
hay que volver a construirlo:

```bash
make box           # ~15 minutos
```

Y después comprobar dentro de la caja lo que aún no se ha ejecutado en real: `lab pack`, `lab unpack`,
`lab push`, `lab pull`, `lab lock` y `lab gc`.

### 2. El laboratorio de Samba AD

El escenario de intrusión real con contenedores: controlador de dominio con Samba, SMB anónimo,
credenciales en ficheros y banderas (usuario anónimo, ID de John Doe, contraseña encontrada), más el
informe escrito.

No es prioridad ahora. La infraestructura está lista: `environment:` para el DC, banderas para
corregir y `labpack` para distribuirlo.

### 3. Firma de paquetes

`labpack` viaja con checksums, que detectan corrupción pero no suplantación. Falta una firma del
autor (GPG o minisign) y `lab unpack --verify-signature`.

## Más adelante

- **Salida a Internet declarada** (`--uplink`): un escenario pide conexión y el resto sigue aislado.
- **Grabación y reproducción de Internet** para prácticas de OSINT sin depender de la red real.
- **Herramientas por nodo** (`tools:`) sin pasar por un toolset completo.
- **Puertos concretos en las políticas** y enlaces punto a punto.
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
