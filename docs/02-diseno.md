# NETinVM bien hecho — diseño consolidado

> Sustituye a [`01-decisiones.md`](01-decisiones.md), que quedó obsoleto al fijarse el objetivo
> real: un laboratorio para **enseñar y practicar seguridad en redes**, ligero, que se ejecuta
> dentro de una única VM de VMware.
>
> Estado: propuesta para validar antes de implementar.

---

## 1. Qué construimos, en una frase

Un **artefacto de VMware** (OVA/VMDK) que contiene un Linux mínimo con un laboratorio de red listo
para usar: una red `example.net` con tres segmentos, un cortafuegos que los une, servicios reales,
máquinas con las que atacar y defenderse, captura de tráfico y **ejercicios que se corrigen solos**.

No es un clon de NETinVM. Es la respuesta a la misma necesidad, tomando las decisiones que el
original no tomó y evitando lo que lo hace pesado.

---

## 2. Los siete principios

Cada uno responde a un defecto concreto del original (ver [`00-analisis-netinvm.md`](00-analisis-netinvm.md) §12).

| # | Principio | Defecto que corrige |
|---|---|---|
| P1 | **Sin virtualización anidada.** La VM de VMware es la frontera; dentro, los nodos son contenedores de sistema. | El anidamiento era el infierno: requisito de hardware, 4,9 GB, arranques de minutos. |
| P2 | **La topología es un dato**, no un script. Un `topology.yaml` genera redes, nodos, DHCP, DNS, cortafuegos y las pruebas. | La topología estaba cableada en guiones; cambiar algo era editarlos a mano. |
| P3 | **Nodo = rol reutilizable.** Roles (`base`, `firewall`, `web`, `ftp`, `ids`, `attacker`) publicados como imágenes con nombre y versión. | Trece imágenes horneadas a mano, imposibles de mantener. |
| P4 | **Estado = snapshot.** Levantar, romper, revertir y repetir en segundos. | El "restore" tardaba minutos y solo servía para la misma versión. |
| P5 | **Los ejercicios se comprueban solos.** Cada práctica declara aserciones ejecutables. | Cero validación: el alumno no sabe si acertó hasta que el profesor corrige. |
| P6 | **Offline y aislado por defecto.** Todo cacheado en la imagen; sin salida a Internet salvo que se pida. | Dependencia de descargas en el aula y de una red que no siempre existe. |
| P7 | **Todo se puede reconstruir y verificar** desde fuentes públicas, con licencia libre. | Sin licencia, sin código, sin build: 4,9 GB opacos. |

---

## 3. Arquitectura

```
┌─────────────────────────────────────────────────────────────────────────┐
│ PORTÁTIL DEL ALUMNO — VMware Player / Workstation / ESXi                │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ VM «caja» · Debian 13 mínimo · 2 vCPU · 2–4 GB RAM · 8 GB disco   │  │
│  │ Sin escritorio. Arranca en ~8 s.                                  │  │
│  │                                                                   │  │
│  │  incus (contenedores de sistema)                                  │  │
│  │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐                   │  │
│  │  │  base  │  │   fw   │  │  dmza  │  │  exta  │   … 13 nodos     │  │
│  │  │ DHCP   │  │ 3 NICs │  │ apache │  │ tools  │                   │  │
│  │  │ DNS    │  │nftables│  │  DVWA  │  │ nmap   │                   │  │
│  │  │ NAT    │  │ routing│  │        │  │ hydra  │                   │  │
│  │  └───┬────┘  └──┬──┬──┘  └───┬────┘  └───┬────┘                   │  │
│  │      │          │  │         │           │                        │  │
│  │  ════╪══════════╪══╪═════════╪═══════════╪════ nvm-ext            │  │
│  │      ═══════════╪══╪═════════╪══════════════════ nvm-dmz            │  │
│  │                 ══╪═════════╪════════════════════ nvm-int           │  │
│  │                   └─────────┘                                     │  │
│  │                                                                   │  │
│  │  Servidor web local :8080 → consolas de todos los nodos           │  │
│  │  CLI `lab` → up · down · status · console · capture · snapshot     │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Por qué una sola VM

- **Es la frontera de seguridad.** Un laboratorio cuyo objetivo es atacar máquinas no puede compartir
  kernel con el portátil del alumno. La VM lo aísla y es **desechable**: si se rompe, se reimporta.
- **Es el artefacto único.** Un OVA que se importa y se arranca, como el original, pero de ~1,5 GB.
- **Elimina el anidamiento.** VMware solo tiene que virtualizar una máquina, no dieciocho.
- **Hace el laboratorio independiente del hipervisor.** Lo que corre dentro es Linux estándar; mañana
  puede correr en QEMU, en Proxmox o en un servidor de aula sin cambiar nada.

### Componentes

| Componente | Tecnología | Papel |
|---|---|---|
| Motor de nodos | **Incus** | Contenedores de sistema con `systemd`, snapshots, NICs con MAC fija |
| Conmutación | bridges Linux (Incus) + OVS opcional | Tres segmentos; modo switch, hub o espejo por red |
| DHCP/DNS | `dnsmasq` en `base` | Reparte `10.5.N.10-15` por MAC, resuelve `example.net` y alias |
| Cortafuegos | `nftables` en `fw` (e `iptables-nft` disponible) | La matriz de conectividad del curso |
| CLI | Python 3.11 + Typer | Toda la vida del laboratorio |
| Consolas | `ttyd` + `xterm.js` | Una pestaña por nodo en el navegador del host |
| Pruebas | `pytest` + aserciones dentro del laboratorio | Aceptación del banco y corrección de ejercicios |

---

## 4. Modelo de datos

Todo sale de un fichero. Ejemplo completo del laboratorio por defecto:

```yaml
version: 1

lab:
  name: example.net
  domain: example.net
  address_plan: 10.5                 # 10.5.<red>.<nodo>
  uplink: false                      # sin salida a Internet (P6)
  default_profile: small

networks:
  ext: { id: 0, mode: switch }       # switch | hub | mirror
  dmz: { id: 1, mode: hub }          # hub: promiscuo funciona sin trucos
  int: { id: 2, mode: switch }

roles:
  base:     { image: lab/base:1,     networks: [ext, dmz, int], address: .1,   mac: 01 }
  firewall: { image: lab/firewall:1, networks: [ext, dmz, int], address: .254, mac: fe }
  web:      { image: lab/web:1,      services: [http, https], vulnerable: true }
  ftp:      { image: lab/ftp:1,      services: [ftp] }
  ids:      { image: lab/ids:1,      services: [suricata], capture: true }
  attacker: { image: lab/attacker:1, tools: [nmap, hydra, tshark, bettercap, mitmproxy] }
  plain:    { image: lab/node:1 }

nodes:
  - { name: base,     role: base }
  - { name: fw,       role: firewall }
  - { name: exta,     role: attacker, network: ext }
  - { name: extb,     role: plain,    network: ext }
  - { name: dmza,     role: web,      network: dmz, aliases: [www] }
  - { name: dmzb,     role: ftp,      network: dmz, aliases: [ftp] }
  - { name: idse,     role: ids,      network: dmz }
  - { name: inta,     role: plain,    network: int }
  - { name: intb,     role: plain,    network: int }

profiles:
  small: [fw, exta, dmza]            # 3 nodos, para un portátil modesto
  std:   [fw, exta, dmza, dmzb, inta]
  full:  [*]                         # los 9 definidos

policies:
  fw:
    - { from: int, to: ext, action: accept }
    - { from: ext, to: int, action: drop }
    - { from: ext, to: dmza, port: 80, action: accept }
    - { from: ext, to: dmza, port: 443, action: reject-reset }   # «closed», no «filtered»
    - { from: ext, to: dmz, action: drop }
```

**IP y MAC se derivan, no se escriben**: `10.5.<id_red>.<nodo>` y `ca:fe:00:00:0<id_red>:<sufijo>`.
Así el plan de direccionamiento del original se conserva sin que nadie tenga que copiarlo a mano, y
cambiarlo es cambiar una línea.

Un nodo nuevo es **una línea**. Un segmento nuevo, dos.

---

## 5. Los ejercicios, que es lo que de verdad importa

Aquí está la diferencia con NETinVM más allá del rendimiento. Un ejercicio no es un PDF: es un
objeto ejecutable.

```yaml
- id: 03-portscan
  title: Reconocimiento de servicios con nmap
  profile: small
  initial: clean                      # snapshot de partida
  brief: |
    Desde exta, averigua qué servicios expone www.example.net.
    Explica por qué el puerto 443 aparece «closed» y el resto «filtered».
  tasks:
    - Ejecuta un escaneo de los 1000 puertos más comunes.
    - Repite el escaneo de todos los puertos.
    - Identifica la versión del servidor web.
  checks:
    - assert: port-state  exta -> www.example.net 80  is open
    - assert: port-state  exta -> www.example.net 443 is closed
    - assert: port-state  exta -> www.example.net 22  is filtered
    - assert: answer      "¿Por qué 443 es closed y no filtered?"  contains "reject"
```

`lab check 03-portscan` ejecuta las aserciones contra el laboratorio en marcha y devuelve un informe.
El profesor escribe el escenario y las aserciones; el alumno recibe feedback inmediato; la
evaluación deja de depender de que alguien revise capturas de pantalla.

**Tres tipos de aserción** cubren casi todo el temario:

| Tipo | Comprueba |
|---|---|
| `port-state` / `reachable` | Resultados de red (escaneo, conectividad, ruta) |
| `capture` | Que un paquete concreto aparezca en un segmento (o que **no** aparezca) |
| `answer` | Preguntas de razonamiento con coincidencia de palabras clave |

---

## 6. Ciclo de vida

```bash
lab up                    # arranca el perfil por defecto
lab up --profile full     # los 9 nodos
lab status                # qué corre, IPs, MACs, uso de recursos
lab console dmza          # consola interactiva
lab web                   # servidor de consolas en :8080
lab capture dmz           # empieza a capturar el segmento dmz → dmz.pcap
lab snapshot antes        # marca de estado
lab reset                 # vuelve al estado inicial en segundos  (P4)
lab check 03-portscan     # corrige el ejercicio
lab down
```

Y por debajo, los comandos de Incus que hacen el trabajo. **El CLI no esconde la herramienta**: en
las prácticas se enseña `incus list`, `incus exec`, `incus config show`, porque saber manejar la
herramienta forma parte del aprendizaje. El CLI es azúcar, no una caja negra.

---

## 7. Red: las tres decisiones que hay que acertar

### 7.1 Modo de cada segmento

| Modo | Qué hace | Para qué |
|---|---|---|
| `switch` | Bridge Linux normal: aprende MACs y reenvía al puerto correcto | Comportamiento realista de red conmutada |
| `hub` | Bridge con `learning off`: inunda todo a todos | **Sniffing sin trucos**, ARP spoofing, escucha pasiva |
| `mirror` | OVS con objeto `Mirror` | Switch realista **y** puerto espejo, como el original |

El error clásico es poner todos los segmentos en `switch` y descubrir en clase que el alumno no ve
nada al ponerse en promiscuo. Por eso el modo es **por red y explícito en el YAML**: el profesor
decide qué quiere que se pueda ver en cada práctica.

### 7.2 DHCP y DNS

`dnsmasq` en `base`, tres `dhcp-range` etiquetados, reservas por MAC, `A`+`PTR` automáticos, alias
`www`/`ftp` y `local=/example.net/`. Las rutas a los otros segmentos se reparten con la opción 121,
de modo que un nodo recién arrancado ya tiene la tabla de rutas correcta.

### 7.3 Salida al exterior

Desactivada por defecto. Un laboratorio de pentesting que hace NAT a Internet está mandando tráfico
de un `nmap` a la red de la institución, y eso es un problema legal, no un detalle de configuración.
Se activa con `lab up --uplink` y se documenta el riesgo.

---

## 8. Presupuesto de recursos

Medido en la caja construida y probada en QEMU con KVM:

| | Medido |
|---|---|
| Artefacto (`.tar.gz`) | **1,9 GB** |
| VMDK descomprimido | 3,3 GB |
| Disco de la caja | 12 GB virtuales, **3,1 GB usados** |
| RAM de la caja | 2 GB (4 GB recomendado para el perfil `full`, 7 nodos) |
| Arranque de un nodo | segundos |
| Arranque de `lab up` (5 nodos) | ~1 minuto |
| NETinVM equivalente | 4,9 GB de artefacto y ~6 GB de RAM |

Las cifras del diseño original (RAM ~900 MB, artefacto ~1,5 GB) se han cumplido salvo el artefacto,
que se queda en 1,9 GB por las cuatro imágenes de nodo que llevan las herramientas dentro.

### El almacenamiento es parte del producto

El driver de almacenamiento por defecto de Incus (`dir`) **copia la imagen completa para cada
contenedor**. Con imágenes de nodo de ~1,2 GB, siete nodos son 8,4 GB y el disco de 12 GB se llena;
el síntoma es un `No space left on device` al escribir cualquier cosa, incluso la respuesta de un
ejercicio.

Por eso la caja crea un pool **btrfs** sobre un fichero y apunta ahí el perfil de los nodos: con
copy-on-write los nodos comparten bloques con la imagen y cada uno ocupa decenas de megas. Si el pool
no se puede crear (kernel sin btrfs, por ejemplo), el provisionamiento avisa y sigue con `dir`, pero
entonces el perfil `full` de siete nodos no cabe.

| Driver | 7 nodos | Artefacto |
|---|---|---|
| `dir` | ~8,4 GB | no cabe en 12 GB |
| `btrfs` (CoW) | ~2–3 GB | cabe con holgura |

La lección: en un laboratorio de contenedores, el espacio en disco no es un detalle de despliegue,
es un requisito de diseño que se manifiesta en la cara del usuario final.

---

## 9. Estructura del repositorio

```
netinvm-rework/
├── lab/                      topologías y escenarios (datos, no código)
│   ├── example.net.yaml
│   └── exercises/
│       ├── 01-arranque.yaml
│       ├── 02-conectividad.yaml
│       ├── 03-portscan.yaml
│       ├── 04-captura.yaml
│       ├── 05-cortafuegos.yaml
│       ├── 06-arp-mitm.yaml
│       ├── 07-dns.yaml
│       └── 08-ids.yaml
├── src/lab/                  CLI y motor
│   ├── cli.py
│   ├── model.py              topología → objetos tipados, con validación
│   ├── generate/             dnsmasq · nftables · bridges · cloud-init
│   ├── engine/               incus · capture · web · checks
│   └── roles/                recetas de construcción de cada rol
├── images/                   construcción del artefacto
│   ├── box/                  Debian mínimo + incus + lab (la VM de VMware)
│   └── roles/                base, firewall, web, ftp, ids, attacker
├── docs/                     este documento, guía de usuario, guía del profesor
├── tests/                    unitarios + aceptación del banco
└── Makefile                  build · test · box · ova
```

---

## 10. Plan de entrega

| Fase | Qué | Criterio de hecho |
|---|---|---|
| **1. Núcleo** | Modelo + `topology.yaml` + generadores + `lab up/down/status/console` + 3 nodos | `lab up` levanta `fw`, `exta`, `dmza` y se puede hacer ping y SSH |
| **2. Red completa** | `base` con dnsmasq, `fw` con nftables, matriz de conectividad, modos hub/switch | La matriz del curso se cumple y está cubierta por tests |
| **3. Didáctica** | Captura, snapshots, `lab reset`, `lab check` y los 8 ejercicios | Un alumno completa el ejercicio 3 y recibe el informe |
| **4. Artefacto** | OVA/VMDK con todo cacheado, consolas web, guía del alumno | Importar en VMware, arrancar y estar dentro en menos de 5 minutos |

Fase 1 es la que demuestra que el diseño se sostiene. Antes de escribirla quiero tu visto bueno.

---

## 11. Decisiones que tomo por defecto (dime si alguna no te vale)

| Tema | Decisión |
|---|---|
| Nombre | `netseclab` provisional, comando `lab` |
| Licencia | GPL-3.0-or-later (código) + CC-BY-SA-4.0 (documentación y ejercicios) |
| SO de la caja y los nodos | Debian 13, sin escritorio |
| Acceso | `lab console` + consolas web `:8080` sincronizadas |
| Idioma | Documentación y ejercicios en español; README y CLI en inglés |
| Reparto | Roles como imágenes versionadas, no máquinas a mano |
| Internet | Desactivada por defecto |
| Incus | Versión de Debian 13 (6.0 LTS); se puede subir a 7.x de backports |
