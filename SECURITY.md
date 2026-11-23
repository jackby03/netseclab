# Seguridad

## Cómo reportar un problema

Si encuentras una vulnerabilidad, **no abras un issue público**. Escribe a
`jackby03@users.noreply.github.com` con:

- qué componente está afectado (el CLI, la caja, un generador, un ejercicio),
- cómo reproducirlo,
- qué impacto tiene.

Se responde en un plazo de siete días y se acuerda contigo la divulgación.

## Alcance

`netseclab` es una herramienta docente que ejecuta un laboratorio aislado en una máquina virtual.
Lo que entra en el alcance:

- **El CLI y los generadores**: inyección de comandos o de ficheros a través de una topología o de un
  ejercicio mal formado.
- **La consola web** (`lab web`): acceso sin el token cuando se configura uno.
- **La construcción de la caja**: descargas sin verificar o permisos excesivos.
- **La distribución de laboratorios** (`labpack`), cuando exista: paquetes que se ejecutan al
  instalarse.

## Lo que no entra

- **El contenido de los ejercicios**: están pensados para enseñar técnicas ofensivas dentro de un
  laboratorio aislado. Un escenario que enseña a atacar un SMB anónimo no es una vulnerabilidad del
  proyecto.
- **El aislamiento del laboratorio frente al anfitrión**: la caja es una VM y los nodos son
  contenedores dentro de ella. Romper esa frontera desde dentro del laboratorio es, en sí, un fallo
  de Incus o del kernel, no de este proyecto; pero avísanos si encuentras un camino que lo consiga.
- **Configuraciones deliberadamente débiles** de los escenarios (contraseñas vacías, servicios
  anónimos): son el material didáctico.

## Versiones soportadas

Se corrige la última versión publicada. Al ser un proyecto joven, no hay ramas de mantenimiento.
