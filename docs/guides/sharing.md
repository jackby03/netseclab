# Compartir laboratorios

Esta página explica cómo se empaqueta un laboratorio, cómo se clavan sus entornos y cómo se
distribuye sin construir imágenes.

## La idea

Un laboratorio es texto, no una imagen. La topología, los ejercicios, los ficheros del escenario y el
lock de sus entornos pesan kilobytes o unos pocos megas, se versionan en Git y se descargan con una
orden. La caja se construye una vez por curso; los laboratorios cambian cada semana.

## Entornos reproducibles con tynix

`tynix` es un paquete independiente —`src/tynix/`— que aplica la idea de Nix a los contenedores de
Incus sin usar Nix ni NixOS: la base sigue siendo Debian y el alumno ve un Linux normal. No importa
nada de `lab`, de modo que se prueba por separado.

Un nodo puede declarar un **entorno** en vez de una imagen concreta:

```yaml
nodes:
  - name: fw
    environment:
      base: debian13
      packages: [nftables, suricata]
      startup:
        - systemctl enable --now suricata
```

El manifiesto del entorno tiene cuatro partes: la imagen base con su huella, los paquetes con versión
y hash, los ficheros inyectados y los comandos de arranque. La declaración de la topología usa base,
paquetes y arranque; los ficheros forman parte del manifiesto de tynix, no del YAML del laboratorio.

El nombre de la imagen se deriva del `sha256` de una serialización canónica del manifiesto:

```
lab-env-env-<12 primeros caracteres del hash>
```

Cambiar un paquete cambia el nombre y produce una imagen distinta; la anterior queda intacta. Dos
nodos con la misma declaración comparten la misma imagen, y `lab up` añade un paso idempotente que la
construye solo si no existe:

1. Comprueba `incus image info`.
2. Arranca una instancia temporal desde la base.
3. Instala los paquetes y ejecuta el arranque.
4. La para, la publica con el alias direccionado por contenido y la borra.

Construir un entorno nuevo instala paquetes con `apt` y necesita acceso a los repositorios de Debian;
la caja sale por la NAT de VMware. Las imágenes de fábrica ya llevan sus paquetes y no pasan por esta
fase.

## Lock de entornos

`lab lock` clava los entornos declarados por una topología en un `lab.lock`:

```bash
lab lock labs/edr-intro/lab.yaml
lab lock labs/edr-intro/lab.yaml --check
```

| Opción | Efecto |
|---|---|
| `--out <ruta>` | Dónde escribir el lock; por defecto `lab.lock`. |
| `--check` | Compara con el lock existente y falla si hay deriva. |

El lock guarda la base, los paquetes, los ficheros y el arranque del entorno declarado. La
comprobación compara por hash de contenido y distingue tres casos: entorno añadido, eliminado o
cambiado. Si la topología no declara ningún entorno, el comando termina con error.

!!! warning "Limitación conocida"
    El lock usa un único nombre de entorno (`env`) por topología. Si una topología declara entornos
    distintos, solo queda clavado el último. Para trabajar con varios entornos conviene usar una
    topología por entorno mientras esta limitación siga abierta.

## Caché de imágenes

Una caché es un directorio —el bucket montado, un pendrive, una carpeta compartida— o una URL de solo
lectura. El índice `index.json` contiene, por cada imagen, su nombre, su `sha256` y su tamaño; el
tarball de la imagen se guarda junto a él como `<nombre>.tar.gz`.

```bash
# Publicar una imagen exportándola de Incus
lab push lab-node-v1 --to /mnt/bucket

# Traerla a otra caja, verificando el hash antes de importarla
lab pull lab-node-v1 --from /mnt/bucket

# Desde una URL de solo lectura, con otro alias local
lab pull lab-node-v1 --from https://bucket.universidad.edu/tynix --as node-base
```

`lab push` necesita Incus y un directorio de destino; escribe la imagen y actualiza el índice.
`lab pull` acepta un directorio o una URL, verifica el `sha256` de lo descargado y **no importa** la
imagen si no coincide.

El alias importado no se añade a `lab/images.yaml`: para usarlo desde una topología hay que referenciar
la referencia completa o añadirlo al catálogo. Publicar en una URL es cosa del sistema de ficheros o
del cliente del bucket: la caché HTTP es de solo lectura.

## Recolección de imágenes

```bash
lab gc lab/examples/example.net.yaml
lab gc lab/examples/example.net.yaml --yes
lab gc --keep lab-web-v1 --yes
```

`lab gc` borra las imágenes del proyecto que ningún laboratorio referencia. Solo considera candidatas
las que empiezan por los prefijos gestionados (`lab-` y `lab/`; se puede cambiar con `--prefix`) y
nunca toca las imágenes del sistema. Exige saber qué conservar: una o varias topologías, o alias con
`--keep`. Sin `--yes` solo enseña lo que borraría.

`lab gc` conserva lo que las topologías referencian en `image:`. Las imágenes de entorno
(`lab-env-*`) no se deducen de una topología que use `environment:`, así que hay que conservarlas con
`--keep` mientras esa relación no esté resuelta.

## Paquetes de laboratorio

Un `.labpack` es un `tar.gz` con un manifiesto y el contenido del laboratorio:

```
edr-intro.labpack
├── labpack.json                 manifiesto: formato, versión, nombre, fecha y sha256 de cada fichero
├── lab/examples/edr-intro.yaml  topología
├── lab/exercises/01-edr.yaml    ejercicios
├── lab.lock                     entornos clavados, si existe
└── …                            cualquier otro fichero del escenario

edr-intro.labpack.sig            firma del paquete, si el autor lo firmó
```

```bash
# Profesor: empaquetar
lab pack labs/edr-intro/lab.yaml --out edr-intro.labpack \
  --exercise labs/edr-intro/exercises/01-edr.yaml

# Alumno: verificar y extraer
lab unpack edr-intro.labpack --to labs/edr-intro
```

| Opción de `lab pack` | Efecto |
|---|---|
| `--out <ruta>` | Fichero de salida; obligatorio. |
| `--name <nombre>` | Nombre del laboratorio; por defecto, el nombre del fichero de topología. |
| `--file <ruta>` | Fichero adicional; repetible. |
| `--exercise <ruta>` | Ejercicio adicional; repetible. |
| `--lock <ruta>` | Lock que se incluye si existe; por defecto `lab.lock`. |
| `--sign <clave>` | Firma el paquete con una clave privada de OpenSSH. |

Los ficheros que se empaquetan tienen que estar dentro del directorio de trabajo desde el que se
ejecuta `lab pack`; sus rutas se guardan relativas a él. El manifiesto lista cada fichero con su
`sha256` y su tamaño en orden alfabético.

`lab unpack` verifica **todo** antes de escribir nada: formato y versión del manifiesto, que todos los
ficheros estén listados, que no falte ninguno y que cada hash coincida. Después extrae con
comprobación de rutas: un miembro que intente escribir fuera del destino se rechaza.

El paquete no se ejecuta al abrirlo. Solo se verifica y se extrae; los `assets` se copian y los
`startup` se ejecutan dentro de los nodos cuando el alumno hace `lab up`.

## Firma: de quién es el paquete

Los checksums detectan corrupción, no suplantación: quien manipule un paquete puede recalcular los
hashes y el resultado cuadra. La firma es lo que ata el paquete a una clave.

Se firma con **OpenSSH** (`ssh-keygen -Y sign`), el mismo mecanismo con el que GitHub firma commits.
No hace falta GPG, ni llavero, ni autoridad de certificación: la clave pública del profesor es un
fichero `.pub` de una línea, la misma que ya usa para el SSH.

```bash
# Profesor: firmar al empaquetar
lab pack labs/edr-intro/lab.yaml --out edr-intro.labpack --sign ~/.ssh/id_ed25519
# packed 3 files into edr-intro.labpack
# signed: edr-intro.labpack.sig

# Alumno: aceptar solo paquetes firmados por esa clave
lab unpack edr-intro.labpack --to labs/edr-intro --signer profesor.pub
# signature ok: Good "netseclab" signature for netseclab with ED25519 key SHA256:…
# 3 files extracted into labs/edr-intro
```

| Opción de `lab unpack` | Efecto |
|---|---|
| `--to <directorio>` | Destino de la extracción; obligatorio. |
| `--signer <clave.pub>` | Clave pública aceptada, o su URL; repetible. Sin esta opción no se mira la firma. |
| `--signature <ruta>` | Firma que se comprueba; por defecto `<paquete>.sig`. |

La huella de la clave se publica junto al enunciado, para que el alumno pueda comprobar que el `.pub`
que le han dado es el que toca:

```bash
ssh-keygen -lf profesor.pub
# 256 SHA256:… profesor@universidad (ED25519)
```

Qué garantiza y qué no:

- **Garantiza** que el paquete lo firmó quien tiene esa clave privada y que no se ha tocado después:
  la firma cubre el fichero entero, no el manifiesto.
- **No garantiza** que la clave sea de quien crees: eso lo resuelve el canal por el que te llega la
  `.pub`. Compárala con la del enunciado del curso o con su huella.
- **No hay revocación**: si una clave se filtra, hay que repartir otra y volver a firmar.
- `--signer` es optativo a propósito: sin él, el paquete se verifica con los checksums de siempre. Un
  paquete sin firma no se rechaza por defecto —quien quiera exigirla la exige—, pero si pides firma y
  falta, `lab unpack` falla.

## Descargar de una URL

`lab unpack` acepta una ruta o una URL. El bucket del curso no necesita nada especial: un servidor
estático sirve.

```bash
lab unpack https://bucket.universidad.edu/labs/edr-intro.labpack \
  --to labs/edr-intro --signer https://bucket.universidad.edu/labs/profesor.pub
```

La firma se busca en `<url>.sig`; si está en otro sitio, se pasa con `--signature`. La descarga va a
un directorio temporal que se borra al terminar, y el paquete se verifica igual que si estuviera en
disco.

## Confianza y límites

La cadena completa tiene tres eslabones: el manifiesto (integridad de cada fichero), la firma (autoría
del paquete) y la clave pública (quién es el autor). Los dos primeros los comprueba `lab`; el tercero
lo comprueba el profesor cuando publica su clave y el alumno cuando decide aceptarla.

Las **herramientas por nodo** (`tools:`) siguen pendientes. Hoy las herramientas propias se consiguen
con una receta de imagen, con un toolset o con `packages:` en el nodo.
