# Cómo contribuir

Gracias por asomarte. Este proyecto es pequeño a propósito: se entiende en una tarde.

## Preparar el entorno

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
```

No hace falta Incus ni Linux para trabajar en el modelo, los generadores, los ejercicios o el CLI:
todo eso se prueba con un ejecutor simulado. Lo que sí necesita Linux es arrancar el laboratorio de
verdad y construir la caja.

## Las cuatro cosas que se pueden añadir

### 1. Un laboratorio

Un fichero en `lab/examples/`. Antes de proponerlo:

```bash
lab validate lab/examples/mi-lab.yaml
lab render lab/examples/mi-lab.yaml --format table
lab up lab/examples/mi-lab.yaml --dry-run
```

Reglas de la casa:

- **Nada de imágenes que no existan.** O `debian13` con `packages:`/`toolsets:`, o una receta en
  `images/recipes/` que se construya con `lab image build`.
- **IPs explícitas solo donde importen.** El resto, que las reparta el motor.
- **Las redes se declaran pensando en la práctica**: `mode: hub` si la práctica es de sniffing,
  `mirror` si hace falta puerto espejo.

### 2. Un ejercicio

Un fichero en `lab/exercises/`. Tiene que traer:

- `brief` que explique el objetivo sin decir la respuesta.
- `tasks` concretas.
- `hints` que ayuden sin resolver.
- `checks` que se puedan ejecutar de verdad.
- `solution` para el profesor.

```bash
lab validate lab/exercises/mi-ejercicio.yaml
```

Cuidado con el YAML: un `assert: ids-alerts since: last` sin comillas rompe el fichero. Usa `=`
en los parámetros (`since=last`) o entrecomilla la línea entera.

### 3. Una receta de imagen

Un fichero en `images/recipes/`. Comprueba el plan antes de nada:

```bash
lab image build images/recipes/mi-imagen.yaml --dry-run
```

### 4. Un toolset

Una entrada en `lab/toolsets.yaml`: un nombre y una lista de paquetes de Debian. Pequeño y con un
propósito. Si son más de veinte paquetes, probablemente son dos toolsets.

## Estilo

- Español en la documentación y en los ejercicios; inglés en el código y en los mensajes del CLI.
- Nada de dependencias nuevas sin una razón muy buena: hoy son `PyYAML` y nada más.
- Los errores se acumulan y dicen **dónde** y **qué arreglar**; no se aborta en el primer fallo.
- Un fallo silencioso es un fallo: si una opción no se puede aplicar, es un error, no un aviso.

## Flujo de trabajo

Aunque el proyecto lo lleve una sola persona, se trabaja como si fueran varias: es lo que deja un
rastro legible de por qué cada cosa está como está.

### Ramas

- `main` siempre en verde. Nada se sube directo si rompe pruebas.
- Cada cambio, en su rama: `feat/labpack`, `fix/pool-btrfs`, `docs/readme-origen`.
- Se integra con *squash* si la rama acumuló commits de prueba; si no, con merge normal.

### Commits

Formato `tipo(alcance): descripción en imperativo`, con el cuerpo explicando **por qué**, no qué.

| Tipo | Cuándo |
|---|---|
| `feat` | Funcionalidad nueva para quien usa el laboratorio |
| `fix` | Arreglo de un comportamiento incorrecto |
| `docs` | Documentación, guía, ejercicios |
| `test` | Pruebas que faltaban o estaban mal |
| `ci` | Flujo de integración |
| `refactor` | Cambio interno sin cambiar comportamiento |
| `chore` | Versiones, dependencias, limpieza |

Ejemplos reales del proyecto:

```
caja: los nodos usan el pool copy-on-write
engine: la fase de ficheros no se ejecutaba nunca
ejercicios: respuestas estrictas con hash e informe
```

Un commit, una idea. Si el mensaje necesita un "y", probablemente son dos commits.

### Versiones

Versionado semántico: `MAYOR.MENOR.PARCHE`.

- `PARCHE`: arreglos compatibles.
- `MENOR`: funcionalidad nueva compatible.
- `MAYOR`: cambios que rompen el formato de topología, de ejercicio o el CLI.

Cada versión lleva su etiqueta (`v0.1.0`) y su entrada en [CHANGELOG.md](CHANGELOG.md), con las
secciones de *Añadido*, *Cambiado*, *Corregido* y *Limitaciones conocidas*. La nota de la release en
GitHub sale de ahí.

### Antes de integrar

```bash
pytest                      # 175 pruebas
ruff check src tests        # estilo
lab validate "lab/examples/*.yaml"
lab validate "lab/exercises/*.yaml"
```

El CI hace lo mismo en tres versiones de Python; si pasa en local, pasa allí.

### Qué no se versiona

`build/`, `answers/` y `capture/` no viajan: son artefactos de una máquina, no del proyecto. El
`.gitignore` ya los cubre.

## Antes de enviar

```bash
pytest
lab validate "lab/examples/*.yaml"
lab validate "lab/exercises/*.yaml"
```

Si tu cambio toca el motor, añade la prueba con `RecordingRunner` en vez de pedirle a quien revise
que tenga Incus.
