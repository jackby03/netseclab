"""Configuración de red dentro de un nodo.

Cada nodo recibe un script idempotente y una unidad systemd que lo ejecuta en cada arranque. Es el
equivalente a lo que hacía `configure.sh` en la versión UML de NETinVM, pero generado desde la
topología en lugar de escrito a mano.
"""

from __future__ import annotations

import ipaddress

from ..model import Node, Topology

NET_SCRIPT = "/usr/local/sbin/lab-net"
STARTUP_SCRIPT = "/usr/local/sbin/lab-startup"


def _red_propia(node: Node) -> list[ipaddress.IPv4Network]:
    return [ipaddress.IPv4Network(f"{link.ip}/{link.prefix}", strict=False) for link in node.links]


def _es_conectada(node: Node, destino: str) -> bool:
    """¿El nodo llega a esa red sin pasar por un router? Entonces la ruta sobra."""
    try:
        red = ipaddress.IPv4Network(destino, strict=False)
    except ValueError:
        return False
    return any(red == propia or red.subnet_of(propia) for propia in _red_propia(node))


def _rutas_de_red(topo: Topology, node: Node) -> list[tuple[str, str, str]]:
    """Rutas que la red anuncia por DHCP, aplicadas a mano para quien tiene IP fija.

    `networks.<red>.routes` se sirve a los clientes DHCP con la opción 121. Un nodo con `ip:`
    explícita no pide DHCP, así que sin esto se quedaba sin rutas hacia los demás segmentos y
    `nmap` desde exta no llegaba a la DMZ. Se saltan las redes que el nodo ya tiene conectadas y
    los saltos que son el propio nodo: el cortafuegos no necesita una ruta hacia sí mismo.
    """
    propias = {link.ip for link in node.links}
    vistas: set[tuple[str, str]] = set()
    rutas: list[tuple[str, str, str]] = []
    for link in node.links:
        for destino, via in topo.networks[link.net].routes:
            if via in propias or _es_conectada(node, destino) or (destino, via) in vistas:
                continue
            vistas.add((destino, via))
            rutas.append((destino, via, link.ifname))
    return rutas


def _dns_servers(topo: Topology, node: Node) -> list[str]:
    """Direcciones de los nodos que hacen de DNS en las redes a las que está conectado."""
    redes = {link.net for link in node.links}
    propias = {link.ip for link in node.links}
    servidores = [
        link.ip
        for otro in topo.nodes
        if otro.dns_server
        for link in otro.links
        if link.net in redes and link.ip and link.ip not in propias
    ]
    return sorted(set(servidores))


def net_script(topo: Topology, node: Node) -> str:
    lineas = [
        "#!/bin/sh",
        "# Generado por netseclab. No editar: cambia la topología y vuelve a arrancar.",
        "set -eu",
        "",
        "# Un solo gestor de red: este script. networkd y su espera de «red en línea» se",
        "# enmascaran; si no, compiten por las mismas interfaces y tras un reinicio dejan al",
        "# nodo con una dirección y sin ruta de vuelta.",
        "systemctl mask --now systemd-networkd.service systemd-networkd.socket "
        "systemd-networkd-wait-online.service 2>/dev/null || true",
        "",
    ]
    for link in node.links:
        net = topo.networks[link.net]
        lineas += [
            f"# {link.ifname} -> red {net.name} ({net.cidr})",
            f"ip link set {link.ifname} up",
        ]
        if link.ip and (net.addressing != "dhcp" or link.explicit_ip):
            # Dirección declarada en la topología: se aplica aquí. No se le deja al DHCP para que el
            # nodo tenga exactamente la misma red en el primer arranque y después de un reinicio; si
            # la dirección viniera del cliente DHCP de la imagen, un reinicio podía dejarlo sin
            # rutas y la web de la DMZ salía filtrada desde exta.
            lineas += [
                f"ip addr flush dev {link.ifname}",
                f"ip addr add {link.ip}/{link.prefix} dev {link.ifname}",
            ]
        else:
            lineas += [
                "# sin dirección declarada: DHCP, reintentando mientras el servidor arranca",
                "for _ in $(seq 1 60); do",
                f'  ip -4 addr show dev {link.ifname} | grep -q "inet " && break',
                f"  timeout 5 dhclient -1 -q {link.ifname} 2>/dev/null || true",
                "  sleep 1",
                "done",
            ]
        lineas.append("")

    # ruta por defecto: la del enlace que la pida, la de una red NAT o la puerta del segmento.
    # Antes la servía el DHCP (opción 3); al aplicarla aquí, un nodo puede contestar al tráfico que
    # le llega de otro segmento aunque nadie le haya dado una concesión.
    propias = {link.ip for link in node.links}
    for link in node.links:
        net = topo.networks[link.net]
        gw = link.gateway or net.gateway
        if not gw or gw in propias:
            continue
        if net.type == "nat" or link.default or net.addressing == "dhcp":
            lineas.append(f"ip route replace default via {gw} dev {link.ifname}")
            break

    lineas += [
        "",
        "# rutas de los segmentos, para que un nodo con dirección fija llegue a los demás",
    ]
    for destino, via, interfaz in _rutas_de_red(topo, node):
        lineas.append(f"ip route replace {destino} via {via} dev {interfaz}")

    lineas += [
        "",
        "# rutas estáticas declaradas en la topología",
    ]
    for link in node.links:
        for destino, via in link.routes:
            lineas.append(f"ip route replace {destino} via {via} dev {link.ifname}")

    servidores = _dns_servers(topo, node)
    if servidores:
        destinos = " ".join(servidores)
        lineas += [
            "",
            "# resolución de nombres por el servidor DNS del laboratorio",
            "rm -f /etc/resolv.conf",
            f"printf 'nameserver %s\\n' {destinos} > /etc/resolv.conf",
        ]

    if node.sysctls:
        lineas += [
            "",
            "# sysctls por nodo",
            "sysctl -q -w " + " ".join(f"{k}={v}" for k, v in node.sysctls.items()),
        ]

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
    return "\n".join([*cabecera, node.startup, ""])


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
