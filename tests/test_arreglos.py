"""Pruebas de los arreglos: reset, hostname, disco, bridged, bajada y consola web."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

SNAPS_INITIAL = json.dumps([{"name": "initial"}])
SNAPS_OTRO = json.dumps([{"name": "otro"}])

from lab.engine import Incus, RecordingRunner, restore_snapshot
from lab.errors import LabErrors
from lab.model import load
from lab.plan import build
from lab.web import LIMITE_SALIDA, FakeTerminal, Session

EJEMPLOS = Path(__file__).resolve().parents[1] / "lab" / "examples"


# --------------------------------------------------------------------------- reset


def test_reset_para_restaura_y_arranca():
    runner = RecordingRunner({"incus query": (0, SNAPS_INITIAL, "")})
    fallos = restore_snapshot(Incus(runner), ["fw"], "initial")
    assert fallos == []
    secuencia = [c for c in runner.comandos() if "stop" in c or "restore" in c or "start" in c]
    # parar -> restaurar -> arrancar, en ese orden
    assert "incus stop fw" in secuencia[0]
    assert "snapshot restore fw initial" in secuencia[1]
    assert secuencia[2].endswith("incus start fw")


def test_reset_no_arranca_si_se_pide():
    runner = RecordingRunner({"incus query": (0, SNAPS_INITIAL, "")})
    restore_snapshot(Incus(runner), ["fw"], "initial", arrancar=False)
    assert not runner.contiene("incus start fw")


def test_reset_sin_snapshot_no_toca_la_instancia():
    runner = RecordingRunner({"snapshot list": (0, "otro\n", "")})
    fallos = restore_snapshot(Incus(runner), ["fw"], "initial")
    assert len(fallos) == 1
    assert not runner.contiene("incus stop fw")


# --------------------------------------------------------------------------- plan


@pytest.fixture(scope="module")
def example_net():
    return load(EJEMPLOS / "example.net.yaml")


def test_el_nombre_del_sistema_se_aplica(example_net):
    plan = build(example_net, profile="mini")
    comandos = [s.command() for s in plan.steps if s.kind == "cmd"]
    assert any("hostnamectl set-hostname fw" in c for c in comandos)
    assert any("hostnamectl set-hostname dmza" in c for c in comandos)


def test_el_disco_declarado_se_aplica(workdir):
    ruta = workdir / "disco.yaml"
    ruta.write_text(
        """
version: 1
name: disco
networks: { n1: { cidr: 10.0.0.0/24 } }
nodes:
  - name: a
    links: [n1]
    resources: { disk: 4GB }
""",
        encoding="utf-8",
    )
    plan = build(load(ruta))
    comandos = [s.command() for s in plan.steps if s.kind == "cmd"]
    assert any("device override a root size=4GB" in c for c in comandos)


def test_red_bridged_cuelga_del_interfaz_fisico(workdir):
    ruta = workdir / "puente.yaml"
    ruta.write_text(
        """
version: 1
name: puente
networks:
  lan: { cidr: 192.168.1.0/24, type: bridged, parent: eth0 }
nodes:
  - { name: a, links: [lan] }
""",
        encoding="utf-8",
    )
    plan = build(load(ruta))
    comandos = [s.command() for s in plan.steps if s.kind == "cmd"]
    assert any("bridge.external_interfaces=eth0" in c for c in comandos)


def test_red_bridged_sin_parent_es_error(workdir):
    ruta = workdir / "puente-malo.yaml"
    ruta.write_text(
        """
version: 1
name: puente-malo
networks:
  lan: { cidr: 192.168.1.0/24, type: bridged }
nodes:
  - { name: a, links: [lan] }
""",
        encoding="utf-8",
    )
    with pytest.raises(LabErrors, match="parent"):
        load(ruta)


def test_parent_solo_vale_en_bridged(workdir):
    ruta = workdir / "parent-raro.yaml"
    ruta.write_text(
        """
version: 1
name: parent-raro
networks:
  n1: { cidr: 10.0.0.0/24, parent: eth0 }
nodes:
  - { name: a, links: [n1] }
""",
        encoding="utf-8",
    )
    with pytest.raises(LabErrors, match="bridged"):
        load(ruta)


# --------------------------------------------------------------------------- consola web


def test_el_buffer_de_la_consola_tiene_tope():
    terminal = FakeTerminal(entrada=b"x" * (LIMITE_SALIDA + 5000))
    sesion = Session(terminal)
    for _ in range(50):
        if sesion.cerrada:
            break
        time.sleep(0.02)
    assert len(sesion.salida) <= LIMITE_SALIDA
    datos, siguiente = sesion.desde(0)
    assert len(datos) <= LIMITE_SALIDA
    assert siguiente == sesion.base + len(sesion.salida)


def test_las_posiciones_siguen_siendo_coherentes_tras_recortar():
    terminal = FakeTerminal(entrada=b"a" * LIMITE_SALIDA + b"b" * 1000)
    sesion = Session(terminal)
    for _ in range(50):
        if sesion.cerrada:
            break
        time.sleep(0.02)
    datos, fin = sesion.desde(0)
    assert datos.endswith(b"b" * 1000)
    assert fin == sesion.base + len(sesion.salida)
