"""Ciclo de vida del laboratorio: levantar, parar, fotografiar y revertir.

La idempotencia es deliberada: `lab up` dos veces seguidas no debe romper nada, y volver a levantarlo
tras un fallo tiene que continuar donde se quedó.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..plan import Plan, Step
from .incus import Incus
from .runner import Result, Runner

# Errores que significan "ya está hecho", no "ha fallado"
IGNORABLES = (
    "already exists",
    "already running",
    "already defined",
    "database integrity",
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
        partes = [f"{self.ejecutados} pasos ejecutados"]
        if self.omitidos:
            partes.append(f"{self.omitidos} ya estaban")
        if self.fallos:
            partes.append(f"{len(self.fallos)} fallos")
        return ", ".join(partes)


def _ignorable(resultado: Result) -> bool:
    texto = (resultado.err + resultado.out).lower()
    return any(marca in texto for marca in IGNORABLES)


def execute(
    plan: Plan,
    runner: Runner,
    seguir: bool = False,
    on_step=None,
) -> Outcome:
    """Ejecuta un plan. Los `push` (ficheros) los resuelve el CLI antes de llamar aquí."""
    resultado = Outcome()
    for step in plan.steps:
        if step.kind == "push":
            continue
        if on_step:
            on_step(step)
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
            fallos.append(f"{nodo}: no existe el snapshot {nombre!r}")
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
