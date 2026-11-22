"""Pruebas del plan generado: orden de fases, cortafuegos, DHCP/DNS y ficheros de nodo."""

from __future__ import annotations

from pathlib import Path

import pytest

from lab.generate import dnsmasq, hosts, netconf, nftables
from lab.model import load
from lab.plan import build

EJEMPLOS = Path(__file__).resolve().parents[1] / "lab" / "examples"


@pytest.fixture(scope="module")
def example_net():
    return load(EJEMPLOS / "example.net.yaml")


@pytest.fixture(scope="module")
def plan(example_net):
    return build(example_net, profile="std")


def _comandos(plan):
    return [s.command() for s in plan.steps if s.kind == "cmd"]


def test_fases_en_orden(plan):
    fases = []
    for step in plan.steps:
        if not fases or fases[-1] != step.phase:
            fases.append(step.phase)
    assert fases == ["perfil", "network", "node", "packages", "files", "enable", "post"]


def test_se_crean_las_tres_redes(plan):
    comandos = _comandos(plan)
    assert any("incus network create nvm-ext" in c for c in comandos)
    assert any("incus network create nvm-dmz" in c for c in comandos)
    assert any("incus network create nvm-int" in c for c in comandos)
    # aisladas: sin dirección en el anfitrión, para que la .1 sea del nodo base
    assert all("ipv4.address=none" in c for c in comandos if "network create" in c)


def test_dmz_usa_espejo_ovs(plan):
    comandos = _comandos(plan)
    assert any("bridge.driver=openvswitch" in c and "nvm-dmz" in c for c in comandos)
    assert any("create Mirror" in c for c in comandos)


def test_ext_es_hub(plan):
    comandos = _comandos(plan)
    assert any("nvm-ext" in c and "learning off" in c for c in comandos)


def test_cada_boca_es_un_dispositivo_con_mac(plan):
    dispositivos = [c for c in _comandos(plan) if "config device add" in c]
    assert len(dispositivos) == sum(len(n.links) for n in plan.nodes)
    assert any("hwaddr=ca:fe:00:00:02:fe" in d for d in dispositivos)


def test_nftables_distingue_cerrado_de_filtrado(example_net):
    fw = example_net.node("fw")
    reglas = nftables.render(example_net, fw)
    assert 'iifname "eth0" oifname "eth1" ip daddr 10.5.1.10 tcp dport 80 accept' in reglas
    assert "tcp dport 443 reject with tcp reset" in reglas
    assert "policy drop" in reglas


def test_dnsmasq_reparte_rutas_estaticas(example_net):
    base = example_net.node("base")
    conf = dnsmasq.render(example_net, base)
    assert "dhcp-range=set:ext" in conf
    assert "dhcp-option=tag:ext,3,10.5.0.1" in conf
    assert "dhcp-option=tag:ext,121,10.5.1.0/24,10.5.0.254" in conf
    assert "dhcp-host=ca:fe:00:00:01:0a,10.5.1.10,dmza,12h" in conf
    assert "cname=www.example.net,dmza.example.net" in conf
    assert "ptr-record=10.1.5.10.in-addr.arpa,dmza.example.net" in conf


def test_hosts_resuelve_alias(example_net):
    texto = hosts.render_for(example_net, example_net.node("inta"))
    assert "10.5.1.10" in texto and "www.example.net" in texto
    assert "10.5.2.10\tinta.example.net" in texto


def test_script_de_red_de_un_nodo_multipata(example_net):
    guion = netconf.net_script(example_net, example_net.node("fw"))
    # fw declara sus direcciones, así que se configuran en fijo aunque la red sea DHCP
    assert "ip addr add 10.5.0.254/24 dev eth0" in guion
    assert "ip addr add 10.5.1.254/24 dev eth1" in guion
    assert "ip addr add 10.5.2.254/24 dev eth2" in guion
    assert "sysctl -q -w net.ipv4.ip_forward=1" in guion


def test_dhcp_solo_para_quien_no_tiene_ip_fija(workdir):
    ruta = workdir / "dhcp.yaml"
    ruta.write_text(
        """
version: 1
name: dhcplab
networks:
  n1: { cidr: 10.9.0.0/24, addressing: dhcp, gateway: 10.9.0.1 }
nodes:
  - { name: srv, links: [{ net: n1, ip: 10.9.0.1 }], dhcp_server: true }
  - { name: cli, links: [n1] }
""",
        encoding="utf-8",
    )
    topo = load(ruta)
    servidor = netconf.net_script(topo, topo.node("srv"))
    cliente = netconf.net_script(topo, topo.node("cli"))
    assert "ip addr add 10.9.0.1/24 dev eth0" in servidor
    assert "dhclient -1 -v eth0" not in servidor
    assert "dhclient -1 -v eth0" in cliente
    assert "ip addr add" not in cliente


def test_el_script_generado_es_shell_valido(plan):
    texto = plan.shell()
    assert texto.startswith("#!/bin/sh")
    assert texto.count("<<'__LAB_EOF_") == texto.count("__LAB_EOF_") // 2
    assert "incus file push" in texto


def test_json_del_plan_tiene_todo_lo_necesario(plan):
    datos = plan.as_dict()
    assert datos["lab"] == "example.net"
    assert {n["name"] for n in datos["nodes"]} == {"base", "fw", "exta", "dmza", "inta"}
    fw = next(n for n in datos["nodes"] if n["name"] == "fw")
    assert len(fw["interfaces"]) == 3


def test_el_plan_escribe_los_ficheros(plan, workdir):
    escritos = plan.write_files(workdir)
    rutas = {p.relative_to(workdir).as_posix() for p in escritos}
    assert "fw/usr/local/sbin/lab-net" in rutas
    assert "base/etc/dnsmasq.d/lab.conf" in rutas
    assert "inta/etc/hosts" in rutas


def test_perfil_mini_reduce_el_plan(example_net):
    completo = build(example_net, profile="full")
    mini = build(example_net, profile="mini")
    assert len(mini.nodes) == 3
    assert len(mini.steps) < len(completo.steps)


def test_un_toolset_desconocido_falla(example_net):
    example_net.node("exta").toolsets = ["noexiste"]
    with pytest.raises(ValueError, match="no existe"):
        build(example_net)
    example_net.node("exta").toolsets = ["recon", "sniff"]
