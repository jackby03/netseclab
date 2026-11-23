# Pendientes que solo puede hacer una persona

Todo lo demás está hecho y probado. Esto es lo que queda, y por qué necesita manos humanas.

---

## 1. Reconstruir la caja con la versión actual

La caja publicada lleva el CLI de la 0.1.0. El código de la 0.2.0 está en el repositorio, pero el
artefacto hay que rehacerlo:

```bash
make box                     # ~15 minutos en Linux/WSL2 con KVM
```

Y después, **dentro de la caja**, ejecutar por primera vez lo que solo se ha probado con el ejecutor
simulado:

```bash
lab pack lab/examples/example.net.yaml --out /tmp/ejemplo.labpack
lab unpack /tmp/ejemplo.labpack --to /tmp/extraido
lab lock lab/examples/example.net.yaml
lab gc lab/examples/example.net.yaml
lab push lab-node-v1 --to /tmp/bucket
lab pull lab-node-v1 --from /tmp/bucket
```

**Qué mirar:** que `lab pack` verifique y extraiga, que `lab lock` escriba el lock y `--check` diga
que está al día, y que `lab gc` no borre nada que se use.

## 2. Recorrer los seis ejercicios

Los enunciados y las soluciones los he escrito yo, sin criterio docente real. Hay que leerlos y
decidir si explican lo que quieres explicar:

```bash
lab check lab/exercises/01-reconocimiento.yaml
lab check lab/exercises/02-conectividad.yaml
lab check lab/exercises/03-captura.yaml
lab check lab/exercises/04-pivoteo.yaml
lab check lab/exercises/05-endurecimiento.yaml
lab check lab/exercises/06-fuzz-evasion.yaml
```

Sospecho de dos: el 05 (endurecimiento) da por hecho que el alumno encuentra el cortafuegos solo, y
el 06 (evasión) depende de que el umbral de Suricata sea el adecuado con el tiempo de espera real.

## 3. Decidir cuándo el repositorio es público

Hoy es privado. Antes de abrirlo:

- revisar el README renderizado en GitHub, que es lo que verá quien llegue;
- decidir si se publica la caja en el release de GitHub (1,92 GiB, cabe en el límite de 2 GiB) o solo
  en el bucket de la universidad;
- si va a Zenodo, conectar el repositorio para que cada release tenga DOI.

## 4. Publicar la caja

El artefacto no está subido. Elegir dónde:

- **Release de GitHub**: un clic, pero 1,92 GiB por release y el límite de 2 GiB por fichero.
- **Bucket universitario**: sin límite, pero hace falta que quien lo descargue sepa la URL.
- **Ambos**: el bucket como origen y el release como espejo.

## 5. Encaje institucional

Un laboratorio que lanza `nmap` y fuerza bruta tiene implicaciones que no son técnicas:

- ¿Permite la normativa de tu universidad este tipo de prácticas?
- Si un escenario sale a Internet, el tráfico de escaneo lleva la IP de la institución. Hoy está
  desactivado por defecto; conviene que siga así.
- Si se despliega en un servidor de aula compartido, `lab web` da shells: **token obligatorio** y red
  de gestión separada.

## 6. Mantener

- La versión de Debian de la caja está fijada (`DEBIAN_BUILD`). Cuando salga una nueva, hay que
  actualizarla, reconstruir y **volver a pasar los ejercicios**.
- Los ejercicios dependen de versiones concretas de herramientas (Suricata, ffuf, Apache). El CI
  detecta que los ficheros son válidos, no que el comportamiento sea el mismo.
- Cada versión: etiqueta, entrada en `CHANGELOG.md` y release con sus notas. La convención está en
  `CONTRIBUTING.md`.

---

## Lo que ya está hecho y no hace falta repetir

- **La caja se construyó y se validó** en QEMU y en VMware: siete nodos, `nmap` correcto, `lab reset`,
  `lab capture`, `lab check` 4/4, credenciales y aviso de `Ctrl-a q`.
- **Las medidas están tomadas**: 1,92 GiB el artefacto, 4,2 GB de disco con siete nodos y snapshots,
  ~1,3 GB de RAM libres con todo levantado.
- **El nombre y la licencia están decididos**: `netseclab`, GPL-3.0 para el código y CC-BY-SA-4.0 para
  documentación y ejercicios.
- **El repositorio existe y tiene CI**: privado por ahora, con siete trabajos en verde.

## Lo que **no** hace falta hacer

- No hay que tocar el modelo ni los generadores para empezar a usarlo.
- No hay que instalar nada en el portátil del alumno: solo VMware y el fichero de la caja.
- No hay que activar la virtualización anidada. Nunca.
