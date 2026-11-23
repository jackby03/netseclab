"""Almacén de entornos: qué está, qué falta y qué sobra.

Es la parte de tynix que habla del almacén real, pero sin saber si detrás hay
Incus, un directorio o un bucket: solo pide un objeto con `names`, `exists` y
`delete`. Así la lógica se prueba sin contenedores y el laboratorio aporta el
adaptador.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .manifest import Environment

#: Prefijo de los nombres que produce tynix.
DEFAULT_PREFIX = "tynix"


@runtime_checkable
class ImageStore(Protocol):
    """Lo mínimo que tynix necesita de un almacén de imágenes."""

    def names(self) -> list[str]:
        """Nombres de las imágenes presentes."""
        ...

    def exists(self, name: str) -> bool:
        """¿Está esa imagen concreta?"""
        ...

    def delete(self, name: str) -> None:
        """Borra una imagen del almacén."""
        ...


def image_name(environment: Environment, prefix: str = DEFAULT_PREFIX) -> str:
    return environment.image_name(prefix)


def referenced(environments: list[Environment], prefix: str = DEFAULT_PREFIX) -> set[str]:
    """Nombres de imagen que los entornos dados necesitan."""
    return {image_name(entorno, prefix) for entorno in environments}


def missing(
    environments: list[Environment], store: ImageStore, prefix: str = DEFAULT_PREFIX
) -> list[Environment]:
    """Entornos cuya imagen no está en el almacén: hay que construirla o traerla."""
    return [entorno for entorno in environments if not store.exists(image_name(entorno, prefix))]


def garbage(
    available: list[str],
    keep: set[str],
    prefixes: tuple[str, ...] = (f"{DEFAULT_PREFIX}-",),
) -> list[str]:
    """Imágenes del almacén que nadie referencia.

    Solo se consideran candidatas las que llevan alguno de los prefijos: lo que
    hay en el almacén y no gestiona este proyecto no se toca.
    """
    return sorted(
        nombre for nombre in available if nombre.startswith(prefixes) and nombre not in keep
    )
