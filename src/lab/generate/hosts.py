"""Generación de `/etc/hosts`.

Se inyecta en todos los nodos para que `ping dmza` funcione sin depender de que el DNS esté en
marcha. El DNS real, cuando hay un nodo que lo sirve, se configura además con dnsmasq.
"""

from __future__ import annotations

from ..model import Topology


def render(topo: Topology) -> str:
    lineas = [
        "127.0.0.1\tlocalhost",
        "::1\tlocalhost ip6-localhost ip6-loopback",
        "",
        f"# laboratorio {topo.name} — generado por netseclab",
    ]
    for node in topo.nodes:
        if not node.address:
            continue
        nombres = [node.name]
        if topo.domain:
            nombres.append(f"{node.name}.{topo.domain}")
        for alias in node.aliases:
            nombres.append(alias)
            if topo.domain:
                nombres.append(f"{alias}.{topo.domain}")
        unicos = list(dict.fromkeys(nombres))
        lineas.append(f"{node.address}\t" + " ".join(unicos))
    return "\n".join(lineas) + "\n"


def fqdn(topo: Topology, nombre: str) -> str:
    return f"{nombre}.{topo.domain}" if topo.domain else nombre


def render_for(topo: Topology, node) -> str:
    """`/etc/hosts` de un nodo concreto: su nombre resuelve a todas sus bocas y ve a los demás."""
    lineas = [
        "127.0.0.1\tlocalhost",
        "::1\tlocalhost ip6-localhost ip6-loopback",
        "",
        f"# laboratorio {topo.name} — generado por netseclab",
    ]
    for link in node.links[:1]:
        lineas.append(f"{link.ip}\t{fqdn(topo, node.name)}")
    if len(node.links) > 1:
        otras = ", ".join(f"{link.ifname}={link.ip}" for link in node.links[1:])
        lineas.append(f"# otras bocas de {node.name}: {otras}")
    for otro in topo.nodes:
        if otro.name == node.name or not otro.address:
            continue
        nombres = [otro.name]
        if topo.domain:
            nombres.append(fqdn(topo, otro.name))
        for alias in otro.aliases:
            nombres.append(alias)
            if topo.domain:
                nombres.append(fqdn(topo, alias))
        lineas.append(f"{otro.address}\t" + " ".join(dict.fromkeys(nombres)))
    return "\n".join(lineas) + "\n"


def reverse(ip: str) -> str:
    return ".".join(reversed(ip.split("."))) + ".in-addr.arpa"
