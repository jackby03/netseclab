"""Manifiesto de un entorno: qué lleva un nodo, clavado y verificable.

Un entorno es una terna de base, paquetes y ficheros. Su hash se calcula sobre
una serialización canónica, así que el orden en que se declaren las cosas no
cambia el resultado, pero cambiar una versión sí. Ese hash es el nombre de la
imagen: es la dirección del contenido, como en el almacén de Nix.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field


def _canonico(datos: object) -> str:
    """JSON estable: claves ordenadas y sin espacios, para que el hash no baile."""
    return json.dumps(datos, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Base:
    """Imagen base del entorno y, si se conoce, la huella de su manifiesto."""

    image: str
    fingerprint: str = ""

    def to_dict(self) -> dict:
        return {"image": self.image, "fingerprint": self.fingerprint}

    @classmethod
    def from_dict(cls, datos: object, where: str) -> Base:
        from .errors import InvalidLock

        if not isinstance(datos, dict) or not datos.get("image"):
            raise InvalidLock(where, "base needs at least 'image'")
        return cls(image=str(datos["image"]), fingerprint=str(datos.get("fingerprint", "") or ""))


@dataclass(frozen=True)
class Package:
    """Paquete Debian con su versión y, cuando existe, el hash del .deb."""

    name: str
    version: str = ""
    sha256: str = ""

    def to_dict(self) -> dict:
        return {"name": self.name, "sha256": self.sha256, "version": self.version}

    @classmethod
    def from_dict(cls, datos: object, where: str) -> Package:
        from .errors import InvalidLock

        if not isinstance(datos, dict) or not datos.get("name"):
            raise InvalidLock(where, "a package needs at least 'name'")
        return cls(
            name=str(datos["name"]),
            version=str(datos.get("version", "") or ""),
            sha256=str(datos.get("sha256", "") or ""),
        )


@dataclass(frozen=True)
class FileEntry:
    """Fichero que se inyecta en el entorno, con el hash de su contenido."""

    path: str
    sha256: str

    def to_dict(self) -> dict:
        return {"path": self.path, "sha256": self.sha256}

    @classmethod
    def from_dict(cls, datos: object, where: str) -> FileEntry:
        from .errors import InvalidLock

        if not isinstance(datos, dict) or not datos.get("path"):
            raise InvalidLock(where, "a file needs at least 'path'")
        return cls(path=str(datos["path"]), sha256=str(datos.get("sha256", "") or ""))


@dataclass(frozen=True)
class Environment:
    """Todo lo que define un nodo, clavado.

    `startup` son los comandos que se ejecutan al construir el entorno (por
    ejemplo, habilitar un servicio). No son los del arranque de cada contenedor:
    esos viven en el plan del laboratorio.
    """

    name: str
    base: Base
    packages: tuple[Package, ...] = field(default_factory=tuple)
    files: tuple[FileEntry, ...] = field(default_factory=tuple)
    startup: tuple[str, ...] = field(default_factory=tuple)

    def canonical(self) -> dict:
        """Representación estable: paquetes y ficheros ordenados por nombre."""
        return {
            "base": self.base.to_dict(),
            "files": [f.to_dict() for f in sorted(self.files, key=lambda f: f.path)],
            "name": self.name,
            "packages": [p.to_dict() for p in sorted(self.packages, key=lambda p: p.name)],
            "startup": list(self.startup),
        }

    def content_hash(self) -> str:
        """Dirección del contenido: cambia si cambia cualquier cosa del entorno."""
        return _sha256(_canonico(self.canonical()))

    def image_name(self, prefix: str = "tynix") -> str:
        """Nombre de imagen direccionado por contenido, estable entre máquinas."""
        return f"{prefix}-{self.name}-{self.content_hash()[:12]}"

    def to_dict(self) -> dict:
        return self.canonical()

    @classmethod
    def from_dict(cls, datos: object, where: str) -> Environment:
        from .errors import InvalidLock

        if not isinstance(datos, dict):
            raise InvalidLock(where, "expected a map")
        nombre = datos.get("name")
        if not nombre:
            raise InvalidLock(where, "missing 'name'")
        base = Base.from_dict(datos.get("base"), f"{where}.base")
        paquetes = datos.get("packages") or []
        if not isinstance(paquetes, list):
            raise InvalidLock(f"{where}.packages", "expected a list")
        ficheros = datos.get("files") or []
        if not isinstance(ficheros, list):
            raise InvalidLock(f"{where}.files", "expected a list")
        arranque = datos.get("startup") or []
        if not isinstance(arranque, list):
            raise InvalidLock(f"{where}.startup", "expected a list")
        return cls(
            name=str(nombre),
            base=base,
            packages=tuple(
                Package.from_dict(p, f"{where}.packages[{i}]") for i, p in enumerate(paquetes)
            ),
            files=tuple(
                FileEntry.from_dict(f, f"{where}.files[{i}]") for i, f in enumerate(ficheros)
            ),
            startup=tuple(str(c) for c in arranque),
        )
