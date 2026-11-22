# Pendientes que solo puede hacer una persona

Todo lo demás está hecho y probado. Esto es lo que necesita manos humanas, en orden de importancia.

---

## 1. Construir la caja y comprobarla de verdad

Es lo único grande que no se ha podido ejecutar: este entorno es Windows, sin Incus, sin WSL
accesible y con `bash` bloqueado. Los scripts están escritos y verificados estructuralmente, pero
**nunca se han ejecutado**.

```bash
# en un Linux x86_64 o WSL2, con qemu-system-x86_64 y ~6 GB libres
make box
```

Tarda unos 15 minutos. Descomprime `build/box/netseclab-vmware.tar.gz`, abre `netseclab.vmx` en
VMware y comprueba:

```bash
lab up /opt/netseclab/lab/examples/example.net.yaml
lab status
lab console exta          # dentro: nmap www
lab reset ...
```

**Qué mirar:** que `lab up` termine sin fallos, que las IPs coincidan con el plan, que `nmap` desde
`exta` dé 80 abierto / 443 cerrado / resto filtrado, y que `lab reset` deje el laboratorio listo.

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

## 3. Probar `lab web` con un PTY de verdad

El servidor HTTP está probado con un terminal simulado, pero **el PTY real no se ha abierto nunca**.
Hay que comprobar que `incus exec -t` se lleva bien con nuestro pseudo-terminal, el redimensionado y
los caracteres de control:

```bash
lab web /opt/netseclab/lab/examples/example.net.yaml --port 8080
```

Y decidir si se deja en `127.0.0.1` o se abre a la red con `--token`.

## 4. Medir

Los números del diseño (RAM, arranque, tamaño) son estimaciones, no medidas. Con la caja delante:

```bash
incus list
free -m
time lab up /opt/netseclab/lab/examples/example.net.yaml
```

Conviene anotarlos en `docs/02-diseno.md` §8, que ahora habla de cifras objetivo.

## 5. Decidir nombre y licencia

Está todo escrito como **netseclab**, con GPL-3.0 para el código y CC-BY-SA-4.0 para la
documentación. Cambiar el nombre es:

```bash
grep -rl netseclab --exclude-dir=.git --exclude-dir=build | xargs sed -i 's/netseclab/NOMBRE/g'
```

Además hay que comprobar que el nombre elegido no esté en uso (PyPI, GitHub, marca registrada).

## 6. Publicar

El repositorio está inicializado y con el historial hecho, pero **no tiene remoto**. Falta:

- crear el repositorio en GitHub/GitLab,
- `git remote add origin …` y `git push`,
- decidir si el CI de `.github/workflows/ci.yml` se queda tal cual (asume GitHub Actions),
- y elegir cómo se distribuye la caja: release de GitHub, Zenodo con DOI, o ambos.

## 7. Revisar el encaje institucional

Un laboratorio que lanza `nmap` y fuerza bruta tiene implicaciones que no son técnicas:

- ¿Permite la normativa de tu universidad este tipo de prácticas?
- Si el laboratorio sale a Internet (`--uplink` o una red `nat`), el tráfico de escaneo lleva la IP
  de la institución. Hoy está desactivado por defecto; conviene que siga así.
- Si se despliega en un servidor de aula compartido, `lab web` da shells: **token obligatorio** y
  red de gestión separada.

## 8. Mantener

- La versión de Debian de la caja está fijada (`DEBIAN_BUILD`). Cuando salga una nueva, hay que
  actualizarla, reconstruir y volver a pasar los ejercicios.
- Las imágenes se descargan de `images.linuxcontainers.org` en la construcción; la caja las cachea,
  pero un cambio de imagen base puede mover versiones de paquetes y cambiar resultados de `nmap`.
- Los ejercicios dependen de versiones concretas de herramientas (Suricata, ffuf, Apache). El CI
  detecta que siguen siendo válidos los ficheros, no que el comportamiento sea el mismo.

---

## Lo que **no** hace falta hacer

- No hay que tocar el modelo ni los generadores para empezar a usarlo.
- No hay que instalar nada en el portátil del alumno: solo VMware y el fichero de la caja.
- No hay que activar la virtualización anidada. Nunca.
