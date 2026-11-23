# Arquitectura

Esta página explica cómo se convierte una topología YAML en un laboratorio en marcha y qué
componentes intervienen por dentro.

## Vista general

```
Portátil del alumno — VMware Workstation o Player
│
└── Caja · Debian 13 mínimo · 2 vCPU · 2 GB de RAM · 12 GB de disco
    │
    ├── incus
    │   ├── perfil netseclab        disco raíz de los nodos
    │   ├── nvm-ext / nvm-dmz / …   bridges de los segmentos
    │   └── base, fw, exta, dmza…   contenedores de sistema
    │
    ├── lab · CLI Python             up · down · status · console · capture…
    ├── consolas web · PTY + HTTP   una pestaña por nodo en :8080
    └── capturas · capture/*.pcap   puerto espejo o interfaz del nodo
```

La caja es una VM de Debian sin escritorio con Incus, el CLI y las imágenes de nodo ya construidas.
Dentro no hay máquinas virtuales: los nodos son contenedores de sistema y comparten el kernel de la
caja.

## Principios de diseño

| Principio | Consecuencia |
|---|---|
| Sin virtualización anidada | La caja es la única VM; los nodos son contenedores. |
| La topología es un dato | Un YAML genera redes, nodos, DHCP, DNS, cortafuegos y plan. |
| Nodo como composición | Imagen, toolsets, paquetes, assets y arranque; roles reutilizables. |
| Estado reversible | Snapshot `initial` y `lab reset` en segundos. |
| Ejercicios comprobables | Hechos del laboratorio y respuestas estrictas, sin revisar capturas. |
| Aislamiento por defecto | Imágenes y paquetes cacheados; la salida se expresa en el tipo de red. |
| Reconstruible y verificable | Código abierto, Debian fijado y checksums en la distribución. |

## De la topología al plan

Toda orden que arranca o inspecciona un laboratorio recorre la misma cadena:

| Fase | Qué hace | Módulo |
|---|---|---|
| Carga y validación | Lee el YAML, rechaza claves desconocidas, valida redes, nodos, perfiles y políticas y deriva IP y MAC que falten. | `model.py` |
| Resolución | Traduce alias de imagen y toolsets, resuelve los entornos de tynix a un nombre de imagen y construye una lista de pasos. | `plan.py`, `catalog.py`, `environments.py` |
| Ejecución | Ejecuta cada paso contra Incus, copia los ficheros generados y crea el snapshot `initial`. | `engine/lifecycle.py`, `engine/incus.py` |

El plan es un objeto inspeccionable antes de ejecutarse. `lab render` lo imprime en tabla, shell o
JSON; `lab render --out <dir>` escribe en disco los ficheros que se copiarían a los nodos, además de
`lab.sh` y `plan.json`. `lab up --dry-run` enseña los comandos sin tocar Incus.

Los errores de validación no se lanzan de uno en uno: se acumulan y se presentan con la ruta exacta
del YAML y una sugerencia cuando la clave está mal escrita. `lab up` es idempotente: los pasos que
fallan con «already exists» se consideran hechos y volver a ejecutarlo continúa donde se quedó.

## Componentes

| Componente | Papel |
|---|---|
| `model.py` | Modelo tipado de la topología, validación y derivación de direcciones. |
| `plan.py` | Construye los pasos: perfil, redes, nodos, paquetes, ficheros, activación y conmutación. |
| `generate/` | Genera `dnsmasq`, `/etc/hosts`, red por nodo, `nftables` y telemetría. |
| `engine/` | Habla con Incus, ejecuta el plan, gestiona snapshots y capturas. |
| `checks.py` | Convierte las comprobaciones de un ejercicio en comandos dentro del laboratorio. |
| `answers.py` | Normaliza y compara respuestas estrictas por `sha256`. |
| `exercise.py` | Carga y valida el YAML de un ejercicio. |
| `images.py` | Construye imágenes propias a partir de una receta. |
| `environments.py` | Resuelve entornos tynix y añade el paso que construye su imagen. |
| `labpack.py` | Empaqueta y verifica laboratorios distribuibles. |
| `web.py` | Servidor HTTP mínimo con un PTY por nodo. |
| `tynix/` | Manifiestos, lock, caché y almacén de entornos reproducibles. |
| `cli.py` | Define los comandos y su salida. |

## Qué se escribe dentro de un nodo

Los ficheros de configuración son generados: se recalculan en cada `lab up` y no se editan a mano
dentro del nodo.

| Ruta | Origen |
|---|---|
| `/etc/hostname` | Nombre del nodo o `hostname:`. |
| `/etc/hosts` | Todos los nodos del escenario, sus alias y sus primeras direcciones. |
| `/usr/local/sbin/lab-net` y `lab-net.service` | Direcciones, rutas, DHCP de cliente y `sysctls`. |
| `/etc/sysctl.d/90-lab.conf` | `sysctls:` del nodo. |
| `/usr/local/sbin/lab-startup` y `lab-startup.service` | `startup:` y `env:` del nodo. |
| `/etc/dnsmasq.d/lab.conf` | Nodo con `dhcp_server` o `dns_server`. |
| `/etc/lab/fw.nft` | Nodo con `firewall: true`, a partir de `policies:`. |
| `/etc/rsyslog.d/50-lab*.conf` | Nodos con telemetría o que actúan de SOC. |
| Rutas de `assets:` | Ficheros o directorios copiados al nodo. |

## Red

Cada segmento es un bridge de Incus llamado `nvm-<segmento>`. El `type` decide la dirección y la
salida: `isolated` no tiene dirección en la caja, `nat` lleva dirección y NAT, `bridged` cuelga de
una interfaz física. El `mode` decide el conmutador: `switch` aprende MAC, `hub` inunda todos los
puertos y `mirror` usa Open vSwitch con un puerto espejo.

El nodo que declara `dhcp_server: true` ejecuta `dnsmasq` en sus interfaces. Las reservas son por MAC,
las direcciones automáticas se reparten desde `.10`, el rango DHCP se calcula dentro de la red (en las
redes `/24` de los ejemplos, de `.100` a `.199`) y las rutas a otros segmentos se reparten con la
opción 121.

El nodo que declara `dns_server: true` publica registros A, PTR y alias para el dominio del escenario.

El nodo con `firewall: true` recibe las reglas `nftables` derivadas de `policies:`. La cadena de
entrada acepta el tráfico establecido y el lazo local; la cadena de reenvío aplica las políticas y
tiene política `drop` cuando el nodo tiene alguna regla que lo afecte. `drop` produce puertos
filtrados y `reject-reset` produce puertos cerrados: la asimetría es didáctica y deliberada.

## Incus

`lab` no esconde la herramienta. Las prácticas pueden usar `incus list`, `incus exec`,
`incus config show` y `incus network list` directamente.

| Objeto de Incus | Nombre | Para qué |
|---|---|---|
| Perfil | `netseclab` | Disco raíz de los nodos, heredado del pool por defecto. |
| Red | `nvm-<segmento>` | Bridge de cada segmento. |
| Instancia | Nombre del nodo | Contenedor de sistema con límites de CPU y memoria. |
| Snapshot | `initial` | Estado al que vuelve `lab reset`. |

## Almacenamiento

El driver `dir` de Incus copia la imagen completa por contenedor. Con imágenes de nodo de más de un
gigabyte, siete nodos llenan un disco de 12 GB y el síntoma aparece al escribir cualquier cosa. Por
eso la caja crea un pool **btrfs** sobre un fichero y apunta ahí el perfil de los nodos: con
copy-on-write los nodos comparten bloques con la imagen y ocupan decenas de megas.

Si el pool no se puede crear, la caja avisa y sigue con `dir`; en ese caso el perfil `full` de siete
nodos no cabe. En un laboratorio de contenedores el almacenamiento es un requisito de diseño, no un
detalle de despliegue.

## Consolas

`lab console` lanza `incus console` y devuelve el terminal al usuario. `lab web` abre un servidor
HTTP con un PTY por sesión (`incus exec -t <nodo> -- bash -l`), acumula la salida y la sirve por
sondeo cada 150 ms. No usa WebSocket ni xterm.js: solo necesita que el navegador del anfitrión llegue
al puerto.

El servidor escucha en `127.0.0.1` por defecto, guarda como máximo 256 KiB de salida por sesión y
admite un token en la URL. Abrirlo a la red es una decisión consciente: da una shell dentro de un
laboratorio de ataque.

## Captura

| Modo del segmento | Cómo se captura |
|---|---|
| `mirror` | En el puerto espejo del anfitrión (`cap-<segmento>`) con `tcpdump`; requiere `sudo`. |
| `hub` | Dentro de un nodo del segmento, con la interfaz en modo promiscuo: se ve todo el segmento. |
| `switch` | Dentro de un nodo del segmento: solo se ve el tráfico del propio nodo. |

El resultado se escribe en `capture/<segmento>.pcap` salvo que se indique otra ruta.

## Aislamiento

La caja es la frontera de seguridad: un laboratorio que ataca máquinas no puede compartir kernel con
el portátil del alumno. Los nodos comparten el kernel de la caja y no hay virtualización anidada, así
que el aislamiento entre nodos es el de Incus y el del kernel. La caja no debe usarse como servidor:
un solo adaptador, la NAT del hipervisor y el fichero de la VM tratado como material didáctico.

## Presupuesto de recursos

Medido durante la validación de la caja:

| | Medido |
|---|---|
| Artefacto (`.tar.gz`) | ~1,9 GB |
| VMDK descomprimido | ~3,5 GB |
| Disco de la caja | 12 GB virtuales; ~4,2 GB usados con siete nodos y snapshots |
| RAM de la caja | 2 GB; ~1,3 GB libres con siete nodos |
| Arranque de un nodo | segundos |
| `lab up` con siete nodos | ~1,5 minutos |

Los nodos usan por defecto 1 vCPU y 256 MB de RAM; se ajustan con `resources:`.

## Límites conocidos

La salida a Internet se declara por segmento con `type: nat`; el atajo `--uplink` y la grabación de
Internet están pendientes. También lo están las herramientas por nodo (`tools:`), los puertos
publicados al anfitrión y los enlaces punto a punto entre nodos. Los nodos Windows no son un objetivo
de esta fase.
