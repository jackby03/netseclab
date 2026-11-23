# Uso diario

Esta página reúne las operaciones habituales dentro de la caja: levantar, entrar, capturar,
fotografiar, restaurar y apagar un laboratorio.

## Levantar el laboratorio

```bash
lab up lab/examples/example.net.yaml
```

`lab up` valida la topología, construye el plan y lo ejecuta contra Incus. Al terminar crea un
snapshot llamado `initial` en cada nodo: es el estado al que vuelve `lab reset`.

| Opción | Efecto |
|---|---|
| `--profile <nombre>` | Levanta solo los nodos del perfil declarado. |
| `--dry-run` | Imprime los comandos del plan sin ejecutarlos. |
| `--keep-going` | No se detiene en el primer error; sigue con el resto de pasos. |
| `--no-snapshot` | No crea el snapshot `initial` al terminar. |

`lab up` es idempotente: si se interrumpe con `Ctrl-C` o un paso falla, volver a ejecutarlo continúa
donde se quedó y los pasos que ya estaban hechos se omiten. El arranque de siete nodos tarda alrededor
de un minuto y medio; los perfiles pequeños tardan menos.

Los perfiles se declaran en la topología y agrupan nodos:

```bash
lab up lab/examples/example.net.yaml --profile mini
lab up lab/examples/example.net.yaml --profile std
lab up lab/examples/example.net.yaml --profile full
```

## Ver el estado

```bash
lab status
```

```
name         state        type       ipv4
base         Running      container  10.5.0.1, 10.5.1.1, 10.5.2.1
fw           Running      container  10.5.0.254, 10.5.1.254, 10.5.2.254
exta         Running      container  10.5.0.10
dmza         Running      container  10.5.1.10
inta         Running      container  10.5.2.10
```

`lab status` no recibe argumentos: lista todas las instancias de Incus que haya en la caja, no solo las
de la topología actual.

## Entrar en un nodo

```bash
lab console exta
```

La consola es la de Incus. Para salir: `Ctrl-a`, soltar y pulsar `q`. `Ctrl-C` solo interrumpe el
programa que esté en primer plano; para cerrar la consola hace falta la secuencia de Incus.

Si el nodo no está arrancado, `lab console` muestra su log en lugar de una sesión que no puede
funcionar:

```
exta is not running; showing its log instead. Bring the lab up to get an interactive console.
```

Los nodos aceptan `root` y `user1`, ambos con la contraseña `netseclab`. `user1` tiene `sudo`.

## Consolas en el navegador

```bash
lab web lab/examples/example.net.yaml --port 8080
```

El servidor escucha en `127.0.0.1:8080` por defecto, así que solo es accesible desde dentro de la
caja. Para abrirlo al anfitrión, usar `--host 0.0.0.0` y entrar desde el navegador en
`http://<ip-de-la-caja>:8080`; también se puede reenviar el puerto desde el hipervisor. Una pestaña
por nodo del perfil, sin instalar nada en el portátil.

| Opción | Efecto |
|---|---|
| `--host <dirección>` | Dirección de escucha; por defecto `127.0.0.1`. |
| `--port <puerto>` | Puerto de escucha; por defecto `8080`. |
| `--token <valor>` | Exige el token en la URL de la API. |
| `--profile <nombre>` | Limita las consolas al perfil indicado. |

Sin fichero de topología, `lab web` ofrece las instancias que ya existan en Incus.

!!! warning "Exponer las consolas"
    `lab web` da una shell dentro de un laboratorio de ataque. Si se abre a la red, usar siempre
    `--token` y mantenerlo en una red de gestión separada.

## Capturar tráfico

```bash
lab capture lab/examples/example.net.yaml --net dmz --seconds 20
```

El pcap se escribe en `capture/dmz.pcap` y el comando termina solo al agotarse el tiempo indicado
(15 segundos por defecto). Con `--out <ruta>` se cambia el destino.

| `mode` de la red | Qué se captura |
|---|---|
| `mirror` | El puerto espejo del switch Open vSwitch; requiere `sudo`. |
| `hub` | Un nodo del segmento en modo promiscuo: se ve todo el segmento. |
| `switch` | Un nodo del segmento: solo se ve el tráfico de ese nodo. |

La diferencia entre `hub` y `switch` no es un detalle: decide si un ejercicio de sniffing funciona o
fracasa. El modo se elige por red en el YAML.

## Snapshots y reinicio

`lab up` crea el snapshot `initial`. Además se pueden crear snapshots con nombre antes de una
práctica destructiva:

```bash
lab snapshot lab/examples/example.net.yaml --name antes-del-ataque
lab reset lab/examples/example.net.yaml --name antes-del-ataque
```

`lab reset` sin `--name` vuelve a `initial`. La restauración se hace nodo a nodo: se para la
instancia, se restaura el snapshot y se vuelve a arrancar. Así el laboratorio queda listo, no a
medias. Los snapshots son de Incus y con el almacenamiento copy-on-write de la caja son instantáneos.

```bash
lab reset lab/examples/example.net.yaml
```

```
lab restored to 'initial' on 7 nodes
```

Si el snapshot no existe, `lab reset` lo dice y recuerda cómo crearlo:

```
  fw: snapshot 'initial' does not exist

Snapshot 'initial' does not exist? Create it with `lab up` (it takes 'initial' at the end) or with
`lab snapshot <file>`.
```

## Parar el laboratorio

```bash
lab down lab/examples/example.net.yaml
```

Para los nodos del perfil por defecto. Se puede indicar un perfil o una lista de nombres:

```bash
lab down lab/examples/example.net.yaml --profile mini
lab down lab/examples/example.net.yaml fw exta
lab down lab/examples/example.net.yaml --dry-run
```

`lab down` para las instancias, no las borra ni borra las redes. Volver a ejecutar `lab up` reutiliza
lo que ya existe.

## Inspeccionar el plan

Antes de arrancar o para depurar, el plan se puede leer entero:

```bash
lab render lab/examples/example.net.yaml --format table
lab render lab/examples/example.net.yaml --format shell
lab render lab/examples/fuzz-evasion.yaml --format json
```

| Formato | Salida |
|---|---|
| `table` | Resumen de redes, nodos y número de pasos (por defecto). |
| `shell` | Script `sh` con los comandos exactos que ejecutaría `lab up`. |
| `json` | Plan estructurado, pensado para pruebas y herramientas. |

`lab render --out <directorio>` escribe los ficheros generados que se copiarían a los nodos, más
`lab.sh` y `plan.json`. Es la forma de revisar la configuración sin Incus:

```bash
lab render lab/examples/example.net.yaml --out /tmp/plan
find /tmp/plan -type f | sort
```

`lab up --dry-run` es equivalente a leer el plan en shell, pero precedido del resumen en tabla.

## Credenciales y acceso

| Dónde | Usuario | Contraseña | Acceso |
|---|---|---|---|
| Caja (consola de VMware) | `lab` | `netseclab` | Consola; SSH solo con clave. |
| Nodos | `root` | `netseclab` | Consola y SSH con contraseña. |
| Nodos | `user1` | `netseclab` | Consola y SSH con contraseña; `sudo`. |

La caja solo acepta clave para SSH: la contraseña sirve para la consola. La clave pública se genera
durante la construcción y queda en `build/box/id_ed25519`. El SSH de los nodos acepta contraseña a
propósito, para que las prácticas de SSH funcionen.

## Problemas frecuentes

| Síntoma | Qué mirar |
|---|---|
| `lab up` falla al crear una red | `incus network list`: puede quedar una red a medias de un intento anterior. |
| Un nodo no arranca | `incus info <nodo>` y `incus console --show-log <nodo>`. |
| No hay conectividad entre segmentos | `incus exec fw -- nft list ruleset` y `incus exec fw -- sysctl net.ipv4.ip_forward`. |
| Un nodo no tiene IP | `incus exec <nodo> -- systemctl status lab-net` y `journalctl -u lab-net`. |
| El IDS no genera alertas | `incus exec fw -- tail /var/log/suricata/suricata.log`. |
| `lab reset` dice que no existe el snapshot | `lab up` crea `initial`; o crear uno con `lab snapshot`. |
| El disco se llena | `df -h /`; liberar imágenes con `lab gc` o borrar snapshots que ya no se usen. |
| Incus rechaza el acceso | El usuario `lab` tiene que pertenecer al grupo del socket de Incus; la caja lo configura al construirla. |

Cuando algo va mal, `lab render <topología> --format shell` da el plan completo en texto: se puede
leer, comparar con el estado real y ejecutar a mano.

## Tareas de mantenimiento

```bash
lab gc lab/examples/example.net.yaml           # enseña las imágenes que sobran
lab gc lab/examples/example.net.yaml --yes     # las borra
```

`lab gc` solo toca imágenes con los prefijos del proyecto (`lab-` y `lab/`) y exige saber qué
conservar: una topología o una lista de alias con `--keep`. Sin `--yes` no borra nada. Las respuestas
entregadas se guardan en `answers/<ejercicio>.json` dentro del directorio de trabajo y no se
versionan.
