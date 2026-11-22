"""Captura de tráfico por segmento.

Depende del modo de la red:

- `mirror`: se captura en el puerto espejo que vive en el propio anfitrión (`cap-<red>`).
- `hub` / `switch`: se captura dentro de un nodo del segmento, poniendo la interfaz en promiscuo.
  En `hub` se ve todo el segmento; en `switch` solo lo del propio nodo, que es justo lo que hay que
  entender cuando se estudia sniffing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..model import Network, Topology

DESTINO_REMOTO = "/tmp/lab-capture.pcap"
DESTINO_LOCAL = "/tmp/lab-capture.pcap"


@dataclass
class CapturePlan:
    red: str
    modo: str
    comandos: list[list[str]]
    salida: Path
    nota: str = ""


def _nodo_del_segmento(topo: Topology, red: Network):
    for nodo in topo.nodes:
        enlace = nodo.link_to(red.name)
        if enlace is not None:
            return nodo, enlace
    return None, None


def plan_capture(
    topo: Topology,
    red: Network,
    segundos: int,
    salida: Path,
) -> CapturePlan:
    if red.mode == "mirror":
        puerto = f"cap-{red.name}"
        # El puerto espejo vive en el anfitrión: capturar necesita root.
        return CapturePlan(
            red=red.name,
            modo="mirror",
            comandos=[
                ["sudo", "timeout", str(segundos), "tcpdump", "-i", puerto, "-w", DESTINO_LOCAL],
                ["sudo", "cp", DESTINO_LOCAL, str(salida)],
                ["sudo", "rm", "-f", DESTINO_LOCAL],
            ],
            salida=salida,
            nota=f"capturando en el puerto espejo {puerto} durante {segundos}s",
        )

    nodo, enlace = _nodo_del_segmento(topo, red)
    if nodo is None:
        raise ValueError(f"no hay ningún nodo en la red {red.name!r}")

    return CapturePlan(
        red=red.name,
        modo=red.mode,
        comandos=[
            ["incus", "exec", nodo.name, "--", "ip", "link", "set", enlace.ifname, "promisc", "on"],
            [
                "incus",
                "exec",
                nodo.name,
                "--",
                "timeout",
                str(segundos),
                "tcpdump",
                "-i",
                enlace.ifname,
                "-w",
                DESTINO_REMOTO,
            ],
            ["incus", "file", "pull", f"{nodo.name}{DESTINO_REMOTO}", str(salida)],
        ],
        salida=salida,
        nota=f"capturando en {nodo.name}/{enlace.ifname} durante {segundos}s (modo {red.mode})",
    )


def run_capture(plan: CapturePlan, runner) -> tuple[bool, str]:
    for argv in plan.comandos:
        res = runner.run(argv)
        # tcpdump termina con 124 al agotarse el timeout: es lo esperado
        if not res.ok and res.code != 124:
            return False, (res.err or res.out).strip() or f"falló: {' '.join(argv)}"
    return True, plan.nota
