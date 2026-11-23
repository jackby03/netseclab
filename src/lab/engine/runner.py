"""Ejecución de comandos, con una implementación real y otra grabable para las pruebas.

Toda la capa de Incus pasa por aquí, de modo que el motor se puede probar sin Incus ni root.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Result:
    code: int
    out: str = ""
    err: str = ""

    @property
    def ok(self) -> bool:
        return self.code == 0


class Runner(Protocol):
    def run(self, argv: Sequence[str], stdin: str | None = None) -> Result: ...


class SubprocessRunner:
    """Ejecuta de verdad. Es lo que se usa dentro de la caja."""

    def run(self, argv: Sequence[str], stdin: str | None = None) -> Result:
        # Sin `stdin`, el comando no hereda la entrada del proceso: `incus profile create` lee su
        # YAML de la entrada estándar cuando no es un terminal, así que un `lab up` lanzado desde un
        # script por stdin se comía el resto del script como si fuera un perfil.
        try:
            if stdin is None:
                proc = subprocess.run(
                    list(argv),
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=600,
                )
            else:
                proc = subprocess.run(
                    list(argv),
                    input=stdin,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=600,
                )
        except FileNotFoundError as exc:
            return Result(127, "", str(exc))
        except subprocess.TimeoutExpired:
            return Result(124, "", "timed out")
        return Result(proc.returncode, proc.stdout, proc.stderr)


@dataclass
class RecordingRunner:
    """No ejecuta nada: apunta los comandos y devuelve respuestas preparadas.

    Las respuestas se eligen por subcadena del comando, de la primera que coincida.
    """

    responses: dict[str, tuple[int, str, str]] = field(default_factory=dict)
    calls: list[list[str]] = field(default_factory=list)

    def run(self, argv: Sequence[str], stdin: str | None = None) -> Result:
        self.calls.append(list(argv))
        clave = " ".join(argv)
        for patron, (code, out, err) in self.responses.items():
            if patron in clave:
                return Result(code, out, err)
        return Result(0, "", "")

    # ayudas para las pruebas
    def comandos(self) -> list[str]:
        return [" ".join(c) for c in self.calls]

    def contiene(self, fragmento: str) -> bool:
        return any(fragmento in c for c in self.comandos())
