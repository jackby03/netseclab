"""De una topología a un plan ejecutable.

El plan es una lista de pasos y ficheros que se puede:

- **renderizar** a un script de shell legible (`lab render`),
- **exportar** a JSON para las pruebas,
- **ejecutar** paso a paso (`lab up`).

La separación importa: el plan se puede revisar y testear sin tener Incus ni ser root.
"""

from __future__ import annotations

import copy
import shlex
from dataclasses import dataclass, field
from pathlib import Path

from .catalog import load_images, load_toolsets, resolve_image
from .generate import dnsmasq, hosts, netconf, nftables, telemetry
from .model import Node, Topology

# Perfil de Incus con el disco raíz de los nodos. El perfil por defecto trae además
# una tarjeta en incusbr0, que no queremos en un laboratorio aislado.
PERFIL_NODOS = "netseclab"


@dataclass
class Step:
    phase: str
    kind: str = "cmd"  # cmd | push | tar
    argv: list[str] = field(default_factory=list)
    node: str | None = None
    note: str = ""
    path: str = ""
    content: str = ""
    mode: str = "0644"

    def command(self) -> str:
        return " ".join(shlex.quote(a) for a in self.exec_argv())

    def exec_argv(self) -> list[str]:
        """Lista de argumentos lista para ejecutar sin pasar por un shell."""
        if self.kind == "push":
            raise ValueError("un push no es un comando")
        if self.kind == "tar":
            origen = shlex.quote(self.argv[0])
            destino = shlex.quote(self.path)
            nodo = shlex.quote(self.node or "")
            return [
                "sh",
                "-c",
                f"tar -C {origen} -cf - . | incus exec {nodo} -- tar -C {destino} -xf -",
            ]
        if self.node:
            return ["incus", "exec", self.node, "--", *self.argv]
        return list(self.argv)

    def as_dict(self) -> dict:
        return {
            "phase": self.phase,
            "kind": self.kind,
            "node": self.node,
            "command": self.command() if self.kind != "push" else None,
            "path": self.path or None,
            "note": self.note or None,
        }


@dataclass
class Plan:
    topology: Topology
    profile: str | None
    nodes: list[Node]
    steps: list[Step]

    # ------------------------------------------------------------------ salida

    def shell(self) -> str:
        lineas = [
            "#!/bin/sh",
            f"# Plan del laboratorio {self.topology.name}"
            + (f" (perfil {self.profile})" if self.profile else "")
            + " — generado por netseclab.",
            "set -eu",
            'WORK="$(mktemp -d)"',
            "trap 'rm -rf \"$WORK\"' EXIT",
            "",
        ]
        fase = None
        contador = 0
        for step in self.steps:
            if step.phase != fase:
                fase = step.phase
                lineas += ["", f"# ── {fase} " + "─" * max(0, 60 - len(fase)), ""]
            if step.note:
                lineas.append(f"# {step.note}")
            if step.kind == "push":
                contador += 1
                marca = f"__LAB_EOF_{contador}__"
                temporal = f'"$WORK/f{contador}"'
                lineas.append(f"cat > {temporal} <<'{marca}'")
                lineas.append(step.content.rstrip("\n"))
                lineas.append(marca)
                destino = shlex.quote(f"{step.node}{step.path}")
                lineas.append(
                    f"incus file push {temporal} {destino} --mode={step.mode}"
                )
            else:
                lineas.append(step.command())
        lineas.append("")
        return "\n".join(lineas)

    def as_dict(self) -> dict:
        return {
            "lab": self.topology.name,
            "domain": self.topology.domain,
            "profile": self.profile,
            "networks": [
                {
                    "name": net.name,
                    "id": net.id,
                    "cidr": net.cidr,
                    "type": net.type,
                    "mode": net.mode,
                    "addressing": net.addressing,
                    "bridge": net.bridge,
                    "gateway": net.gateway,
                }
                for net in self.used_networks()
            ],
            "nodes": [
                {
                    "name": n.name,
                    "image": n.image,
                    "hostname": n.hostname or n.name,
                    "interfaces": [
                        {
                            "ifname": link.ifname,
                            "net": link.net,
                            "ip": link.ip,
                            "prefix": link.prefix,
                            "mac": link.mac,
                        }
                        for link in n.links
                    ],
                }
                for n in self.nodes
            ],
            "steps": [s.as_dict() for s in self.steps],
        }

    def used_networks(self):
        nombres: list[str] = []
        for n in self.nodes:
            for link in n.links:
                if link.net not in nombres:
                    nombres.append(link.net)
        return [self.topology.networks[n] for n in nombres]

    def write_files(self, destino: Path) -> list[Path]:
        """Escribe los ficheros generados en disco, sin Incus."""
        escritos: list[Path] = []
        for step in self.steps:
            if step.kind != "push" or not step.node:
                continue
            rel = Path(step.node) / step.path.lstrip("/")
            ruta = destino / rel
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_text(step.content, encoding="utf-8")
            escritos.append(ruta)
        return escritos


# --------------------------------------------------------------------------- construcción


def _implicit_packages(topo: Topology, node: Node) -> set[str]:
    extra: set[str] = {"openssh-server"}
    for link in node.links:
        net = topo.networks[link.net]
        if net.addressing == "dhcp" and not link.explicit_ip:
            extra.add("isc-dhcp-client")
            break
    if node.dhcp_server or node.dns_server:
        extra.add("dnsmasq")
    if node.firewall:
        extra.add("nftables")
    if telemetry.necesita(node, topo) or telemetry.es_soc(node, topo):
        extra.add("rsyslog")
    return extra


def build(
    topo: Topology,
    profile: str | None = None,
    root: Path | None = None,
) -> Plan:
    # Se trabaja sobre una copia: `build` no debe dejar la topología mutada (las
    # imágenes resueltas, por ejemplo), o la segunda llamada recibe basura.
    topo = copy.deepcopy(topo)

    nodes = topo.resolve_profile(profile)
    if not nodes:
        raise ValueError("el perfil no selecciona ningún nodo")

    imagenes = load_images(root)
    toolsets = load_toolsets(root)
    base = topo.path.parent if topo.path else Path.cwd()

    # las imágenes se resuelven una vez, para que el plan sea explícito
    for node in nodes:
        node.image = resolve_image(node.image, imagenes, where=f"nodes.{node.name}.image")

    steps: list[Step] = []
    redes = [n for n in topo.networks.values() if any(x.link_to(n.name) for x in nodes)]

    # ── perfil de los nodos
    # El disco raíz lo aporta un perfil. No sirve --no-profiles: sin perfil no hay
    # disco raíz y la instancia no arranca. El perfil por defecto trae una tarjeta
    # en incusbr0 que no queremos, así que se crea uno a medida.
    steps.append(
        Step(
            "perfil",
            argv=["incus", "profile", "create", PERFIL_NODOS],
            note=f"perfil {PERFIL_NODOS} para los nodos (si ya existe, se ignora)",
        )
    )
    steps.append(
        Step(
            "perfil",
            argv=[
                "incus",
                "profile",
                "device",
                "add",
                PERFIL_NODOS,
                "root",
                "disk",
                "path=/",
                "pool=default",
            ],
            note="disco raíz de los nodos",
        )
    )

    # ── redes
    for net in redes:
        argv = ["incus", "network", "create", net.bridge, "--type=bridge"]
        if net.type == "nat":
            argv += [
                f"ipv4.address={net.gateway}/{net.prefix}",
                "ipv4.nat=true",
                "ipv4.dhcp=false",
                "ipv6.address=none",
            ]
        elif net.type == "bridged":
            argv += [
                "ipv4.address=none",
                "ipv6.address=none",
                "dns.mode=none",
                f"bridge.external_interfaces={net.parent}",
            ]
        else:
            argv += ["ipv4.address=none", "ipv6.address=none", "dns.mode=none"]
        if net.needs_ovs:
            argv.append("bridge.driver=openvswitch")
        steps.append(
            Step(
                "network",
                argv=argv,
                note=f"red {net.name} ({net.cidr}, {net.type}, modo {net.mode})",
            )
        )

    # ── nodos
    for node in nodes:
        steps.append(
            Step(
                "node",
                argv=[
                    "incus",
                    "launch",
                    node.image,
                    node.name,
                    "--profile",
                    PERFIL_NODOS,
                    f"--config=limits.cpu={node.resources.cpus}",
                    f"--config=limits.memory={node.resources.memory}",
                ],
                note=f"nodo {node.name} desde {node.image}",
            )
        )
        if node.resources.disk:
            steps.append(
                Step(
                    "node",
                    argv=[
                        "incus",
                        "config",
                        "device",
                        "override",
                        node.name,
                        "root",
                        f"size={node.resources.disk}",
                    ],
                    note=f"{node.name}: disco de {node.resources.disk}",
                )
            )
        if node.privileged:
            steps.append(
                Step(
                    "node",
                    argv=["incus", "config", "set", node.name, "security.privileged", "true"],
                    note="privilegios completos dentro del nodo (necesario para algunas herramientas)",
                )
            )
        for link in node.links:
            net = topo.networks[link.net]
            argv = [
                "incus",
                "config",
                "device",
                "add",
                node.name,
                link.ifname,
                "nic",
                "nictype=bridged",
                f"parent={net.bridge}",
                f"name={link.ifname}",
                f"hwaddr={link.mac}",
            ]
            if link.vlan is not None:
                argv.append(f"vlan={link.vlan}")
            steps.append(
                Step(
                    "node",
                    argv=argv,
                    note=f"{link.ifname} -> {net.name} ({link.ip}/{link.prefix})",
                )
            )

    # ── paquetes
    for node in nodes:
        paquetes: list[str] = []
        for nombre in node.toolsets:
            if nombre not in toolsets:
                raise ValueError(
                    f"nodes.{node.name}.toolsets: el toolset {nombre!r} no existe en lab/toolsets.yaml"
                )
            paquetes += toolsets[nombre]
        paquetes += node.packages
        paquetes += sorted(_implicit_packages(topo, node))
        paquetes = list(dict.fromkeys(paquetes))
        if not paquetes:
            continue
        lista = " ".join(paquetes)
        # El laboratorio está aislado: si la imagen ya trae el paquete no se toca apt,
        # y si falta algo se avisa en vez de romper el arranque.
        guion = (
            'faltan=""; for p in ' + lista + '; do '
            'dpkg -s "$p" >/dev/null 2>&1 || faltan="$faltan $p"; done; '
            '[ -z "$faltan" ] && exit 0; '
            "apt-get update -qq && DEBIAN_FRONTEND=noninteractive "
            'apt-get install -y -qq $faltan || '
            f'echo "AVISO: sin red, no se pudieron instalar:$faltan"'
        )
        steps.append(
            Step(
                "packages",
                node=node.name,
                argv=["sh", "-c", guion],
                note=f"{node.name}: {lista}",
            )
        )

    # ── ficheros
    for node in nodes:
        pasos = [
            Step("files", kind="push", node=node.name, path="/etc/hostname",
                 content=(node.hostname or node.name) + "\n"),
            Step("files", kind="push", node=node.name, path="/etc/hosts",
                 content=hosts.render_for(topo, node)),
            Step("files", kind="push", node=node.name, path=netconf.NET_SCRIPT,
                 content=netconf.net_script(topo, node), mode="0755"),
            Step("files", kind="push", node=node.name,
                 path="/etc/systemd/system/lab-net.service", content=netconf.UNIT_NET),
        ]
        if node.sysctls:
            pasos.append(
                Step("files", kind="push", node=node.name,
                     path="/etc/sysctl.d/90-lab.conf", content=netconf.sysctl_file(node))
            )
        arranque = netconf.startup_script(node)
        if arranque:
            pasos += [
                Step("files", kind="push", node=node.name, path=netconf.STARTUP_SCRIPT,
                     content=arranque, mode="0755"),
                Step("files", kind="push", node=node.name,
                     path="/etc/systemd/system/lab-startup.service", content=netconf.UNIT_STARTUP),
            ]
        if node.dhcp_server or node.dns_server:
            pasos.append(
                Step("files", kind="push", node=node.name,
                     path="/etc/dnsmasq.d/lab.conf", content=dnsmasq.render(topo, node))
            )
        if node.firewall and topo.policies:
            pasos.append(
                Step("files", kind="push", node=node.name, path="/etc/lab/fw.nft",
                     content=nftables.render(topo, node), mode="0644")
            )
        if telemetry.es_soc(node, topo):
            pasos.append(
                Step("files", kind="push", node=node.name,
                     path="/etc/rsyslog.d/50-lab-server.conf",
                     content=telemetry.server_config(topo))
            )
            pasos.append(
                Step("files", node=node.name,
                     argv=["mkdir", "-p", "/var/log/lab"],
                     note="directorio de logs del SOC")
            )
        elif telemetry.necesita(node, topo):
            servidor = topo.node(topo.telemetry.soc or "")
            if servidor is not None:
                pasos.append(
                    Step("files", kind="push", node=node.name,
                         path="/etc/rsyslog.d/50-lab.conf",
                         content=telemetry.client_config(topo, node, servidor))
                )
        for asset in node.assets:
            origen = (base / asset.src).resolve()
            if origen.is_dir():
                pasos.append(
                    Step(
                        "files",
                        kind="tar",
                        node=node.name,
                        path=asset.dst,
                        argv=[str(origen)],
                        note=f"{node.name}: {asset.src}/ -> {asset.dst}",
                    )
                )
            elif origen.is_file():
                pasos.append(
                    Step(
                        "files",
                        kind="push",
                        node=node.name,
                        path=asset.dst,
                        content=origen.read_text(encoding="utf-8"),
                        mode=asset.mode,
                    )
                )
            else:
                raise FileNotFoundError(f"nodes.{node.name}.assets: no existe {origen}")
        steps += pasos

    # ── activación
    for node in nodes:
        # Se acaban de copiar unidades nuevas: sin recargar, systemd no las ve y
        # `systemctl enable` falla con "Unit ... does not exist".
        steps.append(
            Step(
                "enable",
                node=node.name,
                argv=["systemctl", "daemon-reload"],
                note=f"{node.name}: recargar systemd",
            )
        )
        unidades = ["lab-net.service"]
        if node.startup.strip():
            unidades.append("lab-startup.service")
        steps.append(
            Step(
                "enable",
                node=node.name,
                argv=["systemctl", "enable", "--now", *unidades],
                note=f"{node.name}: {', '.join(unidades)}",
            )
        )
        steps.append(
            Step(
                "enable",
                node=node.name,
                argv=["hostnamectl", "set-hostname", node.hostname or node.name],
                note=f"{node.name}: nombre del sistema",
            )
        )
        if node.dhcp_server or node.dns_server:
            steps.append(
                Step(
                    "enable",
                    node=node.name,
                    argv=["systemctl", "enable", "--now", "dnsmasq"],
                    note=f"{node.name}: dnsmasq",
                )
            )
        if node.firewall and topo.policies:
            steps.append(
                Step(
                    "enable",
                    node=node.name,
                    argv=["nft", "-f", "/etc/lab/fw.nft"],
                    note=f"{node.name}: reglas de cortafuegos",
                )
            )
        if telemetry.es_soc(node, topo) or telemetry.necesita(node, topo):
            steps.append(
                Step(
                    "enable",
                    node=node.name,
                    argv=["systemctl", "restart", "rsyslog"],
                    note=f"{node.name}: reenvío de logs",
                )
            )

    # ── ajustes de conmutación
    for net in redes:
        if net.mode == "hub":
            steps.append(
                Step(
                    "post",
                    argv=[
                        "sh",
                        "-c",
                        f'for p in /sys/class/net/{net.bridge}/brif/*; do '
                        '[ -e "$p" ] && bridge link set dev "$(basename "$p")" learning off; '
                        "done; true",
                    ],
                    note=f"{net.name}: modo hub (sin aprendizaje de MAC, todo se inunda)",
                )
            )
        elif net.mode == "mirror":
            puerto = f"cap-{net.name}"
            guion = (
                f"ovs-vsctl --may-exist add-port {net.bridge} {puerto} "
                f"-- set Interface {puerto} type=internal; "
                f"ip link set {puerto} up; "
                f"ovs-vsctl -- --id=@p get Port {puerto} "
                f"-- --id=@m create Mirror name=mirror-{net.name} select_all=true output-port=@p "
                f"-- set Bridge {net.bridge} mirrors=@m"
            )
            steps.append(
                Step("post", argv=["sh", "-c", guion],
                     note=f"{net.name}: puerto espejo {puerto} (OVS)")
            )

    return Plan(topology=topo, profile=profile, nodes=nodes, steps=steps)
