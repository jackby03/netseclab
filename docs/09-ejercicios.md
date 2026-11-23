# 9. Ejercicios: respuestas estrictas e informe

Un ejercicio tiene dos partes que se evalúan de forma distinta:

- **La máquina comprueba datos.** El alumno extrae del laboratorio un valor concreto —una IP, un
  usuario, una contraseña, un identificador— y lo entrega. Se compara exactamente.
- **La persona evalúa el razonamiento.** Las preguntas de "por qué" y "cómo" van en el informe, que
  el profesor corrige.

El texto de las preguntas es **libre**: puede estar en cualquier idioma. Lo que es estricto es la
respuesta, no el enunciado.

## Estructura

```yaml
id: 01-reconocimiento
title: Reconocimiento de servicios con nmap
lab: ../examples/example.net.yaml
profile: std
difficulty: fácil
duration: 20 min

brief: |
  Desde exta, averigua qué servicios expone www.example.net.

tasks:
  - Ejecuta un escaneo de los 1000 puertos más comunes.

hints:
  - Un puerto «closed» contesta que no hay nada escuchando.

# Hechos del escenario que se comprueban ejecutando comandos
checks:
  - assert: port-state exta -> www:80 is open
  - assert: reachable inta -> exta is true

# Valores concretos que el alumno debe extraer
answers:
  - id: puerto-cerrado
    kind: fact
    points: 5
    question: "¿Qué puerto de www aparece como «closed» desde exta?"
    hash: 6d05621ab7cb7b4fb796ca2ffbe1a141e0d4319d3deb6a05322b9de85d69b923

report:
  - "¿Por qué el 443 aparece «closed» y el resto «filtered»?"

solution: |
  fw usa reject para el 443 y drop para el resto.
```

## `checks`: hechos del laboratorio

Comprueban el **resultado** de lo que hizo el alumno, dentro del laboratorio. Sirven para prácticas
de configuración: ¿quedó el cortafuegos bien?, ¿responde el servicio?

| Forma | Significado |
|---|---|
| `reachable A -> B is true/false` | ¿hay conectividad? |
| `port-state A -> B:80 is open/closed/filtered` | estado real del puerto |
| `http-status A -> http://B/ is 200` | código HTTP |
| `file nodo /ruta exists/missing` | existencia de un fichero |
| `ids-alerts node=fw, src=10.0.0.5, count=0` | alertas del IDS |
| `capture dmz, contains="GET /admin/"` | contenido de una captura |

## `answers`: valores concretos

Cada respuesta es **un dato, no una frase**. La comparación es exacta, con una normalización mínima:
mayúsculas, espacios sobrantes y comillas no cuentan. Nada más.

| Campo | Obligatorio | Qué es |
|---|---|---|
| `id` | sí | Identificador único |
| `question` | sí | Lo que se pregunta, en el idioma que quieras |
| `points` | no | Puntos que vale (por defecto 0) |
| `kind` | no | `fact` (del escenario) o `flag` (plantado en un nodo) |
| `hash` | sí\* | sha256 del valor esperado |
| `value` | sí\* | El valor en claro. **Solo para la copia del profesor** |
| `accepts` | no | Variantes legítimas, declaradas una a una |
| `where` | no | Pista de dónde buscarlo |
| `message` | no | Texto que se muestra si falla |

\* `hash`, `value` o `accepts`: al menos uno.

### Por qué el hash y no el valor

Si la copia que recibe el alumno lleva el valor en claro, lo lee y lo copia sin hacer el laboratorio.
Con el hash, `lab check` puede verificar sin revelar nada:

```bash
lab hash "10.5.0.10"
# 57451d7709e7eddd408baabf503546ac3947d4deaa3be15cd12d6dbf3441d259
```

Cuando `lab check` detecta un `value` en claro, avisa: esa copia no está limpia para distribuir.

### Variantes

No se adivinan sinónimos. Si un dato admite dos formas legítimas, se declaran:

```yaml
answers:
  - id: ip-admin
    question: "¿Qué IP tenía en el segmento de administración?"
    points: 5
    accepts: ["10.5.0.10", "10.5.0.10/24"]
```

### Qué NO es una respuesta válida

- Una frase ("el cortafuegos usa reject").
- Un "ninguno", "no hay" o "depende": la negación tiene demasiadas formas y depende del idioma.
- Un número escrito de varias maneras ("tres", "3", "3 usuarios").
- Algo que ya está en el escenario que el alumno tiene delante, si pretendes evaluar trabajo:
  eso es un `fact` de comprensión, no una `flag`.

## `report`: el informe escrito

Preguntas abiertas que el alumno responde en un documento y el profesor corrige:

```bash
lab report 01-reconocimiento.yaml --out informe.md
```

Genera una plantilla en Markdown con las respuestas entregadas, la fecha y las preguntas, con espacio
para desarrollar. Se convierte a Word o PDF con cualquier herramienta.

## El ciclo completo

```bash
lab up ../examples/example.net.yaml          # el profesor levanta el laboratorio
lab check 01-reconocimiento.yaml             # 0/1 answers - 0/5 points
lab answer 01-reconocimiento.yaml puerto-cerrado "443"
lab check 01-reconocimiento.yaml             # 1/1 answers - 5/5 points
lab report 01-reconocimiento.yaml --out informe.md
```

## Regla de oro

Si el profesor no puede escribir la respuesta como **un solo valor**, entonces no es una respuesta
estricta: es una pregunta de informe. La máquina comprueba datos; la persona evalúa razonamiento.
