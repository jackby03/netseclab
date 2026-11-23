"""Lockfile de entornos: lo que está clavado y en qué ha cambiado.

Es el equivalente a `flake.lock`: un fichero generado, no escrito a mano, que
dice exactamente qué llevaba cada entorno cuando se resolvió. Comparado con el
estado actual del laboratorio, dice si algo se ha movido.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .errors import InvalidLockError
from .manifest import Environment

VERSION = 1

#: Tipos de deriva que puede haber entre un lock y el estado actual.
ADDED = "added"
REMOVED = "removed"
CHANGED = "changed"


@dataclass(frozen=True)
class Drift:
    """Una diferencia entre lo clavado y lo que hay ahora."""

    environment: str
    kind: str
    detail: str = ""

    def describe(self) -> str:
        if self.kind == ADDED:
            return f"{self.environment}: added since the lock"
        if self.kind == REMOVED:
            return f"{self.environment}: removed since the lock"
        return f"{self.environment}: changed ({self.detail})"


@dataclass
class Lock:
    """Conjunto de entornos clavados."""

    environments: dict[str, Environment] = field(default_factory=dict)
    version: int = VERSION

    def add(self, environment: Environment) -> None:
        self.environments[environment.name] = environment

    def get(self, name: str) -> Environment | None:
        return self.environments.get(name)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "environments": {
                nombre: entorno.to_dict() for nombre, entorno in sorted(self.environments.items())
            },
        }

    def to_yaml(self) -> str:
        return str(yaml.safe_dump(self.to_dict(), sort_keys=False, allow_unicode=True, width=100))

    @classmethod
    def from_dict(cls, datos: object) -> Lock:
        if not isinstance(datos, dict):
            raise InvalidLockError("lock", "expected a map")
        version = datos.get("version", VERSION)
        if not isinstance(version, int) or version > VERSION:
            raise InvalidLockError(
                "lock.version",
                f"unsupported version {version!r}; this build understands up to {VERSION}",
            )
        entornos = datos.get("environments") or {}
        if not isinstance(entornos, dict):
            raise InvalidLockError("lock.environments", "expected a map")
        lock = cls(version=version)
        for nombre, crudo in entornos.items():
            entorno = Environment.from_dict(crudo, f"environments.{nombre}")
            if entorno.name != str(nombre):
                raise InvalidLockError(
                    f"environments.{nombre}",
                    f"name {entorno.name!r} does not match its key",
                )
            lock.environments[str(nombre)] = entorno
        return lock

    @classmethod
    def from_yaml(cls, texto: str) -> Lock:
        try:
            datos = yaml.safe_load(texto) or {}
        except yaml.YAMLError as exc:
            raise InvalidLockError("lock", f"invalid YAML: {exc}") from exc
        return cls.from_dict(datos)

    def drift(self, actual: Lock) -> list[Drift]:
        """Diferencias entre lo clavado (self) y el estado de ahora (actual).

        Se compara por el hash del contenido, no campo a campo: si cambia
        cualquier cosa del entorno, ese entorno está cambiado.
        """
        salida: list[Drift] = []
        for nombre in sorted(set(self.environments) | set(actual.environments)):
            clavado = self.environments.get(nombre)
            ahora = actual.environments.get(nombre)
            if clavado is None and ahora is not None:
                salida.append(Drift(nombre, ADDED))
            elif clavado is not None and ahora is None:
                salida.append(Drift(nombre, REMOVED))
            elif (
                clavado is not None
                and ahora is not None
                and clavado.content_hash() != ahora.content_hash()
            ):
                salida.append(
                    Drift(
                        nombre,
                        CHANGED,
                        f"{clavado.content_hash()[:12]} -> {ahora.content_hash()[:12]}",
                    )
                )
        return salida


def read_lock(path: str | Path) -> Lock:
    ruta = Path(path)
    if not ruta.exists():
        raise InvalidLockError(str(ruta), "the lock does not exist")
    try:
        texto = ruta.read_text(encoding="utf-8")
    except OSError as exc:
        raise InvalidLockError(str(ruta), f"cannot read it: {exc}") from exc
    return Lock.from_yaml(texto)


def write_lock(path: str | Path, lock: Lock) -> Path:
    ruta = Path(path)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(lock.to_yaml(), encoding="utf-8", newline="\n")
    return ruta
