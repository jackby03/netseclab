"""Aserciones de los ejercicios.

Un ejercicio declara comprobaciones en lenguaje natural y el motor las convierte en comandos que se
ejecutan dentro del laboratorio. Así el alumno recibe un informe inmediato en vez de esperar a que
alguien revise una captura de pantalla.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import Issue, LabErrors
from .engine.incus import Incus
from .model import Topology

PATRONES = {
    "reachable": re.compile(r"^reachable\s+(\S+)\s*->\s*(\S+)\s+is\s+(true|false)$"),
    "port-state": re.compile(
        r"^port-state\s+(\S+)\s*->\s*([^\s:]+):(\d+)\s+is\s+(open|closed|filtered)$"
    ),
    "http-status": re.compile(r"^http-status\s+(\S+)\s*->\s*(\S+)\s+is\s+(\d{3})$"),
    "file": re.compile(r"^file\s+(\S+)\s+(\S+)\s+(exists|missing)$"),
    "ids-alerts": re.compile(r"^ids-alerts\s+(.+)$"),
    "capture": re.compile(r"^capture\s+([^,\s]+)\s*(?:,\s*(.+))?$"),
    "answer": re.compile(r'^answer\s+"(.*)"\s+contains\s+"(.*)"$'),
}

# código de salida de `timeout` cuando se agota el tiempo
TIMEOUT = 124


@dataclass
class Check:
    kind: str
    params: dict[str, Any] = field(default_factory=dict)
    message: str = ""

    def describe(self) -> str:
        if self.kind == "reachable":
            return f"{self.params['from']} reaches {self.params['target']}: {self.params['expect']}"
        if self.kind == "port-state":
            return (
                f"from {self.params['from']}, {self.params['target']}:{self.params['port']} "
                f"is {self.params['expect']}"
            )
        if self.kind == "http-status":
            return f"{self.params['from']} gets {self.params['expect']} from {self.params['url']}"
        if self.kind == "file":
            return f"{self.params['node']}:{self.params['path']} {self.params['expect']}"
        if self.kind == "ids-alerts":
            return (
                f"IDS alerts from {self.params.get('src', 'any')}: "
                f"{self.params['count']}"
            )
        if self.kind == "capture":
            return f"capture of {self.params['net']} contains {self.params['contains']!r}"
        if self.kind == "answer":
            return f"answer contains {self.params['contains']!r}"
        return self.kind


def _pares(texto: str) -> dict[str, str]:
    """Parsea `clave=valor, clave=valor`.

    Se admite también `clave: valor` por comodidad, pero el estilo recomendado es `=`: los dos
    puntos dentro de un `assert:` sin comillas rompen el YAML.
    """
    salida: dict[str, str] = {}
    for trozo in texto.split(","):
        trozo = trozo.strip()
        if not trozo:
            continue
        if "=" in trozo:
            clave, _, valor = trozo.partition("=")
        elif ":" in trozo:
            clave, _, valor = trozo.partition(":")
        else:
            salida[trozo] = ""
            continue
        salida[clave.strip()] = valor.strip()
    return salida


def _rechazar_parametros(pares: dict[str, str], permitidas: set[str], tipo: str, where: str) -> None:
    """Un parámetro no admitido no debe ignorarse: sería una comprobación que miente."""
    sobran = sorted(set(pares) - permitidas)
    if sobran:
        raise LabErrors(
            [
                Issue(
                    where,
                    f"parameters not allowed in {tipo}: {', '.join(sobran)}. "
                    f"Allowed: {', '.join(sorted(permitidas))}",
                )
            ]
        )


def parse_check(raw: dict, where: str) -> Check:
    mensaje = str(raw.get("message", "") or "")
    expresion = raw.get("assert")
    if not isinstance(expresion, str):
        raise LabErrors([Issue(where, "a check needs 'assert' or a structured form")])

    texto = expresion.strip()

    m = PATRONES["reachable"].match(texto)
    if m:
        return Check(
            "reachable",
            {"from": m.group(1), "target": m.group(2), "expect": m.group(3) == "true"},
            mensaje,
        )

    m = PATRONES["port-state"].match(texto)
    if m:
        return Check(
            "port-state",
            {
                "from": m.group(1),
                "target": m.group(2),
                "port": int(m.group(3)),
                "expect": m.group(4),
            },
            mensaje,
        )

    m = PATRONES["http-status"].match(texto)
    if m:
        return Check(
            "http-status",
            {"from": m.group(1), "url": m.group(2), "expect": int(m.group(3))},
            mensaje,
        )

    m = PATRONES["file"].match(texto)
    if m:
        return Check(
            "file",
            {"node": m.group(1), "path": m.group(2), "expect": m.group(3)},
            mensaje,
        )

    m = PATRONES["ids-alerts"].match(texto)
    if m:
        pares = _pares(m.group(1))
        if "count" not in pares:
            raise LabErrors([Issue(where, "ids-alerts needs 'count'")])
        _rechazar_parametros(pares, {"node", "src", "count", "log"}, "ids-alerts", where)
        return Check(
            "ids-alerts",
            {
                "node": pares.get("node"),
                "src": pares.get("src"),
                "count": int(pares["count"]),
                "log": pares.get("log", "/var/log/suricata/eve.json"),
            },
            mensaje,
        )

    m = PATRONES["capture"].match(texto)
    if m:
        pares = _pares(m.group(2) or "")
        if "contains" not in pares:
            raise LabErrors([Issue(where, "capture needs 'contains'")])
        _rechazar_parametros(pares, {"contains", "file"}, "capture", where)
        return Check(
            "capture",
            {
                "net": m.group(1),
                "contains": pares["contains"].strip("\"'"),
                "file": pares.get("file", f"capture/{m.group(1)}.pcap"),
            },
            mensaje,
        )

    m = PATRONES["answer"].match(texto)
    if m:
        return Check("answer", {"question": m.group(1), "contains": m.group(2)}, mensaje)

    raise LabErrors(
        [
            Issue(
                where,
                f"unknown check {texto!r}. Supported forms: "
                "reachable, port-state, http-status, file, ids-alerts, capture, answer",
            )
        ]
    )


# --------------------------------------------------------------------------- ejecución


def _nodo_por_defecto_para_ids(topo: Topology) -> str | None:
    for nodo in topo.nodes:
        if "suricata" in [p.lower() for p in nodo.packages]:
            return nodo.name
    for nodo in topo.nodes:
        if "ids" in nodo.name or "ids" in nodo.image:
            return nodo.name
    return None


def _entero(texto: str) -> int:
    try:
        return int(texto.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return 0


def run_check(
    check: Check,
    incus: Incus,
    topo: Topology,
    respuesta: str = "",
) -> tuple[bool, str]:
    p = check.params

    if check.kind == "reachable":
        res = incus.ejecutar(p["from"], "ping", "-c", "1", "-W", "2", p["target"])
        alcanza = res.code == 0
        return (
            alcanza == p["expect"],
            f"reachable={alcanza} (expected {p['expect']})",
        )

    if check.kind == "port-state":
        guion = f"exec 3<>/dev/tcp/{p['target']}/{p['port']}"
        res = incus.ejecutar(p["from"], "timeout", "2", "bash", "-c", guion)
        estado = "open" if res.code == 0 else ("filtered" if res.code == TIMEOUT else "closed")
        return estado == p["expect"], f"state={estado} (expected {p['expect']})"

    if check.kind == "http-status":
        res = incus.ejecutar(
            p["from"], "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "5", p["url"]
        )
        codigo = _entero(res.out)
        return codigo == p["expect"], f"HTTP {codigo} (expected {p['expect']})"

    if check.kind == "file":
        res = incus.ejecutar(p["node"], "test", "-e", p["path"])
        existe = res.code == 0
        return existe == (p["expect"] == "exists"), f"exists={existe} (expected {p['expect']})"

    if check.kind == "ids-alerts":
        nodo = p["node"] or _nodo_por_defecto_para_ids(topo)
        if nodo is None:
            return False, "no node with IDS in the topology"
        filtro = ""
        if p["src"]:
            filtro = " | grep -c " + shlex.quote(f'"src_ip":"{p["src"]}"')
        guion = "grep " + shlex.quote('"event_type":"alert"') + " " + shlex.quote(p["log"])
        guion += " 2>/dev/null" + (filtro + "" if filtro else " | wc -l") + " || true"
        res = incus.ejecutar(nodo, "sh", "-c", guion)
        total = _entero(res.out)
        return total == p["count"], f"{total} alerts (expected {p['count']})"

    if check.kind == "capture":
        ruta = Path(p["file"])
        if not ruta.exists():
            return False, f"capture {ruta} does not exist; run `lab capture {p['net']}` first"
        res = incus.runner.run(["grep", "-a", "-q", p["contains"], str(ruta)])
        return res.ok, f"contains {p['contains']!r}: {res.ok}"

    if check.kind == "answer":
        if not respuesta.strip():
            return False, "no saved answer; use `lab answer <exercise> \"...\"`"
        contiene = p["contains"].lower() in respuesta.lower()
        return contiene, f"contains {p['contains']!r}: {contiene}"

    return False, f"unknown check type: {check.kind}"
