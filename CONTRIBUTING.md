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

Cuidado con el YAML: un `assert: ids-alerts src=10.0.0.10, count=0` sin comillas rompe el
fichero por el `: ` de `assert:`. Escribe los parámetros con `=` y entrecomilla la línea entera si
hace falta.

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
make check                  # ruff + mypy + 190 pruebas
make cov                    # cobertura (mínimo 75 %, configurado en pyproject)
lab validate "lab/examples/*.yaml"
lab validate "lab/exercises/*.yaml"
```

El CI hace lo mismo en tres versiones de Python; si pasa en local, pasa allí.

### Qué se exige al código

- **Tipos**: `mypy` sin errores. El proyecto está anotado.
- **Estilo**: `ruff check` y `ruff format --check` sin cambios. Formatear es `make lint`.
- **Cobertura**: no bajar del 75 %.
- **Pruebas**: ninguna se borra para que pase algo. Si un cambio hace fallar una prueba, o el cambio
  está mal o la prueba estaba mal: se arregla una de las dos, no se silencia.

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

## Trabajo pendiente

Tareas abiertas del proyecto. Cada una indica el comando o el resultado que la cierra.

### 1. Reconstruir la caja con la versión actual

La caja publicada lleva el CLI de la 0.1.0. El artefacto tiene que rehacerse con el código actual y
pasar las comprobaciones dentro de la VM:

```bash
make box
WORK=build/box tools/probar-caja.sh     # la arranca en QEMU y comprueba dentro
```

`tools/probar-caja.sh` usa un overlay desechable, así que el disco que se publica queda intacto. Las
comprobaciones viven en `tools/comprobar-caja.sh`: `lab up` con siete nodos, `lab down` y otra vez
`lab up`, `nmap` desde `exta` (80 abierto, 443 cerrado, 22 filtrado), el ejercicio de reconocimiento,
captura, snapshot/reset, paquetes firmados, `lab lock`, `lab gc`, `lab push`/`lab pull` y la consola
web con y sin token.

Criterio: el guion termina con `0 fallos`. Después, las pruebas con interfaz de verdad (VMware) están
en [tools/pruebas-humanas.md](tools/pruebas-humanas.md).

### 2. Revisar los seis ejercicios con criterio docente

Leer enunciado, tareas, pistas, comprobaciones y solución de cada ejercicio y comprobar que explican
lo que se quiere explicar:

```bash
lab check lab/exercises/01-reconocimiento.yaml
lab check lab/exercises/02-conectividad.yaml
lab check lab/exercises/03-captura.yaml
lab check lab/exercises/04-pivoteo.yaml
lab check lab/exercises/05-endurecimiento.yaml
lab check lab/exercises/06-fuzz-evasion.yaml
```

Criterio: cada corrección da el resultado esperado dentro de la caja y las soluciones son correctas.
Prestar atención al 05, que exige encontrar el cortafuegos del servidor, y al 06, que depende del
umbral real de Suricata y del tiempo de espera de la captura.

### 3. Decidir la visibilidad del repositorio

Antes de abrirlo:

- revisar el README renderizado en GitHub, que es lo primero que verá quien llegue;
- decidir si la caja se publica como release de GitHub, en un bucket de la universidad o en ambos;
- si se publica en Zenodo, conectar el repositorio para que cada release tenga DOI.

Criterio: el repositorio se abre con un README correcto y una decisión escrita sobre el artefacto.

### 4. Publicar la caja

Elegir destino y dejarlo documentado en el README:

- **Release de GitHub**: un clic, pero ~1,9 GB por release y un límite de 2 GB por fichero.
- **Bucket universitario**: sin límite, pero hace falta que quien lo descargue conozca la URL.
- **Ambos**: el bucket como origen y el release como espejo.

Criterio: el artefacto se descarga desde una URL pública y la caja arranca desde ella.

### 5. Revisar el encaje institucional

Un laboratorio que lanza `nmap` y fuerza bruta tiene implicaciones que no son técnicas:

- confirmar que la normativa de la institución permite este tipo de prácticas;
- mantener la salida a Internet desactivada por defecto: el tráfico de escaneo saldría con la IP de
  la institución;
- si se despliega en un servidor de aula compartido, exigir token en `lab web` y separar la red de
  gestión.

Criterio: hay una nota escrita con las condiciones de uso aceptadas.

### 6. Mantener las versiones

- La versión de Debian de la caja está fijada en `DEBIAN_BUILD`. Al cambiarla, reconstruir la caja y
  volver a pasar los ejercicios.
- Los ejercicios dependen de versiones concretas de herramientas (Suricata, ffuf, Apache). El CI
  valida los ficheros, no el comportamiento: la comprobación real se hace en la caja.
- Cada versión lleva etiqueta, entrada en `CHANGELOG.md` y notas de release. La convención está en
  este mismo documento.

Criterio: la caja y el `CHANGELOG.md` describen la misma versión.

### 7. Cerrar los pendientes técnicos

- Atajo `lab up --uplink` (hoy la salida a Internet se declara con un segmento `type: nat`) y
  grabación/reproducción de Internet.
- Herramientas por nodo (`tools:`) con copia y ejecución controlada.
- Escenario de Samba AD para cubrir Active Directory sin nodos Windows.
- Nodos Windows: fuera del alcance actual por licencia, tamaño y virtualización anidada.
