# NETinVM — Revisión técnica del proyecto de referencia

> Documento de análisis previo. **No es documentación del proyecto nuevo**: es el estudio del
> artefacto que queremos reproducir, con la evidencia separada de lo que es inferencia.
>
> Fuente primaria: <https://informatica.uv.es/~carlos/docencia/netinvm/>
> Fecha del análisis: 2026-11-22 · Versión estudiada: **2026-07-24** (Debian 13)

Etiquetas de evidencia usadas en todo el documento:

| Etiqueta | Significado |
|---|---|
| **[A]** | Documentado explícitamente por los autores (web, documentación, changelog, blog o scripts publicados). |
| **[B]** | Derivado de forma determinista de una regla documentada. |
| **[C]** | Inferencia técnica razonable, **no confirmada** por ninguna fuente. |
| **?** | Hueco: no hay fuente pública. |

---

## 1. Qué es NETinVM

Un único artefacto descargable (ZIP de **4,7 GB**, imagen KVM/libvirt; existe también variante VMware
de 4,9 GB) que contiene:

- **L1VM, "base"**: una VM Debian 13 con escritorio completo (KDE sobre Wayland) que actúa como
  *plano de control y de observación* del laboratorio.
- **L2VM, "KVM2"**: hasta ~18 máquinas Debian 13 reales, cada una con su propio kernel, gestionadas
  por libvirt **dentro** de base.
- Una red llamada **`example.net`** con tres subredes (externa, perimetral e interna), un router
  cortafuegos (`fw`), servicios reales (HTTP, FTP, SSH) y un mecanismo de captura de tráfico.

La tesis de fondo: *una red completa dentro de un ordenador, descargable, offline y reproducible por
el alumno en su casa*, con sistemas operativos de verdad (no simuladores de protocolos).

### Linaje

| Fecha | Hito |
|---|---|
| 2008 | Primera versión (autor: Carlos Pérez, Universitat de València). |
| 2010 | Se añade la carpeta de lanzadores en el escritorio ("UML machines"). |
| 2016-11-03 | Última versión basada en **User-mode Linux (UML)**; Debian 8; `base` era openSUSE. |
| 2018-07-23 | Salto a **KVM/libvirt**; **Open vSwitch** en lugar de bridges Linux; `fw` deja de hacer SNAT; segundo disco para swap. |
| 2020-07-15 | **KSM** activado (eficiencia de memoria); Debian 10. |
| 2022-12-29 | `9p` → **`virtiofs`** para la carpeta compartida; Debian 11. |
| 2025-07-22 | Debian 12; `base` usa LVM; nombres de interfaz predecibles (`eth-0`, `eth-dmz`). |
| 2026-07-24 | Debian 13; Wayland; teclado español; una consola por KVM2; scripts `netinvm_config_qemu` / `netinvm_config_kvm` para alternar emulación pura. |

Trabajos académicos asociados: *A nested virtualization tool for information technology practical
education* (SpringerPlus, 2016, acceso abierto) y *Using a nested virtualization tool for teaching
VPN fundamentals* (Cluster Computing, 2024, acceso abierto).

---

## 2. Arquitectura funcional

```
                        ┌──────────────────────────────────────────────┐
                        │            ORDENADOR REAL                    │
                        │   VMware Player/Workstation + vmnet8 (NAT)   │
                        └───────────────────┬──────────────────────────┘
                                            │
┌───────────────────────────────────────────┴──────────────────────────────────────────┐
│ base.example.net · L1VM · Debian 13 · KDE/Wayland                                    │
│                                                                                      │
│  eth0 (vmnet8)         libvirt + Open vSwitch + dnsmasq + iptables/NAT + KSM          │
│  virbr-ext 10.5.0.1/24   virbr-dmz 10.5.1.1/24   virbr-int 10.5.2.1/24                │
│  DHCP, DNS (3 redes) · IP forwarding + NAT · tabla de rutas `netinvm`                 │
│  puertos espejo: mirror-ext · mirror-dmz · mirror-int  → Wireshark / tcpdump          │
└──────┬──────────────────────────────┬───────────────────────────────┬─────────────────┘
       │ switch `ext`                 │ switch `dmz`                  │ switch `int`
  exta .10 … extf .15            dmza .10 (www) … dmzf .15        inta .10 … intf .15
  MAC ca:fe:00:00:00:0x          dmzb .11 (ftp)                   MAC ca:fe:00:00:02:0x
       │                              │                               │
       └──────────────┬───────────────┴───────────────┬───────────────┘
                      │  fw.example.net  (KVM2)       │
                      │  router + cortafuegos         │
                      │  .254/.254/.254 · MAC …:fe    │
                      └───────────────────────────────┘
```

### Recursos

- **`base`**: RAM 2 GB en la era UML; para la versión KVM actual no se publica el sizing **?**.
- **Cada KVM2**: **512 MB** por defecto, ajustable con `netinvm_setmem <tamaño>`; el modo automático
  asigna el **13 % de la RAM de base** a cada una, aplicable en caliente con `virsh setmem` **[A]**.
- **Requisitos declarados**: CPU con virtualización por hardware, **4 GB de RAM**, **20 GB de disco**
  **[A]** (artículo 2016).
- **KSM** activo desde 2020 para deduplicar memoria entre KVM2 **[A]**; parámetros concretos **?**.

---

## 3. Plan de direccionamiento

Reglas documentadas **[A]**: `IP = 10.5.<red>.<máquina>`, `MAC = ca:fe:00:00:0<red>:0<máquina>`,
red ∈ {0 ext, 1 dmz, 2 int}, máquina ∈ {10 a, 11 b, … 15 f}; `fw` = 254 IP / `fe` MAC;
`base` = 1 IP / `01` MAC. Verificado sobre un `ip addr` real de `exta`
(`ca:fe:00:00:00:0a`, `10.5.0.10/24`) **[A]**.

| Rol | ext 10.5.0.0/24 | dmz 10.5.1.0/24 | int 10.5.2.0/24 | MAC |
|---|---|---|---|---|
| `base` | .1 | .1 | .1 | `ca:fe:00:00:0N:01` |
| `fw` | .254 | .254 | .254 | `ca:fe:00:00:0N:fe` |
| `a` (exta/dmza/inta) | .10 | .10 | .10 | `ca:fe:00:00:0N:0a` |
| `b` | .11 | .11 | .11 | `…:0b` |
| `c` | .12 | .12 | .12 | `…:0c` |
| `d` | .13 | .13 | .13 | `…:0d` |
| `e` | .14 | .14 | .14 | `…:0e` |
| `f` | .15 | .15 | .15 | `…:0f` |

Alias DNS: `dmza` = `www.example.net` (HTTP/HTTPS), `dmzb` = `ftp.example.net` (FTP) **[A]**.
Los scripts aceptan además nombres de cuatro letras (`extaa`…`extaf`) → **hasta 12 máquinas por red**
en el modelo de datos, aunque la documentación hable de 6 **[A/B]**.

**Convención de nombres de interfaz** (versión 2025+): `eth-0` en las KVM2 de una sola interfaz,
`eth-ext` / `eth-dmz` / `eth-int` en `fw` **[A]**. El mapeo exacto por rol **?**.

---

## 4. Servicios de red de `base`

| Función | Comportamiento documentado | Implementación real |
|---|---|---|
| **DHCP** | Todas las KVM2 obtienen su configuración de red de `base`, en las tres redes **[A]** | Software **?** — dnsmasq del sistema o el dnsmasq interno de libvirt, ambos plausibles **[C]** |
| **DNS** | Resolución directa e inversa de todas las máquinas en las tres redes; `ping dmza` desde `exta` resuelve `dmza.example.net (10.5.1.10)`; nmap obtiene rDNS **[A]** | **?** |
| **Alias** | `www.example.net` → 10.5.1.10, `ftp.example.net` → 10.5.1.11 **[A]** | Requiere CNAME o registro A duplicado **[C]** |
| **Rutas a clientes** | `exta` tiene `10.5.1.0/24` y `10.5.2.0/24` vía `10.5.0.254` **sin configuración manual** **[A]** | Lo natural es DHCP option 121 **[C]** |
| **NAT** | `base` hace IP forwarding y NAT hacia el exterior **[A]** | iptables/nftables MASQUERADE **[C]** |
| **Policy routing** | Tabla `netinvm`: las respuestas a conexiones salientes de int/dmz vuelven por `fw`, no directamente por el bridge **[A]** | **?** (reglas exactas) |

> **Corrección histórica importante**: en la era UML era `fw` quien hacía SNAT. Desde 2018 **`fw` ya
> no hace SNAT** **[A]**. Cualquier material docente antiguo que lo afirme está desactualizado.

---

## 5. Encaminamiento

- `int*` y `dmz*`: pasarela por defecto = **`fw`** (.254 de su red) **[A]**.
- `fw`: pasarela por defecto = **`base`** (10.5.0.1) **[A]**.
- `ext*`: pasarela por defecto = **`base`** (10.5.0.1) + rutas a dmz/int vía **`fw`** (10.5.0.254) **[A]**.

Tabla de rutas real de `exta` **[A]**:

```
default via 10.5.0.1 dev eth0
10.5.0.0/24 dev eth0 proto kernel scope link src 10.5.0.10
10.5.1.0/24 via 10.5.0.254 dev eth0
10.5.2.0/24 via 10.5.0.254 dev eth0
```

`ping exta → dmza` devuelve **TTL 63**: exactamente un salto enrutado (`fw`) **[A]**.

Consecuencia de diseño: el tráfico entre redes **siempre** atraviesa `fw`; `base` ↔ cualquier KVM2 es
**directo** por su bridge y no pasa por `fw`, de modo que desde `base` se puede administrar todas las
KVM2 por SSH aunque el cortafuegos esté mal configurado **[A]**.

---

## 6. Cortafuegos de `fw`

Tecnología: **iptables** **[A]** (en Debian 13 convive con el backend nftables; motor exacto **?**).
Reglas literales **?**; el comportamiento observable es:

| Origen → destino | Resultado | Evidencia |
|---|---|---|
| `int*` → `ext*` | **permitido** (SSH funciona) | actividad 12 |
| `ext*` → `int*` | **bloqueado** | actividad 12 |
| `ext*` → `dmza` tcp/80 | **open** | nmap |
| `ext*` → `dmza` tcp/443 | **closed** (no filtered) | nmap |
| `ext*` → `dmza` resto | **filtered** (998 y 65534 puertos) | nmap |
| `int*` → `dmz*` | **bloqueado** (SSH no funciona) | actividad 12 |
| `dmz*` → `ext*` | **permitido** | actividad 12 |
| `dmz*` → `int*` | **bloqueado** | actividad 12 |
| `base` ↔ cualquier KVM2 | **siempre permitido** (no pasa por `fw`) | documentación |

Lectura **[C]**:

- Política `FORWARD` por defecto **DROP** → explica "filtered" y no "closed" en el resto de puertos.
- `-m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT` para el tráfico de retorno.
- Reglas explícitas `ext→dmza tcp/80` y `tcp/443` **ACCEPT** (sin listener en 443 → el host responde
  RST → nmap lo ve **closed**, no filtered). Es un detalle fino y muy didáctico: **el alumno puede
  distinguir "filtrado" de "cerrado"**.
- Desde `base`, `nmap www.example.net` ve **22 y 80 abiertos** → `dmza` también corre `sshd`; el 22
  solo lo filtra `fw` para el tráfico que lo atraviesa.

> **Detalle delicado**: en la imagen de 2022 `dmza` servía Apache en 80 pero **no** en 443 (nmap
> `-sV` lo identifica como Apache 2.4.54), pese a que la documentación anuncia "HTTP y HTTPS". Para
> que los ejercicios den exactamente los mismos resultados hay que reproducir esa asimetría a
> propósito y documentarla.

---

## 7. Ciclo de vida: los scripts

Nombres y semántica conocidos por documentación, blog y una copia no oficial de 2023 **[A]**
(*no se reutilizará su código: ver §12*).

| Comando | Función |
|---|---|
| `netinvm` | Lista los comandos disponibles. |
| `netinvm_run <vm> [-d N] [-E] [-C] [-A]` | Arranca una VM, abre consolas, notifica por `kdialog`. |
| `netinvm_run_all` | Arranca **`fw`, `exta`, `inta`, `dmza`** (en la copia de 2023, `dmzb` estaba comentada "for a faster Run all"). |
| `netinvm_run_my_machines` | Arranca un subconjunto definido en un guion editable. |
| `netinvm_shutdown_all` | Apagado ordenado de todo lo que esté corriendo. |
| `netinvm_console <vm> [n] [-d N]` | Conecta a la consola serie n (1..3) en el escritorio indicado. |
| `netinvm_backup` | `tar.gz` **solo de los discos de sistema**, con las VMs apagadas. |
| `netinvm_restore` | Destruye el estado actual y restaura un `tar.gz`. |
| `netinvm_setmem <tamaño>` | Ajusta la RAM de todas las KVM2 (en caliente si están corriendo). |
| `netinvm_config_kvm` / `netinvm_config_qemu` | Conmutan entre KVM anidado y emulación pura de CPU. |
| `netinvm_resume-vm` | Hook de VMware: resincroniza el reloj de las KVM2 con `guest-set-time`. |

Todos se ejecutan **como `user1`** (no root): `user1` gestiona libvirt por pertenencia al grupo
correspondiente y puede usar Wireshark (capabilities) **[A]**.

### Escritorios virtuales por convención

`exta`→2, `fw`→4, `dmza`→5, `dmzb`→6, `inta`→8 **[A]**. Los lanzadores del escritorio son un
"Folder View" de KDE con: *Run all*, *Shutdown all*, *Backup KVM machines*, *Restore KVM machines*,
*NETinVM Documentacion* (copia local en el navegador), *Configure my machines*, *Run my machines*,
*Text consoles* **[A]**.

---

## 8. Almacenamiento, backup y restore

```
/srv/netinvm/                      (en la doc aparece como ~user1/netinvm, probablemente symlink)
├── shared/                        → /mnt/shared y ~/shared en todas las KVM2 (virtiofs)
├── backups/                       kvm_machines_YYYY-MM-DD_HH-MM.tgz
└── libvirt/
    ├── images/                    <vm>-fs.qcow2 , <vm>-swap.qcow2
    └── templates/                 template-debianXX-swap.qcow2 , template-alma9-swap.qcow2
```

Modelo deducido **[A/C]**: **plantilla inmutable + overlay qcow2 por máquina y por disco**
(copia en escritura), con el **swap efímero** (se regenera como overlay en cada `restore`).

- `backup`: `tar zcSf … *-fs.*` → solo discos de sistema, sparse, sin swap. Resultado típico:
  **unos pocos KB–MB**, porque solo se guardan las modificaciones **[A]**.
- `restore`: borra los `*-swap.qcow2`, los recrea con `qemu-img create -b template-…-swap.qcow2`,
  borra los `*-fs.qcow2` y extrae el tar **[A]**.
- Los backups son **incrementales** y **solo compatibles con la misma versión** de NETinVM **[A]**.
- Uso didáctico: distribuir un `tar.gz` como *estado inicial* de un ejercicio (hardening, app web
  vulnerable, `fw` sin reglas) permite plantear escenarios con "efecto sorpresa" **[A]**.

---

## 9. Captura de tráfico

Cada red es un **switch Open vSwitch** (`virbr-ext`, `virbr-dmz`, `virbr-int`) con un objeto
`mirror` de OVS configurado `select-all=true` y `output-port` apuntando a un puerto del propio
bridge; `base` ve ese puerto como interfaz `mirror-ext` / `mirror-dmz` / `mirror-int` **[A]**.
Comando documentado por el autor (para crear un espejo nuevo):

```bash
ovs-vsctl --id=@p get port capture-intc -- \
  --id=@m create mirror name=mirror-capture-intc select-all=true output-port=@p -- \
  add bridge virbr-int mirrors @m
```

Ventaja didáctica frente a `tcpdump` en el bridge: el puerto espejo se comporta como en un switch
físico y no altera el camino de los paquetes. Wireshark está configurado para funcionar **sin root**
y `exta` puede añadirse una interfaz extra en caliente
(`virsh attach-interface … --target capture-exta`) para capturar desde dentro de una KVM **[A]**.

---

## 10. Requisitos funcionales derivados de las 18 actividades oficiales

La práctica "Introducción a NETinVM" (18 actividades) define, de facto, el **contrato didáctico**.
Es la mejor fuente para nuestros tests de aceptación:

| # | Actividad | Requisito verificable |
|---|---|---|
| 1 | Puesta en marcha | `base` arranca en escritorio con `user1`/`root`, clave `You can change me.`, `passwords.txt` en el escritorio |
| 2 | Entorno de escritorio | 8 escritorios virtuales, atajos Win-k/f/e/t/w, gestor de portapapeles, lista de ventanas |
| 3 | Puesta en marcha completa | Un clic/orden arranca `fw, exta, inta, dmza` (+`dmzb`), cada una con su consola en su escritorio |
| 4 | Parada | "Shutdown all" apaga ordenadamente y notifica |
| 5 | Arranque selectivo | `netinvm_run <vm>` con `-d`, `-E`, `-C` |
| 6 | Arranque de subconjunto | Guion editable + "Run my machines" |
| 7 | Otros casos | Parar/arrancar individualmente; `virsh destroy` como recurso |
| 8 | Backup | Backup con VMs apagadas → `kvm_machines_<fecha>.tgz` de pocos MB |
| 9 | Restore | Restaurar recupera `prueba-ok.txt` y elimina `prueba-fallida.txt` |
| 10 | Carpeta compartida | `/srv/netinvm/shared` ↔ `/mnt/shared` ↔ `~/shared` en todas |
| 11 | SSH desde base | `base` → cualquier KVM2 por SSH, incluso con `fw` parado |
| 12 | Matriz de conectividad | Exactamente la tabla de §6 |
| 13 | Captura | Wireshark sin root en las 3 `mirror-*`; se ve ICMP + ARP + DNS |
| 14 | Servicios | `ip addr`, `ss --listen --tcp`, `ip route`: `dmza` = 10.5.1.10, GW 10.5.1.254 |
| 15 | Nmap | `exta`→`www`: 80 open, 443 closed, resto filtered. `base`→`www`: 22 y 80 open |
| 16 | virt-manager | Lista los dominios y refleja su estado |
| 17 | Consola gráfica | `startx` en una KVM2 levanta un escritorio ligero |
| 18 | Interacción con libvirt | Arrancar una VM desde virt-manager funciona, pero sin consolas de texto |

Estas 18 actividades son la definición operativa de "idéntico": **si las 18 se pueden realizar sin
cambiar el texto de las instrucciones, la réplica es válida.**

---

## 11. Fortalezas

1. **Núcleos reales por nodo**: se pueden hacer prácticas de netfilter, systemd, módulos, cuotas,
   arranque, fallos… cosas que un emulador de contenedores no permite.
2. **Topología "de libro"** y plan de direccionamiento regular: se memoriza y permite razonar.
3. **Artefacto único y offline**: el alumno no instala nada, no depende de la red del aula.
4. **Separación limpia de planos**: `fw` filtra y enruta; `base` da servicios, administra y observa.
   Permite romper `fw` sin perder el acceso a las máquinas → *fail-safe* didáctico.
5. **Observabilidad de primera clase**: puertos espejo reales, Wireshark sin root, 3 redes capturables.
6. **Estado versionable**: backups minúsculos gracias a overlays; escenarios distribuibles como `.tgz`.
7. **Doble uso**: sirve para SSOO, redes y seguridad, y de paso enseña libvirt/KVM/OVS reales.

---

## 12. Debilidades y deuda técnica (nuestra oportunidad)

| # | Problema | Impacto |
|---|---|---|
| D-1 | **No es open source**: no hay licencia ni código publicado. Solo imágenes de 4,7 GB. | No auditable, no mantenible por terceros, no se puede arreglar un fallo sin esperar a la próxima versión. |
| D-2 | **Dependencia de VMware** (propietario) para el caso de uso principal. Existe imagen KVM, pero el flujo documentado es VMware. | Barrera de licencia y de instalación; fricción en portátiles modernos. |
| D-3 | **4,7 GB por versión**, y los backups solo valen para la misma versión. | Distribución cara (no cabe en un *release asset* de GitHub), espejos frágiles, aula saturada. |
| D-4 | **Topología cableada en scripts**, no declarativa. | Cambiar el escenario exige editar guiones; no hay validación ni tests. |
| D-5 | **Cero tests**: los fallos se descubren en el aula (p. ej. "rearrancar deja la VM en pausa"). | Regresiones silenciosas entre versiones. |
| D-6 | **Documentación caduca**: enlaces 404 al material en español, y hay contradicciones (SNAT de `fw`, 4 vs 5 máquinas en "Run all", HTTPS anunciado pero no servido). | El alumno y el profesor pierden tiempo. |
| D-7 | **VMs en pausa al reiniciar** (bug conocido en 2018). | Workaround manual (`virsh destroy`). |
| D-8 | **Redimensionado de terminal no detectado**; hay que pulsar INTRO o `resize`. | Molestia constante en el uso real. |
| D-9 | **Copiar del laboratorio al host exige `xclipboard`**. | Fricción diaria con el portátil del alumno. |
| D-10 | **Sin acceso remoto/web**: todo pasa por el escritorio de `base`. | No se puede usar en un servidor de aula, ni desde un Chromebook/tablet. |
| D-11 | **Sin IPv6** (solo link-local) y sin escenarios con NAT de `fw`. | Cobertura didáctica incompleta. |
| D-12 | **Sizing y paquetes no documentados**: no hay lista de paquetes ni XML de dominios. | Imposible reconstruirlo; obliga a fiarse de la imagen. |
| D-13 | **Material didáctico en español roto** (URLs 404, recuperables solo vía Wayback Machine). | Pérdida efectiva de valor docente. |

---

## 13. Huecos de información (lo que no se puede saber sin la imagen)

Ordenados por impacto. Con una copia del ZIP se resuelven en minutos con `virsh dumpxml`,
`ovs-vsctl show`, `iptables-save`, `qemu-img info` y `dpkg -l`; **no vamos a hacerlo**: nuestra
reimplementación parte de cero y esos detalles se *deciden*, no se copian.

1. XML completo de los dominios (dispositivos, `cpu`, `clock`, vídeo, `virtiofs` con su `tag`,
   `serial`/`console`, canal de guest agent).
2. Software y configuración de DHCP/DNS (dnsmasq del sistema vs. de libvirt; zonas; option 121; DDNS).
3. Reglas literales de `fw` y motor real (iptables-legacy / iptables-nft / nft).
4. Tamaño y naturaleza de los discos (fs y swap), y si el fs es overlay o imagen completa.
5. Cómo se configura cada KVM2 al arrancar: `configure.sh` heredado de UML, cloud-init, o imagen
   pre-horneada.
6. Lista de paquetes de `base` y de las KVM2; política de sudo/polkit/libvirt; capabilities de Wireshark.
7. Contenido de `netinvm_config_kvm` / `netinvm_config_qemu` y del `.vmx` de VMware.
8. Cómo se generan los lanzadores del escritorio y la app "Text consoles".
9. Detalle del objeto `mirror` de OVS y tipo de puerto de `mirror-*`.
10. Manejo de energía que provoca la "VM en pausa" al reiniciar.

---

## 14. Implicaciones para la reimplementación

1. **No se puede reutilizar nada del artefacto original** (scripts, docs, imágenes, iconos) salvo los
   *hechos* (direccionamiento, topología, comportamiento). Es un riesgo legal real: no hay licencia.
   → Se reescribe todo desde cero, con nombres y CLI propios, y se cita el trabajo original.
2. **El contrato es funcional, no visual**: las 18 actividades de §10 son la especificación.
   Conviene convertirlas en una **suite de aceptación ejecutable** (ping matrix, DNS, nmap, backup,
   fichero compartido…).
3. **La topología debe ser dato, no código** (`topology.yaml` → libvirt/OVS/dnsmasq/nftables).
   Eso resuelve D-4 y habilita tests y escenarios alternativos.
4. **El hipervisor debe ser QEMU** (GPL-2.0) para eliminar D-2 y habilitar Linux/Windows/macOS.
5. **El tamaño es un requisito de diseño, no un detalle**: partir de la imagen cloud de Debian 13
   (328 MB) en lugar de un disco con escritorio completo cambia el proyecto de "4,7 GB" a "~500 MB
   por perfil", lo que hace viable GitHub Releases, caché y arranque rápido.
6. **La observabilidad y el estado deben ser de primera clase**: mirror ports equivalentes y
   snapshots/overlays con nombre, porque son el núcleo del uso docente (actividades 8, 9 y 13).
