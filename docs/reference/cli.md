# Referencia del CLI

Esta página documenta todos los comandos de `lab`, sus opciones y un ejemplo de uso real.

## Convenciones

Dentro de la caja, el comando es `lab`. Desde el repositorio, sin instalar el paquete:

```bash
PYTHONPATH=src python -m lab.cli --help
```

`lab --help` lista los comandos de primer nivel y `lab <comando> --help` detalla las opciones de cada
uno. La CLI tiene **24 comandos de primer nivel**; `lab image` agrupa tres subcomandos (`build`,
`ls` y `rm`).

Los mensajes del CLI están en inglés; esta documentación está en español. La versión se consulta con:

```bash
lab --version
# netseclab 0.3.0
```

| Código de salida | Significado |
|---|---|
| `0` | La orden terminó correctamente. |
| `1` | La orden se ejecutó pero algo falló: pasos del plan, comprobaciones de un ejercicio, fichero que no se puede escribir. |
| `2` | Entrada no válida: topología o ejercicio mal formado, perfil inexistente, red inexistente, lock sin entornos. |
| `3` | La orden necesita Incus y no está disponible. |

Salvo que se indique otra cosa, las rutas de topología y de ejercicio se pasan como primer argumento.

## Topología y plan

### `validate`

Valida una o varias topologías o ejercicios sin arrancar nada.

```bash
lab validate lab/examples/example.net.yaml
lab validate "lab/examples/*.yaml"
lab validate lab/exercises/01-reconocimiento.yaml
```

```
lab/examples/example.net.yaml: OK - 7 nodes, 3 networks, 8 policies
lab/exercises/01-reconocimiento.yaml: OK - exercise 01-reconocimiento with 3 checks
```

Acepta comodines y varios ficheros. Un fichero se trata como ejercicio cuando contiene a la vez
`checks` y `lab`. Devuelve `1` si alguna topología no es válida y escribe los errores en la salida de
error.

### `render`

Enseña o guarda lo que haría `lab up`, sin ejecutarlo.

```bash
lab render lab/examples/example.net.yaml
lab render lab/examples/example.net.yaml --profile mini
lab render lab/examples/fuzz-evasion.yaml --format shell
lab render lab/examples/fuzz-evasion.yaml --format json
lab render lab/examples/example.net.yaml --out /tmp/plan
```

| Opción | Efecto |
|---|---|
| `--profile <nombre>` | Renderiza solo el perfil indicado. |
| `--format shell\|json\|table` | Formato de salida; por defecto `table`. |
| `--out <directorio>` | Escribe los ficheros generados, `lab.sh` y `plan.json` en el directorio. |

```
lab: example.net   domain: example.net   profile: mini

NETWORKS
  name       cidr             type      mode    bridge         gateway
  ext        10.5.0.0/24      isolated  hub     nvm-ext        10.5.0.1
  ...

NODES
  name       image                  interfaces
  fw         lab-node-v1            eth0=10.5.0.254/24, eth1=10.5.1.254/24, eth2=10.5.2.254/24
  ...

42 steps
```

`--format shell` genera un script `sh` con los comandos de Incus y las copias de ficheros. `--out`
escribe además el árbol de ficheros que se copiaría a los nodos.

### `up`

Levanta el laboratorio: crea el perfil, las redes, los nodos, los paquetes, los ficheros generados y
la activación, y al terminar crea el snapshot `initial`.

```bash
lab up lab/examples/example.net.yaml --profile std
lab up lab/examples/fuzz-evasion.yaml --dry-run
```

| Opción | Efecto |
|---|---|
| `--profile <nombre>` | Levanta solo los nodos del perfil. |
| `--dry-run` | Imprime los comandos sin ejecutarlos. |
| `--keep-going` | No se detiene en el primer error. |
| `--no-snapshot` | No crea el snapshot `initial`. |

```
running the plan (Ctrl-C to interrupt; run it again to continue):
  [ 1/66] profile netseclab for the nodes (ignored if it already exists)
  ...
  [66/66] dmz: mirror port cap-dmz (OVS)

66 steps run
snapshot 'initial' created: `lab reset` returns here
```

La ejecución es idempotente: los pasos que fallan con «already exists» se consideran hechos. Si se
interrumpe, volver a lanzar el comando continúa donde se quedó. Sin Incus termina con el código `3` y
recuerda que `lab render` no lo necesita.

### `down`

Para las instancias de un laboratorio.

```bash
lab down lab/examples/example.net.yaml
lab down lab/examples/example.net.yaml --profile mini
lab down lab/examples/example.net.yaml fw exta
lab down lab/examples/example.net.yaml --dry-run
```

| Opción | Efecto |
|---|---|
| `names` | Nombres concretos de nodo; si se omiten, se para el perfil. |
| `--profile <nombre>` | Perfil que se para cuando no se dan nombres. |
| `--dry-run` | Solo imprime los `incus stop`. |

```
fw: stopped
exta: stopped
```

No borra instancias, redes ni imágenes: `lab up` reutiliza lo que ya existe.

### `status`

Lista las instancias de Incus con su estado y sus direcciones IPv4.

```bash
lab status
```

| Opción | Efecto |
|---|---|
| — | Sin opciones. |

Lista todas las instancias de la caja, no solo las de la topología actual. Si no hay ninguna, imprime
`no instances`.

## Ciclo de vida

### `console`

Abre la consola interactiva de un nodo.

```bash
lab console exta
```

```
Connecting to exta. To leave: Ctrl-a, then q.
```

Para salir: `Ctrl-a`, soltar y pulsar `q`. Si el nodo no está arrancado, muestra su log con
`incus console --show-log` en lugar de abrir una sesión. Un nodo inexistente devuelve `1`.

### `snapshot`

Crea un snapshot de todos los nodos del laboratorio.

```bash
lab snapshot lab/examples/example.net.yaml --name antes-del-ataque
```

| Opción | Efecto |
|---|---|
| `--name <nombre>` | Nombre del snapshot; por defecto `snapshot`. |
| `--profile <nombre>` | Limita el snapshot al perfil. |

```
snapshot 'antes-del-ataque' created on 7 nodes
```

Los snapshots que ya existen se respetan: crear dos veces el mismo nombre no falla.

### `reset`

Restaura un snapshot en todos los nodos del laboratorio y los vuelve a arrancar.

```bash
lab reset lab/examples/example.net.yaml
lab reset lab/examples/example.net.yaml --name antes-del-ataque
```

| Opción | Efecto |
|---|---|
| `--name <nombre>` | Snapshot que se restaura; por defecto `initial`. |
| `--profile <nombre>` | Limita la restauración al perfil. |

```
lab restored to 'initial' on 7 nodes
```

Si el snapshot no existe, informa del nodo afectado y recuerda cómo crearlo. Devuelve `1`.

## Captura y acceso

### `capture`

Captura tráfico de un segmento durante un número de segundos.

```bash
lab capture lab/examples/example.net.yaml --net dmz --seconds 20
lab capture lab/examples/fuzz-evasion.yaml --net ext --seconds 10 --out /tmp/ext.pcap
```

| Opción | Efecto |
|---|---|
| `--net <nombre>` | Segmento que se captura; obligatorio. |
| `--seconds <n>` | Duración en segundos; por defecto 15. |
| `--out <ruta>` | Fichero de salida; por defecto `capture/<segmento>.pcap`. |

```
capturing on mirror port cap-dmz for 20s -> capture/dmz.pcap
```

El mecanismo depende del `mode` de la red: puerto espejo en `mirror` (necesita `sudo`), interfaz
promiscua de un nodo en `hub` y en `switch`. En `hub` se ve todo el segmento; en `switch`, solo el
tráfico del nodo que captura.

### `web`

Sirve consolas de los nodos en el navegador.

```bash
lab web lab/examples/example.net.yaml --port 8080
lab web lab/examples/example.net.yaml --host 0.0.0.0 --token token-de-ejemplo
lab web
```

| Opción | Efecto |
|---|---|
| `file` | Topología opcional; sin ella se ofrecen las instancias existentes. |
| `--profile <nombre>` | Limita las consolas al perfil. |
| `--host <dirección>` | Dirección de escucha; por defecto `127.0.0.1`. |
| `--port <puerto>` | Puerto de escucha; por defecto `8080`. |
| `--token <valor>` | Exige el token en la URL de la API. |

```
consoles at http://127.0.0.1:8080  (7 nodes)
Ctrl-C to stop
```

Abrir el servidor a la red da una shell dentro del laboratorio: usar `--token` y una red de gestión.

## Ejercicios

### `check`

Corrige un ejercicio: ejecuta sus comprobaciones contra el laboratorio y compara las respuestas
entregadas.

```bash
lab check lab/exercises/01-reconocimiento.yaml
```

```
01-reconocimiento - Reconocimiento de servicios con nmap
1/1 answers correct - 5/5 points
3/3 environment checks passed

ANSWERS
  [OK  ]   5 pt  ¿Qué puerto de www aparece como «closed» desde exta?
          answer: 443

ENVIRONMENT
  [OK   ] from exta, www:80 is open
          state=open (expected open)
```

Devuelve `0` si todo está correcto, `1` si algo falla, `2` si el ejercicio no es válido y `3` si tiene
comprobaciones de laboratorio pero no hay Incus. Si el ejercicio lleva valores en claro, avisa de que
esa copia no está limpia para distribuir.

### `answer`

Entrega el valor de una respuesta.

```bash
lab answer lab/exercises/01-reconocimiento.yaml puerto-cerrado "443"
```

```
answer 'puerto-cerrado' saved to answers/01-reconocimiento.json
run `lab check lab/exercises/01-reconocimiento.yaml` to see whether it is correct
```

Escribe en `answers/<ejercicio>.json`, dentro del directorio de trabajo. Un identificador que no
existe en el ejercicio devuelve `2` y lista los disponibles.

### `report`

Genera la plantilla del informe escrito.

```bash
lab report lab/exercises/01-reconocimiento.yaml
lab report lab/exercises/01-reconocimiento.yaml --out informe.md
```

| Opción | Efecto |
|---|---|
| `--out <ruta>` | Escribe la plantilla en un fichero; sin ella, la imprime en el terminal. |

La plantilla incluye título, identificador, fecha, alumno, tabla de respuestas entregadas y una
sección por cada pregunta de `report`.

### `hash`

Calcula el `sha256` normalizado de un valor, para publicar ejercicios sin el valor en claro.

```bash
lab hash "10.5.0.10"
# 57451d7709e7eddd408baabf503546ac3947d4deaa3be15cd12d6dbf3441d259
```

La normalización quita espacios sobrantes y comillas, colapsa espacios y no distingue mayúsculas. Las
tildes cuentan.

## Distribución

### `pack`

Empaqueta una topología, sus ficheros y el lock en un `.labpack`.

```bash
lab pack lab/examples/fuzz-evasion.yaml --out fuzz.labpack \
  --exercise lab/exercises/06-fuzz-evasion.yaml
```

| Opción | Efecto |
|---|---|
| `--out <ruta>` | Fichero de salida; obligatorio. |
| `--name <nombre>` | Nombre del laboratorio; por defecto, el del fichero de topología. |
| `--file <ruta>` | Fichero adicional; repetible. |
| `--exercise <ruta>` | Ejercicio adicional; repetible. |
| `--lock <ruta>` | Lock que se incluye si existe; por defecto `lab.lock`. |
| `--sign <clave>` | Firma el paquete con una clave privada de OpenSSH y deja `<paquete>.sig`. |

```
packed 2 files into fuzz.labpack
signed: fuzz.labpack.sig
```

Los ficheros tienen que estar dentro del directorio de trabajo desde el que se ejecuta el comando. La
firma necesita `ssh-keygen` (OpenSSH 8.2 o posterior).

### `unpack`

Verifica un `.labpack` y lo extrae. Acepta una ruta o una URL.

```bash
lab unpack fuzz.labpack --to /tmp/laboratorio
lab unpack https://bucket.universidad.edu/labs/fuzz.labpack --to /tmp/laboratorio \
  --signer https://bucket.universidad.edu/labs/profesor.pub
```

| Opción | Efecto |
|---|---|
| `--to <directorio>` | Destino de la extracción; obligatorio. |
| `--signer <clave.pub>` | Clave pública aceptada, o su URL; repetible. |
| `--signature <ruta>` | Firma que se comprueba; por defecto `<paquete>.sig`. |

```
signature ok: Good "netseclab" signature for netseclab with ED25519 key SHA256:…
2 files extracted into /tmp/laboratorio
```

Comprueba formato, versión, hashes y rutas **antes de escribir nada**. Si un fichero no coincide o
falta, no extrae ninguno y devuelve `2`. Con `--signer`, la firma se comprueba antes que los hashes y
un paquete sin firmar o firmado por otra clave también devuelve `2`. Sin `--signer` no se mira la
firma: el paquete se verifica con sus checksums.

### `push`

Publica una imagen en una caché de directorio.

```bash
lab push lab-node-v1 --to /mnt/bucket
```

```
lab-node-v1 -> /mnt/bucket  sha256:3f2a9c1b7e4d  1288490188 bytes
```

Exporta la imagen de Incus y la añade al índice de la caché. Necesita Incus y un directorio de
destino.

### `pull`

Trae una imagen de la caché, verifica su `sha256` y la importa.

```bash
lab pull lab-node-v1 --from /mnt/bucket
lab pull lab-node-v1 --from https://bucket.universidad.edu/tynix --as node-base
```

| Opción | Efecto |
|---|---|
| `--from <ruta\|url>` | Directorio de caché o URL de solo lectura; obligatorio. |
| `--as <alias>` | Alias local; por defecto, el nombre de la entrada. |

```
lab-node-v1 imported as lab-node-v1 (sha256 verified)
```

Si el hash no coincide, no importa nada y devuelve `1`.

### `lock`

Clava los entornos declarados por una topología en un `lab.lock`.

```bash
lab lock labs/edr-intro/lab.yaml
lab lock labs/edr-intro/lab.yaml --check
```

| Opción | Efecto |
|---|---|
| `--out <ruta>` | Dónde escribir el lock; por defecto `lab.lock`. |
| `--check` | Compara con el lock existente y falla si hay deriva. |

```
1 environments locked in lab.lock
```

Con `--check` imprime `<ruta>: up to date` o las diferencias (`added`, `removed`, `changed`) y devuelve
`1` si hay deriva. Una topología sin entornos devuelve `2`.

### `gc`

Borra las imágenes del proyecto que ningún laboratorio referencia.

```bash
lab gc lab/examples/example.net.yaml
lab gc lab/examples/example.net.yaml --yes
lab gc --keep lab-web-v1 --yes
```

| Opción | Efecto |
|---|---|
| `files` | Topologías cuyas imágenes hay que conservar. |
| `--keep <alias>` | Alias que se conserva; repetible. |
| `--prefix <prefijo>` | Prefijo gestionado; repetible; por defecto `lab-` y `lab/`. |
| `--yes` | Borra de verdad; sin esta opción solo enseña lo que borraría. |

```
4 images, 1 referenced, 3 to remove
  lab-env-env-9c1f0a2b7e44
  ...

nothing deleted: run again with --yes
```

Sin topologías ni `--keep` devuelve `2`: no se borra nada sin saber qué conservar.

## Imágenes y catálogo

### `images`

Lista el catálogo de alias de imagen del repositorio.

```bash
lab images
```

```
attacker     lab-attacker-v1
debian13     lab-node-v1
ids          lab-ids-v1
soc-lite     lab-soc-lite-v1
web          lab-web-v1
```

### `image`

Construye, lista y borra imágenes propias.

```bash
lab image build images/recipes/web.yaml
lab image build images/recipes/attacker.yaml --dry-run
lab image ls
lab image rm lab/web:1
```

| Subcomando | Efecto |
|---|---|
| `build <receta>` | Construye la imagen y la publica como `lab/<nombre>:<versión>`. |
| `build <receta> --dry-run` | Enseña el plan de construcción sin ejecutarlo. |
| `build <receta> --keep-going` | No se detiene en el primer paso fallido. |
| `ls` | Lista las imágenes locales con alias `lab/`. |
| `rm <ref>` | Borra una imagen. |

```
image lab/web:1 from debian13 (9 steps)
-> incus delete lab-build-web --force
-> incus launch lab-node-v1 lab-build-web --profile netseclab
-> incus config device override lab-build-web root size=4GB
...
```

### `toolsets`

Lista los conjuntos de herramientas de `lab/toolsets.yaml`.

```bash
lab toolsets
```

```
blue        5 packages  auditd aide fail2ban lynis rkhunter
crack       3 packages  hydra john medusa
recon       6 packages  nmap masscan dnsutils whatweb whois curl
sniff       4 packages  tcpdump tshark bettercap tcpflow
tls         3 packages  openssl sslscan certbot
traffic     5 packages  hping3 scapy iperf3 tcpreplay dsniff
webapp      4 packages  sqlmap wfuzz whatweb curl
webfuzz     5 packages  ffuf gobuster dirb curl jq
```

### `init`

Crea una topología de partida a partir de un escenario de ejemplo.

```bash
lab init milab
lab validate milab/topology.yaml
```

```
created milab/topology.yaml - edit it and run: lab up milab/topology.yaml
```

El fichero se crea en `<nombre>/topology.yaml`; si el directorio ya existe, devuelve `1` sin tocar
nada. La plantilla es el escenario `pivot` con el nombre cambiado.
