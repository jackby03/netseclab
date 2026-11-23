"""Entornos del laboratorio construidos con tynix.

Un nodo puede pedir un entorno (base + paquetes) en vez de una imagen concreta.
El plan resuelve ese entorno a un nombre direccionado por contenido y, si la
imagen no está, la construye antes de arrancar el nodo.

La idea es la de Nix: el nombre de la imagen es la dirección de su contenido. Si
cambia un paquete, cambia el nombre y la imagen anterior queda intacta.
"""

from __future__ import annotations

import shlex

from tynix.lock import Lock
from tynix.manifest import Base, Environment, Package

from .catalog import resolve_image
from .model import Node, Topology
from .steps import Step

#: Prefijo de las imágenes que salen de un entorno declarado.
PREFIX = "lab-env"

#: Nombre fijo del entorno: dos nodos con la misma declaración comparten imagen.
ENV_NAME = "env"


def environment_for(node: Node, catalogo: dict[str, str]) -> Environment | None:
    """Entorno tynix declarado por el nodo, o None si usa una imagen directa."""
    declarado = node.environment
    if declarado is None:
        return None
    base = resolve_image(declarado.base, catalogo, where=f"nodes.{node.name}.environment.base")
    return Environment(
        name=ENV_NAME,
        base=Base(image=base),
        packages=tuple(Package(name=paquete) for paquete in sorted(set(declarado.packages))),
        startup=tuple(declarado.startup),
    )


def image_for(node: Node, catalogo: dict[str, str]) -> str:
    """Imagen que usará el nodo: la de su entorno o la que declaró directamente."""
    entorno = environment_for(node, catalogo)
    if entorno is None:
        return node.image
    return entorno.image_name(PREFIX)


def ensure_step(node: Node, catalogo: dict[str, str]) -> Step | None:
    """Paso idempotente que construye la imagen del entorno si no existe.

    Se ejecuta en tiempo de `up`: comprobar el almacén antes de lanzar el nodo no
    se puede hacer al generar el plan, que es texto.
    """
    entorno = environment_for(node, catalogo)
    if entorno is None:
        return None

    nombre = entorno.image_name(PREFIX)
    provisional = f"proto-{nombre}"
    paquetes = " ".join(paquete.name for paquete in entorno.packages)
    lineas = [
        f"if ! incus image info {shlex.quote(nombre)} >/dev/null 2>&1; then",
        f"  incus launch {shlex.quote(entorno.base.image)} {provisional}",
    ]
    if paquetes:
        lineas.append(
            f"  incus exec {provisional} -- sh -c "
            + shlex.quote(
                "apt-get update -qq && DEBIAN_FRONTEND=noninteractive "
                f"apt-get install -y -qq {paquetes}"
            )
        )
    for comando in entorno.startup:
        lineas.append(f"  incus exec {provisional} -- sh -c {shlex.quote(comando)}")
    lineas += [
        f"  incus stop {provisional}",
        f"  incus publish {provisional} --alias {shlex.quote(nombre)} "
        f"--properties user.tynix.manifest={shlex.quote(entorno.content_hash())}",
        f"  incus delete {provisional} --force",
        "fi",
    ]
    return Step(
        "entorno",
        argv=["sh", "-c", "\n".join(lineas)],
        note=f"environment {nombre} for node {node.name}",
    )


def lock_from(topology: Topology, catalogo: dict[str, str]) -> Lock:
    """Lock con los entornos declarados por los nodos de la topología."""
    lock = Lock()
    for node in topology.nodes:
        entorno = environment_for(node, catalogo)
        if entorno is not None:
            lock.add(entorno)
    return lock
