# Netsec Laboratory (`netseclab`)

Laboratorio de **seguridad en redes** para enseñar, practicar y evaluar. Ligero, declarativo y
reproducible.

Una VM (la «caja») con Debian mínimo y [Incus](https://linuxcontainers.org/incus/) dentro. Los nodos
del laboratorio son **contenedores de sistema** con `systemd`, `sshd`, `apache`, `nftables`, `nmap`,
`tcpdump` y las herramientas que hagan falta para atacar y defenderse: se comportan como ordenadores,
arrancan en segundos y caben siete en 2 GB de RAM.

- Se describe en un **YAML** y de ahí salen redes, IPs, MACs, DNS, cortafuegos y pruebas.
- `lab reset` devuelve el laboratorio al estado inicial en segundos.
- Los ejercicios **se corrigen solos**: valores concretos comparados por hash, más un informe escrito
  que corrige el profesor.

## Origen

`netseclab` nace inspirado por **[NETinVM](https://informatica.uv.es/~carlos/docencia/netinvm/)** de
Carlos Pérez, de la Universitat de València: la idea de un laboratorio de redes y seguridad que cabe
en un ordenador y se puede levantar en clase.

Este proyecto **no es un fork ni un reempaquetado**: está escrito desde cero con una visión más
completa —los laboratorios son datos, las prácticas se corrigen solas, los escenarios se pueden
distribuir— y con decisiones técnicas distintas para que sea ligero y reproducible en cualquier
portátil. El análisis del original y lo que se ha querido conservar está en
[docs/00-analisis-netinvm.md](docs/00-analisis-netinvm.md), y el diseño en
[docs/02-diseno.md](docs/02-diseno.md).

## Estado

**v0.1.0 — usable, no completo.** Funciona de punta a punta y está validado dentro de la caja: se
levanta un escenario de siete nodos, se comprueba, se responde, se corrige y se vuelve atrás.

- ✅ Modelo de topología, generación, ciclo de vida, snapshots, captura por segmento, telemetría.
- ✅ Ejercicios con respuestas estrictas, puntuación e informe.
- ✅ Caja de VMware: 1,9 GiB, Debian fijado, imágenes de nodo con las herramientas.
- ✅ **175 pruebas** y CI en GitHub.
- ⏳ `lab pack` / `lab pull` (distribuir laboratorios), laboratorio de Samba AD, salida a Internet
  declarada.

El plan está en [ROADMAP.md](ROADMAP.md) y los cambios en [CHANGELOG.md](CHANGELOG.md).

## La caja

La forma prevista de usarlo es la VM ya construida: se descomprime, se abre en VMware y se entra con
`lab` / `netseclab`.

```bash
tar -xzf netseclab-vmware.tar.gz
# abrir netseclab.vmx en VMware
```

Dentro:

```bash
lab up /opt/netseclab/lab/examples/example.net.yaml   # siete nodos, ~1,5 minutos
lab status
lab console exta
```

Credenciales de los nodos: `root` / `netseclab` y `user1` / `netseclab`. Para salir de una consola:
`Ctrl-a` y luego `q`.

## Uso desde el repositorio

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
```

`lab up` de verdad requiere estar **dentro de la caja** (la VM con Incus). En cualquier otro sitio,
`render` y `--dry-run` funcionan igual: el plan es texto.

```bash
lab validate lab/examples/example.net.yaml
lab render lab/examples/example.net.yaml --format table
lab render lab/examples/fuzz-evasion.yaml --format shell   # el plan completo, en shell
```

### Ciclo de vida (dentro de la caja)

```bash
lab up lab/examples/fuzz-evasion.yaml        # levanta y crea el snapshot "initial"
lab status                                   # estado e IPs de cada nodo
lab console www                              # consola interactiva
lab capture lab/examples/fuzz-evasion.yaml --net dmz --seconds 20
lab snapshot lab/examples/fuzz-evasion.yaml --name antes-del-ataque
lab reset lab/examples/fuzz-evasion.yaml     # vuelve a "initial" en segundos
lab check lab/exercises/06-fuzz-evasion.yaml
lab gc lab/examples/example.net.yaml --yes   # borra imágenes que nadie usa
lab push lab-node-v1 --to /mnt/bucket        # publica una imagen en la caché
lab pull lab-node-v1 --from https://bucket.universidad.edu/tynix
lab web lab/examples/fuzz-evasion.yaml       # consolas por navegador en :8080
```

### Ejercicios

Un ejercicio tiene dos partes: lo que **comprueba la máquina** y lo que **evalúa la persona**.

```yaml
# Un valor concreto que el alumno tiene que extraer. Se guarda el hash, no el valor.
answers:
  - id: usuario-anonimo
    kind: flag
    points: 10
    question: "¿Qué usuario del servicio permite acceso sin contraseña?"
    where: "mira los recursos compartidos"
    hash: 7d793037a0760186574b0282f2f435e7...

# Preguntas abiertas para el informe escrito, que corrige el profesor
report:
  - "¿Cómo descubriste el recurso compartido?"
```

```bash
lab check lab/exercises/01-reconocimiento.yaml      # 0/1 answers - 0/5 points
lab answer lab/exercises/01-reconocimiento.yaml puerto-cerrado "443"
lab check lab/exercises/01-reconocimiento.yaml      # 1/1 answers - 5/5 points
lab report lab/exercises/01-reconocimiento.yaml --out informe.md
```

Las comprobaciones también pueden verificar hechos del laboratorio: `port-state`, `reachable`,
`http-status`, `file`, `ids-alerts` y `capture`. El formato completo está en
[docs/09-ejercicios.md](docs/09-ejercicios.md).

### Ejercicios incluidos

| Ejercicio | Laboratorio | Qué enseña |
|---|---|---|
| `01-reconocimiento` | `example.net` | Puerto abierto, cerrado y filtrado |
| `02-conectividad` | `example.net` | Deducir la política del cortafuegos desde los flujos |
| `03-captura` | `example.net` | Sniffing: por qué un hub se ve y un switch no |
| `04-pivoteo` | `pivot` | Movimiento lateral a una red sin ruta directa |
| `05-endurecimiento` | `example.net` | Cerrar la superficie de un servidor expuesto |
| `06-fuzz-evasion` | `fuzz-evasion` | Descubrimiento de directorios evadiendo el IDS |

## Estructura

```
lab/examples/     topologías de ejemplo (datos, no código)
lab/exercises/    ejercicios
lab/images.yaml   catálogo de imágenes
lab/toolsets.yaml conjuntos de herramientas
src/lab/          CLI, modelo, generadores y plan
src/lab/engine/   ejecución sobre Incus, snapshots, captura
src/lab/checks.py hechos del laboratorio que se comprueban solos
src/lab/answers.py respuestas estrictas comparadas por hash
src/lab/web.py    consolas por navegador (PTY + HTTP, sin dependencias)
images/box/       construcción de la caja de VMware
images/recipes/   recetas de imágenes propias
docs/             análisis, diseño, formato, guía, ejercicios y límites
tests/            175 pruebas
```

## Contribuir

Convenciones de commits, ramas y versiones en [CONTRIBUTING.md](CONTRIBUTING.md). Los cambios se
documentan en [CHANGELOG.md](CHANGELOG.md) con cada versión.

## Licencia

- **Código**: GPL-3.0-or-later. El texto completo está en [LICENSE](LICENSE).
- **Documentación y ejercicios**: CC-BY-SA-4.0. El texto completo está en
  [LICENSES/CC-BY-SA-4.0.txt](LICENSES/CC-BY-SA-4.0.txt).

Se puede usar, copiar, modificar y redistribuir; si se distribuye una versión modificada, tiene que
seguir siendo libre.
