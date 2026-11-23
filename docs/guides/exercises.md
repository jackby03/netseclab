# Ejercicios

Esta página explica cómo se escribe, se corrige y se entrega un ejercicio autocorregible.

## Dos evaluaciones distintas

Un ejercicio tiene dos partes que se evalúan de forma diferente:

- **La máquina comprueba hechos.** El alumno extrae del laboratorio un valor concreto —una IP, un
  usuario, un puerto, un identificador— y lo entrega. Se compara exactamente.
- **La persona evalúa el razonamiento.** Las preguntas de «por qué» y «cómo» van en el informe, que
  corrige el profesor.

El texto de las preguntas es libre: puede estar en cualquier idioma. Lo estricto es la respuesta, no
el enunciado.

## Estructura de un ejercicio

```yaml
id: 01-reconocimiento
title: Reconocimiento de servicios con nmap
lab: ../examples/example.net.yaml
profile: std
initial: initial
difficulty: fácil
duration: 20 min

brief: |
  Desde exta, averigua qué servicios expone www.example.net.

tasks:
  - Ejecuta un escaneo de los 1000 puertos más comunes.
  - Repite el escaneo de todos los puertos y compara los tiempos.

hints:
  - Un puerto «closed» contesta que no hay nada escuchando; uno «filtered» no contesta nada.

checks:
  - assert: port-state exta -> www:80 is open
  - assert: port-state exta -> www:443 is closed
  - assert: port-state exta -> www:22 is filtered

answers:
  - id: puerto-cerrado
    kind: fact
    points: 5
    question: "¿Qué puerto de www aparece como «closed» desde exta?"
    hash: 6d05621ab7cb7b4fb796ca2ffbe1a141e0d4319d3deb6a05322b9de85d69b923

report:
  - "¿Por qué el 443 aparece «closed» y el resto «filtered»?"

solution: |
  fw acepta el 80, rechaza con RST el 443 y descarta el resto.
```

| Campo | Obligatorio | Qué es |
|---|---|---|
| `id` | sí | Identificador único del ejercicio. |
| `title` | no | Título legible; por defecto, el `id`. |
| `lab` | sí | Ruta al escenario, relativa al fichero del ejercicio. |
| `profile` | no | Perfil recomendado para levantar el escenario. |
| `initial` | no | Snapshot de partida; por defecto `initial`. |
| `difficulty` | no | Texto libre para el enunciado. |
| `duration` | no | Texto libre para el enunciado. |
| `brief` | no | Enunciado. |
| `tasks` | no | Lista de tareas concretas. |
| `hints` | no | Lista de pistas que ayudan sin resolver. |
| `checks` | no\* | Comprobaciones que ejecuta la máquina. |
| `answers` | no\* | Valores concretos que entrega el alumno. |
| `report` | no | Preguntas abiertas del informe escrito. |
| `solution` | no | Solución para el profesor. |

\* Hace falta al menos una comprobación o una respuesta. `profile` e `initial` son metadatos: `lab
check` no levanta el laboratorio ni restaura snapshots por su cuenta; el alumno debe haberlo
preparado con `lab up` y `lab reset`.

`lab validate` reconoce el fichero como ejercicio cuando contiene a la vez `checks` y `lab`. Un
ejercicio que solo tenga `answers` se valida con `lab check`, o con un `checks: []` explícito.

## Comprobaciones: hechos del laboratorio

Cada comprobación es una línea `assert:` y, opcionalmente, un `message:` que se muestra si falla.

| Forma | Comprueba |
|---|---|
| `reachable <nodo> -> <destino> is true\|false` | Alcanzabilidad con `ping`. |
| `port-state <nodo> -> <host>:<puerto> is open\|closed\|filtered` | Estado real del puerto con una sonda TCP. |
| `http-status <nodo> -> <url> is <código>` | Código HTTP con `curl`. |
| `file <nodo> <ruta> exists\|missing` | Existencia de un fichero en el nodo. |
| `ids-alerts node=<nodo>, src=<ip>, count=<n>[, log=<ruta>]` | Alertas del IDS en su log. |
| `capture <red>, contains="<texto>"[, file=<ruta>]` | Contenido del pcap de un segmento. |

Detalles que cambian el resultado de una comprobación:

- `port-state` ejecuta una conexión TCP con un tiempo límite de dos segundos: `open` si conecta,
  `closed` si la conexión se rechaza y `filtered` si se agota el tiempo.
- `ids-alerts` exige `count`; `node` es opcional y, si falta, se usa el nodo con `suricata` en
  `packages` o el primero cuyo nombre o imagen contenga `ids`. El log por defecto es
  `/var/log/suricata/eve.json` y se cuentan las líneas de tipo `alert`.
- `capture` busca el texto en el pcap con `grep -a`, en el equipo donde se ejecuta `lab check`. El
  fichero por defecto es `capture/<red>.pcap`.

Usar `=` en los parámetros. Un `assert: ids-alerts since: last` sin comillas rompe el YAML porque los
dos puntos parecen un mapa; con `since=last` no hay ambigüedad. El analizador acepta `:` por
comodidad, pero el estilo recomendado es `=`. Los parámetros no admitidos son un error y no se
ignoran: una comprobación no puede dar un resultado falso.

Las comprobaciones `fw-counters` y las ventanas temporales como `since` **no están implementadas**.
Para comprobar contadores, usar una comprobación `file` sobre un fichero que el propio escenario
genere, o mover la comprobación al informe.

## Respuestas: valores concretos

Cada respuesta es **un dato, no una frase**. La comparación es exacta, con una normalización mínima:
se quitan espacios sobrantes y comillas en los extremos, se colapsan los espacios y no se distinguen
mayúsculas. Las tildes sí cuentan: una contraseña con tilde es otra contraseña.

| Campo | Obligatorio | Qué es |
|---|---|---|
| `id` | sí | Identificador único dentro del ejercicio. |
| `question` | sí | Lo que se pregunta, en el idioma que se quiera. |
| `points` | no | Puntos que vale; por defecto 0. |
| `kind` | no | `fact` (dato del escenario) o `flag` (plantado en un nodo). |
| `hash` | sí\* | `sha256` del valor esperado, calculado con `lab hash`. |
| `value` | sí\* | El valor en claro; solo para la copia del profesor. |
| `accepts` | no | Variantes legítimas, declaradas una a una. |
| `where` | no | Pista de dónde buscar que se muestra si falla. |
| `message` | no | Texto que se muestra si falla. |

\* Hace falta al menos uno de `hash`, `value` o `accepts`. También se admite una lista de hashes.

### Por qué se publica el hash y no el valor

Si la copia que recibe el alumno lleva el valor en claro, se lee y se copia sin hacer el laboratorio.
Con el hash, `lab check` puede verificar sin revelar el valor:

```bash
lab hash "10.5.0.10"
# 57451d7709e7eddd408baabf503546ac3947d4deaa3be15cd12d6dbf3441d259
```

Cuando `lab check` detecta un `value` en claro, avisa de que esa copia no está limpia para
distribuir. El hash no cifra: un valor de baja entropía se puede adivinar. Para banderas conviene
usar valores largos o aleatorios.

### Variantes

No se adivinan sinónimos. Si un dato admite dos formas legítimas, se declaran:

```yaml
answers:
  - id: ip-admin
    question: "¿Qué IP tenía en el segmento de administración?"
    points: 5
    accepts: ["10.5.0.10", "10.5.0.10/24"]
```

### Qué no es una respuesta válida

- Una frase: «el cortafuegos usa reject».
- Una negación: «ninguno», «no hay», «depende».
- Un número escrito de varias maneras: «tres», «3», «3 usuarios».
- Algo que ya está en el escenario que el alumno tiene delante y no demuestra trabajo: eso es un
  `fact` de comprensión, no una `flag` que haya que encontrar.

## Informe escrito

`report` es una lista de preguntas abiertas que el alumno responde en un documento y el profesor
corrige. `lab report` genera una plantilla en Markdown con el título, la fecha, el alumno, las
respuestas entregadas y espacio para desarrollar cada pregunta:

```bash
lab report lab/exercises/01-reconocimiento.yaml --out informe.md
```

Sin `--out`, la plantilla se imprime en el terminal. Se puede convertir a Word o PDF con cualquier
herramienta.

## Corregir y entregar

El ciclo completo dentro de la caja:

```bash
lab up lab/examples/example.net.yaml --profile std
lab check lab/exercises/01-reconocimiento.yaml       # 0/1 answers correct - 0/5 points
lab answer lab/exercises/01-reconocimiento.yaml puerto-cerrado "443"
lab check lab/exercises/01-reconocimiento.yaml       # 1/1 answers correct - 5/5 points
lab report lab/exercises/01-reconocimiento.yaml --out informe.md
```

`lab answer` guarda el valor en `answers/<ejercicio>.json`, dentro del directorio de trabajo. Ese
directorio no se versiona.

La salida de `lab check` separa las respuestas de las comprobaciones:

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
```

Códigos de salida de `lab check`: `0` si todo está correcto, `1` si algo falla, `2` si el ejercicio
no es válido y `3` si hay comprobaciones de laboratorio pero no hay Incus.

## Regla de oro

Si el profesor no puede escribir la respuesta como **un solo valor**, entonces no es una respuesta
estricta: es una pregunta de informe. La máquina comprueba datos; la persona evalúa razonamiento.
