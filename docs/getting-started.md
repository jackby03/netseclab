# Primeros pasos

Esta página deja un laboratorio en marcha y corregido en la caja en menos de cinco minutos.

## Antes de empezar

El uso previsto es la caja: una VM de VMware con Debian 13, Incus, el CLI `lab` y las imágenes de
nodo ya construidas. El artefacto ocupa unos 2,3 GB y se abre con VMware Workstation o Player. La caja
necesita 2 vCPU, 2 GB de RAM y 12 GB de disco; no hace falta activar la virtualización anidada.

Para leer, validar y renderizar topologías desde el repositorio no hace falta Incus. Para ejecutar
`lab up` de verdad sí: el motor habla con el demonio de Incus, que solo existe dentro de la caja.

## Poner en marcha la caja

```bash
tar -xzf netseclab-vmware.tar.gz
# abrir netseclab.vmx con VMware
```

En la consola de VMware, entrar con el usuario `lab` y la contraseña `netseclab`. Cambiar la
contraseña en el primer arranque:

```bash
passwd
lab --help
```

| Dónde | Usuario | Contraseña |
|---|---|---|
| La caja (consola de VMware) | `lab` | `netseclab` |
| Los nodos del laboratorio | `root` | `netseclab` |
| Los nodos del laboratorio | `user1` | `netseclab` |

`user1` es el usuario sin privilegios con `sudo`. El SSH de los nodos acepta contraseña; el de la
caja solo acepta clave.

## Levantar el primer laboratorio

`lab up` lee la topología, calcula el plan y lo ejecuta paso a paso. Al terminar crea el snapshot
`initial`, que es el punto de retorno de `lab reset`.

```bash
lab up /opt/netseclab/lab/examples/example.net.yaml --profile std
```

```
lab: example.net   domain: example.net   profile: std

NETWORKS
  name       cidr             type      mode    bridge         gateway
  ext        10.5.0.0/24      isolated  hub     nvm-ext        10.5.0.1
  dmz        10.5.1.0/24      isolated  mirror  nvm-dmz        10.5.1.254
  int        10.5.2.0/24      isolated  switch  nvm-int        10.5.2.254

NODES
  name       image                  interfaces
  base       lab-node-v1            eth0=10.5.0.1/24, eth1=10.5.1.1/24, eth2=10.5.2.1/24
  fw         lab-node-v1            eth0=10.5.0.254/24, eth1=10.5.1.254/24, eth2=10.5.2.254/24
  exta       lab-node-v1            eth0=10.5.0.10/24
  dmza       lab-web-v1             eth0=10.5.1.10/24
  inta       lab-node-v1            eth0=10.5.2.10/24

running the plan (Ctrl-C to interrupt; run it again to continue):
  [ 1/66] profile netseclab for the nodes (ignored if it already exists)
  ...
  [66/66] dmz: mirror port cap-dmz (OVS)

66 steps run
snapshot 'initial' created: `lab reset` returns here
```

`lab up` es idempotente: si se interrumpe o falla un paso, volver a lanzarlo continúa donde se
quedó. El perfil `std` levanta cinco nodos; el perfil `full` levanta los siete del escenario.

## Ver el estado y entrar en un nodo

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

```bash
lab console exta
```

La consola es un `incus console` normal. Para salir: `Ctrl-a`, soltar y pulsar `q`. Si el nodo no
está arrancado, `lab console` enseña su log en lugar de una consola que no puede funcionar.

## Comprobar el cortafuegos

Desde `exta`, el servidor web de la DMZ solo publica HTTP:

```bash
nmap www.example.net
```

```
PORT    STATE    SERVICE
22/tcp  filtered ssh
80/tcp  open     http
443/tcp closed   https
```

El puerto 443 aparece **closed** porque el cortafuegos responde con un RST; el resto aparece
**filtered** porque se descarta en silencio. La diferencia es deliberada: un puerto cerrado no tiene
servicio, un puerto filtrado tiene un cortafuegos delante.

## Corregir el primer ejercicio

El ejercicio `01-reconocimiento` usa ese mismo escenario y perfil.

```bash
lab check /opt/netseclab/lab/exercises/01-reconocimiento.yaml
```

```
01-reconocimiento - Reconocimiento de servicios con nmap
0/1 answers correct - 0/5 points
3/3 environment checks passed

ANSWERS
  [FAIL]   5 pt  ¿Qué puerto de www aparece como «closed» desde exta?
          not answered
          where to look: Revisa las reglas de fw en /etc/lab/fw.nft.

ENVIRONMENT
  [OK   ] from exta, www:80 is open
          state=open (expected open)
  ...
```

El alumno entrega el valor con `lab answer`, vuelve a corregir y genera el informe escrito:

```bash
lab answer /opt/netseclab/lab/exercises/01-reconocimiento.yaml puerto-cerrado "443"
lab check /opt/netseclab/lab/exercises/01-reconocimiento.yaml
lab report /opt/netseclab/lab/exercises/01-reconocimiento.yaml --out informe.md
```

La segunda corrección devuelve `1/1 answers correct - 5/5 points`. El informe es una plantilla en
Markdown con las respuestas entregadas y las preguntas abiertas que corrige el profesor.

## Siguientes pasos

- [Operación](guides/operating.md): snapshots, captura, consolas web y diagnóstico.
- [Ejercicios](guides/exercises.md): formato completo, respuestas estrictas e informe.
- [Topología](reference/topology.md): todas las claves del YAML.
- [CLI](reference/cli.md): referencia de todos los comandos.

!!! warning "Fuera de la caja"
    `lab up`, `lab down`, `lab status`, `lab console`, `lab capture`, `lab push`, `lab pull` y
    `lab gc` necesitan Incus. En un portátil sin la caja, `lab validate`, `lab render`, `lab pack`,
    `lab unpack`, `lab lock` y `lab report` funcionan igual.

## Trabajar desde el repositorio

Para modificar el proyecto o revisar el plan sin ejecutarlo:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest

lab validate lab/examples/example.net.yaml
lab render lab/examples/example.net.yaml --format table
lab up lab/examples/example.net.yaml --dry-run
```

Con el paquete sin instalar, anteponer `PYTHONPATH=src` y usar `python -m lab.cli`. Los comandos
`render` y `up --dry-run` permiten revisar el plan completo sin tocar Incus.
