# Plan de trabajo

Estado: **v0.1.0 usable, no completo**. Esto es lo que queda, en orden de dependencia.

## Hecho (v0.1.0)

- Modelo de topología en YAML con validación y mensajes que dicen dónde está el error.
- Generación de redes, nodos, `nftables`, `dnsmasq`, `/etc/hosts`, red por nodo y telemetría.
- Ciclo de vida idempotente con snapshots y restauración.
- Captura por segmento en tres modos: switch, hub y puerto espejo.
- Ejercicios: hechos del laboratorio y respuestas estrictas con hash, puntuación e informe.
- Consolas en el navegador.
- Caja de VMware reproducible: 1,9 GiB, siete nodos en 2 GB de RAM.
- CI en GitHub: pruebas en tres versiones de Python, validación de contenido y estilo.

## Siguiente: `tynix`, entornos reproducibles (en curso)

La idea de Nix aplicada a Incus, sin Nix ni NixOS: los nodos siguen siendo Debian y el alumno ve un
Linux normal; la reproducibilidad queda debajo, en cómo se construye y se verifica el entorno.

- ✅ **Manifiesto y lock** (`src/tynix/`): base, paquetes con versión y hash, ficheros y arranque;
  hash de contenido; `tynix.lock` con detección de deriva.
- ✅ **Store**: protocolo de almacén, direccionamiento por contenido y recolección de basura con
  `lab gc`.
- ⏳ **Caché**: `push`/`pull` contra el bucket de la universidad, con verificación y firma opcional.
- ✅ **Integración con el laboratorio**: un nodo puede declarar `environment:` y `lab up` resuelve,
  construye y publica la imagen que toca; `lab lock` clava los entornos y detecta la deriva.

**Por qué primero:** la reproducibilidad de verdad es lo que permite que un mismo laboratorio dé los
mismos resultados en dos universidades, y es la base sobre la que se apoya la distribución.

## Después: distribuir laboratorios (`lab pack` / `lab pull`)

- Formato `.labpack`: topología, ejercicios, assets y manifiesto.
- Manifiesto con checksums por fichero y versión del formato.
- `lab pack` produce el paquete; `lab pull` lo instala y verifica.
- Los ejercicios viajan con hashes, nunca con las respuestas en claro.
- Firma opcional del paquete por el autor.

**Por qué después de tynix:** un paquete de laboratorio tiene que llevar el lock de sus entornos para
que quien lo reciba obtenga lo mismo; sin tynix, `labpack` solo sería un zip con buena intención.

## Después: el laboratorio de Samba AD

El escenario de intrusión real, con contenedores (sin Windows ni virtualización anidada):

- Imagen `dc` con Samba como controlador de dominio.
- Recursos SMB mal configurados (sesión anónima, permisos amplios).
- Credenciales en ficheros de usuarios (`pgadmin`, `postgres`).
- Banderas: el usuario anónimo, el ID de John Doe, la contraseña encontrada.
- Informe escrito con las preguntas de razonamiento.

**Por qué después:** necesita `lab pack` para poder distribuirse, y es el contenido que justifica el
formato.

## Más adelante

- **Salida a Internet declarada** (`--uplink`): un escenario puede pedir conexión, y el resto siguen
  aislados.
- **Grabación y reproducción de Internet** para prácticas de OSINT sin depender de la red real.
- **Herramientas por nodo** (`tools:`) sin pasar por un toolset completo.
- **Puertos concretos en las políticas** y enlaces punto a punto.
- **Plataforma web**: índice de laboratorios publicados, búsqueda y documentación de cada actividad.
  Empieza por un índice en git, no por una aplicación.

## Ideas aparcadas

- Nodos Windows (requieren virtualización anidada; el AD se cubre con Samba).
- Ejecutar el laboratorio directamente en macOS o Windows sin VM: descartado por ahora, Incus
  necesita Linux.
