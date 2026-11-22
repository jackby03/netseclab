"""Envoltorio fino sobre `incus`.

No pretende cubrir la API: solo las consultas y acciones que necesita el motor, con nombres en el
lenguaje del laboratorio (instancia, red, snapshot).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .runner import Result, Runner

SNAPSHOT_INICIAL = "initial"


@dataclass
class Instance:
    name: str
    status: str
    type: str = "container"
    ips: list[str] = field(default_factory=list)


def _direcciones(inst: dict) -> list[str]:
    """Direcciones IPv4 globales de una instancia.

    Según la versión, `state.network` llega como lista de interfaces o como mapa
    nombre→interfaz; se aceptan las dos formas.
    """
    estado = (inst.get("state") or {}).get("network") or {}
    redes = estado.values() if isinstance(estado, dict) else estado
    salida: list[str] = []
    for red in redes:
        if not isinstance(red, dict):
            continue
        for direccion in red.get("addresses") or []:
            if not isinstance(direccion, dict):
                continue
            if direccion.get("family") == "inet" and direccion.get("scope") == "global":
                salida.append(str(direccion.get("address")))
    return salida


class Incus:
    def __init__(self, runner: Runner):
        self.runner = runner

    # ------------------------------------------------------------------ básico

    def _run(self, *args: str, stdin: str | None = None) -> Result:
        return self.runner.run(["incus", *args], stdin=stdin)

    def disponible(self) -> bool:
        return self._run("version").ok

    def red_existe(self, nombre: str) -> bool:
        return self._run("network", "show", nombre).ok

    def instancia_existe(self, nombre: str) -> bool:
        return self._run("info", nombre).ok

    def ejecutar(self, nodo: str, *argv: str) -> Result:
        return self._run("exec", nodo, "--", *argv)

    # ------------------------------------------------------------------ consultas

    def listar(self) -> list[Instance]:
        res = self._run("list", "--format", "json")
        if not res.ok:
            return []
        try:
            datos = json.loads(res.out or "[]")
        except json.JSONDecodeError:
            return []
        return [
            Instance(
                name=str(i.get("name", "")),
                status=str(i.get("status", "?")),
                type=str(i.get("type", "container")),
                ips=_direcciones(i),
            )
            for i in datos
        ]

    def snapshots(self, nodo: str) -> list[str]:
        """Nombres de los snapshots de una instancia.

        Se usa la API (`incus query`), que es estable. El listado por columnas
        (`snapshot list -c name`) no acepta nombres de columna y devuelve vacío
        sin error, que es peor que fallar. La API puede devolver las snapshots
        como objetos o como URLs (`/1.0/instances/<n>/snapshots/<nombre>`).
        """
        res = self._run("query", f"/1.0/instances/{nodo}/snapshots")
        if not res.ok:
            return []
        try:
            datos = json.loads(res.out or "[]")
        except json.JSONDecodeError:
            return []
        if not isinstance(datos, list):
            return []
        nombres: list[str] = []
        for elemento in datos:
            if isinstance(elemento, dict) and elemento.get("name"):
                nombres.append(str(elemento["name"]))
            elif isinstance(elemento, str) and elemento.strip():
                nombres.append(elemento.rstrip("/").rsplit("/", 1)[-1])
        return nombres

    def tiene_snapshot(self, nodo: str, nombre: str) -> bool:
        return nombre in self.snapshots(nodo)

    def ips(self, nodo: str) -> list[str]:
        res = self._run("list", nodo, "--format", "json")
        if not res.ok:
            return []
        try:
            datos = json.loads(res.out or "[]")
        except json.JSONDecodeError:
            return []
        salida: list[str] = []
        for inst in datos:
            salida.extend(_direcciones(inst))
        return salida
