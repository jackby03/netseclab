"""Caché de imágenes: llevar un entorno de una máquina a otra.

Cada elemento son dos ficheros: el tarball de la imagen y una entrada de
manifiesto con su `sha256`. Al traerlo se verifica, y si no coincide no se
instala: una imagen corrupta o manipulada no entra en el laboratorio.

La misma interfaz sirve para un directorio (el bucket montado, un pendrive o el
directorio compartido de la universidad) y para una URL de solo lectura.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from .errors import CacheError

INDEX = "index.json"


def digest_file(path: Path) -> str:
    """sha256 de un fichero, leído a bloques."""
    huella = hashlib.sha256()
    with path.open("rb") as fichero:
        for bloque in iter(lambda: fichero.read(1 << 20), b""):
            huella.update(bloque)
    return huella.hexdigest()


@dataclass(frozen=True)
class CachedImage:
    """Entrada de la caché: qué imagen es y con qué hash se verifica."""

    name: str
    sha256: str
    size: int = 0

    @property
    def blob(self) -> str:
        return f"{self.name}.tar.gz"

    def to_dict(self) -> dict:
        return {"name": self.name, "sha256": self.sha256, "size": self.size}

    @classmethod
    def from_dict(cls, datos: object) -> CachedImage:
        if not isinstance(datos, dict) or not datos.get("name") or not datos.get("sha256"):
            raise CacheError("cache entry needs 'name' and 'sha256'")
        return cls(
            name=str(datos["name"]),
            sha256=str(datos["sha256"]),
            size=int(datos.get("size", 0) or 0),
        )


@runtime_checkable
class Cache(Protocol):
    """Lo mínimo para traer una imagen de la caché."""

    def list(self) -> list[CachedImage]:
        """Entradas disponibles."""
        ...

    def fetch(self, image: CachedImage, dest: Path) -> Path:
        """Copia la imagen a `dest` y la verifica. Falla si no coincide."""
        ...


def verify(path: Path, image: CachedImage) -> Path:
    """Comprueba el hash de lo descargado. Es la puerta de la caché."""
    if not path.exists():
        raise CacheError(f"{path} does not exist after fetching {image.name!r}")
    real = digest_file(path)
    if real != image.sha256:
        raise CacheError(
            f"{image.name!r} does not match its checksum: expected {image.sha256}, got {real}"
        )
    return path


class FileCache:
    """Caché en un directorio: el bucket montado, un pendrive o una carpeta compartida."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _indice(self) -> list[CachedImage]:
        ruta = self.root / INDEX
        if not ruta.exists():
            return []
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise CacheError(f"cannot read {ruta}: {exc}") from exc
        entries = datos.get("images", []) if isinstance(datos, dict) else datos
        return [CachedImage.from_dict(entrada) for entrada in entries]

    def _guardar_indice(self, entradas: list[CachedImage]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        objeto = {
            "version": 1,
            "images": [e.to_dict() for e in sorted(entradas, key=lambda e: e.name)],
        }
        texto = json.dumps(objeto, indent=2, ensure_ascii=False) + "\n"
        (self.root / INDEX).write_text(texto, encoding="utf-8", newline="\n")

    def list(self) -> list[CachedImage]:
        return self._indice()

    def add(self, name: str, fichero: str | Path) -> CachedImage:
        """Publica una imagen en la caché. Devuelve su entrada."""
        origen = Path(fichero)
        if not origen.exists():
            raise CacheError(f"{origen} does not exist")
        entrada = CachedImage(name=name, sha256=digest_file(origen), size=origen.stat().st_size)
        self.root.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origen, self.root / entrada.blob)
        otras = [e for e in self._indice() if e.name != name]
        self._guardar_indice([*otras, entrada])
        return entrada

    def fetch(self, image: CachedImage, dest: Path) -> Path:
        origen = self.root / image.blob
        if not origen.exists():
            raise CacheError(f"{image.name!r} is not in the cache at {self.root}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origen, dest)
        return verify(dest, image)


class HttpCache:
    """Caché de solo lectura sobre una URL: el bucket servido por HTTP.

    Publicar es cosa del sistema de ficheros o del cliente del bucket; aquí solo
    se lee, porque un `PUT` a un bucket no siempre está permitido.
    """

    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/") + "/"

    def _url(self, nombre: str) -> str:
        return urllib.parse.urljoin(self.base, urllib.parse.quote(nombre))

    def list(self) -> list[CachedImage]:
        try:
            with urllib.request.urlopen(self._url(INDEX), timeout=15) as respuesta:  # noqa: S310
                datos = json.loads(respuesta.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
            raise CacheError(f"cannot read the index at {self._url(INDEX)}: {exc}") from exc
        entries = datos.get("images", []) if isinstance(datos, dict) else datos
        return [CachedImage.from_dict(entrada) for entrada in entries]

    def fetch(self, image: CachedImage, dest: Path) -> Path:
        url = self._url(image.blob)
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            with (
                urllib.request.urlopen(url, timeout=120) as respuesta,  # noqa: S310
                dest.open("wb") as salida,
            ):
                shutil.copyfileobj(respuesta, salida)
        except (urllib.error.URLError, OSError) as exc:
            raise CacheError(f"cannot download {url}: {exc}") from exc
        return verify(dest, image)


def open_cache(location: str | Path) -> Cache:
    """Abre la caché que corresponde a una ruta o a una URL."""
    texto = str(location)
    if texto.startswith(("http://", "https://")):
        return HttpCache(texto)
    return FileCache(texto)
