"""Generación de las reglas nftables del cortafuegos.

Las reglas salen de la matriz de conectividad declarada en la topología. La diferencia entre `drop`
y `reject-reset` es deliberada y didáctica: un puerto filtrado y un puerto cerrado no son lo mismo,
y `nmap` lo distingue.
"""

from __future__ import annotations

from ..model import Node, Topology


def _puertos(port) -> str:
    if port is None:
        return ""
    if isinstance(port, int):
        return str(port)
    return str(port)


def render(topo: Topology, node: Node) -> str:
    ifmap = {link.net: link.ifname for link in node.links}

    reglas: list[str] = []
    for policy in topo.policies:
        if policy.from_net not in ifmap or policy.to_net not in ifmap:
            reglas.append(
                f"    # omitida: {policy.from_net} -> {policy.to_net} "
                f"(este nodo no está en las dos redes)"
            )
            continue
        expr = f'iifname "{ifmap[policy.from_net]}" oifname "{ifmap[policy.to_net]}"'
        if policy.daddr:
            expr += f" ip daddr {policy.daddr}"
        puertos = _puertos(policy.port)
        if puertos:
            expr += f" {policy.proto} dport {puertos}"
        if policy.action == "accept":
            reglas.append(f"    {expr} accept")
        elif policy.action == "drop":
            reglas.append(f"    {expr} drop")
        elif policy.action == "reject-reset":
            reglas.append(f"    {expr} reject with tcp reset")
        else:  # pragma: no cover - validado antes
            reglas.append(f"    # acción desconocida: {policy.action}")

    politica = "drop" if reglas else "accept"
    lineas = [
        "#!/usr/sbin/nft -f",
        "# Generado por netseclab desde la matriz de conectividad de la topología.",
        "add table inet lab",
        "flush table inet lab",
        "",
        "table inet lab {",
        "  chain input {",
        "    type filter hook input priority filter; policy accept;",
        "    ct state established,related accept",
        "    iifname \"lo\" accept",
        "  }",
        "",
        "  chain forward {",
        f"    type filter hook forward priority filter; policy {politica};",
        "    ct state established,related accept",
        "    iifname \"lo\" accept",
    ]
    lineas += reglas
    lineas += ["  }", "}", ""]
    return "\n".join(lineas)
