"""Telemetría: envío de logs de todos los nodos al SOC.

Se hace con `rsyslog`, que ya viene en Debian, en lugar de añadir un repositorio de terceros. El
nodo SOC escucha por TCP en el 514 y escribe un fichero por nodo y día; los demás reenvían su syslog
y, si el ejercicio lo pide, siguen además ficheros JSON como el `eve.json` de Suricata.
"""

from __future__ import annotations

from ..model import Node, Topology

PUERTO = 514

# qué ficheros sigue cada fuente declarada en `telemetry.sources`
FICHEROS = {
    "auth": ["/var/log/auth.log"],
    "syslog": ["/var/log/syslog"],
    "suricata": ["/var/log/suricata/eve.json"],
    "apache": ["/var/log/apache2/access.log", "/var/log/apache2/error.log"],
}


def _direccion_soc(topo: Topology, servidor: Node) -> str:
    enlace = servidor.links[0]
    topo.networks[enlace.net]
    return f"{enlace.ip}"


def client_config(topo: Topology, node: Node, servidor: Node) -> str:
    """Configuración del nodo que envía: reenvía todo y sigue los ficheros pedidos."""
    soc = _direccion_soc(topo, servidor)
    lineas = [
        "# Generado por netseclab: reenvío de logs al SOC.",
        'module(load="imfile")',
    ]
    for fuente in topo.telemetry.sources:
        for ruta in FICHEROS.get(fuente, []):
            lineas.append(
                f'input(type="imfile" File="{ruta}" Tag="{fuente}" '
                f'Severity="info" Facility="local5" addMetadata="on")'
            )
    lineas += [
        "",
        'if $syslogfacility-text == "local5" then {',
        f'  action(type="omfwd" target="{soc}" port="{PUERTO}" protocol="tcp"',
        '         template="RSYSLOG_SyslogProtocol23Format")',
        "  stop",
        "}",
        "",
        f"*.* @@{soc}:{PUERTO}",
        "",
    ]
    return "\n".join(lineas)


def server_config(topo: Topology) -> str:
    """Configuración del SOC: recibe y escribe un fichero por nodo y día."""
    return "\n".join(
        [
            "# Generado por netseclab: colector del SOC.",
            'module(load="imtcp")',
            f'input(type="imtcp" port="{PUERTO}" ruleset="lab")',
            "",
            'ruleset(name="lab") {',
            '  template(name="porNodo" type="string"',
            '           string="/var/log/lab/%HOSTNAME%/%$YEAR%-%$MONTH%-%$DAY%.log")',
            '  action(type="omfile" dynaFile="porNodo")',
            "}",
            "",
            f"# retención prevista: {topo.telemetry.retention}",
            "",
        ]
    )


def necesita(nodo: Node, topo: Topology) -> bool:
    return topo.telemetry.enabled and topo.telemetry.soc != nodo.name


def es_soc(nodo: Node, topo: Topology) -> bool:
    return topo.telemetry.enabled and topo.telemetry.soc == nodo.name
