"""Generación de la configuración de dnsmasq para el nodo que sirve DHCP y/o DNS."""

from __future__ import annotations

import ipaddress

from ..model import Node, Topology
from .hosts import fqdn, reverse

RANGO_DHCP_INICIO = 100
RANGO_DHCP_FIN = 199


def _rango(subnet: ipaddress.IPv4Network) -> tuple[str, str]:
    hosts = subnet.num_addresses - 2
    inicio = min(RANGO_DHCP_INICIO, max(2, hosts - 1))
    fin = min(RANGO_DHCP_FIN, hosts)
    return (
        str(subnet.network_address + inicio),
        str(subnet.network_address + fin),
    )


def render(topo: Topology, node: Node) -> str:
    lineas = [
        "# Generado por netseclab. No editar.",
        "bind-dynamic",
        "except-interface=lo",
        "domain-needed",
        "bogus-priv",
        "dhcp-authoritative",
        "log-dhcp",
    ]

    if topo.domain:
        lineas += [
            f"domain={topo.domain}",
            f"local=/{topo.domain}/",
            f"local=/{'.'.join(reversed(topo.domain.split('.')))}/",
        ]

    for link in node.links:
        net = topo.networks[link.net]
        lineas.append(f"interface={link.ifname}")
        if net.addressing != "dhcp":
            continue
        inicio, fin = _rango(net.subnet)
        lineas.append(f"dhcp-range=set:{net.name},{inicio},{fin},{net.subnet.netmask},12h")
        if net.gateway:
            lineas.append(f"dhcp-option=tag:{net.name},3,{net.gateway}")
        propio = node.link_to(net.name)
        if propio is None:
            continue
        lineas.append(f"dhcp-option=tag:{net.name},6,{propio.ip}")
        if topo.domain:
            lineas.append(f"dhcp-option=tag:{net.name},15,{topo.domain}")
        if net.routes:
            # opción 121: rutas sin clase, para que un nodo recién arrancado ya sepa llegar
            valores = ",".join(f"{destino},{via}" for destino, via in net.routes)
            lineas.append(f"dhcp-option=tag:{net.name},121,{valores}")

    lineas.append("")

    # reservas por MAC: la dirección que el motor ya decidió
    for red in topo.networks.values():
        for otro in topo.nodes:
            enlace = otro.link_to(red.name)
            if enlace is None:
                continue
            lineas.append(f"dhcp-host={enlace.mac},{enlace.ip},{otro.name},12h")
    lineas.append("")

    # registros directos e inversos
    for otro in topo.nodes:
        if not otro.address:
            continue
        nombre = fqdn(topo, otro.name)
        lineas.append(f"host-record={nombre},{otro.address}")
        lineas.append(f"ptr-record={reverse(otro.address)},{nombre}")
        for alias in otro.aliases:
            lineas.append(f"cname={fqdn(topo, alias)},{nombre}")

    return "\n".join(lineas) + "\n"
