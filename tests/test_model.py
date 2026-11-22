"""Pruebas del modelo: carga, derivación de direcciones y validación."""

from __future__ import annotations

from pathlib import Path

import pytest

from lab.errors import LabErrors
from lab.model import load

EJEMPLOS = Path(__file__).resolve().parents[1] / "lab" / "examples"


def test_example_net_deriva_el_plan_del_original():
    topo = load(EJEMPLOS / "example.net.yaml")

    assert set(topo.networks) == {"ext", "dmz", "int"}
    assert [n.id for n in topo.networks.values()] == [0, 1, 2]

    base = topo.node("base")
    assert [link.ip for link in base.links] == ["10.5.0.1", "10.5.1.1", "10.5.2.1"]
    assert [link.mac for link in base.links] == [
        "ca:fe:00:00:00:01",
        "ca:fe:00:00:01:01",
        "ca:fe:00:00:02:01",
    ]

    fw = topo.node("fw")
    assert [link.ip for link in fw.links] == ["10.5.0.254", "10.5.1.254", "10.5.2.254"]
    assert [link.mac for link in fw.links] == [
        "ca:fe:00:00:00:fe",
        "ca:fe:00:00:01:fe",
        "ca:fe:00:00:02:fe",
    ]

    exta = topo.node("exta")
    assert exta.links[0].ip == "10.5.0.10"
    assert exta.links[0].mac == "ca:fe:00:00:00:0a"

    dmza = topo.node("dmza")
    assert dmza.links[0].ip == "10.5.1.10"
    assert dmza.links[0].mac == "ca:fe:00:00:01:0a"
    assert dmza.aliases == ["www"]


def test_las_direcciones_explicitas_se_reservan_antes_que_las_automaticas():
    topo = load(EJEMPLOS / "fuzz-evasion.yaml")
    assert topo.node("www").links[0].ip == "10.20.1.10"
    # fw es anterior en el fichero, pero no puede quedarse la .10 de www
    assert topo.node("fw").link_to("dmz").ip == "10.20.1.11"


def test_las_macs_son_unicas_por_red():
    topo = load(EJEMPLOS / "pivot.yaml")
    for red in topo.networks:
        macs = [n.link_to(red).mac for n in topo.nodes if n.link_to(red)]
        assert len(macs) == len(set(macs))


def test_multipata_y_pivoteo():
    topo = load(EJEMPLOS / "pivot.yaml")
    pivot = topo.node("pivot")
    assert [link.net for link in pivot.links] == ["dmz", "int-a"]
    assert pivot.links[1].ip == "10.10.10.254"


def _escribir(workdir: Path, texto: str) -> Path:
    ruta = workdir / "topo.yaml"
    ruta.write_text(texto, encoding="utf-8")
    return ruta


def test_ip_repetida_en_la_misma_red(workdir):
    ruta = _escribir(
        workdir,
        """
version: 1
name: dup
networks: { n1: { cidr: 10.0.0.0/24 } }
nodes:
  - { name: a, links: [{ net: n1, ip: 10.0.0.10 }] }
  - { name: b, links: [{ net: n1, ip: 10.0.0.10 }] }
""",
    )
    with pytest.raises(LabErrors) as exc:
        load(ruta)
    assert "already in use by" in str(exc.value)


def test_ip_fuera_de_la_red(workdir):
    ruta = _escribir(
        workdir,
        """
version: 1
name: fuera
networks: { n1: { cidr: 10.0.0.0/24 } }
nodes:
  - { name: a, links: [{ net: n1, ip: 10.9.9.9 }] }
""",
    )
    with pytest.raises(LabErrors) as exc:
        load(ruta)
    assert "is not inside" in str(exc.value)


def test_red_inexistente(workdir):
    ruta = _escribir(
        workdir,
        """
version: 1
name: rota
networks: { n1: { cidr: 10.0.0.0/24 } }
nodes:
  - { name: a, links: [noexiste] }
""",
    )
    with pytest.raises(LabErrors) as exc:
        load(ruta)
    assert "is not defined" in str(exc.value)


def test_dhcp_sin_servidor(workdir):
    ruta = _escribir(
        workdir,
        """
version: 1
name: sindhcp
networks: { n1: { cidr: 10.0.0.0/24, addressing: dhcp } }
nodes:
  - { name: a, links: [n1] }
""",
    )
    with pytest.raises(LabErrors) as exc:
        load(ruta)
    assert "dhcp_server" in str(exc.value)


def test_nodo_sin_enlaces(workdir):
    ruta = _escribir(
        workdir,
        """
version: 1
name: suelto
networks: { n1: { cidr: 10.0.0.0/24 } }
nodes:
  - { name: a }
""",
    )
    with pytest.raises(LabErrors) as exc:
        load(ruta)
    assert "at least one link" in str(exc.value)


def test_perfil_selecciona_nodos():
    topo = load(EJEMPLOS / "example.net.yaml")
    mini = topo.resolve_profile("mini")
    assert [n.name for n in mini] == ["fw", "exta", "dmza"]
    completo = topo.resolve_profile("full")
    assert len(completo) == len(topo.nodes)


def test_registros_dns_incluyen_alias():
    topo = load(EJEMPLOS / "example.net.yaml")
    registros = dict(topo.dns_records())
    assert registros["dmza.example.net"] == "10.5.1.10"
    assert registros["www.example.net"] == "10.5.1.10"


def test_una_clave_mal_escrita_no_se_ignora(workdir):
    ruta = workdir / "typo.yaml"
    ruta.write_text(
        """
version: 1
name: typo
networks: { n1: { cidr: 10.0.0.0/24 } }
nodes:
  - name: a
    links: [n1]
    linx: [n1]
""",
        encoding="utf-8",
    )
    with pytest.raises(LabErrors) as exc:
        load(ruta)
    texto = str(exc.value)
    assert "unknown key" in texto
    assert "links" in texto  # sugiere la clave correcta


def test_metadatos_del_laboratorio():
    topo = load(EJEMPLOS / "example.net.yaml")
    assert topo.version == 1
    assert topo.domain == "example.net"
    assert len(topo.policies) == 8
