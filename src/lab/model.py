"""Modelo de datos del laboratorio.

Una topología se describe en YAML y este módulo la convierte en objetos tipados, validados y con
todas las direcciones ya derivadas. Nadie escribe MACs ni tablas de rutas a mano.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .errors import LabErrors, Scope

NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,30}$")          # nodos y redes
LAB_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$")  # nombre del laboratorio (admite puntos)

NETWORK_TYPES = ("isolated", "nat", "bridged")
NETWORK_MODES = ("switch", "hub", "mirror")
ADDRESSING = ("auto", "dhcp")

FIRST_HOST = 10          # las direcciones se reparten a partir de .10, como en el original
RESERVED = {1, 254}      # .1 gateway, .254 router
MAC_PREFIX = "ca:fe:00:00"


# --------------------------------------------------------------------------- utilidades


def _as_dict(value: Any, where: str, sc: Scope) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        sc.add(where, "expected a key: value map")
        return {}
    return value


CLAVES = {
    "topologia": {
        "version", "name", "description", "domain", "defaults",
        "networks", "nodes", "profiles", "policies", "telemetry",
    },
    "red": {"id", "cidr", "type", "mode", "addressing", "gateway", "routes", "parent"},
    "nodo": {
        "name", "image", "links", "toolsets", "packages", "assets", "startup", "sysctls",
        "aliases", "resources", "dhcp_server", "dns_server", "firewall", "hostname", "env",
        "privileged",
    },
    "enlace": {"net", "ip", "mac", "vlan", "default", "gateway", "routes", "ifname"},
    "asset": {"src", "dst", "mode"},
    "recursos": {"cpus", "memory", "disk"},
    "telemetria": {"soc", "sources", "retention"},
    "politica": {"from", "to", "action", "port", "proto", "daddr"},
}


def _rechazar_desconocidas(data: dict, tipo: str, where: str, sc: Scope) -> None:
    """Una clave mal escrita no debe ignorarse en silencio."""
    permitidas = CLAVES[tipo]
    for clave in data:
        if clave not in permitidas:
            sugerencia = _mas_parecida(str(clave), permitidas)
            extra = f"; did you mean {sugerencia!r}?" if sugerencia else ""
            sc.add(f"{where}.{clave}", f"unknown key{extra}")


def _mas_parecida(clave: str, candidatas) -> str | None:
    from difflib import get_close_matches

    encontradas = get_close_matches(clave, list(candidatas), n=1, cutoff=0.6)
    return encontradas[0] if encontradas else None


def _as_list(value: Any, where: str, sc: Scope) -> list:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    sc.add(where, "expected a list")
    return []


def _parse_cidr(text: str, where: str, sc: Scope) -> ipaddress.IPv4Network | None:
    try:
        return ipaddress.ip_network(str(text), strict=False)
    except ValueError as exc:
        sc.add(where, f"invalid CIDR ({exc})")
        return None


def _parse_ip(text: str, where: str, sc: Scope) -> ipaddress.IPv4Address | None:
    try:
        return ipaddress.ip_address(str(text))
    except ValueError as exc:
        sc.add(where, f"invalid IP address ({exc})")
        return None


def _parse_routes(value: Any, where: str, sc: Scope) -> list[tuple[str, str]]:
    rutas: list[tuple[str, str]] = []
    for idx, raw in enumerate(_as_list(value, where, sc)):
        data = _as_dict(raw, f"{where}[{idx}]", sc)
        destino = data.get("to") or data.get("dest") or data.get("dst")
        via = data.get("via")
        if not destino or not via:
            sc.add(f"{where}[{idx}]", "a route needs 'to' and 'via'")
            continue
        try:
            red = ipaddress.ip_network(str(destino), strict=False)
        except ValueError as exc:
            sc.add(f"{where}[{idx}].to", f"invalid destination ({exc})")
            continue
        if _parse_ip(via, f"{where}[{idx}].via", sc) is None:
            continue
        rutas.append((str(red), str(via)))
    return rutas


# --------------------------------------------------------------------------- piezas


@dataclass
class Network:
    name: str
    id: int
    cidr: str
    type: str = "isolated"
    mode: str = "switch"
    addressing: str = "auto"
    gateway: str = ""
    parent: str = ""
    routes: list[tuple[str, str]] = field(default_factory=list)

    @property
    def bridge(self) -> str:
        return f"nvm-{self.name}"

    @property
    def subnet(self) -> ipaddress.IPv4Network:
        return ipaddress.ip_network(self.cidr, strict=False)

    @property
    def prefix(self) -> int:
        return self.subnet.prefixlen

    @property
    def is_nat(self) -> bool:
        return self.type == "nat"

    @property
    def needs_ovs(self) -> bool:
        return self.mode == "mirror"


@dataclass
class Link:
    net: str
    ip: str | None = None
    mac: str | None = None
    vlan: int | None = None
    default: bool = False
    gateway: str | None = None
    routes: list[tuple[str, str]] = field(default_factory=list)
    explicit_ip: bool = False
    # derivados
    ifname: str = ""
    prefix: int = 24


@dataclass
class Asset:
    src: str
    dst: str
    mode: str = "0644"

    @property
    def filename(self) -> str:
        return Path(self.src).name


@dataclass
class Resources:
    cpus: int = 1
    memory: str = "256MB"
    disk: str | None = None


@dataclass
class Node:
    name: str
    image: str
    links: list[Link] = field(default_factory=list)
    toolsets: list[str] = field(default_factory=list)
    packages: list[str] = field(default_factory=list)
    assets: list[Asset] = field(default_factory=list)
    startup: str = ""
    sysctls: dict[str, Any] = field(default_factory=dict)
    aliases: list[str] = field(default_factory=list)
    resources: Resources = field(default_factory=Resources)
    dhcp_server: bool = False
    dns_server: bool = False
    firewall: bool = False
    hostname: str = ""
    env: dict[str, str] = field(default_factory=dict)
    privileged: bool = False

    def link_to(self, net: str) -> Link | None:
        for link in self.links:
            if link.net == net:
                return link
        return None

    @property
    def address(self) -> str:
        """Primera dirección del nodo, la que se publica en DNS."""
        return self.links[0].ip if self.links else ""


@dataclass
class Policy:
    from_net: str
    to_net: str
    action: str
    port: int | str | None = None
    proto: str = "tcp"
    daddr: str | None = None

    def as_nft(self) -> str:
        src = f'iifname "{self.from_net}"'
        dst = f'oifname "{self.to_net}"'
        expr = f"{src} {dst}"
        if self.daddr:
            expr += f" ip daddr {self.daddr}"
        if self.port is not None:
            expr += f" {self.proto} dport {self.port}"
        match self.action:
            case "accept":
                return f"    {expr} accept"
            case "drop":
                return f"    {expr} drop"
            case "reject-reset":
                return f"    {expr} reject with tcp reset"
            case other:
                raise ValueError(f"unknown action: {other}")


@dataclass
class Telemetry:
    soc: str | None = None
    sources: list[str] = field(default_factory=lambda: ["auth", "syslog"])
    retention: str = "24h"

    @property
    def enabled(self) -> bool:
        return bool(self.soc)


@dataclass
class Topology:
    version: int
    name: str
    path: Path | None = None
    description: str = ""
    domain: str = ""
    networks: dict[str, Network] = field(default_factory=dict)
    nodes: list[Node] = field(default_factory=list)
    profiles: dict[str, list[str]] = field(default_factory=dict)
    policies: list[Policy] = field(default_factory=list)
    telemetry: Telemetry = field(default_factory=Telemetry)
    defaults_image: str = "debian13"

    # ----------------------------------------------------------------- consultas

    def node(self, name: str) -> Node | None:
        return next((n for n in self.nodes if n.name == name), None)

    def node_on(self, net: str) -> list[Node]:
        return [n for n in self.nodes if n.link_to(net)]

    def resolve_profile(self, profile: str | None) -> list[Node]:
        if not profile:
            return list(self.nodes)
        if profile not in self.profiles:
            raise KeyError(profile)
        names = self.profiles[profile]
        if names == ["*"] or "*" in names:
            return list(self.nodes)
        seleccion = set(names)
        return [n for n in self.nodes if n.name in seleccion]

    def dns_records(self) -> list[tuple[str, str]]:
        dominio = self.domain
        out: list[tuple[str, str]] = []
        for n in self.nodes:
            if not n.address:
                continue
            base = n.name
            fqdn = f"{base}.{dominio}" if dominio else base
            out.append((fqdn, n.address))
            for alias in n.aliases:
                out.append((f"{alias}.{dominio}" if dominio else alias, n.address))
        return out


# --------------------------------------------------------------------------- carga


def load(path: str | Path) -> Topology:
    """Carga y valida una topología desde un fichero YAML."""
    path = Path(path)
    if not path.exists():
        raise LabErrors([__issue(str(path), "file does not exist")])
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise LabErrors([__issue(str(path), f"invalid YAML: {exc}")]) from exc
    if not isinstance(raw, dict):
        raise LabErrors([__issue(str(path), "the document must be a map at the root")])
    return from_dict(raw, path=path)


def __issue(where: str, message: str):
    from .errors import Issue

    return Issue(where, message)


def from_dict(raw: dict, path: Path | None = None) -> Topology:
    sc = Scope()

    version = raw.get("version", 1)
    if version != 1:
        sc.add("version", f"only version 1 is supported (found {version!r})")

    name = raw.get("name")
    if not isinstance(name, str) or not LAB_NAME_RE.match(name):
        sc.add(
            "name",
            "required; lowercase, starts with a letter or digit, up to 63 characters [a-z0-9._-]",
        )

    _rechazar_desconocidas(raw, "topologia", "topology", sc)

    defaults = _as_dict(raw.get("defaults"), "defaults", sc)
    default_image = str(defaults.get("image", "debian13"))
    domain = str(raw.get("domain", f"{name}.lab" if isinstance(name, str) else "lab"))

    topo = Topology(
        version=int(version) if isinstance(version, int) else 1,
        name=str(name or "lab"),
        path=path,
        description=str(raw.get("description", "") or ""),
        domain=domain,
        defaults_image=default_image,
    )

    # ---- redes
    redes_raw = _as_dict(raw.get("networks"), "networks", sc)
    if not redes_raw:
        sc.add("networks", "a topology needs at least one network")

    used_ids: dict[int, str] = {}
    for idx, (net_name, net_raw) in enumerate(redes_raw.items()):
        where = f"networks.{net_name}"
        if not NAME_RE.match(str(net_name)):
            sc.add(where, "invalid name (lowercase, [a-z0-9-])")
        data = _as_dict(net_raw, where, sc)
        _rechazar_desconocidas(data, "red", where, sc)
        net_id = data.get("id", idx)
        if not isinstance(net_id, int) or not 0 <= net_id <= 255:
            sc.add(f"{where}.id", "must be an integer between 0 and 255")
            net_id = idx
        if net_id in used_ids:
            sc.add(f"{where}.id", f"duplicated with {used_ids[net_id]}")
        used_ids[net_id] = str(net_name)

        tipo = str(data.get("type", "isolated"))
        if tipo not in NETWORK_TYPES:
            sc.add(f"{where}.type", f"must be one of {', '.join(NETWORK_TYPES)}")
        modo = str(data.get("mode", "switch"))
        if modo not in NETWORK_MODES:
            sc.add(f"{where}.mode", f"must be one of {', '.join(NETWORK_MODES)}")
        addressing = str(data.get("addressing", "auto"))
        if addressing not in ADDRESSING:
            sc.add(f"{where}.addressing", f"must be one of {', '.join(ADDRESSING)}")

        cidr = data.get("cidr")
        if cidr is None:
            if tipo == "nat":
                cidr = f"10.99.{net_id}.0/24"
            else:
                sc.add(f"{where}.cidr", "required for isolated networks")
        subnet = _parse_cidr(cidr, f"{where}.cidr", sc) if cidr else None
        if subnet is not None and subnet.num_addresses < 8:
            sc.add(f"{where}.cidr", "the network is too small")

        gateway = data.get("gateway")
        if gateway is not None:
            gw_ip = _parse_ip(gateway, f"{where}.gateway", sc)
            if gw_ip and subnet and gw_ip not in subnet:
                sc.add(f"{where}.gateway", f"{gateway} is not inside {cidr}")
        elif tipo == "nat" and subnet is not None:
            gateway = str(subnet.network_address + 1)
        else:
            gateway = ""

        parent = str(data.get("parent", "") or "")
        if tipo == "bridged" and not parent:
            sc.add(
                f"{where}.parent",
                "a 'bridged' network needs parent: the host physical interface to attach to",
            )
        if tipo != "bridged" and parent:
            sc.add(f"{where}.parent", "only makes sense on networks of type 'bridged'")

        topo.networks[str(net_name)] = Network(
            name=str(net_name),
            id=net_id,
            cidr=str(cidr),
            type=tipo,
            mode=modo,
            addressing=addressing,
            gateway=str(gateway),
            routes=_parse_routes(data.get("routes"), f"{where}.routes", sc),
            parent=parent,
        )

    # ---- nodos
    nodos_raw = _as_list(raw.get("nodes"), "nodes", sc)
    if not nodos_raw:
        sc.add("nodes", "a topology needs at least one node")

    seen: set[str] = set()
    for idx, nodo_raw in enumerate(nodos_raw):
        where = f"nodes[{idx}]"
        data = _as_dict(nodo_raw, where, sc)
        node_name = str(data.get("name", ""))
        where = f"nodes[{idx}:{node_name or '?'}]"
        _rechazar_desconocidas(data, "nodo", where, sc)
        if not NAME_RE.match(node_name):
            sc.add(f"{where}.name", "required; lowercase, [a-z0-9-]")
        elif node_name in seen:
            sc.add(f"{where}.name", "duplicated name")
        seen.add(node_name)

        res_raw = _as_dict(data.get("resources"), f"{where}.resources", sc)
        _rechazar_desconocidas(res_raw, "recursos", f"{where}.resources", sc)
        resources = Resources(
            cpus=int(res_raw.get("cpus", 1)),
            memory=str(res_raw.get("memory", "256MB")),
            disk=str(res_raw["disk"]) if "disk" in res_raw else None,
        )

        assets = []
        for a_idx, a_raw in enumerate(_as_list(data.get("assets"), f"{where}.assets", sc)):
            a_where = f"{where}.assets[{a_idx}]"
            a_data = _as_dict(a_raw, a_where, sc)
            _rechazar_desconocidas(a_data, "asset", a_where, sc)
            src = a_data.get("src")
            dst = a_data.get("dst")
            if not src:
                sc.add(f"{a_where}.src", "required")
            if not dst:
                sc.add(f"{a_where}.dst", "required")
            if src and dst:
                assets.append(Asset(src=str(src), dst=str(dst), mode=str(a_data.get("mode", "0644"))))

        node = Node(
            name=node_name,
            image=str(data.get("image", default_image)),
            toolsets=[str(t) for t in _as_list(data.get("toolsets"), f"{where}.toolsets", sc)],
            packages=[str(p) for p in _as_list(data.get("packages"), f"{where}.packages", sc)],
            assets=assets,
            startup=str(data.get("startup", "") or ""),
            sysctls=dict(_as_dict(data.get("sysctls"), f"{where}.sysctls", sc)),
            aliases=[str(a) for a in _as_list(data.get("aliases"), f"{where}.aliases", sc)],
            resources=resources,
            dhcp_server=bool(data.get("dhcp_server", False)),
            dns_server=bool(data.get("dns_server", False)),
            firewall=bool(data.get("firewall", False)),
            hostname=str(data.get("hostname", "")),
            env={str(k): str(v) for k, v in _as_dict(data.get("env"), f"{where}.env", sc).items()},
            privileged=bool(data.get("privileged", False)),
        )

        # ---- enlaces
        links_raw = _as_list(data.get("links"), f"{where}.links", sc)
        if not links_raw:
            sc.add(f"{where}.links", "a node needs at least one link")
        for l_idx, link_raw in enumerate(links_raw):
            l_where = f"{where}.links[{l_idx}]"
            if isinstance(link_raw, str):
                link_raw = {"net": link_raw}
            l_data = _as_dict(link_raw, l_where, sc)
            _rechazar_desconocidas(l_data, "enlace", l_where, sc)
            net_name = l_data.get("net")
            if not net_name:
                sc.add(f"{l_where}.net", "required")
                continue
            if net_name not in topo.networks:
                sc.add(f"{l_where}.net", f"network {net_name!r} is not defined")
                continue
            vid = l_data.get("vlan")
            if vid is not None and (not isinstance(vid, int) or not 1 <= vid <= 4094):
                sc.add(f"{l_where}.vlan", "must be between 1 and 4094")
                vid = None

            node.links.append(
                Link(
                    net=str(net_name),
                    ip=str(l_data["ip"]) if "ip" in l_data else None,
                    mac=str(l_data["mac"]) if "mac" in l_data else None,
                    vlan=vid,
                    default=bool(l_data.get("default", False)),
                    gateway=str(l_data["gateway"]) if "gateway" in l_data else None,
                    routes=_parse_routes(l_data.get("routes"), f"{l_where}.routes", sc),
                    explicit_ip="ip" in l_data,
                    ifname=str(l_data.get("ifname", f"eth{l_idx}")),
                )
            )

        topo.nodes.append(node)

    # ---- perfiles
    for p_name, p_raw in _as_dict(raw.get("profiles"), "profiles", sc).items():
        members = [str(m) for m in _as_list(p_raw, f"profiles.{p_name}", sc)]
        if members != ["*"]:
            for m in members:
                if m not in seen:
                    sc.add(f"profiles.{p_name}", f"node {m!r} does not exist")
        topo.profiles[str(p_name)] = members

    # ---- políticas
    for p_idx, p_raw in enumerate(_as_list(raw.get("policies"), "policies", sc)):
        p_where = f"policies[{p_idx}]"
        data = _as_dict(p_raw, p_where, sc)
        _rechazar_desconocidas(data, "politica", p_where, sc)
        origen = str(data.get("from", ""))
        destino = str(data.get("to", ""))
        if origen not in topo.networks:
            sc.add(f"{p_where}.from", f"network {origen!r} does not exist")
        if destino not in topo.networks:
            sc.add(f"{p_where}.to", f"network {destino!r} does not exist")
        accion = str(data.get("action", "drop"))
        if accion not in ("accept", "drop", "reject-reset"):
            sc.add(f"{p_where}.action", "must be accept, drop or reject-reset")
        topo.policies.append(
            Policy(
                from_net=origen,
                to_net=destino,
                action=accion,
                port=data.get("port"),
                proto=str(data.get("proto", "tcp")),
                daddr=str(data["daddr"]) if "daddr" in data else None,
            )
        )

    # ---- telemetría
    tele = _as_dict(raw.get("telemetry"), "telemetry", sc)
    _rechazar_desconocidas(tele, "telemetria", "telemetry", sc)
    if tele:
        soc = tele.get("soc")
        if soc is not None and soc not in seen:
            sc.add("telemetry.soc", f"node {soc!r} does not exist")
        topo.telemetry = Telemetry(
            soc=str(soc) if soc else None,
            sources=[str(s) for s in _as_list(tele.get("sources"), "telemetry.sources", sc)]
            or ["auth", "syslog"],
            retention=str(tele.get("retention", "24h")),
        )

    sc.raise_if_any()
    derive(topo)
    return topo


# --------------------------------------------------------------------------- derivación


def _finalize_link(
    net: Network,
    node: Node,
    link: Link,
    ip: ipaddress.IPv4Address,
    macs: dict[str, str],
    sc: Scope,
    where: str,
) -> None:
    link.ip = str(ip)
    link.prefix = net.prefix
    if link.mac:
        mac = link.mac.strip().lower()
        if not re.fullmatch(r"([0-9a-f]{2}:){5}[0-9a-f]{2}", mac):
            sc.add(f"{where}.mac", "invalid MAC format (aa:bb:cc:dd:ee:ff)")
            return
    else:
        octeto = int(str(ip).split(".")[-1])
        mac = f"{MAC_PREFIX}:{net.id:02x}:{octeto:02x}"
    if mac in macs:
        sc.add(f"{where}.mac", f"MAC duplicated with {macs[mac]}")
        return
    macs[mac] = node.name
    link.mac = mac


def derive(topo: Topology) -> None:
    """Asigna IPs y MACs que no se hayan escrito a mano y valida lo resultante.

    Se hacen dos pasadas por red: primero se reservan las direcciones explícitas y después se
    reparten las automáticas, de modo que un nodo con IP fija nunca choca con uno automático.
    """
    sc = Scope()

    for net in topo.networks.values():
        subnet = net.subnet
        usadas: dict[ipaddress.IPv4Address, str] = {}
        macs: dict[str, str] = {}
        pendientes: list[tuple[Node, Link]] = []

        # 1. direcciones explícitas
        for node in topo.nodes:
            link = node.link_to(net.name)
            if link is None:
                continue
            where = f"nodes.{node.name}.links[{net.name}]"
            if not link.ip:
                pendientes.append((node, link))
                continue
            ip = _parse_ip(link.ip, f"{where}.ip", sc)
            if ip is None:
                continue
            if ip not in subnet:
                sc.add(f"{where}.ip", f"{ip} is not inside {net.cidr}")
                continue
            if ip in (subnet.network_address, subnet.broadcast_address):
                sc.add(f"{where}.ip", f"{ip} is a reserved address of the network")
                continue
            if ip in usadas:
                sc.add(f"{where}.ip", f"{ip} is already in use by {usadas[ip]}")
                continue
            usadas[ip] = node.name
            _finalize_link(net, node, link, ip, macs, sc, where)

        # 2. direcciones automáticas
        siguiente = FIRST_HOST
        for node, link in pendientes:
            where = f"nodes.{node.name}.links[{net.name}]"
            ip = None
            while siguiente < subnet.num_addresses - 1:
                host = siguiente
                siguiente += 1
                if host in RESERVED:
                    continue
                candidata = subnet.network_address + host
                if candidata in usadas:
                    continue
                ip = candidata
                break
            if ip is None:
                sc.add(f"{where}.ip", "no free addresses left in the network")
                continue
            usadas[ip] = node.name
            _finalize_link(net, node, link, ip, macs, sc, where)

    # DHCP exige servidor
    for net in topo.networks.values():
        if net.addressing == "dhcp":
            servidores = [n for n in topo.nodes if n.link_to(net.name) and n.dhcp_server]
            if not servidores:
                sc.add(
                    f"networks.{net.name}.addressing",
                    "is 'dhcp' but no node on that network has dhcp_server: true",
                )

    if topo.telemetry.enabled and topo.node(topo.telemetry.soc or "") is None:
        sc.add("telemetry.soc", f"SOC node {topo.telemetry.soc!r} does not exist")

    sc.raise_if_any()
