"""Paquetes de laboratorio (`.labpack`): topología, ejercicios y lock en un fichero.

El objetivo es que un profesor pueda compartir un laboratorio sin mandar una
carpeta con instrucciones: un fichero de kilobytes que se verifica al abrirlo.

El paquete es un `tar.gz` con un `labpack.json` que lista cada fichero con su
`sha256`. Al abrirlo se comprueba todo antes de escribir nada: si un byte no
cuadra, no se extrae. Las rutas se validan para que un paquete malicioso no
pueda escribir fuera del destino.
"""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .errors import Issue, LabErrors

FORMAT = "labpack"
VERSION = 1
MANIFEST = "labpack.json"


def _sha256(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


@dataclass(frozen=True)
class PackedFile:
    path: str
    sha256: str
    size: int

    def to_dict(self) -> dict:
        return {"path": self.path, "sha256": self.sha256, "size": self.size}


def pack(
    files: list[Path],
    out: Path,
    *,
    name: str,
    root: Path | None = None,
) -> Path:
    """Crea el `.labpack` con los ficheros dados, relativos a `root`."""
    base = (root or Path.cwd()).resolve()
    entradas: list[PackedFile] = []
    contenidos: dict[str, bytes] = {}

    for ruta in files:
        absoluta = ruta if ruta.is_absolute() else Path.cwd() / ruta
        if not absoluta.is_file():
            raise LabErrors([Issue(str(ruta), "file does not exist")])
        relativa = absoluta.resolve().relative_to(base)
        datos = absoluta.read_bytes()
        clave = relativa.as_posix()
        entradas.append(PackedFile(path=clave, sha256=_sha256(datos), size=len(datos)))
        contenidos[clave] = datos

    listado = [entrada.to_dict() for entrada in sorted(entradas, key=lambda e: e.path)]
    manifiesto = {
        "format": FORMAT,
        "version": VERSION,
        "name": name,
        "created": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files": listado,
    }
    datos_manifiesto = (json.dumps(manifiesto, indent=2, ensure_ascii=False) + "\n").encode("utf-8")

    out.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(out, "w:gz") as tar:
        _agregar(tar, MANIFEST, datos_manifiesto)
        for entrada in listado:
            _agregar(tar, str(entrada["path"]), contenidos[str(entrada["path"])])
    return out


def _agregar(tar: tarfile.TarFile, nombre: str, datos: bytes) -> None:
    info = tarfile.TarInfo(nombre)
    info.size = len(datos)
    info.mtime = 0
    tar.addfile(info, io.BytesIO(datos))


def read_manifest(labpack: Path) -> dict:
    """Lee y valida el manifiesto del paquete, sin extraer nada."""
    try:
        with tarfile.open(labpack, "r:gz") as tar:
            miembro = tar.extractfile(MANIFEST)
            if miembro is None:
                raise LabErrors([Issue(str(labpack), f"missing {MANIFEST}")])
            datos = json.loads(miembro.read().decode("utf-8"))
    except tarfile.TarError as exc:
        raise LabErrors([Issue(str(labpack), f"not a valid labpack: {exc}")]) from exc
    except json.JSONDecodeError as exc:
        raise LabErrors([Issue(str(labpack), f"invalid {MANIFEST}: {exc}")]) from exc

    if not isinstance(datos, dict) or datos.get("format") != FORMAT:
        raise LabErrors([Issue(str(labpack), "not a labpack (wrong format)")])
    version = datos.get("version")
    if not isinstance(version, int) or version > VERSION:
        raise LabErrors(
            [Issue(str(labpack), f"unsupported labpack version {version!r}; up to {VERSION}")]
        )
    return datos


def verify(labpack: Path) -> list[PackedFile]:
    """Comprueba el paquete entero sin escribir nada. Devuelve sus ficheros."""
    manifiesto = read_manifest(labpack)
    crudos = manifiesto.get("files") or []
    if not isinstance(crudos, list):
        raise LabErrors([Issue(str(labpack), "'files' must be a list")])
    esperados = {
        str(entrada.get("path", "")): str(entrada.get("sha256", ""))
        for entrada in crudos
        if isinstance(entrada, dict)
    }
    if not esperados:
        raise LabErrors([Issue(str(labpack), "the labpack has no files")])

    problemas: list[Issue] = []
    encontrados: set[str] = set()
    with tarfile.open(labpack, "r:gz") as tar:
        for miembro in tar.getmembers():
            if not miembro.isfile() or miembro.name == MANIFEST:
                continue
            encontrados.add(miembro.name)
            fichero = tar.extractfile(miembro)
            if fichero is None:
                problemas.append(Issue(miembro.name, "cannot be read"))
                continue
            real = _sha256(fichero.read())
            if miembro.name not in esperados:
                problemas.append(Issue(miembro.name, "not listed in the manifest"))
            elif real != esperados[miembro.name]:
                problemas.append(
                    Issue(
                        miembro.name, f"checksum mismatch (expected {esperados[miembro.name][:12]})"
                    )
                )
    for nombre in sorted(set(esperados) - encontrados):
        problemas.append(Issue(nombre, "listed in the manifest but missing"))
    if problemas:
        raise LabErrors(problemas)
    return [
        PackedFile(path=nombre, sha256=hash, size=0) for nombre, hash in sorted(esperados.items())
    ]


def unpack(labpack: Path, dest: Path) -> list[Path]:
    """Verifica el paquete y lo extrae dentro de `dest`, sin salirse de él."""
    verify(labpack)
    destino = dest.resolve()
    destino.mkdir(parents=True, exist_ok=True)
    extraidos: list[Path] = []
    with tarfile.open(labpack, "r:gz") as tar:
        for miembro in tar.getmembers():
            if not miembro.isfile() or miembro.name == MANIFEST:
                continue
            salida = (destino / miembro.name).resolve()
            if not salida.is_relative_to(destino):
                raise LabErrors([Issue(miembro.name, "refuses to write outside the destination")])
            salida.parent.mkdir(parents=True, exist_ok=True)
            fichero = tar.extractfile(miembro)
            if fichero is None:
                continue
            salida.write_bytes(fichero.read())
            extraidos.append(salida)
    return extraidos
