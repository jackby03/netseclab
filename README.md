# netseclab

[![ci](https://github.com/jackby03/netseclab/actions/workflows/ci.yml/badge.svg)](https://github.com/jackby03/netseclab/actions/workflows/ci.yml)
[![docs](https://github.com/jackby03/netseclab/actions/workflows/docs.yml/badge.svg)](https://jackby03.github.io/netseclab/)
[![release](https://img.shields.io/github/v/release/jackby03/netseclab)](https://github.com/jackby03/netseclab/releases)
[![licencia](https://img.shields.io/badge/licencia-GPL--3.0--or--later-blue.svg)](LICENSE)
[![python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](pyproject.toml)

Laboratorio de **seguridad en redes** para enseñar, practicar y evaluar. Se describe en YAML, se
levanta en una sola máquina virtual y se restaura en segundos.

## Qué es

Una VM —la *caja*— con Debian mínimo e [Incus](https://linuxcontainers.org/incus/) dentro. Los nodos
del laboratorio son **contenedores de sistema** que se comportan como ordenadores: `systemd`, `sshd`,
`apache`, `nftables`, `nmap` y las herramientas que haga falta para atacar y defenderse. Siete nodos
caben en 2 GB de RAM y arrancan en segundos, sin virtualización anidada.

Un laboratorio es un fichero:

```yaml
name: example.net
domain: example.net

networks:
  ext: { cidr: 10.5.0.0/24, type: isolated, mode: hub }
  dmz: { cidr: 10.5.1.0/24, type: isolated, mode: mirror }
  int: { cidr: 10.5.2.0/24, type: isolated, mode: switch }

nodes:
  - name: fw
    links: [ { net: ext, ip: 10.5.0.254 }, { net: dmz, ip: 10.5.1.254 },
             { net: int, ip: 10.5.2.254 } ]
  - name: dmza
    image: web
    links: [ { net: dmz, ip: 10.5.1.10 } ]
```

De ahí salen las redes, las IPs, las MACs, el DNS, el cortafuegos y las pruebas. `lab up` lo levanta,
`lab reset` vuelve al estado inicial y `lab check` corrige los ejercicios.

## Características

- **Declarativo.** Topologías en YAML con validación y errores que dicen dónde está el problema.
- **Reproducible.** Base Debian fijada, imágenes con checksum y entornos direccionados por contenido
  con tynix, que toma las ideas de Nix sin usar Nix.
- **Captura por segmento.** Tres modos de conmutación: *switch*, *hub* (se ve todo el tráfico) y
  *mirror* (puerto espejo sobre Open vSwitch).
- **Corrección automática.** Hechos del laboratorio comprobables y respuestas estrictas comparadas por
  hash, con puntuación y plantilla de informe.
- **Distribución.** Laboratorios empaquetados en `.labpack` con checksums, firma con OpenSSH y
  descarga por URL, más caché de imágenes para un bucket o un directorio compartido.
- **Ligero.** Unos 2,3 GB de artefacto; siete nodos en 2 GB de RAM.

## Empezar

### La caja

La forma prevista de usarlo es la VM ya construida: se descomprime, se abre en VMware y se entra con
`lab` / `netseclab`. El artefacto (`netseclab-<versión>-vmware.tar.gz`) pesa unos 2,3 GB, por encima
del límite de 2 GB de un fichero adjunto en una release de GitHub, así que se publica en el alojamiento
que indique el curso junto a su `SHA256SUMS`. Si no está disponible, se construye con `make box` en un
Linux con QEMU y KVM (o WSL2).

```bash
sha256sum -c SHA256SUMS
tar -xzf netseclab-*-vmware.tar.gz
# abrir netseclab.vmx en VMware

lab up /opt/netseclab/lab/examples/example.net.yaml
lab status
lab console exta
```

Las credenciales de los nodos son `root` / `netseclab` y `user1` / `netseclab`. Para salir de una
consola: `Ctrl-a` y luego `q`.

### Desde el repositorio

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
make check
```

`lab up` necesita estar dentro de la caja. Fuera de ella, `render` y `--dry-run` funcionan igual: el
plan es texto.

```bash
lab validate lab/examples/example.net.yaml
lab render lab/examples/example.net.yaml --format table
lab up lab/examples/example.net.yaml --dry-run
```

## Documentación

La documentación completa está en **[jackby03.github.io/netseclab](https://jackby03.github.io/netseclab/)**
y en [`docs/`](docs/index.md):

- [Empezar](docs/getting-started.md) — de cero a un laboratorio funcionando.
- [Conceptos](docs/concepts/taxonomy.md) — qué es la caja, un nodo, un escenario.
- [Guías](docs/guides/operating.md) — uso diario, ejercicios y distribución.
- [Referencia](docs/reference/topology.md) — formato de topología y comandos del CLI.
- [Diseño](docs/design/origins.md) — de dónde viene y por qué está hecho así.

## Estado

Versión **0.3.0**, usable. El plan de trabajo está en [ROADMAP.md](ROADMAP.md) y los cambios en
[CHANGELOG.md](CHANGELOG.md). Las convenciones de contribución están en [CONTRIBUTING.md](CONTRIBUTING.md).

## Origen

Nace inspirado por **[NETinVM](https://informatica.uv.es/~carlos/docencia/netinvm/)** de Carlos Pérez
(Universitat de València): un laboratorio de redes y seguridad que cabe en un ordenador. Este proyecto
no es un fork ni un reempaquetado, sino una implementación desde cero con otro enfoque: los
laboratorios son datos, la corrección es automática y los escenarios se pueden distribuir. El detalle
está en [docs/design/origins.md](docs/design/origins.md).

## Uso responsable

Este proyecto es material docente. Enseña técnicas de reconocimiento, pivoteo y evasión de IDS
**dentro de un laboratorio aislado**, y los ejercicios incluyen servicios deliberadamente débiles y
credenciales conocidas para que se puedan practicar.

- Ejecútalo solo en la caja o en un entorno que controles. No conectes los segmentos del laboratorio a
  redes ajenas: un escaneo lanzado desde el laboratorio saldría con la IP de tu institución.
- El laboratorio está aislado por defecto; si un escenario necesita Internet, se declara con un
  segmento `type: nat` y esa decisión queda escrita en la topología.
- Si encuentras un problema de seguridad **del proyecto**, no abras un issue público: sigue
  [SECURITY.md](SECURITY.md).

## Licencia

- **Código**: GPL-3.0-or-later. Texto completo en [LICENSE](LICENSE).
- **Documentación y ejercicios**: CC-BY-SA-4.0. Texto completo en
  [LICENSES/CC-BY-SA-4.0.txt](LICENSES/CC-BY-SA-4.0.txt).
