"""Errores de tynix, independientes de los del laboratorio."""

from __future__ import annotations


class TynixError(Exception):
    """Cualquier problema de un entorno o de su lock."""


class InvalidLockError(TynixError):
    """El lock no se puede leer o no cumple el formato."""

    def __init__(self, where: str, detail: str) -> None:
        super().__init__(f"{where}: {detail}")
        self.where = where
        self.detail = detail
