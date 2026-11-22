"""Errores del laboratorio, con localización precisa.

El objetivo es que un fallo en el YAML diga *qué* arreglar y *dónde*, no solo que algo va mal.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Issue:
    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.where}: {self.message}"


class LabErrors(Exception):
    """Conjunto de problemas encontrados al cargar o validar una topología."""

    def __init__(self, issues: list[Issue]):
        self.issues = list(issues)
        super().__init__(self._render())

    def _render(self) -> str:
        n = len(self.issues)
        cabecera = "1 issue" if n == 1 else f"{n} issues"
        lineas = [f"{cabecera} in the topology:"]
        lineas += [f"  - {i}" for i in self.issues]
        return "\n".join(lineas)


class Scope:
    """Acumulador de problemas para no abortar en el primer fallo."""

    def __init__(self) -> None:
        self.issues: list[Issue] = []

    def add(self, where: str, message: str) -> None:
        self.issues.append(Issue(where, message))

    def require(self, condition: bool, where: str, message: str) -> bool:
        if not condition:
            self.add(where, message)
            return False
        return True

    def raise_if_any(self) -> None:
        if self.issues:
            raise LabErrors(self.issues)
