# Guía de uso

Para un profesor que abre el proyecto por primera vez. De cero a un laboratorio con el que dar clase.

---

## 1. La caja

El artefacto es una VM de VMware con Debian 13 mínimo, Incus y el CLI. Se construye una vez y se
reparte.

```bash
make box            # necesita un Linux x86_64 con QEMU (o WSL2)
```

Sale en `build/box/netseclab-vmware.tar.gz`. Se descomprime, se abre `netseclab.vmx` con VMware
Workstation o Player, y ya está. Dos núcleos y 2 GB son suficientes para tres o cuatro nodos.

No hace falta activar la virtualización anidada. Dentro de la caja no hay máquinas virtuales: hay
contenedores de sistema.

---

## 2. Levantar el laboratorio

Dentro de la caja, por consola de VMware o por SSH con el usuario `lab`:

```bash
lab up /opt/netseclab/lab/examples/example.net.yaml
```

Eso crea tres redes, el nodo `base` con DHCP y DNS, `fw` con sus tres bocas y las reglas del
cortafuegos, `exta`, `dmza` con Apache y `inta`. Al terminar crea un snapshot llamado `initial`: es
el botón de reinicio.

```bash
lab status
```

```
nombre     estado       tipo       ipv4
base       RUNNING      container  10.5.0.1, 10.5.1.1, 10.5.2.1
fw         RUNNING      container  10.5.0.254, 10.5.1.254, 10.5.2.254
exta       RUNNING      container  10.5.0.10
dmza       RUNNING      container  10.5.1.10
inta       RUNNING      container  10.5.2.10
```

---

## 3. Trabajar dentro de un nodo

```bash
lab console exta
```

Es un Debian normal: `apt install`, `systemctl`, `iptables`, `nmap`, `tcpdump`. Desde `exta`:

```bash
nmap www.example.net
```

Deberían salir el 80 abierto, el 443 cerrado y el resto filtrado. Si sale otra cosa, el
cortafuegos no está como toca: `incus exec fw -- nft list ruleset`.

> Para volver de una consola: `Ctrl-a`, sueltas, y luego `q`. Es la secuencia de `incus console`;
> `Ctrl-C` solo interrumpe el login y vuelve a pedirlo. Si el nodo no está arrancado, `lab console`
> muestra su log en vez de una consola que no puede funcionar.

**Credenciales de los nodos:** `root` / `netseclab` y `user1` / `netseclab` (`user1` con `sudo`, como
en el NETinVM original). El SSH de los nodos acepta contraseña; la caja, en cambio, solo acepta clave.

---

## 4. Romper y volver atrás

```bash
lab snapshot ... --name antes-del-ataque
lab reset ...                       # vuelve al estado inicial en segundos
lab reset ... --name antes-del-ataque
```

`lab up` crea el snapshot `initial`. `lab reset` restaura el que le pidas. Los snapshots son de
Incus: con el almacenamiento por defecto son instantáneos.

Esto es lo que permite un ritmo de clase real: cada alumno rompe, revierte y repite sin esperar
minutos.

---

## 5. Consolas en el navegador

```bash
lab web /opt/netseclab/lab/examples/example.net.yaml --port 8080
```

Y desde el navegador del anfitrión, `http://<ip-de-la-caja>:8080`. Una pestaña por nodo, sin instalar
nada en el portátil.

Por defecto escucha en `127.0.0.1`. Si lo abres a la red, ten claro lo que estás dando: una shell
dentro de un laboratorio de ataque.

---

## 6. Capturar tráfico

```bash
lab capture /opt/netseclab/lab/examples/example.net.yaml --net dmz --seconds 20
```

Deja `capture/dmz.pcap`. El mecanismo depende de cómo esté declarado el segmento:

| modo | qué hace |
|---|---|
| `mirror` | captura en el puerto espejo del switch (OVS) |
| `hub` | captura dentro de un nodo, y se ve **todo** el segmento |
| `switch` | captura dentro de un nodo, y solo se ve lo suyo |

La diferencia entre `hub` y `switch` no es un detalle: es la que hace que un ejercicio de sniffing
funcione o fracase. Se elige por red en el YAML.

---

## 7. Corregir un ejercicio

```bash
lab up /opt/netseclab/lab/examples/fuzz-evasion.yaml --profile mini
lab check /opt/netseclab/lab/exercises/06-fuzz-evasion.yaml
```

```
06-fuzz-evasion — Descubrimiento de directorios y evasión de IDS
3/4 comprobaciones superadas

  [OK   ] evil1 obtiene 200 de http://10.20.1.10/backup/
          HTTP 200 (esperado 200)
  [FALLA] alertas del IDS con origen 10.20.0.30: 0
          El IDS ha registrado alertas con tu IP...
          detalle: 7 alertas (esperado 0)
```

El alumno itera solo. El profesor corrige escenarios, no capturas de pantalla.

Las preguntas de razonamiento se guardan con:

```bash
lab answer /opt/netseclab/lab/exercises/06-fuzz-evasion.yaml "porque la regla usa el user-agent"
```

---

## 8. Escribir una topología nueva

```bash
lab init milab
```

Crea `milab/topology.yaml` con un escenario de ejemplo. Los conceptos:

- **redes**: `type` (`isolated` / `nat`) y `mode` (`switch` / `hub` / `mirror`).
- **nodos**: una lista de `links`. Dos enlaces es un router o un pivote.
- **toolsets**: qué herramientas lleva el nodo (`recon`, `webfuzz`, `sniff`, …).
- **estilo recomendado**: IPs explícitas solo donde importen; el resto se reparten solas.

```bash
lab validate milab/topology.yaml
lab render milab/topology.yaml --format table
lab up milab/topology.yaml --dry-run
```

`--dry-run` enseña los comandos exactos de Incus sin ejecutarlos: es la mejor forma de entender qué
va a pasar y de depurar.

Detalle completo en [03-formato-topologia.md](03-formato-topologia.md).

---

## 9. Escribir un ejercicio

Un ejercicio es un YAML con enunciado y aserciones:

```yaml
id: 07-dhcp
title: Encontrar al servidor DHCP falso
lab: ../examples/example.net.yaml
profile: std

brief: |
  En la red interna hay un DHCP no autorizado repartiendo direcciones.
  Localízalo y explica cómo lo has hecho.

checks:
  - assert: answer "¿Qué dirección del servidor DHCP devuelve un lease?" contains "option 54"
    message: Piensa en las opciones DHCP que se ven en un `tcpdump` del puerto 67.
```

`lab check 07-dhcp.yaml` y a corregir. Gramática completa en
[03-formato-topologia.md](03-formato-topologia.md) §5.

---

## 10. Cuándo algo no funciona

| Síntoma | Qué mirar |
|---|---|
| `lab up` falla al crear una red | `incus network list`; ¿quedó una a medias de otro intento? |
| Un nodo no arranca | `incus info <nodo>` y `incus console <nodo>` |
| No hay conectividad entre redes | `incus exec fw -- nft list ruleset` y `incus exec fw -- sysctl net.ipv4.ip_forward` |
| Un nodo no tiene IP | `incus exec <nodo> -- systemctl status lab-net`, `journalctl -u lab-net` |
| El IDS no genera alertas | `incus exec fw -- tail /var/log/suricata/suricata.log` |
| `lab reset` dice que no existe el snapshot | `lab up` lo crea; o `lab snapshot <topología> --name <nombre>` |

Cuando algo va mal, `lab render <topología> --format shell` da el plan completo en texto: se puede
leer, comparar y ejecutar a mano.
