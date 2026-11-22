"""Ciclo de vida del laboratorio: levantar, parar, fotografiar y revertir.

La idempotencia es deliberada: `lab up` dos veces seguidas no debe romper nada, y volver a levantarlo
tras un fallo tiene que continuar donde se quedó.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from ..plan import Plan, Step
from .incus import Incus
from .runner import Result, Runner

# Errores que significan "ya está hecho", no "ha fallado". Incus no siempre usa el
# mismo mensaje: al relanzar un `incus launch` sobre una instancia existente lo que
# devuelve es una violación de unicidad de su base de datos.
IGNORABLES = (
    "already exists",
    "already running",
    "already defined",
    "already in use",
    "database integrity",
    "unique constraint failed",
)


@dataclass
class Outcome:
    ejecutados: int = 0
    omitidos: int = 0
    fallos: list[tuple[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.fallos

    def resumen(self) -> str:
        partes = [f"{self.ejecutados} steps run"]
        if self.omitidos:
            partes.append(f"{self.omitidos} already present")
        if self.fallos:
            partes.append(f"{len(self.fallos)} failures")
        return ", ".join(partes)


def _ignorable(resultado: Result) -> bool:
    texto = (resultado.err + resultado.out).lower()
    return any(marca in texto for marca in IGNORABLES)


def _push(step: Step, runner: Runner, carpeta: Path, contador: int) -> Result:
    """Copia un fichero generado dentro de un nodo.

    Se escribe primero en un temporal y se usa `incus file push`. El directorio
    destino se crea antes: `/etc/lab` o `/var/log/lab` pueden no existir.
    """
    padre = str(PurePosixPath(step.path).parent)
    if padre not in ("", "/"):
        runner.run(["incus", "exec", step.node or "", "--", "mkdir", "-p", padre])
    temporal = carpeta / f"push-{contador}"
    temporal.write_text(step.content, encoding="utf-8")
    return runner.run(
        [
            "incus",
            "file",
            "push",
            str(temporal),
            f"{step.node}{step.path}",
            f"--mode={step.mode}",
        ]
    )


def _carpeta_temporal() -> Path:
    """Directorio escribible para los ficheros que se van a copiar a los nodos.

    Se prueban `LAB_TMPDIR`, el temporal del sistema y el directorio actual: en
    entornos con el temporal restringido (contenedores, sandboxes) los dos
    primeros pueden no ser escribibles. No se usa `mkdtemp` porque en algunos
    sandboxes crea un directorio donde luego no se puede escribir.
    """
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
    raise RuntimeError("no writable temporary directory for `lab`")


def execute(
    plan: Plan,
    runner: Runner,
    seguir: bool = False,
    on_step=None,
) -> Outcome:
    """Ejecuta un plan: comandos y copia de ficheros."""
    resultado = Outcome()
    contador = 0
    carpeta = _carpeta_temporal()
    try:
        for step in plan.steps:
            if on_step:
                on_step(step)
            if step.kind == "push":
                contador += 1
                res = _push(step, runner, carpeta, contador)
            else:
                res = runner.run(step.exec_argv())
            if res.ok:
                resultado.ejecutados += 1
                continue
            if _ignorable(res):
                resultado.omitidos += 1
                continue
            resultado.fallos.append((step.command(), (res.err or res.out).strip()))
            if not seguir:
                break
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)
    return resultado


# --------------------------------------------------------------------------- snapshots


def take_snapshot(incus: Incus, nodos: list[str], nombre: str) -> list[str]:
    """Crea un snapshot en cada nodo. Devuelve los que no se pudieron crear."""
    fallos: list[str] = []
    for nodo in nodos:
        if incus.tiene_snapshot(nodo, nombre):
            continue
        res = incus._run("snapshot", "create", nodo, nombre)
        if not res.ok:
            fallos.append(f"{nodo}: {res.err.strip() or res.out.strip()}")
    return fallos


def restore_snapshot(
    incus: Incus,
    nodos: list[str],
    nombre: str,
    arrancar: bool = True,
) -> list[str]:
    """Restaura un snapshot en cada nodo.

    Incus no deja restaurar una instancia en marcha, así que se para antes y se arranca después:
    para el alumno, `lab reset` debe dejar el laboratorio listo, no a medias.
    """
    fallos: list[str] = []
    for nodo in nodos:
        if not incus.tiene_snapshot(nodo, nombre):
            fallos.append(f"{nodo}: snapshot {nombre!r} does not exist")
            continue
        # parar puede fallar si ya estaba parada: no es un problema
        incus._run("stop", nodo)
        res = incus._run("snapshot", "restore", nodo, nombre)
        if not res.ok:
            fallos.append(f"{nodo}: {res.err.strip() or res.out.strip()}")
            continue
        if arrancar:
            incus._run("start", nodo)
    return fallos


def lista_snapshots(incus: Incus, nodos: list[str]) -> dict[str, list[str]]:
    return {nodo: incus.snapshots(nodo) for nodo in nodos}
