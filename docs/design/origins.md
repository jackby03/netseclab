# Origen y diferencias con NETinVM

Esta página explica qué era NETinVM, qué ideas conserva `netseclab` y en qué se separa del proyecto
original.

## Qué era NETinVM

NETinVM es un laboratorio de redes y seguridad docente de la Universitat de València, creado por
Carlos Pérez. Su propuesta es una red completa dentro de un ordenador, descargable, sin conexión y
reproducible, con sistemas operativos reales en lugar de simuladores de protocolos.

El artefacto original es un ZIP de unos 4,7 GB con una imagen de KVM/libvirt —existe también una
variante de VMware— que contiene:

- **`base`**: una VM Debian 13 con escritorio KDE sobre Wayland que hace de plano de control y de
  observación.
- **Hasta 18 máquinas `KVM2`**: VMs Debian 13 con kernel propio, gestionadas por libvirt dentro de
  `base`.
- **`example.net`**: tres subredes —externa, perimetral e interna—, un router cortafuegos (`fw`),
  servicios HTTP, FTP y SSH, y captura de tráfico por segmento.

| Hito | Cambio |
|---|---|
| 2008 | Primera versión, basada en User-mode Linux. |
| 2016 | Última versión UML; Debian 8. |
| 2018 | Salto a KVM/libvirt y Open vSwitch. |
| 2022 | `virtiofs` para la carpeta compartida. |
| 2026 | Debian 13, Wayland y teclado español. |

El direccionamiento es regular y se memoriza: `10.5.<red>.<máquina>`, con `ext` en 0, `dmz` en 1 e
`int` en 2; `base` en `.1` y `fw` en `.254`. Las MAC siguen el mismo patrón, `ca:fe:00:00:0<red>:<sufijo>`.
`base` sirve DHCP y DNS, reparte rutas a los otros segmentos y hace NAT; `fw` filtra y enruta.

El cortafuegos produce una asimetría que el material didáctico aprovecha: desde `exta`, el puerto 80
de `dmza` responde, el 443 aparece **closed** y el resto **filtered**. Un puerto cerrado demuestra que
hay un filtro que deja pasar el paquete y un servidor que lo rechaza; uno filtrado, que el filtro lo
descarta en silencio.

El ciclo de vida se hacía con scripts (`netinvm_run`, `netinvm_run_all`, `netinvm_shutdown_all`,
`netinvm_backup`, `netinvm_restore`, `netinvm_setmem`, `netinvm_console`) y el estado se guardaba con
plantillas inmutables y overlays `qcow2`. Los backups eran pequeños porque solo contenían las
modificaciones. La captura usaba puertos espejo de Open vSwitch.

El proyecto publica 18 actividades docentes que definen, de hecho, el contrato funcional del
laboratorio. Ese contrato es la referencia que `netseclab` usa para decidir qué conservar.

## Qué conserva netseclab

| Idea | Cómo aparece en netseclab |
|---|---|
| Una red completa en un ordenador | Una VM —la caja— que contiene todo el laboratorio. |
| Topología regular | Tres segmentos con el plan de direccionamiento `10.5.<red>.<nodo>`. |
| Nombres y servicios clásicos | `base`, `fw`, `exta`, `dmza`, `inta`, `intb`, `intc`; alias `www` para la web. |
| Matriz de cortafuegos | `policies:` en el YAML, con `accept`, `drop` y `reject-reset`. |
| Cerrado, filtrado y abierto | La diferencia entre `closed` y `filtered` se reproduce a propósito. |
| DHCP y DNS en un nodo | `dnsmasq` en el nodo con `dhcp_server` y `dns_server`. |
| Rutas repartidas | Opción 121 de DHCP y `/etc/hosts` en todos los nodos. |
| Captura por segmento | Modos `switch`, `hub` y `mirror`, con pcap en `capture/`. |
| Estado reversible | Snapshot `initial` y `lab reset` en segundos. |
| Artefacto único y sin conexión | La caja lleva las imágenes y los paquetes cacheados. |
| Trabajo reversible | Snapshots antes de cada práctica y restauración inmediata. |

Además, `netseclab` añade dos cosas que el original no tenía: los ejercicios se corrigen solos y el
laboratorio se describe en YAML en lugar de en scripts.

## Qué cambia

| Aspecto | NETinVM | netseclab |
|---|---|---|
| Ejecución | VMs anidadas con kernel propio dentro de `base`. | Una VM de VMware con contenedores de sistema de Incus; sin anidamiento. |
| Tamaño | ZIP de ~4,7 GB y ~6 GB de RAM. | Caja de ~1,9 GB; siete nodos caben en 2 GB de RAM. |
| Topología | Cableada en scripts. | Declarativa en YAML, validada y convertible en plan. |
| Gestión | libvirt, `virsh`, `virt-manager` y Open vSwitch. | Incus y el CLI `lab`. |
| Interfaz | Escritorio KDE y lanzadores. | Consola, consolas web y plan renderizable; sin escritorio. |
| Estado | Overlays `qcow2` y `tar.gz` de backup. | Snapshots de Incus y `lab reset`. |
| Distribución | Imágenes opacas de gran tamaño. | Código abierto, caché de imágenes y paquetes `.labpack`. |
| Evaluación | Corrige el profesor. | Comprobaciones y respuestas estrictas, más informe escrito. |
| Licencia | Sin licencia publicada. | GPL-3.0-or-later para el código y CC-BY-SA-4.0 para la documentación. |

El cambio de VMs a contenedores es el más visible. Un contenedor de sistema comparte el kernel de la
caja: no puede cargar módulos ni arrancar un kernel propio, pero sí tiene `systemd`, `sshd`,
`nftables`, `nmap` y `tcpdump`, arranca en segundos y cabe varias veces en la memoria que ocupaba una
sola VM del original.

Cubre las prácticas de red y seguridad del proyecto; las de kernel o de arranque quedan fuera de su
alcance.

La decisión de no anidar también elimina la dependencia de la virtualización anidada en el portátil
del alumno. La caja solo necesita VMware, y los nodos son contenedores dentro de ella.

## Qué no se copia

NETinVM no publica licencia, así que su código, sus scripts, su documentación y sus imágenes no se
reutilizan. `netseclab` reescribe todo desde cero y toma solo los hechos no protegibles: la topología,
el plan de direccionamiento, el comportamiento observable del cortafuegos y las ideas didácticas.

El nombre NETinVM no se usa como nombre del proyecto; se cita como inspiración y se enlazan sus
referencias.

- Proyecto original: <https://informatica.uv.es/~carlos/docencia/netinvm/>
- *A nested virtualization tool for information technology practical education* (SpringerPlus, 2016)
- *Using a nested virtualization tool for teaching VPN fundamentals* (Cluster Computing, 2024)

## Actividades del original y equivalente actual

| Actividad de NETinVM | En netseclab |
|---|---|
| Puesta en marcha | Caja y `lab up`. |
| Entorno de escritorio | No aplica: no hay escritorio; las consolas son de terminal o web. |
| Arranque completo | `lab up --profile`. |
| Parada completa | `lab down`. |
| Arranque selectivo | Por perfil; no hay arranque de un nodo suelto. |
| Subconjunto editable | Perfiles declarados en la topología. |
| Parar y arrancar nodos | `lab down` acepta nombres; volver a arrancar es `lab up`. |
| Backup | `lab snapshot`. |
| Restore | `lab reset`. |
| Carpeta compartida | No implementada; los `assets` copian ficheros al nodo. |
| SSH desde `base` | Disponible si el escenario incluye un nodo `base`. |
| Matriz de conectividad | `policies:`. |
| Captura | `lab capture` con modos `hub`, `switch` y `mirror`; sin Wireshark dentro de la caja. |
| Servicios | Nodos con `packages`, `startup` y `assets`. |
| Nmap | Mismo comportamiento `open`/`closed`/`filtered` en `example.net`. |
| `virt-manager` | No aplica: no hay libvirt dentro de la caja. |
| Consola gráfica | No aplica: no hay escritorio. |
| Interacción con libvirt | No aplica: el motor es Incus. |

Las actividades ligadas al escritorio y a libvirt desaparecen del alcance. Las de red, sistema,
captura y corrección son las que el proyecto conserva y las que usa como pruebas de aceptación.

## Lo que el original hacía y aquí está pendiente

La salida a Internet declarada, la grabación y reproducción de Internet y los nodos Windows están
pendientes. La carpeta compartida del original se sustituye por `assets`, que copian ficheros al
nodo durante el arranque. La alternativa prevista para Active Directory es un controlador de dominio
Samba en un nodo Linux, no una VM de Windows.
