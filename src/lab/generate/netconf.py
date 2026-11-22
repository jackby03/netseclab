"""Configuración de red dentro de un nodo.

Cada nodo recibe un script idempotente y una unidad systemd que lo ejecuta en cada arranque. Es el
equivalente a lo que hacía `configure.sh` en la versión UML de NETinVM, pero generado desde la
topología en lugar de escrito a mano.
"""

from __future__ import annotations

from ..model import Node, Topology

NET_SCRIPT = "/usr/local/sbin/lab-net"
STARTUP_SCRIPT = "/usr/local/sbin/lab-startup"


def net_script(topo: Topology, node: Node) -> str:
    lineas = [
        "#!/bin/sh",
        "# Generado por netseclab. No editar: cambia la topología y vuelve a arrancar.",
        "set -eu",
        "",
    ]
    for link in node.links:
        net = topo.networks[link.net]
        lineas += [
            f"# {link.ifname} -> red {net.name} ({net.cidr})",
            f"ip link set {link.ifname} up",
            f"ip addr flush dev {link.ifname}",
        ]
        if net.addressing == "dhcp" and not link.explicit_ip:
            lineas += [
                f"# DHCP servido por el nodo designado de la red {net.name}",
                "if command -v dhclient >/dev/null 2>&1; then",
                f"  dhclient -1 -v {link.ifname} || true",
                "fi",
            ]
        else:
            lineas += [
                f"ip addr add {link.ip}/{link.prefix} dev {link.ifname}",
            ]
        lineas.append("")

    # ruta por defecto: en las redes NAT, o donde el enlace lo pida explícitamente
    for link in node.links:
        net = topo.networks[link.net]
        if net.type == "nat" or link.default:
            gw = link.gateway or net.gateway
            if gw:
                lineas.append(f"ip route replace default via {gw} dev {link.ifname}")
                break

    lineas += [
        "",
        "# rutas estáticas declaradas en la topología",
    ]
    for link in node.links:
        for destino, via in link.routes:
            lineas.append(f"ip route replace {destino} via {via} dev {link.ifname}")

    if node.sysctls:
        lineas += ["", "# sysctls por nodo", "sysctl -q -w " + " ".join(f"{k}={v}" for k, v in node.sysctls.items())]

    return "\n".join(lineas) + "\n"


def startup_script(node: Node) -> str | None:
    if not node.startup.strip():
        return None
    cabecera = [
        "#!/bin/sh",
        "# Script de arranque declarado en la topología.",
        "set -eu",
        "",
    ]
    for clave, valor in node.env.items():
        cabecera.append(f"export {clave}={valor!r}")
    return "\n".join(cabecera + [node.startup, ""])


UNIT_NET = """[Unit]
Description=netseclab network configuration
After=network.target
Before=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/sbin/lab-net

[Install]
WantedBy=multi-user.target
"""

UNIT_STARTUP = """[Unit]
Description=netseclab scenario startup
After=lab-net.service
Requires=lab-net.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/sbin/lab-startup

[Install]
WantedBy=multi-user.target
"""


def sysctl_file(node: Node) -> str:
    lineas = [f"# {k} = {v}" for k, v in node.sysctls.items()]
    return "\n".join(lineas) + "\n"
