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

## Antes de enviar

```bash
pytest
lab validate "lab/examples/*.yaml"
lab validate "lab/exercises/*.yaml"
```

Si tu cambio toca el motor, añade la prueba con `RecordingRunner` en vez de pedirle a quien revise
que tenga Incus.
