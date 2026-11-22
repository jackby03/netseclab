# Dossier de decisiones técnicas

> ⚠️ **Documento superado.** Se conserva como registro del proceso de decisión. El objetivo real
> quedó fijado después: un laboratorio de **seguridad en redes**, ejecutado dentro de una única VM
> de VMware, con contenedores de sistema como nodos. El diseño vigente está en
> [`02-diseno.md`](02-diseno.md).
>
> Siguen siendo válidos de este documento: R1–R5 (restricciones), D5 (topología como dato),
> D8 (dnsmasq), D9 (nftables + iptables), D10 (overlays y escenarios), D12 (licencia) y D14
> (distribución). Quedan descartados D1–D4, D6, D7, D11 y D13 en su forma original.

> Fase previa a la implementación. Cada decisión tiene opciones, consecuencias y una
> **recomendación**. Las marcadas con **❗** necesitan tu visto bueno antes de escribir código.

---

## 0. Criterios de evaluación

Toda decisión se juzga contra estos seis criterios, en este orden:

| # | Criterio | Por qué |
|---|---|---|
| C1 | **Fidelidad didáctica** | Debe permitir las 18 actividades oficiales sin reescribir los enunciados. |
| C2 | **Reproducibilidad** | Cualquiera debe poder reconstruir el laboratorio desde fuentes públicas y verificarlo. |
| C3 | **Portabilidad real** | Linux, Windows y macOS son los portátiles del alumnado. "Real" = sin hipervisor propietario. |
| C4 | **Tamaño y distribución** | Hoy son 4,7 GB; eso condiciona caché, espejos, aula y releases. |
| C5 | **Mantenibilidad** | Topología como dato, tests, CI. Es la deuda principal del original. |
| C6 | **Licencia y ética** | 100 % open source, sin arrastrar licencias no-OSI ni código ajeno sin permiso. |

---

## 1. Restricciones duras descubiertas (no son opinables)

Estas cinco realidades acotan el espacio de diseño. Conviene tenerlas presentes en todas las
decisiones siguientes.

### R1 — El anidamiento solo existe en Linux (y en WSL2)

| Host | Aceleración de L1 | ¿KVM dentro de L1? |
|---|---|---|
| Linux + KVM (Intel/AMD) | KVM | **Sí**, con `-cpu host` / `host-passthrough` |
| **Windows 11 + WSL2** | WSL2 usa Hyper-V y expone anidamiento | **Sí** — `nestedVirtualization` vale `true` por defecto en `.wslconfig` |
| Windows 11 + QEMU/WHPX | WHPX | **No**. QEMU no expone VMX al invitado (issue #628 abierta) |
| macOS Intel (HVF) | HVF | **No**: HVF no anida |
| macOS Apple Silicon | TCG para x86_64 | **No**: HVF solo virtualiza ARM |
| Cualquiera, solo TCG | TCG | **No**: TCG no emula VMX/SVM |

**Consecuencia:** "idéntico a NETinVM" (base como hipervisor de las KVM2) es viable en **Linux y en
Windows 11 vía WSL2**. En macOS solo cabe a) modo plano, b) TCG (inviable para 8–12 VM) o c) un host
Linux remoto.

> Dato clave que cambia el diseño: **no hace falta reescribir el laboratorio para Windows**. Basta con
> que el producto sea un *appliance Linux* y que en Windows se ejecute dentro de WSL2, donde el
> anidamiento ya está disponible. Eso preserva la fidelidad y elimina la dependencia de WHPX.

### R2 — Packer ya no es open source

Packer pasó a **BUSL-1.1** en la 1.10.0: no es una licencia OSI. Usarlo contradice el objetivo del
proyecto. Alternativas: **cloud-init + Ansible** (camino principal), **debos** (Apache-2.0) o
**mkosi** (LGPL-2.1) si se quiere construir desde cero.

### R3 — Los tamaños son manejables si se parte de la imagen cloud

Medido hoy en `cloud.debian.org` (trixie / Debian 13.8):

| Artefacto | Tamaño |
|---|---|
| `debian-13-genericcloud-amd64.qcow2` | **328 MB** |
| `debian-13-generic-amd64.qcow2` | 415 MB |
| `raw` | 3,0 GB |
| NETinVM actual (ZIP) | **4,7 GB** |

Y el límite práctico de GitHub Releases es **~2 GiB por asset**. Con una imagen de nodo única
compartida por todas las VM y overlays qcow2 por máquina, el total puede quedar **por debajo de
1,2 GB**: cabe en un release, cabe en una caché de aula y se descarga en minutos.

### R4 — `virtiofs` no existe en Windows/macOS

La carpeta compartida del original (`/srv/netinvm/shared` → `/mnt/shared`) usa virtiofs desde 2022.
virtiofsd solo corre en Linux. En modo plano hacen falta alternativas (SMB del host, `vvfat`, o un
servicio de ficheros dentro de la red). Debe ser una capa abstracta, no un supuesto.

### R5 — GitHub Actions no tiene `/dev/kvm`

Los runners alojados no exponen KVM ni anidamiento. El CI puede validar XML, nftables, dnsmasq y
generadores en segundos, y arrancar **una** VM con TCG en ~20–40 min, pero la matriz completa de
conectividad exige un **runner autoalojado con KVM**. El plan de pruebas debe asumirlo desde el día 1.

---

## 2. Decisiones

### ❗ D1 — Modo de ejecución (la decisión estructural)

| Opción | Qué es | Fidelidad | Portabilidad | Esfuerzo |
|---|---|---|---|---|
| **A. Anidado fiel** | `base` (L1) corre libvirt/KVM/OVS y dentro viven las KVM2. Igual que el original, sin VMware. | **Total (18/18)** | Linux + Windows/WSL2; macOS no | Medio |
| **B. Anidado + plano** | A, más un backend "plano" donde el host lanza todas las VM como hermanas por redes `socket,mcast`. | 15/18 en plano | Total (incluido macOS) | Alto |
| **C. Solo plano** | Nunca hay anidamiento; `base` es un nodo router más. | 15/18 | Total | Bajo-m Medio |

Lo que se pierde en modo plano: las actividades **16, 17 y 18** (virt-manager, consola gráfica vía
libvirt, interacción con `virsh`) y el espejo OVS real, que se sustituye por una captura implícita
(todo el tráfico de la red pasa por el nodo de captura).

**Recomendación: A ahora, con la arquitectura preparada para B.**
El CLI nace con una interfaz `backend` (`nested` | `flat`) y la topología como dato; en la primera
entrega solo se implementa `nested`, pero los generadores y el modelo no se cierran a él. Añadir
`flat` después es trabajo acotado, no una reescritura.

*Por qué no C:* renunciar a `virt-manager`/`virsh` contradice "idéntico" y, sobre todo, renuncia a
enseñar la pila de virtualización real, que el propio autor usa como valor añadido.

---

### ❗ D2 — Experiencia de usuario dentro de `base`

| Opción | Qué ve el alumno | Peso | Portabilidad |
|---|---|---|---|
| **A. Consolas web** | `lab console <vm>` abre una pestaña con la consola serie (xterm.js); `lab ssh <vm>`; captura en `capturas/` | **Mínimo** | Total |
| **B. Escritorio ligero** | LXQt + VNC/noVNC opcional en `base`, consolas serie por defecto | Medio | Buena |
| **C. Escritorio completo** | KDE/Wayland como el original, con lanzadores, 8 escritorios, Virt-manager | **Alto** (y frágil en Wayland) | Solo Linux/WSL2 con GUI |

**Recomendación: A de serie, B como perfil opcional (`--desktop`) y C descartado.**

Justificación: las actividades didácticas que importan son las de red y sistema (1, 3–15); el
escritorio del original aporta sobre todo comodidad. Una consola web por máquina, con pestañas y
"arrastrar y soltar" para copiar, resuelve de paso dos debilidades del original (D-8 redimensionado,
D-9 `xclipboard`) y hace el producto usable desde un Chromebook o un iPad. El perfil con escritorio
ligero cubre a quien quiera ratón, y `virt-manager` sigue disponible dentro de `base` en modo anidado.

---

### ❗ D3 — Cómo se construyen las imágenes

| Opción | Reproducible | Coste | Riesgo |
|---|---|---|---|
| **A. Cloud image fijada + cloud-init + Ansible** | Alta (SHA-512 fijado, config en git) | ~10 min | Bajo |
| **B. Build desde ISO con debos/mkosi** | Muy alta (hermético) | ~40 min, requiere Linux | Medio |
| **C. Preseed + `virt-install`** | Alta | ~15 min | Medio (preseed que mantener) |
| ~~D. Packer~~ | — | — | **Descartado por licencia (R2)** |

**Recomendación: A como camino principal y B como camino "reproducible desde cero" en CI periódica.**

Fijar el build `20261116-2664` de Debian 13.8 con su SHA-512, generar `user-data` por rol y aplicar
Ansible idempotente. Publicar el manifiesto de versiones para que el build sea auditable. El build
desde ISO con debos queda como *job* mensual que demuestra que el proyecto no depende de una imagen
opaca.

---

### ❗ D4 — Cómo se configura cada máquina al arrancar

El problema real: cloud-init solo actúa en el primer arranque, pero el original reconfigura el rol en
cada arranque (`configure.sh` idempotente en la era UML).

| Opción | Pros | Contras |
|---|---|---|
| **A. Imagen única + seed cloud-init por máquina** | Una sola imagen; rol = dato | Solo primer arranque; regenerar exige recrear el disco |
| **B. Imagen única + agente que reaplica config en cada arranque** desde un volumen de configuración compartido | Cambiar el rol no exige rebuild; idempotente; testeable | Un componente propio más |
| **C. Una imagen horneada por rol** | Simple de entender | 13 imágenes, backups enormes, cero flexibilidad |

**Recomendación: A + B combinados.** cloud-init prepara identidad, claves y paquetes en el primer
arranque; un `lab-agent` (systemd, ~100 líneas, sin dependencias) lee `/run/lab/config.json` del
volumen de configuración en cada arranque y aplica rol, red e interfaces. Ventaja colateral: un
"escenario" puede cambiar el comportamiento de las máquinas sin tocar discos.

---

### D5 — De dónde salen la topología y la configuración

**Decisión propuesta (sin alternativas serias): `topology.yaml` como única fuente de verdad.**

De ese fichero se generan: XML de libvirt (o líneas de QEMU), redes OVS, `dnsmasq.conf`, reglas
`nftables`, seeds cloud-init, inventario Ansible, el diagrama y la documentación. Con validación de
esquema y tests de *golden files*.

Consecuencia: **cambiar el laboratorio deja de ser editar scripts**. Se pueden definir escenarios
alternativos (otra topología, otra numeración, una red de invitados) sin tocar el motor.

---

### ❗ D6 — Conmutación y puerto espejo

| Opción | Espejo real | Kernel module | WSL2 | Windows/macOS |
|---|---|---|---|---|
| **OVS** (como el original) | **Sí** (`Mirror` nativo) | Sí | **No por defecto** (falta `CONFIG_OPENVSWITCH`) | No |
| Linux bridge + `tc mirred` | Solo ingreso o por puerto | `act_mirred` | Probable | No |
| Hub QEMU (`socket,mcast`) | **Implícito**: todos ven todo | No | Sí | **Sí** |

**Recomendación: OVS donde exista, hub donde no; el "switch" es una pieza sustituible.**

- **Backend `ovs`** en Linux nativo: fiel al original, enseña OVS y `ovs-vsctl`, y da el espejo que
  esperan las actividades 13.
- **Backend `hub`** en WSL2, Windows, macOS y como fallback: tres `-netdev socket,mcast` (uno por
  red). Semánticamente es un hub, no un switch, pero **para tráfico IP el comportamiento observable
  es el mismo** y la captura sale gratis (la interfaz de `base` en modo promiscuo ve todo).
  Se documenta la diferencia: "en este modo la red es un hub, no aprende MACs".
- Opción de OVS en **datapath de usuarios** (`datapath_type=netdev`) para WSL2: funciona sin módulo,
  a costa de rendimiento. A validar antes de prometerlo.

---

### D7 — Gestión de las máquinas virtuales

| Opción | Fidelidad | Complejidad | Plano |
|---|---|---|---|
| **libvirt** (como el original) | Total: `virsh`, `virt-manager`, XML | Media (demonio, XML) | No |
| QEMU directo | Baja: no hay capa que enseñar | Baja | Sí |

**Recomendación: libvirt en `nested`; QEMU directo en `flat`.** El CLI expone la misma interfaz en
ambos casos (`up`, `down`, `status`, `console`, `capture`, `snapshot`, `restore`), de modo que el
alumno no cambia de herramientas cuando cambia de backend.

---

### ❗ D8 — Pila de red de `base`: DHCP + DNS

**Recomendación: `dnsmasq` único para todo.**

- Tres `dhcp-range` con etiqueta por red, `dhcp-option` 3/6/15 y **option 121** para las rutas
  estáticas que el original reparte sin intervención.
- `dhcp-host=<MAC>,<IP>,<nombre>` → reserva y registro DNS automáticos (A + PTR).
- `cname=www.example.net,dmza.example.net` y `ftp.example.net`.
- `local=/example.net/` para ser autoritativo sin renunciar a reenviar el resto.
- `auth-zone` + SOA solo si se quiere enseñar DNS autoritativo de verdad (opcional, escenario aparte).

Se descarta el dnsmasq interno de libvirt (habría que duplicar registros en tres redes) e ISC DHCP
(en desuso upstream). Bind/Kea quedan como escenario avanzado, no como base.

---

### ❗ D9 — Cortafuegos de `fw`: ¿nftables o iptables?

Aquí hay una tensión real: **el original enseña iptables**, pero Debian 13 vive en nftables.

| Opción | Didáctica | Modernidad |
|---|---|---|
| **nftables** | Enseña lo que se usa hoy | Alta |
| `iptables-nft` | Continuidad con los apuntes existentes del alumnado | Media |
| Ambos | Dos escenarios equivalentes | Alta |

**Recomendación: nftables en la infraestructura, `iptables-nft` disponible y escenario de `fw`
escrito en iptables.**

- La red, el NAT y las reglas internas de `base` y de `fw` se declaran en **nftables**.
- El paquete `iptables` se instala y `iptables` funciona (backend nft), de modo que **los apuntes y
  prácticas clásicas de iptables siguen siendo válidas palabra por palabra**.
- Se añade un escenario "firewall con nftables" como práctica nueva.

Detalle fino que hay que replicar a propósito: **`reject with tcp reset` produce `closed` y `drop`
produce `filtered`**. La asimetría 80 abierto / 443 cerrado / resto filtrado de la actividad 15 es un
objetivo de diseño explícito, no un accidente.

---

### D10 — Estado, copias y escenarios

**Recomendación: plantilla inmutable + overlay qcow2 por máquina y por disco.**

- Plantilla de nodo en solo lectura; cada VM escribe en su overlay → el backup son unos KB, como en
  el original.
- Swap **efímero** (se regenera), fuera del backup.
- `lab backup` / `lab restore` sobre un `.tar.zst` con los overlays y el `topology.yaml` embebido.
- **Escenarios como ciudadanos de primera**: un escenario es un conjunto de overlays +
  configuración, versionado en git y distribuible como fichero pequeño. Esto generaliza el truco del
  autor (distribuir `kvm_machines_*.tgz` con un `dmzc` inseguro) y lo hace reproducible y testeable.
- Alternativa considerada y descartada como mecanismo principal: snapshots internos de qcow2
  (`qemu-img snapshot`), porque no sobreviven a cambios de plantilla. Se ofrecerán como conveniencia.

---

### D11 — Lenguaje y forma del CLI

| Opción | Ventaja |
|---|---|
| **Python 3.11+ (Typer/Click)** | Es el idioma natural de un proyecto docente; extensible por el alumnado; sin compilar |
| Go | Binario único, ideal para distribución |
| Bash | Fiel al original, pero frágil y difícil de testear |

**Recomendación: Python 3.11+**, CLI `lab`, dependencias mínimas (PyYAML, Jinja2) y plantillas como
archivos de texto visibles. Regla de estilo: **el CLI no concatena shell**; genera ficheros y llama a
`virsh`/`ovs-vsctl`/`qemu-img` con argumentos.

---

### ❗ D12 — Licencia

| Opción | Efecto |
|---|---|
| **GPL-3.0-or-later** (código) + **CC-BY-SA-4.0** (docs) | Impide que alguien cierre el proyecto; coherente con Kathara/GNS3/live-build |
| Apache-2.0 + CC-BY-SA-4.0 | Máxima adopción institucional y concesión de patentes; permite derivados cerrados |
| MIT | Máxima adopción; no protege la reciprocidad |

**Recomendación: GPL-3.0-or-later + CC-BY-SA-4.0.** El activo es un bien docente común; el linaje
(EVE-NG → PNetLab) muestra qué pasa cuando el núcleo abierto se convierte en producto cerrado.

**Independientemente de la licencia**, hay reglas que hay que respetar sí o sí:
- **No copiar** scripts, documentación, imágenes ni iconos de NETinVM: no tienen licencia publicada
  (`info@netinvm.org` no responde, `netinvm.org` caído) → por defecto, todos los derechos reservados.
- **No usar "NETinVM" como nombre** del proyecto. Se puede decir "inspirado en el modelo didáctico de
  NETinVM" y citar los artículos de 2016 y 2024.
- Los *hechos* (topología, plan de direccionamiento, `example.net`, comportamiento observable) no son
  objeto de copyright: eso sí se replica.

---

### D13 — Nombre del proyecto

Candidatos (ninguno usa la marca original):

| Nombre | Idea |
|---|---|
| **`labnetvm`** | Parónimo respetuoso de NETinVM; claro en buscadores |
| **`aulanet`** / **`aulavm`** | Español, "aula" |
| **`redbox`** | "una red en una caja" |
| **`nido`** | Rima con "nido de máquinas"; corto y memorable |
| **`openlabvm`** | Neutro, internacional, deja claro que es abierto |

**Recomendación: `labnetvm` para el software y `lab` para el comando.** Se parece lo suficiente para
que un profesor reconozca el linaje y lo bastante distinto para no confundir proyectos.

---

### D14 — Distribución

**Recomendación: híbrido.**

1. **GitHub Releases** con un `.tar.zst` de imágenes + `SHA256SUMS` + manifiesto de versiones
   (objetivo: < 1,5 GB, cabe en un asset).
2. **`make image`** como vía "desde cero", reproducible, para CI y para quien no quiera binarios.
3. **Registro OCI volátil (GHCR) opcional** para aulas que ya tienen `podman`/`docker`.
4. **Zenodo con DOI** para la versión de cada curso: citable y archivable a largo plazo.

Sin torrentes, sin espejos universitarios propios en la v1.

---

### D15 — Alcance de la primera entrega (MVP)

**Recomendación: corte vertical completo, no horizontal.**

- `base` + `fw` + `exta` + `inta` + `dmza` (las 5 del "Run all").
- Tres redes, DHCP/DNS con alias, `fw` filtrando con la matriz exacta de §6, NAT, captura, SSH.
- Las actividades **3, 5, 8, 9, 10, 11, 12, 13, 14, 15** funcionando de punta a punta.
- Suite de aceptación ejecutable que comprueba esas actividades.
- Documentación: análisis, diseño, guía de usuario, guía de construcción, y las 5 actividades
  reescritas en español e inglés.
- Resto de máquinas (`extb…f`, `dmzb…f`, `intb…f`), escritorio opcional, modo plano y escenarios
  adicionales: entrega 2.

Criterio de "hecho": **una persona con un Linux limpio clona el repo, ejecuta tres comandos y en
menos de 15 minutos está dentro de `inta` hablando con `dmza`.**

---

## 3. Resumen

| # | Decisión | Recomendación | Necesita OK |
|---|---|---|---|
| D1 | Modo de ejecución | Anidado fiel ahora, backend plano previsto | **❗** |
| D2 | UX de `base` | Consolas web; escritorio ligero opcional | **❗** |
| D3 | Construcción de imágenes | Cloud image fijada + cloud-init + Ansible | **❗** |
| D4 | Configuración en arranque | Imagen única + seed + agente idempotente | **❗** |
| D5 | Topología | `topology.yaml` como fuente de verdad | No |
| D6 | Conmutación | OVS si hay módulo; hub QEMU si no | **❗** |
| D7 | Gestión de VM | libvirt en anidado; QEMU directo en plano | No |
| D8 | DHCP/DNS | dnsmasq único, tres rangos etiquetados | **❗** |
| D9 | Cortafuegos | nftables + `iptables-nft` disponible | **❗** |
| D10 | Estado | Overlays + escenarios versionados | No |
| D11 | CLI | Python + Typer | No |
| D12 | Licencia | GPL-3.0 + CC-BY-SA-4.0 | **❗** |
| D13 | Nombre | `labnetvm` / comando `lab` | **❗** |
| D14 | Distribución | Releases + build local + Zenodo | No |
| D15 | MVP | Corte vertical de 5 máquinas y 10 actividades | No |

---

## 4. Lo que todavía no sabemos (y no bloquea)

1. Si el kernel de WSL2 soporta OVS (probablemente **no**) o `nf_tables` (probablemente **sí**).
   → Prueba de 10 minutos en un Windows 11 con WSL2 antes de prometer `ovs` en ese host.
2. Rendimiento real del anidamiento con 5 VM en un portátil modesto (medir, no suponer).
3. Si conviene `memfd` + `virtiofs` o un volumen de configuración por otro medio en modo plano (R4).
4. Tamaño final de la imagen de nodo con `nmap`, `tcpdump`, `snmpd` y `vsftpd` instalados.
