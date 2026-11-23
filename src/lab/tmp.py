"""Directorio de trabajo temporal para lo que no debe quedarse.

Se prueban varios sitios porque el temporal del sistema no siempre es
escribible (contenedores, sandboxes). No se usa `mkdtemp` porque en algunos
entornos crea un directorio donde luego no se puede escribir.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path


def carpeta_temporal() -> Path:
    """Directorio escribible, con nombre único, para ficheros de paso."""
    candidatos = [os.environ.get("LAB_TMPDIR"), tempfile.gettempdir(), os.getcwd()]
    nombre = f"netseclab-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    for base in candidatos:
        if not base:
            continue
        carpeta = Path(base) / nombre
        try:
            carpeta.mkdir(parents=True, exist_ok=False)
            prueba = carpeta / "prueba"
            prueba.write_text("ok", encoding="utf-8")
            prueba.unlink()
            return carpeta
        except OSError:
            shutil.rmtree(carpeta, ignore_errors=True)
            continue
    raise RuntimeError("no hay un directorio temporal escribible para `lab`")
