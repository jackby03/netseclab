# Referencia de topología

Esta página documenta el formato YAML con el que se describe un escenario: todas las claves, sus
valores admitidos y lo que genera cada una.

## Ejemplo mínimo

```yaml
version: 1
name: mini
networks:
  ext:
    cidr: 10.0.0.0/24
nodes:
  - name: a
    links: [ext]
```

```bash
lab validate mini.yaml
# mini.yaml: OK - 1 nodes, 1 networks, 0 policies
```

Un fichero válido necesita `version`, `name`, al menos una red y al menos un nodo. Todo lo demás es
opcional o se deriva.

## Claves de primer nivel

| Clave | Obligatoria | Qué es |
|---|---|---|
| `version` | sí | Versión del formato; solo se admite `1`. |
| `name` | sí | Nombre del laboratorio: `[a-z0-9][a-z0-9._-]{0,62}`. |
| `description` | no | Texto libre. |
| `domain` | no | Dominio DNS; por defecto `<name>.lab`. |
| `defaults` | no | Valores por defecto; de momento solo se lee `image`. |
| `networks` | sí | Mapa nombre → red; al menos una. |
| `nodes` | sí | Lista de nodos; al menos uno. |
| `profiles` | no | Subconjuntos de nodos con nombre. |
| `policies` | no | Matriz de conectividad del cortafuegos. |
| `telemetry` | no | Envío de logs a un nodo SOC. |

Una clave desconocida es un error, no se ignora. El mensaje incluye la ruta exacta y, cuando la clave
se parece a una válida, una sugerencia.

## Redes

```yaml
networks:
  dmz:
    id: 1
    cidr: 10.10.20.0/24
    type: isolated
    mode: switch
    addressing: auto
    gateway: 10.10.20.254
```

| Clave | Por defecto | Qué es |
|---|---|---|
| `id` | orden de declaración | Entero de 0 a 255; se usa en las MAC y en el CIDR automático de las redes `nat`. |
| `cidr` | — | Red IPv4; obligatoria salvo en `type: nat`, donde se genera `10.99.<id>.0/24`. |
| `type` | `isolated` | `isolated`, `nat` o `bridged`. |
| `mode` | `switch` | `switch`, `hub` o `mirror`. |
| `addressing` | `auto` | `auto` o `dhcp`. |
| `gateway` | — | Dirección de la puerta de enlace; en `nat` por defecto es la primera dirección de la red. |
| `routes` | — | Rutas que se reparten por DHCP con la opción 121. |
| `parent` | — | Interfaz física de la caja; obligatoria en `bridged` y solo válida ahí. |

El bridge se llama `nvm-<nombre de la red>`.

### Tipos de red

| `type` | Qué hace |
|---|---|
| `isolated` | Bridge sin dirección en la caja; solo lo ven los nodos conectados. |
| `nat` | Bridge con dirección, NAT de salida a la caja y DNS por la puerta: sirve para las prácticas que necesitan Internet. |
| `bridged` | Cuelga de una interfaz física de la caja; exige `parent`. |

### Modos de conmutación

| `mode` | Qué hace | Cuándo |
|---|---|---|
| `switch` | Bridge Linux normal: aprende MAC y reenvía al puerto correcto. | Comportamiento realista. |
| `hub` | Sin aprendizaje de MAC: inunda todas las tramas a todos los puertos. | Sniffing y ARP spoofing sin trucos. |
| `mirror` | Open vSwitch con un objeto `Mirror` y un puerto espejo. | Switch realista y captura desde el anfitrión. |

`mirror` necesita Open vSwitch en la caja y `sudo` para crear el puerto espejo al levantar.

### Direccionamiento

| `addressing` | Comportamiento |
|---|---|
| `auto` | El motor asigna direcciones deterministas y el nodo las configura de forma estática. |
| `dhcp` | El nodo pide la dirección por DHCP al nodo que tenga `dhcp_server: true` en esa red. |

Con `addressing: dhcp` tiene que existir un nodo con `dhcp_server: true` conectado a esa red; si no,
la validación falla. La dirección calculada para cada nodo se usa como reserva por MAC. Si el enlace
declara `ip`, el nodo la configura de forma estática aunque la red sea `dhcp`.

`routes` se aplica en la configuración de `dnsmasq` del servidor DHCP. Para rutas en nodos con
direccionamiento estático, usar `routes` en el enlace del nodo.

## Nodos

```yaml
nodes:
  - name: fw
    image: debian13
    firewall: true
    sysctls:
      net.ipv4.ip_forward: 1
    links:
      - { net: ext, ip: 10.5.0.254 }
      - { net: dmz, ip: 10.5.1.254 }
```

| Clave | Por defecto | Qué es |
|---|---|---|
| `name` | — | Obligatorio y único: `[a-z][a-z0-9-]{0,30}`. |
| `image` | `debian13` | Alias del catálogo o referencia completa de Incus. |
| `links` | — | Al menos un enlace; ver la sección siguiente. |
| `toolsets` | — | Lista de conjuntos de herramientas de `lab/toolsets.yaml`. |
| `packages` | — | Paquetes Debian extra que se instalan en el nodo. |
| `assets` | — | Ficheros o directorios que se copian dentro del nodo. |
| `startup` | — | Script que se ejecuta en cada arranque. |
| `sysctls` | — | Valores de `sysctl` que se aplican en cada arranque. |
| `aliases` | — | Nombres DNS adicionales que apuntan a la primera dirección. |
| `resources` | 1 vCPU, 256 MB | Límites de CPU, memoria y disco. |
| `dhcp_server` | `false` | Ejecuta `dnsmasq` y sirve DHCP en sus redes DHCP. |
| `dns_server` | `false` | Publica el dominio del laboratorio en `dnsmasq`. |
| `firewall` | `false` | Aplica las reglas de `policies:` en el nodo. |
| `hostname` | `name` | Nombre del sistema dentro del nodo. |
| `env` | — | Variables de entorno para `startup`. |
| `privileged` | `false` | Contenedor privilegiado; solo para herramientas que lo exijan. |
| `environment` | — | Entorno de tynix (base y paquetes) en vez de una imagen. |

`environment` y `image` no se pueden declarar juntos. Un entorno se resuelve a una imagen
direccionada por contenido; ver [Compartir laboratorios](../guides/sharing.md).

### Assets

```yaml
assets:
  - { src: assets/site, dst: /var/www/html }
  - { src: assets/fw.nft, dst: /etc/lab/fw.nft, mode: "0644" }
```

`src` es relativo al fichero de topología. Un directorio se copia con `tar`; un fichero se envía como
texto UTF-8. El `mode` solo se aplica a los ficheros.

### Recursos

```yaml
resources: { cpus: 2, memory: 512MB, disk: 4GB }
```

`cpus` es un entero; `memory` y `disk` son cadenas con la unidad que entiende Incus. `disk` sobrescribe
el tamaño del disco raíz del nodo.

### Enlaces

```yaml
links:
  - ext
  - { net: dmz, ip: 10.10.20.50 }
  - { net: int, ip: 10.10.10.254, mac: ca:fe:00:00:02:fe, routes: [{ to: 10.10.11.0/24, via: 10.10.10.1 }] }
```

| Clave | Por defecto | Qué es |
|---|---|---|
| `net` | — | Nombre de una red declarada; obligatorio. |
| `ip` | derivada | Dirección IPv4 dentro de la red. |
| `mac` | derivada | MAC con formato `aa:bb:cc:dd:ee:ff`; única en el laboratorio. |
| `vlan` | — | VLAN del enlace, de 1 a 4094. |
| `default` | `false` | Convierte este enlace en la ruta por defecto. |
| `gateway` | el de la red | Puerta de enlace de la ruta por defecto. |
| `routes` | — | Rutas estáticas `{to, via}` del nodo. |
| `ifname` | `eth<índice>` | Nombre de la interfaz dentro del nodo. |

La forma corta `- ext` equivale a `{ net: ext }`.

### Direcciones derivadas

Si un enlace no lleva `ip`, el motor la asigna en dos pasadas por red: primero reserva todas las
direcciones explícitas y después reparte las automáticas desde `.10`, saltando `.1`, `.254` y las ya
usadas. La dirección de red y la de broadcast se rechazan.

La MAC se deriva de la red y del último octeto: `ca:fe:00:00:<id de red>:<último octeto>`. Solo se
escribe a mano cuando hay un motivo didáctico.

La primera dirección del nodo es la que se publica en DNS y en `/etc/hosts`; las demás bocas se
anotan en un comentario del fichero.

## Perfiles

```yaml
profiles:
  mini: [fw, exta, dmza]
  std: [base, fw, exta, dmza, inta]
  full: ["*"]
```

Un perfil es una lista de nombres de nodo o `["*"]` para todos. `lab up --profile <nombre>` levanta
solo esos nodos. Un perfil que no selecciona ningún nodo es un error.

## Políticas

```yaml
policies:
  - { from: int, to: ext, action: accept }
  - { from: ext, to: dmz, daddr: 10.5.1.10, port: 80, action: accept }
  - { from: ext, to: dmz, daddr: 10.5.1.10, port: 443, action: reject-reset }
  - { from: ext, to: dmz, action: drop }
```

| Clave | Por defecto | Qué es |
|---|---|---|
| `from` | — | Red de origen; debe existir. |
| `to` | — | Red de destino; debe existir. |
| `action` | `drop` | `accept`, `drop` o `reject-reset`. |
| `port` | — | Puerto de destino; si falta, la regla afecta a todos. |
| `proto` | `tcp` | Protocolo del puerto (`tcp` o `udp`). |
| `daddr` | — | Dirección IP de destino. |

Las reglas solo se escriben en el nodo con `firewall: true`, cuando la topología declara `policies:` y
para las políticas cuyas dos redes están conectadas a ese nodo. La cadena de reenvío acepta el tráfico
establecido y el lazo local, aplica las políticas y usa política `drop` cuando el nodo tiene alguna
regla aplicable.

La diferencia entre acciones es observable desde `nmap`:

| Acción | Efecto en un escaneo |
|---|---|
| `accept` | El puerto aparece `open` si hay servicio. |
| `reject-reset` | El puerto aparece `closed`. |
| `drop` | El puerto aparece `filtered`. |

## Telemetría

```yaml
telemetry:
  soc: soc
  sources: [auth, syslog, suricata]
  retention: 48h
```

| Clave | Por defecto | Qué es |
|---|---|---|
| `soc` | — | Nodo que recibe y almacena los logs; debe existir. |
| `sources` | `[auth, syslog]` | Ficheros que se siguen además del syslog: `auth`, `syslog`, `suricata`, `apache`. |
| `retention` | `24h` | Retención prevista; se anota en la configuración, no se aplica. |

El nodo SOC escucha por TCP en el 514 y escribe un fichero por nodo y día en `/var/log/lab/`. Los
demás nodos reenvían su syslog y los ficheros de las fuentes declaradas.

## Validación

`lab validate` comprueba, antes de arrancar:

- que la versión es 1 y el nombre cumple el formato;
- que hay al menos una red y un nodo, y que las claves son conocidas;
- CIDR IPv4 válidos, de tamaño suficiente, con la puerta de enlace dentro de la red;
- que los identificadores de red son únicos y los tipos y modos están entre los admitidos;
- que cada nodo declara al menos un enlace, que cada enlace apunta a una red existente y que la VLAN
  está en rango;
- que `addressing: dhcp` tiene un nodo con `dhcp_server` en esa red;
- que las redes `bridged` declaran `parent` y las demás no;
- direcciones dentro de su red, sin duplicados, y MAC únicas y bien formadas;
- que los perfiles solo referencian nodos existentes;
- que las políticas referencian redes existentes y acciones admitidas;
- que el nodo SOC de la telemetría existe;
- que un entorno tiene `base` y no convive con `image`.

Los errores se acumulan y se presentan con la ruta del YAML: `nodes.fw.links[ext].ip`, por ejemplo.
`lab validate` acepta varios ficheros y comodines.

!!! note "Lo que no comprueba"
    La validación no detecta solapes entre CIDR de redes distintas, no valida el formato de
    `memory`/`disk` más allá de pasarlo a Incus y no comprueba que un puerto de una política exista.
    Un solape puede producir un comportamiento inesperado en el bridge.

## Cobertura del formato

| Carencia | Estado |
|---|---|
| VLAN dentro de un segmento | Implementado: `vlan:` por enlace. |
| Límites de CPU, RAM y disco | Implementado: `resources:`. |
| Assets de tipo fichero | Implementado para texto UTF-8; los binarios van dentro de un directorio o de una imagen. |
| Publicar un puerto del nodo al anfitrión | Pendiente: `ports:`. |
| Enlaces punto a punto entre dos nodos | Pendiente: `links: [{peer: otro-nodo}]`. |
| Herramientas propias por nodo | Pendiente: `tools:`. |
| Salida a Internet | Implementada por segmento con `type: nat` (NAT y DNS); el atajo `lab up --uplink`, pendiente. |
| Nodos Windows | Pendiente y fuera del alcance actual. |
| Compatibilidad con Containerlab o GNS3 | No; se puede exportar el plan, no el fichero. |

!!! tip "Ejemplo completo"
    `lab/examples/example.net.yaml` reproduce el laboratorio clásico: tres segmentos, DHCP y DNS en
    `base`, cortafuegos en `fw`, web en `dmza` y perfiles `mini`, `std` y `full`.
