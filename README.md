# netseclab

Laboratorio de **seguridad en redes** para enseñar y practicar: ligero, declarativo y reproducible.

Una VM (la «caja») con Debian mínimo y [Incus](https://linuxcontainers.org/incus/) dentro. Los nodos
del laboratorio son **contenedores de sistema** con `systemd`, `sshd`, `apache`, `iptables`/`nftables`
y todo lo que hace falta para atacar y defenderse. **Sin virtualización anidada.**

- Se describe en un **YAML** y de ahí salen redes, IPs, MACs, DNS, cortafuegos y pruebas.
- `lab reset` devuelve el laboratorio al estado inicial en segundos.
- Los ejercicios **se corrigen solos** con aserciones ejecutables.

Estado: **PoC completo** — modelo, generación, motor de ciclo de vida, captura, telemetría,
ejercicios autocorregibles, consolas por navegador y construcción de la caja, con **102 pruebas**.

Lo que depende de Incus o de Linux (arrancar el laboratorio, construir la caja) se entrega como
código probado contra los planes generados, con instrucciones en [docs/05-guia-usuario.md](docs/05-guia-usuario.md).
Ver también [docs/02-diseno.md](docs/02-diseno.md).

## Instalación para desarrollo

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Uso

```bash
lab validate lab/examples/example.net.yaml
lab render lab/examples/example.net.yaml --format table
lab render lab/examples/fuzz-evasion.yaml --format shell      # el plan completo, en shell
lab render lab/examples/example.net.yaml --out /tmp/plan       # todos los ficheros generados
lab up lab/examples/fuzz-evasion.yaml --dry-run
```

`lab up` de verdad requiere estar **dentro de la caja** (la VM con Incus). En cualquier otro sitio,
`render` y `--dry-run` funcionan igual: el plan es texto.

### Ciclo de vida (dentro de la caja)

```bash
lab up lab/examples/fuzz-evasion.yaml        # levanta y crea el snapshot "initial"
lab status                                   # estado e IPs de cada nodo
lab console www                              # consola interactiva
lab capture lab/examples/fuzz-evasion.yaml --net dmz --seconds 20
lab snapshot lab/examples/fuzz-evasion.yaml --name antes-del-ataque
lab reset lab/examples/fuzz-evasion.yaml     # vuelve a "initial" en segundos
lab check lab/exercises/06-fuzz-evasion.yaml # corrige el ejercicio
lab web lab/examples/fuzz-evasion.yaml       # consolas por navegador en :8080
lab down lab/examples/fuzz-evasion.yaml
```

`lab check` ejecuta las aserciones del ejercicio contra el laboratorio en marcha y devuelve un
informe. El alumno sabe si ha acertado sin esperar a que nadie revise una captura de pantalla:

```
06-fuzz-evasion — Descubrimiento de directorios y evasión de IDS
3/4 comprobaciones superadas

  [OK   ] evil1 obtiene 200 de http://10.20.1.10/backup/
  [OK   ] evil1:/home/user/evidencia/db.sql exists
  [FALLA] alertas del IDS con origen 10.20.0.30: 0
          7 alertas (esperado 0)
  [OK   ] la respuesta contiene 'agente de usuario'
```

### Una topología

```yaml
version: 1
name: fuzz-evasion

networks:
  ext: { cidr: 10.20.0.0/24, type: nat, mode: hub }
  dmz: { cidr: 10.20.1.0/24, type: isolated, mode: mirror }

nodes:
  - name: evil1
    toolsets: [webfuzz, sniff]
    links: [{ net: ext, ip: 10.20.0.30 }]

  - name: fw
    links: [ext, dmz]
    packages: [nftables, suricata]
    sysctls: { net.ipv4.ip_forward: 1 }

  - name: www
    links: [{ net: dmz, ip: 10.20.1.10 }]
    aliases: [www]
    packages: [apache2, php, libapache2-mod-php]
```

Un nodo con dos enlaces es un router o un pivote. Una red con `mode: hub` permite sniffing sin
trucos; con `mode: mirror` da switch realista más puerto espejo.

### Ejercicios incluidos

| Ejercicio | Laboratorio | Qué enseña |
|---|---|---|
| `01-reconocimiento` | `example.net` | Diferencia entre puerto abierto, cerrado y filtrado |
| `02-conectividad` | `example.net` | Deducir la política del cortafuegos desde los flujos |
| `06-fuzz-evasion` | `fuzz-evasion` | Descubrimiento de directorios evadiendo el IDS |

### Estructura

```
lab/examples/     topologías de ejemplo (datos, no código)
lab/exercises/    ejercicios autocorregibles
lab/images.yaml   catálogo de imágenes
lab/toolsets.yaml sets de herramientas
src/lab/          CLI, modelo, generadores y plan
src/lab/engine/   ejecución sobre Incus, snapshots, captura
src/lab/checks.py gramática y ejecución de las aserciones
src/lab/web.py    consolas por navegador (PTY + HTTP, sin dependencias)
images/box/       construcción del artefacto de VMware
docs/             análisis, diseño, formato, catálogo y guía de uso
tests/            102 pruebas (modelo, generadores, motor, ejercicios, web, caja, CLI)
```

## Licencia

GPL-3.0-or-later para el código y CC-BY-SA-4.0 para la documentación y los ejercicios.
El texto completo de las licencias se añadirá antes de la primera publicación.
