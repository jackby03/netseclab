# Laboratorios distribuibles

> Cómo comparte un profesor un laboratorio con sus alumnos sin construir imágenes.
> Estado: **propuesta**. Hoy funcionan los laboratorios que solo usan las imágenes de la caja.

---

## 1. La idea

Un laboratorio es **texto**, no una imagen. Un fichero de topología, uno o varios ejercicios, los
ficheros del escenario y, si hace falta, algunas herramientas. Todo eso pesa kilobytes o unos pocos
megas, se versiona en git y se descarga con una orden.

La imagen de la caja se construye una vez por curso. Los laboratorios cambian cada semana y no
tocan la imagen.

---

## 2. El paquete de laboratorio (`labpack`)

**Implementado**: `lab pack` y `lab unpack`.

```
edr-intro.labpack            (tar.gz)
├── labpack.json             # manifiesto: formato, versión y sha256 de cada fichero
├── lab/examples/lab.yaml    # la topología, tal cual
├── lab/exercises/01-edr.yaml # uno o varios ejercicios
├── lab.lock                 # los entornos clavados con tynix, si existen
└── ...                      # cualquier otro fichero del escenario
```

Al abrirlo se verifica **todo** antes de escribir nada: si un byte no cuadra con el manifiesto, el
paquete no se extrae. Además se rechazan las rutas que intenten escribir fuera del destino, para que
un paquete malicioso no pueda tocar el sistema de quien lo abre.

Un detalle que da la reproducibilidad: el `.labpack` lleva el `lab.lock` de sus entornos, así que
quien lo recibe puede comprobar con `lab lock --check` que tiene exactamente lo que el autor clavó.

## 3. Órdenes

```bash
# profesor, para publicar
lab lock labs/edr-intro/lab.yaml                    # clava los entornos
lab pack labs/edr-intro/lab.yaml --out edr-intro.labpack \
  --exercise labs/edr-intro/exercises/01-edr.yaml

# alumno
lab unpack edr-intro.labpack --to labs/edr-intro     # verifica y extrae
lab up labs/edr-intro/lab.yaml
lab check labs/edr-intro/exercises/01-edr.yaml
```

`lab unpack` **verifica el sha256 de cada fichero** y no extrae nada si algo no cuadra. Nada más.

## 4. Herramientas propias

Este es el punto que hoy no está resuelto, y es el que hace falta para un EDR, un `rustscan` o
cualquier herramienta que no venga en las imágenes base.

Dos caminos, y ninguno exige construir una imagen:

### a. Herramienta dentro del paquete

Para un binario estático o un `.deb` pequeño. El nodo no necesita Internet: el fichero viaja con el
laboratorio.

```yaml
# en lab.yaml
nodes:
  - name: evil1
    image: attacker
    tools:
      - { src: tools/rustscan, dst: /usr/local/bin/rustscan, mode: "0755" }
      - { src: tools/install.sh, dst: /tmp/install.sh, run: true }
```

`lab up` copia los ficheros al nodo y ejecuta lo que haga falta. Es la misma mecánica que ya usamos
para los `assets` de un escenario; solo se añade el bit de «ejecutar».

### b. Paquete de Debian dentro del paquete

Si la herramienta está empaquetada, se incluye el `.deb` (y sus dependencias) en `tools/debs/` y el
script hace `dpkg -i`. Más pesado, pero reproducible y auditable.

### c. Receta de imagen, solo si es imprescindible

Para algo como un SIEM completo, construir una imagen tiene sentido: se hace una vez, se publica como
`lab/<nombre>:<versión>` y los laboratorios la referencian. `lab image build` ya existe para eso.
Pero es la excepción, no el camino normal.

## 5. Qué falta para que esto exista

| Pieza | Estado |
|---|---|
| Topología y ejercicios como texto versionable | **Hecho** |
| `assets` (ficheros del escenario) | **Hecho** |
| Recetas de imagen (`lab image build`) | **Hecho** |
| Comprimir/descomprimir un laboratorio (`lab pack` / `lab pull`) | Pendiente |
| Verificación de integridad al descargar | Pendiente |
| `tools:` por nodo, con copia y ejecución | Pendiente |

Son tres cosas pequeñas y bien delimitadas. Ninguna toca el modelo ni el motor.

## 6. Sobre la confianza

Un `labpack` ejecuta cosas dentro de las máquinas del alumno. Por eso:

- el paquete **no** se ejecuta en la caja, solo dentro de los nodos del laboratorio;
- `lab pull` muestra un resumen (nodos, ejercicios, herramienta que se va a ejecutar) y pide
  confirmación antes de la primera ejecución de un `tools/install.sh`;
- el SHA-256 va publicado junto al paquete, y a futuro se puede firmar.

Un laboratorio que no se puede auditar es exactamente el problema del NETinVM original: 4,7 GB
opacos. Aquí el profesor puede leer el paquete entero antes de usarlo.
