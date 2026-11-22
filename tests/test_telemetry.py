"""Pruebas de telemetría: el SOC recibe los logs de todos los nodos."""

from __future__ import annotations

from pathlib import Path

import pytest

from lab.generate import telemetry
from lab.model import load
from lab.plan import build

EJEMPLOS = Path(__file__).resolve().parents[1] / "lab" / "examples"


@pytest.fixture(scope="module")
def topo():
    return load(EJEMPLOS / "soc.yaml")


def test_el_soc_se_carga(topo):
    assert topo.telemetry.enabled
    assert topo.telemetry.soc == "soc"
    assert topo.telemetry.sources == ["auth", "syslog", "suricata"]
    assert topo.node("soc").links[0].ip == "10.30.9.20"


def test_cliente_reenvia_al_soc(topo):
    conf = telemetry.client_config(topo, topo.node("attacker"), topo.node("soc"))
    assert "*.* @@10.30.9.20:514" in conf
    assert 'module(load="imfile")' in conf
    assert "/var/log/suricata/eve.json" in conf
    assert "/var/log/auth.log" in conf


def test_servidor_escucha_y_separa_por_nodo(topo):
    conf = telemetry.server_config(topo)
    assert 'module(load="imtcp")' in conf
    assert 'port="514"' in conf
    assert "/var/log/lab/%HOSTNAME%/" in conf


def test_el_plan_instala_y_configura_rsyslog(topo):
    plan = build(topo)
    comandos = [s.command() for s in plan.steps if s.kind == "cmd"]
    assert any("rsyslog" in c for c in comandos)
    assert any("mkdir -p /var/log/lab" in c for c in comandos)
    assert sum(1 for c in comandos if "systemctl restart rsyslog" in c) == 4

    ficheros = {s.path for s in plan.steps if s.kind == "push" and s.node}
    assert "/etc/rsyslog.d/50-lab-server.conf" in ficheros
    assert "/etc/rsyslog.d/50-lab.conf" in ficheros


def test_sin_telemetria_no_se_toca_rsyslog():
    topo = load(EJEMPLOS / "fuzz-evasion.yaml")
    plan = build(topo)
    comandos = [s.command() for s in plan.steps if s.kind == "cmd"]
    assert not any("rsyslog" in c for c in comandos)


def test_la_telemetria_de_un_nodo_inexistente_falla(workdir):
    from lab.errors import LabErrors

    ruta = workdir / "malo.yaml"
    ruta.write_text(
        """
version: 1
name: malo
networks: { n1: { cidr: 10.0.0.0/24 } }
nodes:
  - { name: a, links: [n1] }
telemetry: { soc: noexiste }
""",
        encoding="utf-8",
    )
    with pytest.raises(LabErrors, match="no existe"):
        load(ruta)
