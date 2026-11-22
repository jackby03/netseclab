# Formato de topología

> Un laboratorio es un fichero YAML. Este documento define el formato, sus reglas y sus límites.
> El modelo está inspirado en Containerlab (`topology.clab.yml`), que es hoy el formato de facto para
> laboratorios de red declarativos, pero con nodos que son **máquinas** (contenedores de sistema) en
> vez de procesos.

---

## 1. Estructura

```yaml
version: 1                # obligatorio
name: <string>            # obligatorio, nombre del laboratorio
description: <string>     # opcional

defaults: { ... }         # opcional: valores por defecto para nodos y redes
networks: { ... }         # obligatorio: mapa nombre → definición
nodes: [ ... ]            # obligatorio: lista ordenada
profiles: { ... }         # opcional: subconjuntos con nombre
telemetry: { ... }        # opcional: SOC y envío de logs
```

Todo lo demás son valores derivados. **Nadie escribe direcciones MAC ni tablas de rutas.**

---

## 2. Redes

```yaml
networks:
  dmz:
    cidr: 10.10.20.0/24      # opcional si type=nat (se genera)
    type: isolated           # isolated | nat | bridged     (por defecto isolated)
    mode: switch             # switch | hub | mirror        (por defecto switch)
    addressing: auto         # auto | dhcp                  (por defecto auto)
    gateway: <ip>            # opcional; por defecto la del nodo que enruta
```

| `type` | Qué hace | Equivalente mental |
|---|---|---|
| `isolated` | Bridge sin dirección en la caja. Solo ven los nodos conectados | Red interna / host-only |
| `nat` | Bridge con dirección y NAT de salida a la caja. Con DHCP y DNS propios | Red NAT de VirtualBox/VMware |
| `bridged` | Cuelga del interfaz físico de la caja | Adaptador puente |

| `mode` | Qué hace | Cuándo |
|---|---|---|
| `switch` | Bridge Linux normal: aprende MACs y reenvía al puerto correcto | Comportamiento realista |
| `hub` | `learning off`: inunda todo a todos los puertos | **Sniffing y ARP spoofing sin trucos** |
| `mirror` | OVS con objeto `Mirror` | Switch realista + puerto espejo |

> El error clásico de los laboratorios de pentesting es dejar todos los segmentos en `switch` y
> descubrir en clase que el alumno en modo promiscuo no ve el tráfico de los demás. Aquí se elige
> por red, explícitamente.

`addressing: dhcp` exige que exista un nodo con `dhcp_server: true` en esa red (normalmente `base`).

---

## 3. Nodos

```yaml
nodes:
  - name: fw                       # obligatorio, único
    image: debian13                # imagen del catálogo (por defecto defaults.image)
    links: [ext, dmz]              # forma corta: una interfaz por red, IP automática
    hostname: fw.lab               # opcional, por defecto <name>.<dominio>

  - name: pivot
    links:
      - { net: dmz,   ip: 10.10.20.50 }
      - { net: int-a, ip: 10.10.10.254, mac: ca:fe:00:00:02:fe }

  - name: base
    links: [int-a, int-b, dmz]
    dhcp_server: true              # sirve DHCP en las redes con addressing: dhcp
    dns_server: true               # sirve DNS para el dominio del laboratorio
```

| Campo | Efecto |
|---|---|
| `links` | Una interfaz por entrada. **La lista puede tener las entradas que quieras** → pivoteo y routers gratis |
| `image` | Imagen del catálogo (`debian13`, `web`, `attacker`, `ids`, `soc-lite`, `monitoring`, …) |
| `toolsets` | Lista de sets de herramientas (`recon`, `webfuzz`, `sniff`, `crack`, …) — ver `04-catalogo-imagenes.md` |
| `packages` | Paquetes extra a instalar en la creación (compón roles sin imagen nueva) |
| `assets` | Ficheros del escenario a copiar dentro del nodo (`{src, dst}`) |
| `startup` | Script que se ejecuta en cada arranque, como `/etc/rc.local` |
| `sysctls` | Valores por nodo (`net.ipv4.ip_forward: 1`) |
| `aliases` | Nombres DNS adicionales que apuntan a la primera IP |
| `resources` | `{cpus: 1, memory: 256MB}` — por defecto 1 vCPU / 256 MB |
| `env` | Variables de entorno para `startup` |

### Direcciones

Si un enlace no lleva `ip`, se resuelve así:

1. Red `nat` → DHCP de la red.
2. Red con `addressing: dhcp` y un `dhcp_server` → DHCP de ese nodo.
3. Resto → asignación determinista del motor: `.10`, `.11`, … por orden de declaración.

Las MAC también se derivan por defecto (`ca:fe:00:00:0<red>:<n>`) y solo se escriben cuando hay un
motivo didáctico para hacerlo.

---

## 4. Perfiles

```yaml
profiles:
  mini:  [attacker, fw, www]
  std:   [attacker, fw, www, pivot, inta1]
  full:  [*]        # todos
```

`lab up --profile mini`. Sirve para que el mismo laboratorio quepa en un portátil modesto o para
montar solo la parte de la práctica que toca.

---

## 5. Ejercicios

Un ejercicio es otro YAML que referencia un laboratorio, un estado inicial y unas aserciones.

```yaml
id: 06-pivoteo
title: Pivoteo de ext a la red interna a través de la DMZ
lab: ../examples/pivot.yaml
profile: std
initial: initial

brief: |
  Desde attacker, alcanza inta1 sin que el tráfico salga de la red interna.

checks:
  - assert: reachable  attacker -> 10.10.10.10 is false
  - assert: reachable  pivot    -> 10.10.10.10 is true
  - assert: port-state pivot    -> 10.10.10.10:22 is open
  - assert: capture    dmz, contains="10.10.20.50"
```

`lab check 06-pivoteo.yaml` ejecuta las aserciones y devuelve un informe por comprobación.

### Gramática de las aserciones

| Forma | Comprueba |
|---|---|
| `reachable <nodo> -> <destino> is true\|false` | Alcanzabilidad con `ping` |
| `port-state <nodo> -> <ip>:<puerto> is open\|closed\|filtered` | Estado real del puerto (sonda TCP) |
| `http-status <nodo> -> <url> is <código>` | Código HTTP |
| `file <nodo> <ruta> exists\|missing` | Existencia de un fichero |
| `ids-alerts src=<ip>, count=<n>[, node=<nodo>][, log=<ruta>]` | Alertas del IDS |
| `capture <red>, contains="<texto>"[, file=<ruta>]` | Contenido de una captura |
| `answer "<pregunta>" contains "<palabra>"` | Respuesta de razonamiento |

> **Usa `=` en los parámetros, no `:`.** Un `assert: ids-alerts since: last` sin comillas rompe el
> YAML porque los dos puntos parecen un mapa. Con `since=last` no hay ambigüedad y no hacen falta
> comillas. El motor acepta ambos, pero el estilo recomendado es `=`.

Las respuestas de razonamiento se guardan con `lab answer <ejercicio> "texto"` en `answers/<id>.txt`.

---

## 6. Validación

- **Esquema JSON** (`lab/schema/topology.schema.json`) para autocompletado y validación en el editor.
- `lab validate` comprueba antes de arrancar: nombres únicos, CIDR válidos y sin solapes, IPs dentro
  de su red, MACs únicas, `dhcp` con servidor, `mirror` con OVS disponible, imágenes existentes.
- Los errores dicen **qué arreglar y dónde**, no solo que algo falla.

---

## 7. Lo que el formato no hace (todavía)

| Carencia | ¿Previsto? |
|---|---|
| VLANs dentro de un segmento | Sí, `vlan:` por enlace |
| Publicar un puerto del nodo al host | Sí, `ports:` por nodo |
| Enlaces punto a punto entre dos nodos sin red intermedia | Sí, `links: [{peer: otro-nodo}]` |
| Límites de CPU/RAM/disco | Sí, `resources:` |
| Topologías grandes (>50 nodos) | No es el objetivo; el límite práctico es el portátil |
| Compatibilidad con Containerlab o GNS3 | No; se puede exportar el diagrama, no el fichero |
