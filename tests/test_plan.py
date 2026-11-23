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
    assert fases == ["perfil", "network", "node", "packages", "files", "enable", "wait", "post"]


def test_se_recarga_systemd_antes_de_activar(plan):
    """Sin daemon-reload, systemd no ve las unidades recién copiadas."""
    comandos = _comandos(plan)
    indice_reload = next(i for i, c in enumerate(comandos) if "systemctl daemon-reload" in c)
    indice_enable = next(i for i, c in enumerate(comandos) if "systemctl enable" in c)
    assert indice_reload < indice_enable


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


@pytest.fixture(scope="module")
def estatico(tmp_path_factory):
    """Topología con direccionamiento fijo, para probar lo que ya no se le deja al DHCP."""
    ruta = tmp_path_factory.mktemp("estatico") / "estatico.yaml"
    ruta.write_text(
        """
version: 1
name: estatico
networks:
  a:
    cidr: 10.7.0.0/24
    addressing: auto
    gateway: 10.7.0.1
    routes:
      - { to: 10.8.0.0/24, via: 10.7.0.254 }
  b: { cidr: 10.8.0.0/24, addressing: auto, gateway: 10.8.0.1 }
nodes:
  - name: r
    links: [{ net: a, ip: 10.7.0.254 }, { net: b, ip: 10.8.0.254 }]
    sysctls: { net.ipv4.ip_forward: 1 }
  - { name: cli, links: [{ net: a, ip: 10.7.0.10 }] }
  - { name: srv, links: [{ net: b, ip: 10.8.0.10 }] }
""",
        encoding="utf-8",
    )
    return load(ruta)


def test_una_red_dhcp_con_direccion_declarada_se_configura_en_el_nodo(example_net):
    """Antes dependía del cliente DHCP de la imagen: tras un reinicio se quedaba sin rutas y la web
    de la DMZ salía filtrada desde exta."""
    guion = netconf.net_script(example_net, example_net.node("exta"))
    assert "ip addr add 10.5.0.10/24 dev eth0" in guion
    assert "ip route replace 10.5.1.0/24 via 10.5.0.254 dev eth0" in guion
    assert "ip route replace default via 10.5.0.1 dev eth0" in guion


def test_el_nodo_enmascara_el_gestor_de_red_de_la_imagen(example_net):
    """Dos gestores de red peleándose por la misma interfaz: uno pone la dirección y el otro la
    quita, y tras un reinicio el nodo se quedaba sin ruta de vuelta."""
    guion = netconf.net_script(example_net, example_net.node("exta"))
    assert "systemctl mask --now systemd-networkd.service" in guion


def test_los_nombres_se_resuelven_con_el_dns_del_laboratorio(example_net):
    """Sin networkd, el resolv.conf de la imagen apunta a un stub sin upstream."""
    guion = netconf.net_script(example_net, example_net.node("exta"))
    assert "printf 'nameserver %s\\n' 10.5.0.1" in guion


def test_una_red_nat_usa_la_puerta_como_resolutor(workdir):
    """El bridge NAT de Incus hace de DNS y reenvía al anfitrión: sin esto el nodo sale a Internet
    por IP pero no resuelve nombres."""
    ruta = workdir / "wan.yaml"
    ruta.write_text(
        """
version: 1
name: wan
networks:
  wan: { id: 7, type: nat, cidr: 10.99.7.0/24 }
nodes:
  - { name: cli, links: [{ net: wan, ip: 10.99.7.10 }] }
""",
        encoding="utf-8",
    )
    topo = load(ruta)
    guion = netconf.net_script(topo, topo.node("cli"))
    assert "printf 'nameserver %s\\n' 10.99.7.1" in guion


def test_un_nodo_sin_direccion_pide_dhcp_y_reintenta(workdir):
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
    cliente = netconf.net_script(topo, topo.node("cli"))
    assert "dhclient -1 -q eth0" in cliente
    assert "seq 1 60" in cliente
    assert "ip addr add" not in cliente


def test_una_red_fija_se_configura_en_el_nodo(estatico):
    guion = netconf.net_script(estatico, estatico.node("cli"))
    assert "ip addr add 10.7.0.10/24 dev eth0" in guion
    assert "ip route replace 10.8.0.0/24 via 10.7.0.254 dev eth0" in guion


def test_un_nodo_multipata_configura_todas_sus_direcciones(estatico):
    guion = netconf.net_script(estatico, estatico.node("r"))
    assert "ip addr add 10.7.0.254/24 dev eth0" in guion
    assert "ip addr add 10.8.0.254/24 dev eth1" in guion
    assert "sysctl -q -w net.ipv4.ip_forward=1" in guion


def test_el_router_no_se_crea_rutas_hacia_si_mismo(estatico):
    """r es el siguiente salto: una ruta hacia sí mismo rompería la suya conectada."""
    guion = netconf.net_script(estatico, estatico.node("r"))
    assert "via 10.7.0.254" not in guion


def test_las_redes_ya_conectadas_no_llevan_ruta(estatico):
    """r está en las dos redes: no necesita ruta para llegar a ninguna."""
    guion = netconf.net_script(estatico, estatico.node("r"))
    assert "ip route replace 10.8.0.0/24" not in guion


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
    with pytest.raises(ValueError, match="does not exist"):
        build(example_net)
    example_net.node("exta").toolsets = ["recon", "sniff"]


def test_el_plan_arranca_los_nodos_que_ya_existen(plan):
    """`lab up` después de `lab down` fallaba: launch no arranca una instancia parada."""
    comandos = [" ".join(paso.exec_argv()) for paso in plan.steps if paso.kind != "push"]
    for nodo in plan.nodes:
        assert f"incus start {nodo.name}" in comandos


def test_el_plan_espera_a_que_los_nodos_termine_de_arrancar(plan):
    """Sin la espera, el primer nmap llega a una web que todavía no escucha."""
    esperas = [paso for paso in plan.steps if paso.phase == "wait"]
    assert len(esperas) == len(plan.nodes)
    assert all("is-system-running" in paso.command() for paso in esperas)
    # y cada espera conoce la dirección que el nodo tiene que tener
    fw = next(paso for paso in esperas if " fw " in paso.command() + " ")
    assert "10.5.0.254" in fw.command() and "10.5.1.254" in fw.command()
